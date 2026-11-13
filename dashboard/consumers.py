import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder

from dashboard.models import (
    STATUS_CONCLUIDO,
    STATUS_EM_ANDAMENTO,
    STATUS_PENDENTE,
    Pedido,
    Notificacao,
    serialize_pedidos,
)
from dashboard.views import get_dashboard_summary


class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'dashboard_updates'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        await self.send_dashboard_update()
        await self.send_initial_notifications_data()
        await self.send_historico_update()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get('type')

        if message_type == 'mark_notification_read':
            notification_id = data.get('notification_id')
            result = await self._mark_notification_as_read_in_db(notification_id)
            if result['status'] == 'success':
                await self.send(text_data=json.dumps({
                    'type': 'notification.update',
                    'unread_count': result['unread_count']
                }))
        elif message_type == 'mark_all_notifications_read':
            await self._mark_all_notifications_as_read_in_db()
            await self.send_notifications_list()
        elif message_type == 'fetch_notifications':
            await self.send_notifications_list()
        elif message_type == 'fetch_unread_count':
            await self.send_unread_count()
        elif message_type == 'process_pending_order':
            pedido_id = data.get('pedido_id')
            await self.process_pending_order(pedido_id)

    async def dashboard_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': event['data']
        }, cls=DjangoJSONEncoder))

    async def dashboard_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'dashboard_message',
            'message_type': event['message_type'],
            'toast_message': event['toast_message'],
            'toast_type': event['toast_type']
        }))

    async def notification_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification.update',
            'unread_count': event['unread_count']
        }))

    async def notification_new(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification.new',
            'notification': event['notification'],
            'unread_count': event['unread_count']
        }))

    async def notification_create(self, event):
        titulo = event['titulo']
        mensagem = event['mensagem']
        tipo = event['tipo']
        link = event['link']

        notification_info = await self._create_notification_and_get_data(titulo, mensagem, tipo, link)

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'notification.new',
                'notification': notification_info['notification_data'],
                'unread_count': notification_info['unread_count']
            }
        )

    async def dashboard_update_trigger(self, event):
        await self.send_dashboard_update()

    async def historico_update_trigger(self, event):
        await self.send_historico_update()

    @sync_to_async
    def get_dashboard_data_from_db(self):
        summary = get_dashboard_summary()
        return {
            'em_andamento_count': summary['em_andamento_count'],
            'concluido_count': summary['concluido_count'],
            'total_pedidos_count': summary['total_pedidos_count'],
            'pending_order': summary['pending_order'],
            'estado_robo': summary['estado_robo'],
            'stock_info': summary['stock_info'],
            'any_low_stock': summary['any_low_stock'],
        }

    @sync_to_async
    def get_pedidos_data(self):
        return serialize_pedidos()

    async def send_historico_update(self):
        pedidos_data = await self.get_pedidos_data()
        await self.send(text_data=json.dumps({
            'type': 'historico_update',
            'pedidos': pedidos_data
        }, cls=DjangoJSONEncoder))

    @sync_to_async
    def _create_notification_and_get_data(self, titulo, mensagem, tipo, link):
        notification = Notificacao.objects.create(
            titulo=titulo,
            mensagem=mensagem,
            tipo=tipo,
            link=link
        )
        all_notifications = list(Notificacao.objects.all())
        unread_count = sum(1 for n in all_notifications if not n.lida)
        return {
            'notification_data': notification.to_dict(),
            'unread_count': unread_count
        }

    @sync_to_async
    def _get_notifications_data_from_db(self):
        notifications_list_raw = list(Notificacao.objects.all())
        notifications_list_raw.sort(key=lambda x: x.data_criacao, reverse=True)
        display_notifications = notifications_list_raw[:10]
        unread_count = sum(1 for n in notifications_list_raw if not n.lida)

        notifications_list = [n.to_dict() for n in display_notifications]
        return {'notifications': notifications_list, 'unread_count': unread_count}

    @sync_to_async
    def _mark_notification_as_read_in_db(self, notification_id):
        try:
            notification = Notificacao.objects.get(id=notification_id)
            if not notification.lida:
                notification.lida = True
                notification.save()

            all_notifications = list(Notificacao.objects.all())
            unread_count = sum(1 for n in all_notifications if not n.lida)
            return {'status': 'success', 'unread_count': unread_count}
        except Notificacao.DoesNotExist:
            return {'status': 'error', 'message': 'Notificação não encontrada'}

    @sync_to_async
    def _mark_all_notifications_as_read_in_db(self):
        with transaction.atomic():
            for notif in Notificacao.objects.all():
                if not notif.lida:
                    notif.lida = True
                    notif.save()
        return {'status': 'success', 'unread_count': 0}

    @sync_to_async
    def _process_pending_order_in_db(self, pedido_id=None):
        try:
            if pedido_id:
                pedido = Pedido.objects.get(id=pedido_id)
            else:
                pedido = (
                    Pedido.objects.filter(status=STATUS_PENDENTE).first()
                    or Pedido.objects.filter(status=STATUS_EM_ANDAMENTO).first()
                )
                if not pedido:
                    return {'status': 'error', 'message': 'Nenhum pedido ativo para processar.'}

            if pedido.status == STATUS_PENDENTE:
                pedido.status = STATUS_EM_ANDAMENTO
                msg_status = "Em Andamento"
            elif pedido.status == STATUS_EM_ANDAMENTO:
                pedido.status = STATUS_CONCLUIDO
                msg_status = "Concluído"
            else:
                return {'status': 'error', 'message': 'Pedido não está em estado processável.'}

            pedido.save()
            return {
                'status': 'success',
                'pedido_id': pedido.id,
                'message': f'Pedido #{pedido.id} atualizado para "{msg_status}".',
                'pedido_status': msg_status
            }
        except Pedido.DoesNotExist:
            return {'status': 'error', 'message': 'Pedido não encontrado.'}
        except Exception as e:
            return {'status': 'error', 'message': f'Erro ao processar pedido: {str(e)}'}

    async def send_dashboard_update(self):
        dashboard_data = await self.get_dashboard_data_from_db()
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'dashboard_update',
                'data': dashboard_data
            }
        )

    async def send_initial_notifications_data(self):
        notifications_data = await self._get_notifications_data_from_db()
        await self.send(text_data=json.dumps({
            'type': 'notification.update',
            'unread_count': notifications_data['unread_count']
        }))
        await self.send(text_data=json.dumps({
            'type': 'notifications.list',
            'notifications': notifications_data['notifications'],
            'unread_count': notifications_data['unread_count']
        }))

    async def send_notifications_list(self):
        notifications_data = await self._get_notifications_data_from_db()
        await self.send(text_data=json.dumps({
            'type': 'notifications.list',
            'notifications': notifications_data['notifications'],
            'unread_count': notifications_data['unread_count']
        }))

    async def send_unread_count(self):
        all_notifications = await sync_to_async(list)(Notificacao.objects.all())
        unread_count = sum(1 for n in all_notifications if not n.lida)
        await self.send(text_data=json.dumps({
            'type': 'notification.update',
            'unread_count': unread_count
        }))

    async def process_pending_order(self, pedido_id=None):
        result = await self._process_pending_order_in_db(pedido_id)
        if result['status'] == 'success':
            resolved_id = result['pedido_id']
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'notification.create',
                    'titulo': f"Status do Pedido #{resolved_id} Atualizado!",
                    'mensagem': f"O pedido #{resolved_id} foi marcado como '{result['pedido_status']}'.",
                    'tipo': "pedido_status",
                    'link': f"/pedidos/historico?search={resolved_id}"
                }
            )
            await self.send_dashboard_update()
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'dashboard.message',
                    'message_type': 'show_toast',
                    'toast_message': f"🤖 {result['message']}",
                    'toast_type': 'success'
                }
            )
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'historico_update_trigger'
                }
            )
        else:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'dashboard.message',
                    'message_type': 'show_toast',
                    'toast_message': result['message'],
                    'toast_type': 'error'
                }
            )
