from django.db import models
from django.utils import timezone

STATUS_CONCLUIDO = 0
STATUS_EM_ANDAMENTO = 1
STATUS_PENDENTE = 2
STATUS_CANCELADO = 3

PEDIDO_STATUS_CHOICES = [
    (STATUS_CANCELADO, 'Cancelado'),
    (STATUS_PENDENTE, 'Pendente'),
    (STATUS_EM_ANDAMENTO, 'Em Andamento'),
    (STATUS_CONCLUIDO, 'Concluído'),
]

STATUS_DISPLAY_MAP = dict(PEDIDO_STATUS_CHOICES)

TIPO_FORMA_CHOICES = [
    ('circulo', 'Círculo'),
    ('quadrado', 'Quadrado'),
    ('hexagono', 'Hexágono'),
]

LOW_STOCK_THRESHOLD = 3

DEFAULT_PECAS = [
    {'id': 1, 'name': 'Círculo', 'tipo': 'circulo', 'qtd': 15, 'color_hex': '#1CA1C6'},
    {'id': 2, 'name': 'Quadrado', 'tipo': 'quadrado', 'qtd': 12, 'color_hex': '#4B4382'},
    {'id': 3, 'name': 'Hexágono', 'tipo': 'hexagono', 'qtd': 10, 'color_hex': '#8ABF7A'},
]


class Peca(models.Model):
    id = models.IntegerField(
        primary_key=True,
        verbose_name="ID da Peça (1=Círculo, 2=Quadrado, 3=Hexágono)"
    )
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome da Peça")
    tipo = models.CharField(max_length=50, choices=TIPO_FORMA_CHOICES, unique=True, verbose_name="Tipo de Forma")
    qtd = models.IntegerField(default=0, verbose_name="Quantidade em Estoque")
    color_hex = models.CharField(max_length=7, default="#CCCCCC", verbose_name="Cor Hexadecimal")

    @property
    def is_low_stock(self):
        return self.qtd <= LOW_STOCK_THRESHOLD

    def __str__(self):
        return f"{self.name} ({self.get_tipo_display()}): {self.qtd} em estoque"

    class Meta:
        verbose_name = "Peça em Estoque"
        verbose_name_plural = "Peças em Estoque"


class Estoque(models.Model):
    pass


class Pedido(models.Model):
    data = models.DateTimeField(default=timezone.now, verbose_name="Data e Hora do Pedido")
    pecas = models.JSONField(verbose_name="IDs das Peças nas Montagens")
    status = models.IntegerField(
        choices=PEDIDO_STATUS_CHOICES,
        default=STATUS_PENDENTE,
        verbose_name="Status do Pedido"
    )

    def __str__(self):
        return f"Pedido {self.pk} - Status: {self.get_status_display()}"

    def _flatten_peca_ids(self):
        if not isinstance(self.pecas, list):
            return []
        flat_ids = []
        for sublist in self.pecas:
            if isinstance(sublist, list):
                flat_ids.extend(sublist)
        return flat_ids

    def get_pecas_nomes(self):
        flat_list_ids = self._flatten_peca_ids()
        pecas_obj = Peca.objects.filter(id__in=flat_list_ids)
        peca_map = {p.id: p.name for p in pecas_obj}
        return [peca_map.get(peca_id, "Desconhecido") for peca_id in flat_list_ids]

    def get_pecas_shape_types(self):
        flat_list_ids = self._flatten_peca_ids()
        pecas_obj = Peca.objects.filter(id__in=flat_list_ids)
        peca_map = {p.id: p.tipo for p in pecas_obj}
        return [peca_map.get(peca_id, "unknown") for peca_id in flat_list_ids]

    def to_dict(self, all_pecas=None):
        if all_pecas is None:
            all_pecas = {p.id: p for p in Peca.objects.all()}

        pecas_ids, pecas_shapes, pecas_names = [], [], []
        for pid in self._flatten_peca_ids():
            peca = all_pecas.get(pid)
            if peca:
                pecas_ids.append(peca.id)
                pecas_shapes.append(peca.tipo)
                pecas_names.append(peca.name)
            else:
                pecas_ids.append(None)
                pecas_shapes.append("desconhecida")
                pecas_names.append("Peça não encontrada")

        return {
            'id': self.id,
            'status': STATUS_DISPLAY_MAP.get(self.status, "Desconhecido"),
            'status_code': self.status,
            'pecas_list_ids': pecas_ids,
            'pecas_list_shapes': pecas_shapes,
            'pecas_list_names': pecas_names,
            'data': self.data.strftime("%d/%m/%Y %H:%M") if self.data else "Sem data",
        }

    class Meta:
        verbose_name = "Pedido de Montagem"
        verbose_name_plural = "Pedidos de Montagem"


class Notificacao(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título da Notificação")
    mensagem = models.TextField(verbose_name="Mensagem Completa")
    data_criacao = models.DateTimeField(default=timezone.now, verbose_name="Data de Criação")
    lida = models.BooleanField(default=False, verbose_name="Lida")
    tipo = models.CharField(max_length=50, default='info', verbose_name="Tipo")
    link = models.CharField(max_length=255, blank=True, null=True, verbose_name="Link de Destino")

    def to_dict(self):
        return {
            'id': self.id,
            'titulo': self.titulo,
            'mensagem': self.mensagem,
            'data_criacao': self.data_criacao.strftime("%d/%m/%Y %H:%M") if self.data_criacao else "",
            'lida': self.lida,
            'tipo': self.tipo,
            'link': self.link,
        }

    def __str__(self):
        return f"[{'Lida' if self.lida else 'Não Lida'}] {self.titulo} ({self.data_criacao.strftime('%d/%m %H:%M')})"

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ['-data_criacao']


def ensure_default_pecas():
    """Ensures the 3 standard assembly shapes exist in the database."""
    try:
        if Peca.objects.count() == 0:
            for item in DEFAULT_PECAS:
                Peca.objects.update_or_create(id=item['id'], defaults=item)
    except Exception:
        pass


def serialize_pedidos():
    """Returns all orders formatted for templates, JSON APIs, and WebSockets."""
    pedidos = list(Pedido.objects.all())
    all_pecas = {p.id: p for p in Peca.objects.all()}
    pedidos_formatados = [pedido.to_dict(all_pecas=all_pecas) for pedido in pedidos]
    pedidos_formatados.sort(key=lambda p: p['id'] or 0, reverse=True)
    return pedidos_formatados
