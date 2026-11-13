import { showLoader, hideLoader, setupGlobalTooltips, showToast } from '/static/js/modules/utils.js';
import { connectWebSocket, initializeNotifications, sendWebSocketMessage } from '/static/js/modules/notifications.js';
import { initializeModals, bindOrderItemEvents, filterOrders } from '/static/js/modules/modals.js';
import { updateOrdersChart } from '/static/js/modules/charts.js';
import { newOrderForm, confirmOrderButton, initializeNewOrderPieceSelectors, handleConfirmOrderClick } from '/static/js/modules/newOrder.js';

const totalPedidosEl = document.getElementById('total-pedidos');
const pedidosEmAndamentoEl = document.getElementById('pedidos-em-andamento');
const pedidosConcluidosEl = document.getElementById('pedidos-concluidos');
const circuloQtdEl = document.getElementById('circulo-qtd');
const hexagonoQtdEl = document.getElementById('hexagono-qtd');
const quadradoQtdEl = document.getElementById('quadrado-qtd');
const lowStockAlertEl = document.getElementById('low-stock-alert');
const robotStatusEl = document.getElementById('robot-status');
const pendingOrderCardEl = document.getElementById('pending-order-card');
const pendingOrderBadgeEl = document.getElementById('pending-order-badge');
const pendingOrderLabelEl = document.getElementById('pending-order-label');
const pendingOrderIdEl = document.getElementById('pending-order-id');
const pendingOrderSubtitleEl = document.getElementById('pending-order-subtitle');
const robotSimControlsEl = document.getElementById('robot-simulation-controls');
const simulateRobotBtn = document.getElementById('simulate-robot-btn');
const simulateRobotBtnText = document.getElementById('simulate-robot-btn-text');

function renderRobotStatus(estadoRobo) {
    if (!robotStatusEl) return;
    if (estadoRobo === 'Ocioso') {
        robotStatusEl.innerHTML = `
            <i class="fas fa-circle text-emerald-500 text-sm animate-pulse"></i>
            <span class="text-emerald-700">Ocioso</span>
        `;
    } else if (estadoRobo === 'Em Montagem') {
        robotStatusEl.innerHTML = `
            <i class="fas fa-cog fa-spin text-amber-500 text-base"></i>
            <span class="text-amber-700">Em Montagem</span>
        `;
    } else if (estadoRobo === 'Erro') {
        robotStatusEl.innerHTML = `
            <i class="fas fa-exclamation-triangle text-red-500 text-base animate-bounce"></i>
            <span class="text-red-700">Erro!</span>
        `;
    } else {
        robotStatusEl.innerHTML = `
            <i class="fas fa-question-circle text-slate-400 text-base"></i>
            <span class="text-slate-600">${estadoRobo || 'Desconhecido'}</span>
        `;
    }
}

