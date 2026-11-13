import { showToast, showLoader, hideLoader } from './utils.js';

const notificationBell = document.getElementById('notification-bell');
const notificationCount = document.getElementById('notification-count');
const notificationsDropdown = document.getElementById('notifications-dropdown');
const notificationsList = document.getElementById('notifications-list');
const noNotificationsMessageElem = document.getElementById('no-notifications-message');
const markAllReadBtn = document.getElementById('mark-all-read');
const wsStatusDot = document.getElementById('ws-status-dot');
const wsStatusText = document.getElementById('ws-status-text');

let websocket = null;

function updateWsIndicator(state) {
    if (!wsStatusDot || !wsStatusText) return;
    wsStatusDot.className = 'w-2 h-2 rounded-full';
    if (state === 'connected') {
        wsStatusDot.classList.add('bg-emerald-400');
        wsStatusText.textContent = 'Tempo Real Ativo';
    } else if (state === 'connecting') {
        wsStatusDot.classList.add('bg-amber-400', 'animate-pulse');
        wsStatusText.textContent = 'Conectando...';
    } else {
        wsStatusDot.classList.add('bg-red-400');
        wsStatusText.textContent = 'Reconectando...';
    }
}

export function sendWebSocketMessage(payload) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify(payload));
        return true;
    }
    return false;
}

export function connectWebSocket(forceNew = false) {
    if (!notificationBell && window.location.pathname !== '/' && !forceNew) return;
    if (websocket && websocket.readyState === WebSocket.OPEN && !forceNew) return;
    if (websocket && websocket.readyState !== WebSocket.CLOSED) websocket.close();

    updateWsIndicator('connecting');

    const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsURL = wsProtocol + window.location.host + '/ws/dashboard/';

    websocket = new WebSocket(wsURL);

    websocket.onopen = () => {
        updateWsIndicator('connected');
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        switch (data.type) {
            case 'dashboard_update':
                document.dispatchEvent(new CustomEvent('dashboardUpdate', { detail: data.data }));
                break;
            case 'historico_update':
                document.dispatchEvent(new CustomEvent('historicoUpdate', { detail: data.pedidos }));
                break;
            case 'dashboard_message':
                if (data.message_type === 'show_toast') {
                    showToast(data.toast_message, data.toast_type);
                }
                break;
            case 'notification.update':
                updateNotificationCountUI(data.unread_count);
                break;
            case 'notification.new':
                showToast(`🔔 ${data.notification.titulo}`, 'info', 4500);
                updateNotificationCountUI(data.unread_count);
                break;
            case 'notifications.list':
                renderNotificationsList(data.notifications, data.unread_count);
                break;
            default:
                break;
        }
    };

    websocket.onclose = (event) => {
        updateWsIndicator('disconnected');
        if (event.code !== 1000) {
            setTimeout(() => connectWebSocket(true), 3000);
        }
    };

    websocket.onerror = () => {
        updateWsIndicator('disconnected');
        if (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING) {
            websocket.close();
        }
    };
}

function updateNotificationCountUI(count) {
    if (!notificationCount) return;
    if (count > 0) {
        notificationCount.textContent = count > 99 ? '99+' : count;
        notificationCount.classList.remove('hidden');
        notificationBell?.setAttribute('aria-label', `Ver ${count} novas notificações`);
        notificationCount.setAttribute('title', `${count} novas notificações`);
    } else {
        notificationCount.classList.add('hidden');
        notificationCount.textContent = '0';
        notificationBell?.setAttribute('aria-label', 'Ver notificações');
        notificationCount.setAttribute('title', 'Nenhuma notificação não lida');
    }
}

function renderNotificationsList(notifications, unreadCount) {
    if (!notificationsList) return;
    notificationsList.innerHTML = '';
    if (!notifications || notifications.length === 0) {
        if (noNotificationsMessageElem) {
            noNotificationsMessageElem.classList.remove('hidden');
            notificationsList.appendChild(noNotificationsMessageElem);
        }
    } else {
        noNotificationsMessageElem?.classList.add('hidden');
        notifications.forEach(notif => {
            const notifItem = document.createElement('div');
            notifItem.className = `px-4 py-3 hover:bg-purple-50/60 cursor-pointer transition-colors ${notif.lida ? 'text-slate-500' : 'text-slate-900 font-semibold bg-purple-50/20'}`;
            notifItem.setAttribute('role', 'listitem');
            notifItem.setAttribute('aria-label', `${notif.lida ? 'Lida' : 'Não lida'}: ${notif.titulo}. ${notif.mensagem}`);
            notifItem.dataset.notificationId = notif.id;
            notifItem.innerHTML = `
                <div class="flex items-center justify-between gap-2">
                    <p class="text-sm">${notif.titulo}</p>
                    ${!notif.lida ? '<span class="w-2 h-2 rounded-full bg-purple-600 flex-shrink-0"></span>' : ''}
                </div>
                <p class="text-xs text-slate-500 mt-0.5 line-clamp-2">${notif.mensagem}</p>
                <p class="text-[11px] text-slate-400 mt-1">${notif.data_criacao}</p>
            `;
            notifItem.addEventListener('click', () => handleNotificationClick(notif));
            notificationsList.appendChild(notifItem);
        });
    }
    updateNotificationCountUI(unreadCount);
    hideLoader();
}

async function handleNotificationClick(notif) {
    if (!notif.lida && websocket?.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'mark_notification_read', notification_id: notif.id }));
    }
    notificationsDropdown?.classList.add('hidden');
    if (notif.link) window.location.href = notif.link;
}

export async function markAllNotificationsAsRead() {
    if (websocket?.readyState === WebSocket.OPEN) {
        showLoader();
        websocket.send(JSON.stringify({ type: 'mark_all_notifications_read' }));
        showToast("Todas as notificações foram marcadas como lidas.", "success");
    } else {
        showToast("WebSocket desconectado. Recarregue a página.", "error");
    }
}

export function initializeNotifications() {
    if (!notificationBell) return;

    notificationBell.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!notificationsDropdown) return;
        notificationsDropdown.classList.toggle('hidden');
        if (!notificationsDropdown.classList.contains('hidden') && websocket?.readyState === WebSocket.OPEN) {
            showLoader();
            websocket.send(JSON.stringify({ type: 'fetch_notifications' }));
        }
    });

    document.addEventListener('click', (e) => {
        if (notificationsDropdown && notificationBell && !notificationsDropdown.contains(e.target) && !notificationBell.contains(e.target)) {
            notificationsDropdown.classList.add('hidden');
        }
    });

    markAllReadBtn?.addEventListener('click', markAllNotificationsAsRead);
}
