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

  async function loadHistory(clinicId) {
    const res = await fetch(`/chat/history/${clinicId}`);
    if (!res.ok) return;
    const msgs = await res.json();
    const list = document.getElementById('chat_list_' + clinicId);
    if (!list) return;
    list.innerHTML = '';
    msgs.forEach(m => {
      const el = document.createElement('div');
      el.className = m.sender === 'clinic' ? 'chat-msg clinic' : 'chat-msg user';
      el.innerHTML = `<div class="small text-muted">${m.sender}</div><div>${escapeHtml(m.text)}</div><div class="small text-muted">${new Date(m.created_at).toLocaleString()}</div>`;
      list.appendChild(el);
    });
    list.scrollTop = list.scrollHeight;
    // join socket room for live updates
    if (socket && currentUserId) {
      try {
        socket.emit('join', {clinic_id: parseInt(clinicId), user_id: parseInt(currentUserId)});
      } catch(e) { console.warn('socket join failed', e); }
    }
  }

  async function sendMessage(evt, clinicId) {
    evt.preventDefault();
    const input = document.getElementById('chat_input_' + clinicId);
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
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
      // optimistic refresh: append locally; server will emit to clinic room
      loadHistory(clinicId);
    } else {
      alert('Failed to send message');
    }
  }

  window.sendMessage = sendMessage;

  // Handle incoming socket messages
  if (socket) {
    socket.on('chat_message', function(data) {
      try {
        const payload = data && data.message ? data.message : null;
        if (!payload) return;
        const clinicId = payload.clinic_id || payload.clinicId || (data && data.clinic_id);
        const userId = payload.user_id || payload.userId || (data && data.user_id);
        // If this message is for the currently open panel for this user, append it
        const list = document.getElementById('chat_list_' + clinicId);
        if (!list) return;
        const el = document.createElement('div');
        el.className = payload.sender === 'clinic' ? 'chat-msg clinic' : 'chat-msg user';
        el.innerHTML = `<div class="small text-muted">${payload.sender}</div><div>${escapeHtml(payload.text)}</div><div class="small text-muted">${new Date(payload.created_at).toLocaleString()}</div>`;
        list.appendChild(el);
        list.scrollTop = list.scrollHeight;
      } catch(e) {
        console.warn('chat_message handler error', e);
      }
    });
  }

  function escapeHtml(unsafe) {
    return unsafe.replace(/[&<>"']/g, function(m) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#039;"})[m]; });
  }
});