function updatePendingOrderCard(pendingOrder) {
    if (!pendingOrderCardEl || !pendingOrderIdEl) return;

    pendingOrderCardEl.classList.remove(
        'bg-amber-50/70', 'border-amber-300',
        'bg-blue-50/70', 'border-blue-300',
        'bg-emerald-50/70', 'border-emerald-300'
    );
    pendingOrderBadgeEl?.classList.remove(
        'bg-amber-200/80', 'text-amber-900',
        'bg-blue-200/80', 'text-blue-900',
        'bg-emerald-200/80', 'text-emerald-900'
    );
    pendingOrderIdEl.classList.remove('text-amber-600', 'text-blue-600', 'text-emerald-600');

    if (pendingOrder && pendingOrder.id) {
        const isPending = pendingOrder.status_code === 2 || pendingOrder.status === 'Pendente';
        if (isPending) {
            pendingOrderCardEl.classList.add('bg-amber-50/70', 'border-amber-300');
            pendingOrderBadgeEl?.classList.add('bg-amber-200/80', 'text-amber-900');
            if (pendingOrderLabelEl) pendingOrderLabelEl.textContent = 'Fila Pendente';
            pendingOrderIdEl.classList.add('text-amber-600');
            if (pendingOrderSubtitleEl) pendingOrderSubtitleEl.textContent = 'Aguardando início da montagem pelo robô...';
            if (simulateRobotBtnText) simulateRobotBtnText.textContent = 'Iniciar Montagem (Simular CLP)';
        } else {
            pendingOrderCardEl.classList.add('bg-blue-50/70', 'border-blue-300');
            pendingOrderBadgeEl?.classList.add('bg-blue-200/80', 'text-blue-900');
            if (pendingOrderLabelEl) pendingOrderLabelEl.textContent = 'Em Execução';
            pendingOrderIdEl.classList.add('text-blue-600');
            if (pendingOrderSubtitleEl) pendingOrderSubtitleEl.textContent = 'Robô executando a montagem das peças...';
            if (simulateRobotBtnText) simulateRobotBtnText.textContent = 'Concluir Montagem (Simular CLP)';
        }
        pendingOrderIdEl.textContent = `#${pendingOrder.id}`;
        pendingOrderIdEl.dataset.orderId = pendingOrder.id;
        if (simulateRobotBtn) simulateRobotBtn.dataset.orderId = pendingOrder.id;
        robotSimControlsEl?.classList.remove('hidden');
    } else {
        pendingOrderCardEl.classList.add('bg-emerald-50/70', 'border-emerald-300');
        pendingOrderBadgeEl?.classList.add('bg-emerald-200/80', 'text-emerald-900');
        if (pendingOrderLabelEl) pendingOrderLabelEl.textContent = 'Fila Livre';
        pendingOrderIdEl.classList.add('text-emerald-600');
        pendingOrderIdEl.textContent = 'Nenhum';
        pendingOrderIdEl.dataset.orderId = '';
        if (pendingOrderSubtitleEl) pendingOrderSubtitleEl.textContent = 'Todos os pedidos foram processados com sucesso!';
        robotSimControlsEl?.classList.add('hidden');
    }
}

function updateDashboardUI(data) {
    if (!data) return;

    if (totalPedidosEl) {
        totalPedidosEl.textContent = data.total_pedidos_count ?? (data.em_andamento_count + data.concluido_count);
    }
    if (pedidosEmAndamentoEl) {
        pedidosEmAndamentoEl.textContent = data.em_andamento_count ?? 0;
    }
    if (pedidosConcluidosEl) {
        pedidosConcluidosEl.textContent = data.concluido_count ?? 0;
    }

    if (data.estado_robo) {
        renderRobotStatus(data.estado_robo);
    }

    updatePendingOrderCard(data.pending_order);

    if (data.stock_info) {
        let anyLow = false;
        for (const shapeType in data.stock_info) {
            const stockItem = data.stock_info[shapeType];
            let element, parentDiv;

            if (shapeType === 'circulo' && circuloQtdEl) {
                element = circuloQtdEl;
                parentDiv = element.closest('.bg-\\[\\#1CA1C6\\]');
            } else if (shapeType === 'hexagono' && hexagonoQtdEl) {
                element = hexagonoQtdEl;
                parentDiv = element.closest('.bg-\\[\\#8ABF7A\\]');
            } else if (shapeType === 'quadrado' && quadradoQtdEl) {
                element = quadradoQtdEl;
                parentDiv = element.closest('.bg-\\[\\#4B4382\\]');
            }

            if (element) {
                element.textContent = stockItem.quantity;
            }
            if (parentDiv) {
                parentDiv.classList.toggle('border-4', Boolean(stockItem.is_low_stock));
                parentDiv.classList.toggle('border-red-500', Boolean(stockItem.is_low_stock));
            }
            if (stockItem.is_low_stock) anyLow = true;
        }
        if (lowStockAlertEl) {
            lowStockAlertEl.classList.toggle('hidden', !anyLow);
        }
    }
}

