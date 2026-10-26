/* ══════════════════════════════════════════════════════
   Aura Skincare — aria.js  v3
   ChatGPT-style Aria page  ·  voice + typed  ·  full chat
   ══════════════════════════════════════════════════════ */
(() => {
  'use strict';

  const API = (window.AURA_API_BASE || '').replace(/\/$/, '');

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const sidebar         = document.getElementById('ariaSidebar');
  const sidebarOverlay  = document.getElementById('sidebarOverlay');
  const collapseSidebar = document.getElementById('collapseSidebar');
  const expandSidebar   = document.getElementById('expandSidebar');
  const newChatBtn      = document.getElementById('newChatBtn');
  const clearChatBtn    = document.getElementById('clearChatBtn');
  const messagesInner   = document.getElementById('messagesInner');
  const welcomeScreen   = document.getElementById('welcomeScreen');
  const composerInput   = document.getElementById('composerInput');
  const sendBtn         = document.getElementById('sendBtn');
  const plusBtn         = document.getElementById('plusBtn');
  const plusMenuPopup   = document.getElementById('plusMenuPopup');
  const micBtn          = document.getElementById('micBtn');
  const voiceBar        = document.getElementById('voiceBar');
  const voiceBarText    = document.getElementById('voiceBarText');
  const stopVoiceBtn    = document.getElementById('stopVoiceBtn');
  const stopSpeechBtn   = document.getElementById('stopSpeechBtn');
  const ariaMessages    = document.getElementById('ariaMessages');
  const ariaStatusBadge = document.getElementById('ariaStatusBadge');
  const robotWrap       = document.getElementById('robotWrap');
  const robotBadge      = document.getElementById('robotBadge');
  const ariaRobot       = document.getElementById('ariaRobot');

  // ── State ─────────────────────────────────────────────────────────────────
  let messages      = [];
  let isProcessing  = false;
  let isSpeaking    = false;
  let recognition   = null;
  let isListening   = false;
  let lastIntent    = 'GENERAL_QUERY';
  let lastOrderId   = null;
  let lastResolution= 'UNRESOLVED';
  let lastActions   = [];

  // ── Robot mascot state ────────────────────────────────────────────────────
  const BADGE_ICONS = { idle: '✦', thinking: '⏳', listening: '🎙️', speaking: '🔊', error: '⚠️' };

  function setRobotState(state) {
    if (!robotWrap || !robotBadge) return;
    robotWrap.className = `robot-mascot-wrap ${state}`;
    robotBadge.textContent = BADGE_ICONS[state] || '✦';
  }

  ariaRobot?.addEventListener('click', () => {
    composerInput?.focus();
    if (welcomeScreen?.style.display !== 'none') {
      composerInput.placeholder = 'Type your question for Aria…';
    }
  });

  // ── Sidebar ───────────────────────────────────────────────────────────────
  function isMobile() { return window.innerWidth < 769; }

  function openSidebar() {
    sidebar.classList.add('open');
    sidebarOverlay.hidden = false;
  }
  function closeSidebar() {
    sidebar.classList.remove('open');
    sidebarOverlay.hidden = true;
  }
  function toggleSidebar() {
    if (isMobile()) {
      sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
    } else {
      sidebar.classList.toggle('collapsed');
    }
  }

  collapseSidebar?.addEventListener('click', toggleSidebar);
  expandSidebar?.addEventListener('click', toggleSidebar);
  sidebarOverlay?.addEventListener('click', closeSidebar);

  document.querySelectorAll('.sidebar-link[data-question]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (isMobile()) closeSidebar();
      sendMessage(btn.dataset.question);
    });
  });

  // ── Status badge ──────────────────────────────────────────────────────────
  function setStatus(text, active = false) {
    if (!ariaStatusBadge) return;
    ariaStatusBadge.textContent = text;
    ariaStatusBadge.classList.toggle('active', active);
  }

  // ── Welcome screen ────────────────────────────────────────────────────────
  function hideWelcome() {
    if (welcomeScreen) welcomeScreen.style.display = 'none';
  }
  function showWelcome() {
    if (welcomeScreen) welcomeScreen.style.display = '';
    messages = [];
    lastIntent = 'GENERAL_QUERY'; lastOrderId = null;
    lastResolution = 'UNRESOLVED'; lastActions = [];
    setRobotState('idle');
  }

  // Suggestion cards
  document.querySelectorAll('.suggestion-card[data-question]').forEach(btn => {
    btn.addEventListener('click', () => sendMessage(btn.dataset.question));
  });

  // Evaluator buttons
  document.querySelectorAll('.eval-btn[data-order]').forEach(btn => {
    btn.addEventListener('click', () => sendMessage(`Where is my order ${btn.dataset.order}?`));
  });

  // ── Markdown-lite renderer ────────────────────────────────────────────────
  function renderMarkdown(text) {
    return String(text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      // bold **text**
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // italic *text* or _text_  (not at start of bullet)
      .replace(/(?<!\n)\*(?!\*|[ \n])(.+?)\*(?!\*)/g, '<em>$1</em>')
      // bullet lines "• text" or "* text" or "- text"
      .replace(/^[•\-\*] (.+)$/gm, '<li>$1</li>')
      // numbered lines "1. text"
      .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
      // newlines
      .replace(/\n/g, '<br>');
  }

  // ── Message rendering ─────────────────────────────────────────────────────
  function addMessageNode(role, text) {
    const isAria = role === 'aria';
    const row = document.createElement('div');
    row.className = `msg-row ${isAria ? 'aria' : 'user'}`;
    const bubbleContent = isAria ? renderMarkdown(text) : escapeHtml(text);
    row.innerHTML = `
      <div class="msg-avatar ${isAria ? 'aria-av' : 'user-av'}" aria-hidden="true">${isAria ? 'A' : 'You'}</div>
      <div class="msg-bubble">${bubbleContent}</div>
    `;
    messagesInner.appendChild(row);
    scrollToBottom();
    return row;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  }

  function addTypingIndicator() {
    const row = document.createElement('div');
    row.className = 'msg-row aria';
    row.id = 'typingRow';
    row.innerHTML = `
      <div class="msg-avatar aria-av" aria-hidden="true">A</div>
      <div class="typing-indicator" role="status" aria-label="Aria is thinking">
        <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
      </div>
    `;
    messagesInner.appendChild(row);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    document.getElementById('typingRow')?.remove();
  }

  function scrollToBottom() {
    ariaMessages.scrollTop = ariaMessages.scrollHeight;
  }

  // ── Core send message ─────────────────────────────────────────────────────
  async function sendMessage(text) {
    const clean = text.trim();
    if (!clean || isProcessing) return;

    hideWelcome();
    isProcessing = true;
    sendBtn.disabled = true;
    setStatus('Thinking…');
    setRobotState('thinking');

    messages.push({ role: 'user', text: clean, ts: new Date().toISOString() });
    addMessageNode('user', clean);
    composerInput.value = '';
    autoResize();
    addTypingIndicator();

    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: clean }),
      });

      let data;
      try { data = await res.json(); }
      catch { throw new Error('The server returned an unreadable response.'); }

      removeTypingIndicator();

      if (!res.ok) {
        throw new Error(data?.detail || `Server error ${res.status}`);
      }

      const reply = data.reply || 'I could not prepare a response. Please try again.';
      lastIntent     = data.customer_intent || 'GENERAL_QUERY';
      lastOrderId    = data.order_id || null;
      lastResolution = data.resolution_status || 'UNRESOLVED';
      lastActions    = Array.isArray(data.actions_taken) ? data.actions_taken : [];

      messages.push({ role: 'aria', text: reply, ts: new Date().toISOString() });
      addMessageNode('aria', reply);
      setStatus('Ready');
      setRobotState('idle');
      speakText(reply);

    } catch (err) {
      removeTypingIndicator();
      const errMsg =
        `I'm unable to reach the Aura support service right now. ` +
        `Please make sure the backend is running at ${API || 'http://127.0.0.1:8000'}. ` +
        `(${err.message})`;
      messages.push({ role: 'aria', text: errMsg, ts: new Date().toISOString() });
      addMessageNode('aria', errMsg);
      setStatus('Error');
      setRobotState('error');
      setTimeout(() => setRobotState('idle'), 4000);
    } finally {
      isProcessing = false;
      sendBtn.disabled = composerInput.value.trim().length === 0;
    }
  }

  // ── Composer ──────────────────────────────────────────────────────────────
  function autoResize() {
    composerInput.style.height = 'auto';
    composerInput.style.height = Math.min(composerInput.scrollHeight, 160) + 'px';
    sendBtn.disabled = composerInput.value.trim().length === 0;
  }

  composerInput?.addEventListener('input', autoResize);
  composerInput?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) sendMessage(composerInput.value);
    }
  });
  sendBtn?.addEventListener('click', () => sendMessage(composerInput.value));

  // ── Plus quick-action menu ────────────────────────────────────────────────
  plusBtn?.addEventListener('click', e => {
    e.stopPropagation();
    const open = plusMenuPopup.classList.toggle('open');
    plusBtn.setAttribute('aria-expanded', String(open));
  });

  document.querySelectorAll('.pm-item[data-question]').forEach(btn => {
    btn.addEventListener('click', () => {
      plusMenuPopup.classList.remove('open');
      plusBtn.setAttribute('aria-expanded', 'false');
      sendMessage(btn.dataset.question);
    });
  });

  document.addEventListener('click', () => {
    if (plusMenuPopup?.classList.contains('open')) {
      plusMenuPopup.classList.remove('open');
      plusBtn.setAttribute('aria-expanded', 'false');
    }
  });

  // ── New Chat / Clear ──────────────────────────────────────────────────────
  function newChat() {
    [...messagesInner.children].forEach(c => { if (c.id !== 'welcomeScreen') c.remove(); });
    showWelcome();
    setStatus('Ready');
    composerInput.value = '';
    autoResize();
    stopSpeech();
    stopVoice();
  }

  newChatBtn?.addEventListener('click', newChat);
  clearChatBtn?.addEventListener('click', newChat);

  // ── Text-to-speech ────────────────────────────────────────────────────────
  function plainText(html) {
    // Strip HTML tags and convert <br> to spaces for TTS
    return html.replace(/<br\s*\/?>/gi, ' ').replace(/<[^>]+>/g, '');
  }

  function speakText(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    // Speak the plain text version (strip markdown-rendered HTML)
    const utterText = plainText(renderMarkdown(text)).slice(0, 800); // cap length
    const utt = new SpeechSynthesisUtterance(utterText);
    utt.lang = 'en-IN'; utt.rate = 0.95; utt.pitch = 1.05;
    utt.onstart = () => {
      isSpeaking = true;
      if (stopSpeechBtn) stopSpeechBtn.hidden = false;
      setStatus('Speaking…', true);
      setRobotState('speaking');
    };
    utt.onend = utt.onerror = () => {
      isSpeaking = false;
      if (stopSpeechBtn) stopSpeechBtn.hidden = true;
      setStatus('Ready');
      setRobotState('idle');
    };
    window.speechSynthesis.speak(utt);
  }

  function stopSpeech() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    isSpeaking = false;
    if (stopSpeechBtn) stopSpeechBtn.hidden = true;
    setStatus('Ready');
    setRobotState('idle');
  }

  stopSpeechBtn?.addEventListener('click', stopSpeech);

  // ── Voice input ───────────────────────────────────────────────────────────
  function createRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    const r = new SR();
    r.lang = 'en-IN'; r.continuous = false; r.interimResults = true; r.maxAlternatives = 1;
    let finalText = '';

    r.onresult = ev => {
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += ' ' + t;
        else interim += t;
      }
      const candidate = finalText.trim();
      if (candidate) {
        composerInput.value = candidate;
        autoResize();
        voiceBarText.textContent = `Heard: "${candidate.slice(0, 60)}"`;
      } else if (interim) {
        voiceBarText.textContent = `Hearing: "${interim.slice(0, 60)}"`;
      }
    };

    r.onerror = ev => {
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
        stopVoice();
        addMessageNode('aria', 'Microphone permission was denied. Please allow access in your browser settings and try again.');
      } else if (ev.error !== 'no-speech' && ev.error !== 'aborted') {
        voiceBarText.textContent = `Error: ${ev.error}. You can type instead.`;
        stopVoice();
      }
    };

    r.onend = () => {
      const txt = composerInput.value.trim();
      stopVoice();
      if (txt) {
        // Same sendMessage used by typed input — unified pipeline
        sendMessage(txt);
        composerInput.value = '';
        autoResize();
      } else {
        voiceBarText.textContent = 'No speech detected. Try again or type your message.';
      }
    };

    return r;
  }

  async function startVoice() {
    if (isListening) { stopVoice(); return; }
    if (!window.SpeechRecognition && !window.webkitSpeechRecognition) {
      addMessageNode('aria', 'Speech recognition is not supported in this browser. Try Chrome or Edge on desktop, or type your question instead.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(t => t.stop());
    } catch {
      addMessageNode('aria', 'Microphone access is blocked. Please allow microphone permission in your browser and try again.');
      return;
    }

    recognition = createRecognition();
    if (!recognition) return;

    try {
      recognition.start();
      isListening = true;
      micBtn.classList.add('listening');
      micBtn.setAttribute('aria-label', 'Stop voice input');
      voiceBar.classList.add('show');
      voiceBarText.textContent = 'Listening… speak your question clearly.';
      setStatus('Listening…', true);
      setRobotState('listening');
      stopSpeech();
    } catch (e) {
      if (e.name !== 'InvalidStateError') {
        addMessageNode('aria', 'Could not start speech recognition. Please try again.');
      }
    }
  }

  function stopVoice() {
    isListening = false;
    try { recognition?.stop(); } catch {}
    recognition = null;
    micBtn.classList.remove('listening');
    micBtn.setAttribute('aria-label', 'Start voice input');
    voiceBar.classList.remove('show');
    setStatus('Ready');
    setRobotState('idle');
  }

  micBtn?.addEventListener('click', startVoice);
  stopVoiceBtn?.addEventListener('click', stopVoice);

  // ── Keyboard shortcut ─────────────────────────────────────────────────────
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      stopSpeech();
      stopVoice();
      if (isMobile() && sidebar.classList.contains('open')) closeSidebar();
    }
  });

  // ── Init ──────────────────────────────────────────────────────────────────
  setStatus('Ready');
  setRobotState('idle');
  composerInput?.focus();
})();
