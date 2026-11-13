import json
from unittest.mock import ANY, AsyncMock, patch

from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    STATUS_CONCLUIDO,
    STATUS_EM_ANDAMENTO,
    STATUS_PENDENTE,
    Notificacao,
    Peca,
    Pedido,
)


def criar_pecas_base():
    return {
        "circulo": Peca.objects.update_or_create(
            id=1, defaults={'name': 'Círculo', 'tipo': 'circulo', 'qtd': 5, 'color_hex': '#1CA1C6'}
        )[0],
        "quadrado": Peca.objects.update_or_create(
            id=2, defaults={'name': 'Quadrado', 'tipo': 'quadrado', 'qtd': 10, 'color_hex': '#4B4382'}
        )[0],
        "hexagono": Peca.objects.update_or_create(
            id=3, defaults={'name': 'Hexágono', 'tipo': 'hexagono', 'qtd': 1, 'color_hex': '#8ABF7A'}
        )[0],
    }


class PecaModelTest(TestCase):
    def setUp(self):
        self.pecas = criar_pecas_base()

    def test_peca_creation_and_low_stock(self):
        self.assertEqual(str(self.pecas["circulo"]), "Círculo (Círculo): 5 em estoque")
        self.assertFalse(self.pecas["circulo"].is_low_stock)
        self.assertTrue(self.pecas["hexagono"].is_low_stock)

    def test_peca_unique_constraints(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            Peca.objects.create(id=100, name="Peça Única", tipo='circulo', qtd=1, color_hex="#111111")

        with self.assertRaises(DatabaseError), transaction.atomic():
            Peca.objects.create(id=101, name="Círculo", tipo='quadrado', qtd=1, color_hex="#222222")


class PedidoModelTest(TestCase):
    def setUp(self):
        self.pecas = criar_pecas_base()

    def tearDown(self):
        Pedido.objects.all().delete()
        Peca.objects.all().delete()

    def test_pedido_creation(self):
        pecas_ids_json = [[1, 2, 3], [1, 3, 2], [2, 1, 3]]
        pedido = Pedido.objects.create(pecas=pecas_ids_json, status=STATUS_PENDENTE)
        self.assertEqual(pedido.status, STATUS_PENDENTE)
        self.assertEqual(pedido.pecas, pecas_ids_json)
        self.assertTrue(timezone.is_aware(pedido.data))

    def test_get_pecas_nomes(self):
        pedido = Pedido.objects.create(pecas=[[1, 2], [3]])
        nomes = pedido.get_pecas_nomes()
        self.assertEqual(nomes, ['Círculo', 'Quadrado', 'Hexágono'])

    def test_get_pecas_shape_types(self):
        pedido = Pedido.objects.create(pecas=[[1, 2], [3]])
        tipos = pedido.get_pecas_shape_types()
        self.assertEqual(tipos, ['circulo', 'quadrado', 'hexagono'])

    def test_to_dict(self):
        pedido = Pedido.objects.create(pecas=[[1, 2, 3]], status=STATUS_CONCLUIDO)
        data = pedido.to_dict()
        self.assertEqual(data['status'], 'Concluído')
        self.assertEqual(data['pecas_list_ids'], [1, 2, 3])
        self.assertEqual(data['pecas_list_shapes'], ['circulo', 'quadrado', 'hexagono'])


class ViewsTest(TestCase):
    def setUp(self):
        self.pecas = criar_pecas_base()
        self.matriz_valida = [[1, 2, 3], [1, 3, 2], [2, 1, 3]]
        self.pedido1 = Pedido.objects.create(pecas=self.matriz_valida, status=STATUS_EM_ANDAMENTO)
        self.pedido2 = Pedido.objects.create(pecas=self.matriz_valida, status=STATUS_CONCLUIDO)

    def tearDown(self):
        Notificacao.objects.all().delete()
        Pedido.objects.all().delete()
        Peca.objects.all().delete()

    @patch('dashboard.views.get_channel_layer')
    def test_novo_pedido_post_success(self, mock_get_channel_layer):
        mock_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_layer

        payload = {
            'peca1': '1', 'peca2': '2', 'peca3': '3',
            'peca4': '1', 'peca5': '3', 'peca6': '2',
            'peca7': '2', 'peca8': '1', 'peca9': '3',
        }

        response = self.client.post(reverse('novoPedido'), json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('Pedido criado com sucesso!', response.json()['message'])
        self.assertEqual(Pedido.objects.count(), 3)

        mock_layer.group_send.assert_any_call(
            'dashboard_updates',
            {'type': 'dashboard_update_trigger'}
        )

    @patch('dashboard.views.get_channel_layer')
    def test_novo_pedido_post_duplicate_in_assembly(self, mock_get_channel_layer):
        mock_get_channel_layer.return_value = AsyncMock()

        payload = {
            'peca1': '1', 'peca2': '1', 'peca3': '3',
            'peca4': '1', 'peca5': '3', 'peca6': '2',
            'peca7': '2', 'peca8': '1', 'peca9': '3',
        }

        response = self.client.post(reverse('novoPedido'), json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Montagem 1 contém peças repetidas', response.json()['message'])

    @patch('dashboard.views.get_channel_layer')
    def test_novo_pedido_post_invalid_peca(self, mock_get_channel_layer):
        mock_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_layer

        payload = {
            'peca1': '99', 'peca2': '2', 'peca3': '3',
            'peca4': '1', 'peca5': '3', 'peca6': '2',
            'peca7': '1', 'peca8': '2', 'peca9': '3',
        }

        response = self.client.post(reverse('novoPedido'), json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Peça inválida ou não encontrada: 99', response.json()['message'])

        mock_layer.group_send.assert_any_call(
            'dashboard_updates',
            {'type': 'dashboard.message', 'message_type': 'show_toast', 'toast_message': ANY, 'toast_type': 'error'}
        )

    @patch('dashboard.views.get_channel_layer')
    def test_update_status_pedido(self, mock_get_channel_layer):
        mock_get_channel_layer.return_value = AsyncMock()
        pedido_pendente = Pedido.objects.create(pecas=self.matriz_valida, status=STATUS_PENDENTE)

        res1 = self.client.post(reverse('updateStatusPedido', args=[pedido_pendente.id]))
        self.assertEqual(res1.status_code, 200)
        pedido_pendente.refresh_from_db()
        self.assertEqual(pedido_pendente.status, STATUS_EM_ANDAMENTO)

        res2 = self.client.post(reverse('updateStatusPedido', args=[pedido_pendente.id]))
        self.assertEqual(res2.status_code, 200)
        pedido_pendente.refresh_from_db()
        self.assertEqual(pedido_pendente.status, STATUS_CONCLUIDO)

    def test_home_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertEqual(response.context['em_andamento_count'], 1)
        self.assertEqual(response.context['concluido_count'], 1)
        self.assertEqual(response.context['circulo_qtd'], 5)
        self.assertEqual(response.context['hexagono_qtd'], 1)
        self.assertTrue(response.context['hexagono_low_stock'])

    def test_historico_and_json_views(self):
        response = self.client.get(reverse('historico'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'historico.html')
        self.assertEqual(len(response.context['pedidos']), 2)

        json_res = self.client.get(reverse('pedidos_json'))
        self.assertEqual(json_res.status_code, 200)
        self.assertEqual(len(json_res.json()['pedidos']), 2)

    def test_grafico_pedidos_view(self):
        response = self.client.get(reverse('graficoPedidos') + '?period=7days')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['labels']), 7)
        self.assertEqual(len(data['created_counts']), 7)
        self.assertEqual(len(data['completed_counts']), 7)