function getStatusPillHtml(status) {
    if (status === 'Em Andamento') {
        return '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">Em Andamento</span>';
    }
    if (status === 'Concluído') {
        return '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">Concluído</span>';
    }
    if (status === 'Pendente') {
        return '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800">Pendente</span>';
    }
    if (status === 'Cancelado') {
        return '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800">Cancelado</span>';
    }
    return `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700">${status}</span>`;
}

function updateHistoricoUI(pedidos) {
    if (!window.location.pathname.includes('/pedidos/historico')) return;
    const pedidoLista = document.getElementById('pedidoLista');
    if (!pedidoLista || !Array.isArray(pedidos)) return;

    pedidoLista.innerHTML = '';

    pedidos.forEach(pedido => {
        const li = document.createElement('li');
        li.className = 'pedido-item w-full flex items-center justify-between p-3.5 bg-slate-50 hover:bg-purple-50/50 border border-slate-200/80 hover:border-purple-300 rounded-xl cursor-pointer transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-purple-500';
        li.dataset.id = pedido.id;
        li.dataset.status = pedido.status;
        li.dataset.pecas = (pedido.pecas_list_ids || []).join(',');
        li.setAttribute('role', 'listitem');
        li.setAttribute('tabindex', '0');
        li.setAttribute('aria-label', `Detalhes do pedido ${pedido.id}, status ${pedido.status}`);
        li.setAttribute('data-tooltip', `Clique ou pressione Enter para inspecionar as 3 montagens do pedido #${pedido.id}`);

        li.innerHTML = `
            <div>
                <div class="flex items-center gap-2">
                    <span class="text-sm font-bold text-slate-900">Pedido #${pedido.id}</span>
                    ${getStatusPillHtml(pedido.status)}
                </div>
                <p class="text-xs text-slate-500 mt-1">
                    <i class="far fa-clock mr-1"></i> ${pedido.data}
                </p>
            </div>
            <span class="text-slate-400 text-sm">
                <i class="fas fa-chevron-right"></i>
            </span>
        `;
        bindOrderItemEvents(li);
        pedidoLista.appendChild(li);
    });

    setupGlobalTooltips();
    filterOrders();
}

document.addEventListener('dashboardUpdate', (event) => {
    updateDashboardUI(event.detail);
});

document.addEventListener('historicoUpdate', (event) => {
    updateHistoricoUI(event.detail);
});

document.addEventListener('DOMContentLoaded', () => {
    setupGlobalTooltips();
    connectWebSocket();
    initializeNotifications();

    if (newOrderForm) {
        initializeNewOrderPieceSelectors();
        if (confirmOrderButton) {
            confirmOrderButton.addEventListener('click', async (e) => {
                showLoader();
                await handleConfirmOrderClick(e);
                hideLoader();
            });
        }
    }

    if (simulateRobotBtn) {
        simulateRobotBtn.addEventListener('click', async () => {
            const orderId = simulateRobotBtn.dataset.orderId;
            if (!orderId) return;

            const sentViaWs = sendWebSocketMessage({
                type: 'process_pending_order',
                pedido_id: parseInt(orderId)
            });

            if (!sentViaWs) {
                try {
                    showLoader();
                    const res = await fetch(`/api/pedidos/${orderId}/updateStatus/`, { method: 'POST' });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(`🤖 ${data.message}`, 'success');
                        window.location.reload();
                    } else {
                        showToast(data.message || 'Erro ao atualizar status.', 'error');
                    }
                } catch (err) {
                    showToast('Erro de comunicação com o servidor.', 'error');
                } finally {
                    hideLoader();
                }
            }
        });
    }

    initializeModals();

    if (window.location.pathname.includes('/pedidos/historico')) {
        updateOrdersChart('7days');
        document.getElementById('filter7Days')?.addEventListener('click', () => updateOrdersChart('7days'));
        document.getElementById('filter30Days')?.addEventListener('click', () => updateOrdersChart('30days'));
        document.getElementById('filterThisMonth')?.addEventListener('click', () => updateOrdersChart('this_month'));
    }
});
