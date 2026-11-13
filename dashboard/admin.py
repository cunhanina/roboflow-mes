from django.contrib import admin
from .models import Peca, Pedido, Notificacao


@admin.register(Peca)
class PecaAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'tipo', 'qtd', 'color_hex')
    list_editable = ('qtd', 'color_hex')
    search_fields = ('name', 'tipo')
    ordering = ('id',)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'data', 'pecas')
    list_filter = ('status', 'data')
    search_fields = ('id',)
    ordering = ('-data',)


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'tipo', 'lida', 'data_criacao')
    list_filter = ('lida', 'tipo', 'data_criacao')
    search_fields = ('titulo', 'mensagem')
    ordering = ('-data_criacao',)
