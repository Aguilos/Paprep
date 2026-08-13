document.addEventListener('DOMContentLoaded', function() {
  function qs(s) { return document.querySelector(s); }
  function qsa(s) { return document.querySelectorAll(s); }

  const chatButtons = qsa('[data-chat-open]');
  const socket = (window.socket && window.socket.connected) ? window.socket : (typeof io !== 'undefined' ? io() : null);
  const currentUserId = document.getElementById('currentUser') ? document.getElementById('currentUser').dataset.id : null;
  chatButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const clinicId = btn.getAttribute('data-clinic-id');
      const panel = document.getElementById('chat_panel_' + clinicId);
      if (panel) panel.classList.toggle('d-none');
      loadHistory(clinicId);
    });
  });

  function createMsgrBubble(sender, text, createdAt, attachmentUrl, attachmentType) {
    const row = document.createElement('div');
    const isUser = (sender === 'user');
    row.className = `msgr-msg-row ${isUser ? 'sent' : 'recv'}`;
    const timeStr = createdAt ? new Date(createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

    let bodyHtml = '';
    if (attachmentType === 'image' && attachmentUrl) {
      bodyHtml = `<a href="${attachmentUrl}" target="_blank"><img src="${attachmentUrl}" alt="Image" style="max-width:190px;max-height:170px;border-radius:10px;display:block;"></a>`;
    } else if (attachmentType === 'file' && attachmentUrl) {
      const fname = attachmentUrl.split('/').pop();
      bodyHtml = `<a href="${attachmentUrl}" target="_blank" class="d-flex align-items-center gap-2 text-decoration-none" style="color:inherit;"><i class="bi bi-file-earmark-arrow-down fs-5"></i><span class="small">${escapeHtml(fname)}</span></a>`;
    } else {
      bodyHtml = `<div>${escapeHtml(text)}</div>`;
    }

    if (isUser) {
      row.innerHTML = `
        <div class="msgr-bubble">
          ${bodyHtml}
          <div class="msgr-time">${timeStr}</div>
        </div>`;
    } else {
      row.innerHTML = `
        <div class="messenger-avatar avatar-sm flex-shrink-0" style="width:26px;height:26px;font-size:11px;background:#0084FF;">C</div>
        <div class="msgr-bubble">
          ${bodyHtml}
          <div class="msgr-time">${timeStr}</div>
        </div>`;
    }
    return row;
  }

  async function loadHistory(clinicId) {
    const res = await fetch(`/chat/history/${clinicId}`);
    if (!res.ok) return;
    const msgs = await res.json();
    const list = document.getElementById('chat_list_' + clinicId);
    if (!list) return;
    list.innerHTML = '';
    msgs.forEach(m => {
      list.appendChild(createMsgrBubble(m.sender, m.text, m.created_at, m.attachment_url, m.attachment_type));
    });
    list.scrollTop = list.scrollHeight;
    if (socket && currentUserId) {
      try {
        socket.emit('join', {clinic_id: parseInt(clinicId), user_id: parseInt(currentUserId)});
      } catch(e) { console.warn('socket join failed', e); }
    }
  }

  async function sendMessage(evt, clinicId) {
    if (evt) evt.preventDefault();
    const input = document.getElementById('chat_input_' + clinicId);
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    if (socket && socket.connected && currentUserId) {
      socket.emit('send_message', { clinic_id: parseInt(clinicId), user_id: parseInt(currentUserId), text: text });
      input.value = '';
    } else {
      const CSRF_TOKEN = (document.getElementById('csrfToken') || {}).dataset.token || '';
      const res = await fetch('/chat/send', {
        method: 'POST',
        headers: {
          'Content-Type':'application/json',
          'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({clinic_id: clinicId, text})
      });
      if (res.ok) {
        input.value = '';
        loadHistory(clinicId);
      } else {
        alert('Failed to send message');
      }
    }
  }

  // Typing indicator debounce helper
  let typingTimeout = null;
  function handleTypingEvent(clinicId, sender = 'user') {
    if (!socket || !socket.connected || !currentUserId) return;
    socket.emit('typing', { clinic_id: parseInt(clinicId), user_id: parseInt(currentUserId), sender: sender, is_typing: true });
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
      socket.emit('typing', { clinic_id: parseInt(clinicId), user_id: parseInt(currentUserId), sender: sender, is_typing: false });
    }, 1800);
  }

  window.sendMessage = sendMessage;
  window.loadHistory = loadHistory;
  window.handleTypingEvent = handleTypingEvent;

  // Handle incoming socket messages & typing events
  if (socket) {
    socket.on('connect', function() {
      console.log('Socket.IO WebSocket connected cleanly.');
    });

    socket.on('chat_message', function(data) {
      try {
        const payload = data && data.message ? data.message : null;
        if (!payload) return;
        const clinicId = payload.clinic_id || payload.clinicId || (data && data.clinic_id);
        const list = document.getElementById('chat_list_' + clinicId);
        if (!list) return;

        // Remove typing indicator if present
        const existingTyping = list.querySelector('.typing-indicator-row');
        if (existingTyping) existingTyping.remove();

        list.appendChild(createMsgrBubble(payload.sender, payload.text, payload.created_at, payload.attachment_url, payload.attachment_type));
        list.scrollTop = list.scrollHeight;
      } catch(e) {
        console.warn('chat_message handler error', e);
      }
    });

    socket.on('typing_status', function(data) {
      try {
        const clinicId = data.clinic_id;
        const list = document.getElementById('chat_list_' + clinicId);
        if (!list) return;

        let typingRow = list.querySelector('.typing-indicator-row');
        if (data.is_typing) {
          if (!typingRow) {
            typingRow = document.createElement('div');
            typingRow.className = 'msgr-msg-row recv typing-indicator-row';
            typingRow.innerHTML = `
              <div class="messenger-avatar avatar-sm flex-shrink-0" style="width:24px;height:24px;font-size:10px;background:#0084FF;">C</div>
              <div class="msgr-bubble text-muted fst-italic" style="padding:6px 12px;font-size:12px;">
                <span class="spinner-grow spinner-grow-sm me-1" role="status" style="width:8px;height:8px;"></span>Typing...
              </div>`;
            list.appendChild(typingRow);
            list.scrollTop = list.scrollHeight;
          }
        } else {
          if (typingRow) typingRow.remove();
        }
      } catch(e) {}
    });

    socket.on('unread_update', function(data) {
      try {
        const badge = document.getElementById('global_chat_unread_badge');
        if (badge) badge.classList.remove('d-none');
      } catch(e) {}
    });
  }

  function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe.replace(/[&<>"']/g, function(m) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#039;"})[m]; });
  }

  // ── Notification Center helpers ─────────────────────────
  async function markNotificationsRead(evt) {
    if (evt) evt.preventDefault();
    const CSRF_TOKEN = (document.getElementById('csrfToken') || {}).dataset.token || '';
    try {
      const res = await fetch('/api/notifications/mark-read', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({})
      });
      if (res.ok) {
        const badge = document.getElementById('notifBadge');
        if (badge) badge.remove();
      }
    } catch(e) { /* silently ignore — e.g. clinic portal users */ }
  }

  async function markSingleNotifRead(nid) {
    const CSRF_TOKEN = (document.getElementById('csrfToken') || {}).dataset.token || '';
    try {
      fetch('/api/notifications/mark-read', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({ id: nid })
      });
    } catch(e) { /* silently ignore */ }
  }

  window.markNotificationsRead = markNotificationsRead;
  window.markSingleNotifRead = markSingleNotifRead;
  window.loadHistory = loadHistory;

  // ── PaPrep Assistant Bot Handler ────────────────────────
  async function handleBotSubmit(evt) {
    if (evt) evt.preventDefault();
    const input = document.getElementById('bot_input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    appendBotUserMessage(text);
    input.value = '';

    await fetchBotResponse(text);
  }

  async function sendBotQuickQuery(queryText) {
    appendBotUserMessage(queryText);
    await fetchBotResponse(queryText);
  }

  function appendBotUserMessage(text) {
    const list = document.getElementById('bot_messages_list');
    if (!list) return;
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-msg user bg-primary text-white p-2 rounded-3 mb-2 small shadow-sm ms-auto';
    userDiv.style.maxWidth = '85%';
    userDiv.innerHTML = `<div>${escapeHtml(text)}</div>`;
    list.appendChild(userDiv);
    list.scrollTop = list.scrollHeight;
  }

  async function fetchBotResponse(text) {
    const list = document.getElementById('bot_messages_list');
    const CSRF_TOKEN = (document.getElementById('csrfToken') || {}).dataset.token || '';

    // Show typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.id = 'bot_typing';
    typingDiv.className = 'chat-msg assistant text-muted p-2 small mb-2';
    typingDiv.innerHTML = '<em>PaPrep Assistant is typing...</em>';
    list.appendChild(typingDiv);
    list.scrollTop = list.scrollHeight;

    try {
      const res = await fetch('/chat/bot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (document.getElementById('bot_typing')) {
        document.getElementById('bot_typing').remove();
      }

      if (res.ok && data.ok) {
        renderBotReply(data);
      } else {
        renderBotError();
      }
    } catch (e) {
      if (document.getElementById('bot_typing')) {
        document.getElementById('bot_typing').remove();
      }
      renderBotError();
    }
  }

  function renderBotReply(data) {
    const list = document.getElementById('bot_messages_list');
    if (!list) return;

    const botDiv = document.createElement('div');
    botDiv.className = 'chat-msg assistant bg-light text-dark p-2 rounded-3 mb-2 small shadow-sm';
    botDiv.style.maxWidth = '90%';

    let formattedText = escapeHtml(data.text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');

    let html = `<div>${formattedText}</div>`;

    if (data.shortcuts && data.shortcuts.length > 0) {
      html += `<div class="mt-2 pt-2 border-top d-flex flex-wrap gap-1">`;
      data.shortcuts.forEach(s => {
        html += `<a href="${s.url}" class="btn btn-sm btn-outline-primary py-0 px-2 rounded-pill" style="font-size:0.72rem;"><i class="${s.icon} me-1"></i>${escapeHtml(s.label)}</a>`;
      });
      html += `</div>`;
    }

    botDiv.innerHTML = html;
    list.appendChild(botDiv);
    list.scrollTop = list.scrollHeight;

    // Update quick actions if actions provided
    if (data.actions && data.actions.length > 0) {
      const actionsContainer = document.getElementById('bot_quick_actions');
      if (actionsContainer) {
        let actHtml = `<div class="d-flex flex-wrap gap-1">`;
        data.actions.forEach(act => {
          actHtml += `<button class="btn btn-outline-secondary btn-xs py-0 px-2 rounded-pill" style="font-size:0.75rem;" onclick="sendBotQuickQuery('${escapeHtml(act)}')">${escapeHtml(act)}</button>`;
        });
        actHtml += `</div>`;
        actionsContainer.innerHTML = actHtml;
      }
    }
  }

  function renderBotError() {
    const list = document.getElementById('bot_messages_list');
    if (!list) return;
    const errDiv = document.createElement('div');
    errDiv.className = 'chat-msg assistant bg-warning-subtle text-dark p-2 rounded-3 mb-2 small';
    errDiv.innerHTML = 'Sorry, I had trouble processing that. Please try asking again or select a shortcut above!';
    list.appendChild(errDiv);
    list.scrollTop = list.scrollHeight;
  }

  window.handleBotSubmit = handleBotSubmit;
  window.sendBotQuickQuery = sendBotQuickQuery;
});

