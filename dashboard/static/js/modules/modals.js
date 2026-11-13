import { PIECE_ID_TO_DETAILS } from './constants.js';
import { renderShape } from './newOrder.js';

export let orderDetailsModal;
export let closeModalButton;
let modalOrderId;
let modalOrderStatus;
let searchInput;
let orderList;
let noResultsMessage;

function getStatusBadgeClasses(status) {
    const normalized = (status || '').toLowerCase();
    if (normalized.includes('andamento')) {
        return 'px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800';
    }
    if (normalized.includes('conclu')) {
        return 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800';
    }
    if (normalized.includes('pendente')) {
        return 'px-3 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-800';
    }
    if (normalized.includes('cancelado')) {
        return 'px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-800';
    }
    return 'px-3 py-1 rounded-full text-xs font-bold bg-slate-200 text-slate-700';
}

export function showOrderDetailsModal(id, status, piecesIdsString) {
    if (!modalOrderId || !modalOrderStatus || !orderDetailsModal) return;

    modalOrderId.textContent = `#${id}`;
    modalOrderStatus.textContent = status;
    modalOrderStatus.className = getStatusBadgeClasses(status);

    for (let m = 1; m <= 3; m++) {
        for (let p = 1; p <= 3; p++) {
            renderShape(`modal_peca_pedido${m}_peca${p}`, '', '', 'border-status-default', 'w-14 h-14');
            const labelElement = document.getElementById(`modal_label_pedido${m}_peca${p}`);
            if (labelElement) labelElement.textContent = '';
        }
    }

    const piecesIds = (piecesIdsString || '').split(',').filter(Boolean).map(Number);

    if (piecesIds.length === 9) {
        const positionLabels = ['Base', 'Meio', 'Topo'];
        piecesIds.forEach((pieceId, i) => {
            const globalPieceIndex = i + 1;
            const montageNumber = Math.ceil(globalPieceIndex / 3);
            const pieceInMontageIndex = (globalPieceIndex - 1) % 3 + 1;

            const previewId = `modal_peca_pedido${montageNumber}_peca${pieceInMontageIndex}`;
            const labelId = `modal_label_pedido${montageNumber}_peca${pieceInMontageIndex}`;
            const pieceDetails = PIECE_ID_TO_DETAILS[pieceId.toString()];
            const posName = positionLabels[pieceInMontageIndex - 1] || `Peça ${pieceInMontageIndex}`;

            if (pieceDetails) {
                renderShape(previewId, pieceId, montageNumber.toString(), 'border-status-selected', 'w-14 h-14');
                const labelElement = document.getElementById(labelId);
                if (labelElement) {
                    labelElement.textContent = `${posName}: ${pieceDetails.name}`;
                }
            } else {
                renderShape(previewId, 'unknown', montageNumber.toString(), 'border-status-default', 'w-14 h-14');
                const labelElement = document.getElementById(labelId);
                if (labelElement) {
                    labelElement.textContent = `${posName}: Desconhecida`;
                }
            }
        });
    }

    orderDetailsModal.classList.remove('hidden');
    orderDetailsModal.classList.add('flex');
}

export function hideOrderDetailsModal() {
    if (orderDetailsModal) {
        orderDetailsModal.classList.add('hidden');
        orderDetailsModal.classList.remove('flex');
    }
}

export function bindOrderItemEvents(item) {
    if (!item || item.dataset.bound === 'true') return;
    item.dataset.bound = 'true';

    item.addEventListener('click', function () {
        const { id, status, pecas } = this.dataset;
        showOrderDetailsModal(id, status, pecas);
    });

    item.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            const { id, status, pecas } = this.dataset;
            showOrderDetailsModal(id, status, pecas);
        }
    });
}

export function initializeHistoricalOrderItems() {
    document.querySelectorAll('.pedido-item').forEach(bindOrderItemEvents);
}

export function filterOrders() {
    if (!searchInput || !noResultsMessage) return;
    const query = searchInput.value.trim().toLowerCase();
    let found = false;

    const currentHistoricalOrderItems = document.querySelectorAll('.pedido-item');
    currentHistoricalOrderItems.forEach(item => {
        const id = (item.dataset.id || '').toLowerCase();
        const status = (item.dataset.status || '').toLowerCase();

        if (id.includes(query) || status.includes(query)) {
            item.style.display = 'flex';
            found = true;
        } else {
            item.style.display = 'none';
        }
    });

    noResultsMessage.classList.toggle('hidden', found);
}

function updateActiveFilterPills(activeValue) {
    document.querySelectorAll('.status-filter-pill').forEach(pill => {
        const isMatch = (pill.dataset.statusFilter || '').toLowerCase() === (activeValue || '').toLowerCase();
        pill.classList.toggle('bg-purple-600', isMatch);
        pill.classList.toggle('text-white', isMatch);
        pill.classList.toggle('bg-slate-100', !isMatch);
        pill.classList.toggle('text-slate-600', !isMatch);
    });
}

export function setupOrderSearch() {
    if (!searchInput || !orderList || !noResultsMessage) return;

    searchInput.addEventListener('input', () => {
        updateActiveFilterPills(searchInput.value.trim());
        filterOrders();
    });

    searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            filterOrders();
        }
    });

    document.querySelectorAll('.status-filter-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const filterVal = pill.dataset.statusFilter || '';
            searchInput.value = filterVal;
            updateActiveFilterPills(filterVal);
            filterOrders();
        });
    });

    // Apply initial ?search= query parameter if present in URL
    const urlSearch = new URLSearchParams(window.location.search).get('search');
    if (urlSearch) {
        searchInput.value = urlSearch;
        updateActiveFilterPills(urlSearch);
        filterOrders();
    }
}

export function initializeModals() {
    orderDetailsModal = document.getElementById('pedido-modal');
    closeModalButton = document.getElementById('close-modal-btn');
    modalOrderId = document.getElementById('modal-pedido-id');
    modalOrderStatus = document.getElementById('modal-pedido-status');
    searchInput = document.getElementById('searchInput');
    orderList = document.getElementById('pedidoLista');
    noResultsMessage = document.getElementById('avisoNenhumPedido');

    closeModalButton?.addEventListener('click', hideOrderDetailsModal);

    orderDetailsModal?.addEventListener('click', (event) => {
        if (event.target === orderDetailsModal) {
            hideOrderDetailsModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && orderDetailsModal && !orderDetailsModal.classList.contains('hidden')) {
            hideOrderDetailsModal();
        }
    });

    setupOrderSearch();
    initializeHistoricalOrderItems();
}
