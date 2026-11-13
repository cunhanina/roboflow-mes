from collections import defaultdict
from datetime import timedelta
import json
import traceback

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient

from .models import (
    LOW_STOCK_THRESHOLD,
    STATUS_CONCLUIDO,
    STATUS_EM_ANDAMENTO,
    STATUS_PENDENTE,
    Peca,
    Pedido,
    ensure_default_pecas,
    serialize_pedidos,
)


def get_robot_status(em_andamento_count=0):
    """Fetches the latest cobot status from MongoDB telemetry or infers from active orders."""
    try:
        mongo_uri = getattr(settings, 'MONGO_URI', 'mongodb://localhost:27017/')
        mongo_db_name = getattr(settings, 'MONGO_DB_NAME', 'pi-iv')
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=500)
        try:
            db = client[mongo_db_name]
            collection = db['dashboard_robo']
            robo_status_doc = collection.find_one(sort=[('_id', -1)])
            if robo_status_doc and robo_status_doc.get('status'):
                return robo_status_doc.get('status')
        finally:
            client.close()
    except Exception:
        pass

    return 'Em Montagem' if em_andamento_count > 0 else 'Ocioso'


def get_dashboard_summary():
    """Builds the unified real-time dashboard payload for HTTP views and WebSockets."""
    ensure_default_pecas()

    em_andamento_count = Pedido.objects.filter(status=STATUS_EM_ANDAMENTO).count()
    pedidos_concluidos_count = Pedido.objects.filter(status=STATUS_CONCLUIDO).count()
    total_pedidos = em_andamento_count + pedidos_concluidos_count

    pedido_pendente = Pedido.objects.filter(status=STATUS_PENDENTE).first()
    pedido_em_andamento = Pedido.objects.filter(status=STATUS_EM_ANDAMENTO).first()
    active_order = pedido_pendente or pedido_em_andamento

    pecas = list(Peca.objects.all())
    stock_info = {}
    for p in pecas:
        stock_info[p.tipo] = {
            'id': p.id,
            'name': p.name,
            'quantity': p.qtd,
            'is_low_stock': p.qtd <= LOW_STOCK_THRESHOLD,
            'color_hex': p.color_hex,
        }

    for default_shape, default_name in [('circulo', 'Círculo'), ('quadrado', 'Quadrado'), ('hexagono', 'Hexágono')]:
        if default_shape not in stock_info:
            stock_info[default_shape] = {
                'id': 0,
                'name': default_name,
                'quantity': 0,
                'is_low_stock': True,
                'color_hex': '#CCCCCC',
            }

    estado_robo = get_robot_status(em_andamento_count=em_andamento_count)

    return {
        'em_andamento_count': em_andamento_count,
        'concluido_count': pedidos_concluidos_count,
        'total_pedidos_count': total_pedidos,
        'pedido_pendente': pedido_pendente,
        'pedido_ativo': active_order,
        'pending_order': {
            'id': active_order.id,
            'status': active_order.get_status_display(),
            'status_code': active_order.status,
            'data': active_order.data.strftime("%d/%m/%Y %H:%M") if active_order.data else "",
        } if active_order else None,
        'estado_robo': estado_robo,
        'stock_info': stock_info,
        'any_low_stock': any(item['is_low_stock'] for item in stock_info.values()),
    }


def broadcast_order_event(channel_layer, titulo, mensagem, tipo, link, toast_message, toast_type='success'):
    """Helper to broadcast notification, toast, dashboard, and history updates over Channels."""
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        'dashboard_updates',
        {
            'type': 'notification.create',
            'titulo': titulo,
            'mensagem': mensagem,
            'tipo': tipo,
            'link': link,
        }
    )
    async_to_sync(channel_layer.group_send)(
        'dashboard_updates',
        {'type': 'dashboard_update_trigger'}
    )
    async_to_sync(channel_layer.group_send)(
        'dashboard_updates',
        {'type': 'historico_update_trigger'}
    )
    async_to_sync(channel_layer.group_send)(
        'dashboard_updates',
        {
            'type': 'dashboard.message',
            'message_type': 'show_toast',
            'toast_message': toast_message,
            'toast_type': toast_type,
        }
    )


def home(request):
    summary = get_dashboard_summary()
    stock = summary['stock_info']

    context = {
        **summary,
        'circulo_qtd': stock['circulo']['quantity'],
        'quadrado_qtd': stock['quadrado']['quantity'],
        'hexagono_qtd': stock['hexagono']['quantity'],
        'circulo_low_stock': stock['circulo']['is_low_stock'],
        'quadrado_low_stock': stock['quadrado']['is_low_stock'],
        'hexagono_low_stock': stock['hexagono']['is_low_stock'],
    }
    return render(request, 'home.html', context)


