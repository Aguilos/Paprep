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
        <div class="messenger-avatar avatar-sm flex-shrink-0 bot-avatar">
          <img src="/static/image/chatbot_icon.png" alt="PaPrep Assistant" style="width:28px;height:28px;object-fit:contain;">
        </div>
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
              <div class="messenger-avatar avatar-sm flex-shrink-0 bot-avatar">
                <img src="/static/image/chatbot_icon.png" alt="PaPrep Assistant" style="width:28px;height:28px;object-fit:contain;">
              </div>
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

  // ============================================================
  // NURSE KITTY & GEMINI AI INTERACTIVE ENGINE
  // ============================================================

  function setKittyTalking(isTalking) {
    const heads = document.querySelectorAll('.kitty-chathead-wrap');
    heads.forEach(h => {
      if (isTalking) {
        h.classList.add('talking');
      } else {
        h.classList.remove('talking');
      }
    });
  }

  function triggerKittyMouthChatter(duration = 2200) {
    setKittyTalking(true);
    clearTimeout(window._kittyTalkTimeout);
    window._kittyTalkTimeout = setTimeout(() => {
      setKittyTalking(false);
    }, duration);
  }

  function pokeNurseKitty() {
    const heads = document.querySelectorAll('.kitty-chathead-wrap');
    heads.forEach(h => {
      h.classList.add('winking');
      setTimeout(() => h.classList.remove('winking'), 650);
    });
    triggerKittyMouthChatter(1500);
  }

  // Eye pupil tracking following mouse cursor
  document.addEventListener('mousemove', (e) => {
    const pupils = document.querySelectorAll('.kitty-pupil-eye');
    if (!pupils.length) return;
    const xOffset = ((e.clientX / window.innerWidth) - 0.5) * 3.5;
    const yOffset = ((e.clientY / window.innerHeight) - 0.5) * 2.5;
    pupils.forEach(p => {
      p.style.transform = `translate(${xOffset.toFixed(1)}px, ${yOffset.toFixed(1)}px)`;
    });
  });

  async function handleBotSubmit(e) {
    if (e) e.preventDefault();
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
    userDiv.className = 'dark-msg-row sent';
    userDiv.innerHTML = `<div class="dark-msg-bubble user-bubble">${escapeHtml(text)}</div>`;
    list.appendChild(userDiv);
    list.scrollTop = list.scrollHeight;
  }

  async function fetchBotResponse(text) {
    const list = document.getElementById('bot_messages_list');
    const CSRF_TOKEN = (document.getElementById('csrfToken') || {}).dataset.token || '';

    // Show typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.id = 'bot_typing';
    typingDiv.className = 'dark-msg-row recv';
    typingDiv.innerHTML = `
      <div class="dark-msg-bubble bot-bubble typing-bubble">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="ms-2" style="font-size:0.8rem;color:#93c5fd;">Nurse Kitty is thinking...</span>
      </div>`;
    list.appendChild(typingDiv);
    list.scrollTop = list.scrollHeight;

    // Mouth begins subtle movement during thinking
    setKittyTalking(true);

    try {
      const res = await fetch('/chat/bot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({ text })
      });
      const responseBody = await res.text();
      let data = {};
      try {
        data = responseBody ? JSON.parse(responseBody) : {};
      } catch (parseError) {
        console.error('[PaPrep Assistant] Invalid JSON response', {
          status: res.status,
          body: responseBody,
          error: parseError
        });
      }
      if (document.getElementById('bot_typing')) {
        document.getElementById('bot_typing').remove();
      }
      setKittyTalking(false);

      if (res.ok && data.ok) {
        if (data.degraded) {
          console.warn('[PaPrep Assistant] Backend returned fallback response', data);
        }
        renderBotReply(data);
      } else {
        console.error('[PaPrep Assistant] Request failed', {
          url: '/chat/bot',
          status: res.status,
          statusText: res.statusText,
          body: data || responseBody
        });
        renderBotError();
      }
    } catch (e) {
      console.error('[PaPrep Assistant] Network or fetch error', {
        url: '/chat/bot',
        error: e
      });
      if (document.getElementById('bot_typing')) {
        document.getElementById('bot_typing').remove();
      }
      setKittyTalking(false);
      renderBotError();
    }
  }

  function renderBotReply(data) {
    const list = document.getElementById('bot_messages_list');
    if (!list) return;

    if (data.auto_redirect && data.shortcuts && data.shortcuts.length === 1) {
      window.location.href = data.shortcuts[0].url;
      return;
    }

    const botDiv = document.createElement('div');
    botDiv.className = 'dark-msg-row recv';

    let formattedText = escapeHtml(data.text)
      .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#93c5fd;">$1</strong>')
      .replace(/\n/g, '<br>');

    let html = `<div class="dark-msg-bubble bot-bubble"><div>${formattedText}</div>`;

    if (data.shortcuts && data.shortcuts.length > 0) {
      html += `<div class="mt-2 pt-2 border-top d-flex flex-wrap gap-1" style="border-color:#1c355a!important;">`;
      data.shortcuts.forEach(s => {
        html += `<a href="${s.url}" class="dark-chip-btn text-decoration-none"><i class="${s.icon} me-1"></i>${escapeHtml(s.label)}</a>`;
      });
      html += `</div>`;
    }

    html += `</div>`;
    botDiv.innerHTML = html;
    list.appendChild(botDiv);
    list.scrollTop = list.scrollHeight;

    // Visual Nurse Kitty mouth movement on reply
    triggerKittyMouthChatter(2400);

    // Update quick actions if actions provided
    if (data.actions && data.actions.length > 0) {
      const actionsContainer = document.getElementById('bot_quick_actions');
      if (actionsContainer) {
        let actHtml = `<div class="d-flex flex-wrap gap-1 bot-chip-row">`;
        data.actions.forEach(act => {
          actHtml += `<button type="button" class="dark-chip-btn" onclick="sendBotQuickQuery('${escapeHtml(act)}')">${escapeHtml(act)}</button>`;
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
    errDiv.className = 'dark-msg-row recv';
    errDiv.innerHTML = '<div class="dark-msg-bubble bot-bubble" style="border-color:#b91c1c;color:#fca5a5;">Sorry, I had trouble processing that with Gemini AI. Please try asking again or select a shortcut below!</div>';
    list.appendChild(errDiv);
    list.scrollTop = list.scrollHeight;
    triggerKittyMouthChatter(1200);
  }

  window.handleBotSubmit = handleBotSubmit;
  window.sendBotQuickQuery = sendBotQuickQuery;
  window.setKittyTalking = setKittyTalking;
  window.triggerKittyMouthChatter = triggerKittyMouthChatter;
  window.pokeNurseKitty = pokeNurseKitty;
});
