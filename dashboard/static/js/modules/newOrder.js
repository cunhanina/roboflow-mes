import { showToast, getCookie } from './utils.js';
import { MONTAGE_COLORS, PIECE_ID_TO_DETAILS } from './constants.js';

export const newOrderForm = document.getElementById('pedidoForm');
export const confirmOrderButton = document.getElementById('confirmarBtn');
export const randomFillButton = document.getElementById('randomFillBtn');
export const resetOrderButton = document.getElementById('resetOrderBtn');

export function renderShape(elementId, pieceIdentifier, montageNumber, statusClass = 'border-status-default', sizeClasses = 'w-12 h-12') {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.className = `${sizeClasses} flex items-center justify-center shadow-sm transition-all duration-300`;
    element.innerHTML = '';

    let shapeClass = '';
    let iconHtml = '';
    const colorClass = MONTAGE_COLORS[montageNumber] || 'bg-gray-100';

    let shapeType = '';
    if (typeof pieceIdentifier === 'number' || (typeof pieceIdentifier === 'string' && pieceIdentifier !== '' && !isNaN(pieceIdentifier))) {
        const pieceDetails = PIECE_ID_TO_DETAILS[pieceIdentifier.toString()];
        shapeType = pieceDetails ? pieceDetails.type : 'unknown';
    } else {
        shapeType = pieceIdentifier;
    }

    switch (shapeType) {
        case 'circulo':
            shapeClass = 'rounded-full';
            iconHtml = '<i class="fas fa-circle text-white text-lg"></i>';
            break;
        case 'quadrado':
            shapeClass = 'rounded-lg';
            iconHtml = '<i class="fas fa-square text-white text-lg"></i>';
            break;
        case 'hexagono':
            shapeClass = 'hexagon-shape';
            iconHtml = `<svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <polygon points="12,2 22,7 22,17 12,22 2,17 2,7"/>
                        </svg>`;
            break;
        default:
            element.classList.add('bg-slate-100', 'rounded-full', 'border-status-default');
            return;
    }
    element.classList.add(shapeClass, colorClass, statusClass);
    element.innerHTML = iconHtml;
}

function validateMontageGroup(montageNumber) {
    const startIdx = (montageNumber - 1) * 3 + 1;
    const selectedValues = [];
    for (let i = startIdx; i < startIdx + 3; i++) {
        const sel = document.querySelector(`select[name="peca${i}"]`);
        if (sel && sel.value) {
            selectedValues.push(sel.value);
        }
    }

    const badge = document.getElementById(`montagem-badge-${montageNumber}`);
    const warning = document.getElementById(`montagem-warning-${montageNumber}`);
    const hasDuplicates = new Set(selectedValues).size < selectedValues.length;

    if (warning) {
        warning.classList.toggle('hidden', !hasDuplicates);
    }

    if (badge) {
        badge.textContent = `${selectedValues.length}/3 peças`;
        badge.className = 'text-xs font-semibold px-2.5 py-0.5 rounded-full ';
        if (hasDuplicates) {
            badge.className += 'bg-red-100 text-red-700';
        } else if (selectedValues.length === 3) {
            badge.className += 'bg-emerald-100 text-emerald-700';
            badge.textContent = '✓ Válida';
        } else {
            badge.className += 'bg-slate-200 text-slate-600';
        }
    }

    return !hasDuplicates;
}

function updatePiecePreview(selectName) {
    const selectElement = document.querySelector(`select[name="${selectName}"]`);
    if (!selectElement) return;

    const globalPieceIndex = parseInt(selectName.replace('peca', ''));
    const montageNumber = Math.ceil(globalPieceIndex / 3);
    const pieceInMontageIndex = (globalPieceIndex - 1) % 3 + 1;

    const previewId = `peca_pedido${montageNumber}_peca${pieceInMontageIndex}`;
    const selectedPieceId = selectElement.value;

    const statusClass = selectedPieceId ? 'border-status-selected' : 'border-status-default';
    renderShape(previewId, selectedPieceId, montageNumber.toString(), statusClass);
    validateMontageGroup(montageNumber);
}

export function fillRandomValidOrder() {
    const validPermutations = [
        ['1', '2', '3'],
        ['1', '3', '2'],
        ['2', '1', '3'],
        ['2', '3', '1'],
        ['3', '1', '2'],
        ['3', '2', '1'],
    ];

    for (let m = 0; m < 3; m++) {
        const perm = validPermutations[Math.floor(Math.random() * validPermutations.length)];
        for (let p = 0; p < 3; p++) {
            const idx = m * 3 + p + 1;
            const select = document.querySelector(`select[name="peca${idx}"]`);
            if (select) {
                select.value = perm[p];
                updatePiecePreview(`peca${idx}`);
            }
        }
    }
    showToast('✨ Exemplo de pedido preenchido com sucesso!', 'info', 2500);
}

export function resetOrderSelections() {
    if (!newOrderForm) return;
    newOrderForm.reset();
    for (let i = 1; i <= 9; i++) {
        updatePiecePreview(`peca${i}`);
    }
}

export async function handleConfirmOrderClick(event) {
    event.preventDefault();

    if (!newOrderForm) return;

    const orderData = {};
    let allPiecesSelected = true;

    for (let i = 1; i <= 9; i++) {
        const select = newOrderForm.querySelector(`select[name="peca${i}"]`);
        if (select && select.value) {
            const pieceId = parseInt(select.value);
            if (isNaN(pieceId)) {
                allPiecesSelected = false;
                break;
            }
            orderData[`peca${i}`] = pieceId;
        } else {
            allPiecesSelected = false;
            break;
        }
    }

    if (!allPiecesSelected) {
        showToast('⚠️ Selecione todas as 9 peças antes de confirmar o pedido.', 'warning');
        return;
    }

    for (let m = 1; m <= 3; m++) {
        if (!validateMontageGroup(m)) {
            showToast(`⚠️ A Montagem ${m} possui peças repetidas. Escolha 3 formas distintas.`, 'error');
            return;
        }
    }

    try {
        const csrfToken = getCookie('csrftoken');
        const headers = { 'Content-Type': 'application/json' };
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        const response = await fetch('/pedidos/', {
            method: 'POST',
            headers,
            body: JSON.stringify(orderData),
        });

        const responseData = await response.json();

        if (!response.ok) {
            showToast(responseData.message || 'Erro ao criar o pedido.', 'error');
            return;
        }

        resetOrderSelections();
    } catch (error) {
        showToast(`❌ Erro de comunicação: ${error.message}`, 'error');
        console.error('Detailed error confirming order:', error);
    }
}

export function initializeNewOrderPieceSelectors() {
    for (let i = 1; i <= 9; i++) {
        const select = document.querySelector(`select[name="peca${i}"]`);
        if (select) {
            select.addEventListener('change', () => updatePiecePreview(`peca${i}`));
            updatePiecePreview(`peca${i}`);
        }
    }

    randomFillButton?.addEventListener('click', fillRandomValidOrder);
    resetOrderButton?.addEventListener('click', resetOrderSelections);
}