@csrf_exempt
def novoPedido(request):
    ensure_default_pecas()
    channel_layer = get_channel_layer()

    if request.method == 'POST':
        try:
            data_json = json.loads(request.body)
            pecas_ids = []
            for i in range(1, 10):
                peca_str_id = data_json.get(f'peca{i}')
                if peca_str_id is None:
                    return JsonResponse({'message': f'Peça {i} não fornecida.'}, status=400)
                try:
                    peca_id = int(peca_str_id)
                    peca = Peca.objects.get(id=peca_id)
                    pecas_ids.append(peca.id)
                except (ValueError, Peca.DoesNotExist):
                    msg = f'Peça inválida ou não encontrada: {peca_str_id}'
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            'dashboard_updates',
                            {
                                'type': 'dashboard.message',
                                'message_type': 'show_toast',
                                'toast_message': f'❌ {msg}',
                                'toast_type': 'error',
                            }
                        )
                    return JsonResponse({'message': msg}, status=400)

            matriz_pecas_ids = [pecas_ids[i:i + 3] for i in range(0, 9, 3)]
            for idx, montagem in enumerate(matriz_pecas_ids, 1):
                if len(set(montagem)) < 3:
                    return JsonResponse(
                        {'message': f'Montagem {idx} contém peças repetidas. Cada montagem deve ter 3 formas distintas.'},
                        status=400
                    )

            with transaction.atomic():
                if Pedido.objects.filter(status=STATUS_PENDENTE).exists():
                    return JsonResponse({'message': '🚨 Já existe um pedido pendente aguardando o robô.'}, status=409)
                pedido = Pedido.objects.create(pecas=matriz_pecas_ids, status=STATUS_PENDENTE)

            broadcast_order_event(
                channel_layer=channel_layer,
                titulo="Novo Pedido Criado!",
                mensagem=f"O pedido #{pedido.id} foi criado e está pendente na fila.",
                tipo="pedido_criado",
                link=f"/pedidos/historico?search={pedido.id}",
                toast_message=f'✅ Pedido #{pedido.id} criado com sucesso!',
                toast_type='success',
            )
            return JsonResponse({'message': 'Pedido criado com sucesso!', 'pedido_id': str(pedido.id)}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'message': 'JSON inválido.'}, status=400)
        except Exception as e:
            traceback.print_exc()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'dashboard_updates',
                    {
                        'type': 'dashboard.message',
                        'message_type': 'show_toast',
                        'toast_message': '❌ Erro interno ao criar o pedido.',
                        'toast_type': 'error',
                    }
                )
            return JsonResponse({'message': f'Erro interno: {str(e)}'}, status=500)

    elif request.method == 'GET':
        pecas = Peca.objects.all().order_by('id')
        return render(request, 'novoPedido.html', {
            'pecas_cadastradas': [{'id': p.id, 'name': p.name, 'tipo': p.tipo} for p in pecas]
        })

    return JsonResponse({'message': 'Método não permitido.'}, status=405)


@csrf_exempt
def updateStatusPedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if pedido.status == STATUS_PENDENTE:
        pedido.status = STATUS_EM_ANDAMENTO
        msg_status = "Em Andamento"
    elif pedido.status == STATUS_EM_ANDAMENTO:
        pedido.status = STATUS_CONCLUIDO
        msg_status = "Concluído"
    else:
        return JsonResponse({'status': 'error', 'message': 'Pedido já concluído ou cancelado.'}, status=400)

    pedido.save()

    channel_layer = get_channel_layer()
    broadcast_order_event(
        channel_layer=channel_layer,
        titulo=f"Status do Pedido #{pedido.id} Atualizado!",
        mensagem=f"O pedido #{pedido.id} foi marcado como '{msg_status}'.",
        tipo="pedido_status",
        link=f"/pedidos/historico?search={pedido.id}",
        toast_message=f'Status do pedido #{pedido.id} atualizado para "{msg_status}".',
        toast_type='success',
    )
    return JsonResponse({
        'status': 'success',
        'message': f'Status atualizado para {msg_status} com sucesso!',
        'pedido_status': msg_status,
        'status_code': pedido.status,
    })


def historico(request):
    ensure_default_pecas()
    pedidos_formatados = serialize_pedidos()
    return render(request, 'historico.html', {'pedidos': pedidos_formatados})


def pedidos_json(request):
    pedidos_formatados = serialize_pedidos()
    return JsonResponse({'pedidos': pedidos_formatados})


def getGraficoPedidos(request):
    period = request.GET.get('period', '7days')
    end_date = timezone.now().date()

    if period == '30days':
        start_date = end_date - timedelta(days=29)
    elif period == 'this_month':
        start_date = end_date.replace(day=1)
    else:
        start_date = end_date - timedelta(days=6)

    pedidos = Pedido.objects.all()
    created, completed = defaultdict(int), defaultdict(int)

    for day in (start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)):
        created[day] = 0
        completed[day] = 0

    for pedido in pedidos:
        if not pedido.data:
            continue
        pedido_day = pedido.data.date()
        if start_date <= pedido_day <= end_date:
            created[pedido_day] += 1
            if pedido.status == STATUS_CONCLUIDO:
                completed[pedido_day] += 1

    sorted_days = sorted(created)
    labels = [d.strftime("%d/%m") for d in sorted_days]
    return JsonResponse({
        'labels': labels,
        'created_counts': [created[d] for d in sorted_days],
        'completed_counts': [completed[d] for d in sorted_days],
    })
