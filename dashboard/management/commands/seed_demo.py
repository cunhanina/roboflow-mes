from datetime import timedelta
import random

from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import (
    DEFAULT_PECAS,
    STATUS_CONCLUIDO,
    STATUS_EM_ANDAMENTO,
    STATUS_PENDENTE,
    Notificacao,
    Peca,
    Pedido,
)


class Command(BaseCommand):
    help = 'Populates RoboFlow MES with default parts, sample historical orders, and notifications.'

    def handle(self, *args, **options):
        for item in DEFAULT_PECAS:
            Peca.objects.update_or_create(id=item['id'], defaults=item)
        self.stdout.write(self.style.SUCCESS('✅ Peças padrão criadas/atualizadas (Círculo, Quadrado, Hexágono).'))

        if Pedido.objects.count() == 0:
            now = timezone.now()
            permutations = [
                [1, 2, 3],
                [1, 3, 2],
                [2, 1, 3],
                [2, 3, 1],
                [3, 1, 2],
                [3, 2, 1],
            ]

            for days_ago in range(14, 0, -1):
                orders_for_day = random.randint(1, 3)
                for _ in range(orders_for_day):
                    matriz = [random.choice(permutations) for _ in range(3)]
                    order_date = now - timedelta(days=days_ago, hours=random.randint(1, 8))
                    Pedido.objects.create(
                        data=order_date,
                        pecas=matriz,
                        status=STATUS_CONCLUIDO,
                    )

            Pedido.objects.create(
                data=now - timedelta(minutes=25),
                pecas=[[1, 2, 3], [2, 3, 1], [3, 1, 2]],
                status=STATUS_EM_ANDAMENTO,
            )
            pendente = Pedido.objects.create(
                data=now - timedelta(minutes=5),
                pecas=[[3, 2, 1], [1, 3, 2], [2, 1, 3]],
                status=STATUS_PENDENTE,
            )

            Notificacao.objects.create(
                titulo="Sistema RoboFlow MES Inicializado",
                mensagem=f"Dados de demonstração carregados. Pedido #{pendente.id} aguarda processamento.",
                tipo="info",
                link=f"/pedidos/historico?search={pendente.id}",
            )
            self.stdout.write(self.style.SUCCESS('✅ Pedidos históricos e notificações de demonstração criados!'))
        else:
            self.stdout.write(self.style.WARNING('ℹ️ Pedidos já existem no banco; mantendo histórico atual.'))
