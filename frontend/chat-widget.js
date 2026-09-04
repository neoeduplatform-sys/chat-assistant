/**
 * Widget de Chat para el Chatbot Educativo
 * =========================================
 *
 * Un widget de chat ligero, completamente personalizable con soporte para Markdown.
 * Soporta múltiples cursos mediante configuración dinámica.
 *
 * Uso:
 * 1. Configura las variables requeridas ANTES de incluir el script:
 *    <script>
 *      // Requerido: ID del curso
 *      window.CHATBOT_COURSE_ID = 'course_123';
 *
 *      // Requerido: JWT firmado por el servidor (Moodle/LTI). Se envía en
 *      // la cabecera Authorization: Bearer <token> y el backend extrae de
 *      // forma segura user_id y course_id desde el token.
 *      window.CHATBOT_TOKEN = '<JWT>';
 *
 *      // Opcional: ID del usuario para tracking local (el backend ignora
 *      // este valor y usa el sub del token).
 *      window.CHATBOT_USER_ID = 'user_456';
 *
 *      // Opcional: Personalización
 *      window.CHATBOT_API_URL = 'http://localhost:8080/api/chat';
 *      // Opcional: GET historial (por defecto se deduce de CHATBOT_API_URL → .../api/chat/history)
 *      window.CHATBOT_HISTORY_URL = 'http://localhost:8080/api/chat/history';
 *      window.CHATBOT_TITLE = 'Asistente del Curso';
 *      window.CHATBOT_SUBTITLE = 'Pregúntame sobre el curso';
 *
 *      // Opcional: altura máxima (px) del área de escritura antes de scroll vertical (mín. 80)
 *      window.CHATBOT_INPUT_MAX_HEIGHT = 200;
 *
 *      // Opcional: módulo ESM de marked (por defecto: {origen API}/static/marked.esm.js)
 *      window.CHATBOT_MARKED_ESM_URL = 'https://tu-servidor/static/marked.esm.js';
 *    </script>
 *
 * 2. Incluye el widget:
 *    <script src="chat-widget.js"></script>
 *
 * Nota: CHATBOT_COURSE_ID y CHATBOT_TOKEN son obligatorios. El widget
 * mostrará un error si alguno no está configurado.
 */

(function() {
  'use strict';

  // Minimal runtime marker to confirm the script executed on the page.
  // (Useful in environments where the script loads but is blocked/crashes early.)
  try {
    window.__CHATBOT_WIDGET_JS_LOADED__ = (window.__CHATBOT_WIDGET_JS_LOADED__ || 0) + 1;
    console.debug('[chat-widget] loaded', { count: window.__CHATBOT_WIDGET_JS_LOADED__ });
  } catch (_) {
    // ignore
  }

  // ========================================================================
  // CARGAR MARKED.JS PARA MARKDOWN
  // ========================================================================

  let markedLoaded = false;
  let markedLoadPromise = null;

  function isLocalhostLikeUrl(urlStr) {
    if (!urlStr) {
      return false;
    }
    try {
      var u = new URL(urlStr, window.location.href);
      return /^(localhost|127\.0\.0\.1)$/i.test(u.hostname);
    } catch (_) {
      return false;
    }
  }

  /**
   * Último script con chat-widget.js en el src (origin + URL completa).
   * Requerimos /static/ en la ruta para inferir API: evita confundir el host de Moodle
   * si el widget se sirve desde pluginfile u otra ruta en el LMS.
   */
  function getChatWidgetScriptInfo() {
    try {
      var nodes = document.scripts || document.getElementsByTagName('script');
      for (var i = nodes.length - 1; i >= 0; i--) {
        var src = nodes[i].src;
        if (src && /(^|\/)chat-widget\.js(\?|#|$)/i.test(src)) {
          var u = new URL(src);
          return { origin: u.origin, src: src };
        }
      }
    } catch (_) {
      /* ignore */
    }
    return null;
  }

  function normalizeApiChatUrl(u) {
    var s = String(u).trim().replace(/\/?$/, '');
    if (/\/api\/chat$/i.test(s)) {
      return s;
    }
    return s + '/api/chat';
  }

  /**
   * URL efectiva POST …/api/chat:
   * - Si CHATBOT_API_URL ya apunta a un host público → se usa tal cual.
   * - Si sigue en localhost pero el widget se sirve desde otro host (p. ej. assistant.neoedu.mx/static/) → mismo origen + /api/chat (corrige Moodle mal configurado).
   * - Si no, CHATBOT_API_URL explícita o fallback dev.
   */
  function getResolvedApiChatUrl() {
    var explicit = window.CHATBOT_API_URL;
    var scriptInfo = getChatWidgetScriptInfo();
    var scriptOrigin = scriptInfo && scriptInfo.origin;
    var scriptSrc = scriptInfo && scriptInfo.src;

    if (explicit && String(explicit).trim() && !isLocalhostLikeUrl(explicit)) {
      return normalizeApiChatUrl(explicit);
    }

    if (
      scriptOrigin &&
      scriptSrc &&
      !isLocalhostLikeUrl(scriptOrigin) &&
      /(^|\/)chat-widget\.js(\?|#|$)/i.test(scriptSrc)
    ) {
      try {
        var sameAsPage = scriptOrigin === window.location.origin;
        if (!sameAsPage || /\/static\//i.test(scriptSrc)) {
          return scriptOrigin.replace(/\/?$/, '') + '/api/chat';
        }
      } catch (_) {
        /* ignore */
      }
    }

    var widgetOrigin = window.CHATBOT_WIDGET_ORIGIN;
    if (
      explicit &&
      String(explicit).trim() &&
      isLocalhostLikeUrl(explicit) &&
      widgetOrigin &&
      String(widgetOrigin).trim() &&
      !isLocalhostLikeUrl(widgetOrigin)
    ) {
      return String(widgetOrigin).replace(/\/?$/, '') + '/api/chat';
    }

    if (explicit && String(explicit).trim()) {
      return normalizeApiChatUrl(explicit);
    }

    return 'http://localhost:8080/api/chat';
  }

  /** Origin del API sin /api/chat (para /static/marked.esm.js). */
  function deriveApiStaticBase() {
    var chatUrl = getResolvedApiChatUrl();
    var base = chatUrl.replace(/\/?api\/chat\/?$/i, '');
    return base.replace(/\/?$/, '');
  }

  /**
   * Carga marked vía import() dinámico del bundle ESM (marked.esm.js).
   * No usa el iframe sandbox (evita advertencia allow-scripts + allow-same-origin)
   * ni toca window.define: no hay conflicto con RequireJS de Moodle.
   *
   * Entre sitios distintos el servidor del API debe enviar CORS para el .js ESM.
   */
  function loadMarked() {
    if (markedLoadPromise) {
      return markedLoadPromise;
    }

    markedLoadPromise = new Promise(function (resolve, reject) {
      if (window.marked) {
        markedLoaded = true;
        configureMarked();
        resolve();
        return;
      }

      var esmUrl =
        window.CHATBOT_MARKED_ESM_URL ||
        window.CHATBOT_MARKED_URL ||
        deriveApiStaticBase() + '/static/marked.esm.js';

      function finishFail(err) {
        console.warn('No se pudo cargar marked (ESM), usando texto plano', err || '');
        reject(err || new Error('marked unavailable'));
      }

      try {
        import(esmUrl)
          .then(function (mod) {
            window.marked = mod.marked;
            markedLoaded = true;
            configureMarked();
            resolve();
          })
          .catch(function (err) {
            finishFail(err);
          });
      } catch (err) {
        finishFail(err);
      }
    });

    return markedLoadPromise;
  }

  function configureMarked() {
    const md = window.marked;
    if (!md) {
      return;
    }
    md.setOptions({
      breaks: true,        // Convertir \n en <br>
      gfm: true,          // GitHub Flavored Markdown
      headerIds: false,   // No generar IDs en headers
      mangle: false,      // No ofuscar emails
    });

    const renderer = new md.Renderer();

    const originalLink = renderer.link.bind(renderer);
    renderer.link = (href, title, text) => {
      if (!href) {
        return text;
      }
      if (href.startsWith('javascript:') || href.startsWith('data:')) {
        return text;
      }
      return originalLink(href, title, text);
    };

    md.use({ renderer });
  }

  function parseMarkdown(text) {
    const md = window.marked;
    if (markedLoaded && md) {
      try {
        return md.parse(text);
      } catch (error) {
        console.error('Error al parsear markdown:', error);
        return escapeHtml(text);
      }
    }
    // Fallback a texto plano con HTML escapado
    return escapeHtml(text).replace(/\n/g, '<br>');
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ========================================================================
  // CONFIGURACIÓN
  // ========================================================================

  const _explicitApiRaw = window.CHATBOT_API_URL;
  const _apiBase = getResolvedApiChatUrl();
  const CONFIG = {
    apiUrl: _apiBase,
    historyUrl:
      window.CHATBOT_HISTORY_URL ||
      _apiBase.replace(/\/?api\/chat\/?$/i, '') + '/api/chat/history',
    courseId: window.CHATBOT_COURSE_ID || null,  // Required: Course identifier
    userId: window.CHATBOT_USER_ID || null,       // Optional: User identifier
    token: window.CHATBOT_TOKEN || null,          // Required: JWT firmado por el servidor
    title: window.CHATBOT_TITLE || 'Asistente del Curso',
    subtitle: window.CHATBOT_SUBTITLE || 'Pregúntame sobre el curso',
    placeholder: window.CHATBOT_PLACEHOLDER || 'Escribe tu pregunta...',
    position: window.CHATBOT_POSITION || 'bottom-right', // bottom-right, bottom-left
    primaryColor: window.CHATBOT_PRIMARY_COLOR || '#9c2135',
    accentColor: window.CHATBOT_ACCENT_COLOR || '#B4283F',
    /** Altura máxima del área de escritura (px); luego aparece scroll vertical. */
    inputMaxHeightPx: (function () {
      const n = Number(window.CHATBOT_INPUT_MAX_HEIGHT);
      return Number.isFinite(n) && n >= 80 ? n : 160;
    })(),
  };

  try {
    if (
      _explicitApiRaw &&
      isLocalhostLikeUrl(_explicitApiRaw) &&
      !isLocalhostLikeUrl(_apiBase)
    ) {
      console.info(
        '[chat-widget] CHATBOT_API_URL era localhost; usando el mismo host que chat-widget.js →',
        _apiBase
      );
    } else if (
      isLocalhostLikeUrl(_apiBase) &&
      window.location &&
      window.location.hostname &&
      !isLocalhostLikeUrl(window.location.origin)
    ) {
      console.warn(
        '[chat-widget] La URL del API sigue siendo localhost y la página no; no se pudo inferir otro host ' +
          '(¿chat-widget.js sin src absoluto?). Configura en Moodle la URL pública del API.'
      );
    }
  } catch (_) {
    /* ignore */
  }

  /** Prefer live window.* so Moodle/embedders can set globals after this file parses (load-order safety). */
  function resolveCourseId() {
    return window.CHATBOT_COURSE_ID || CONFIG.courseId || null;
  }

  function resolveToken() {
    return window.CHATBOT_TOKEN || CONFIG.token || null;
  }

  // Validate required configuration
  if (!resolveCourseId()) {
    console.error('❌ CHATBOT ERROR: CHATBOT_COURSE_ID is required but not configured.');
    console.error('Please set window.CHATBOT_COURSE_ID before loading the widget.');
    console.error('Example: window.CHATBOT_COURSE_ID = "course_123";');
  }

  if (!resolveToken()) {
    console.error('❌ CHATBOT ERROR: CHATBOT_TOKEN is required but not configured.');
    console.error('Please set window.CHATBOT_TOKEN (JWT firmado por el servidor) before loading the widget.');
  }

  function authHeaders(extra) {
    const headers = Object.assign({}, extra || {});
    const t = resolveToken();
    if (t) {
      headers['Authorization'] = 'Bearer ' + t;
    }
    return headers;
  }

  loadMarked().catch(function () {
    /* Markdown opcional */
  });

  // ========================================================================
  // ESTILOS
  // ========================================================================

  const styles = `
    .chatbot-widget-container {
      position: fixed;
      ${CONFIG.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
      bottom: 20px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      z-index: 9999;
    }

    .chatbot-column-container {
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    }

    /* Estilos para la columna del chat cuando se integra en otro sitio */
    #chat-column,
    .chat-column {
      width: 0;
      overflow: hidden;
      transition: width 0.3s ease;
      display: flex;
      flex-direction: column;
      height: 100%;
      align-self: stretch;
      min-height: 0;
    }

    #chat-column.open,
    .chat-column.open {
      width: ${CONFIG.columnWidth};
      border-left: 1px solid #E5E7EB;
    }

    /* Asegurar que el contenedor padre tenga altura definida */
    .content-card.with-chat,
    [data-chat-container] {
      position: relative;
      display: flex;
      gap: 20px;
      min-height: 600px;
      align-items: stretch;
      height: 100%;
    }

    .content-card-main,
    [data-chat-main] {
      flex: 1;
      transition: width 0.3s ease;
      min-width: 0;
    }

    /* Botón flotante para abrir el chat */
    #chat-toggle-floating,
    .chat-toggle-floating {
      position: fixed;
      right: 20px;
      bottom: 20px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, ${CONFIG.primaryColor} 0%, ${CONFIG.accentColor} 100%);
      border: none;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
      z-index: 9999;
    }

    #chat-toggle-floating:hover,
    .chat-toggle-floating:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
    }

    #chat-toggle-floating svg,
    .chat-toggle-floating svg {
      width: 28px;
      height: 28px;
      fill: white;
    }

    .chatbot-toggle-button {
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, ${CONFIG.primaryColor} 0%, ${CONFIG.accentColor} 100%);
      border: none;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 1;
      transition: opacity 0.25s ease, transform 0.3s ease, box-shadow 0.3s ease;
    }

    .chatbot-widget-container:has(.chatbot-window.open) .chatbot-toggle-button {
      opacity: 0.5;
    }

    .chatbot-widget-container:has(.chatbot-window.open) .chatbot-toggle-button:hover {
      opacity: 0.72;
    }

    .chatbot-toggle-button:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
    }

    .chatbot-toggle-button svg {
      width: 28px;
      height: 28px;
      fill: white;
    }

    .chatbot-window {
      position: absolute;
      bottom: 80px;
      ${CONFIG.position.includes('right') ? 'right: 0;' : 'left: 0;'}
      width: 380px;
      height: 550px;
      background: white;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
      display: none;
      flex-direction: column;
      overflow: hidden;
      animation: slideUp 0.3s ease;
    }

    .chatbot-window.column-mode {
      position: relative;
      bottom: auto;
      right: auto;
      left: auto;
      width: 100%;
      height: 100%;
      min-height: 0;
      border-radius: 0;
      box-shadow: none;
      display: flex;
      flex-direction: column;
      animation: none;
      overflow: hidden;
      flex: 1;
    }

    .chatbot-window.column-mode .chatbot-messages {
      flex: 1;
      overflow-y: auto;
    }

    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .chatbot-window.open {
      display: flex;
    }

    .chatbot-header {
      background: linear-gradient(135deg, ${CONFIG.primaryColor} 0%, ${CONFIG.accentColor} 100%);
      color: white;
      padding: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .chatbot-header-content {
      flex: 1;
    }

    .chatbot-header h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }

    .chatbot-header p {
      margin: 4px 0 0 0;
      font-size: 13px;
      opacity: 0.9;
    }

    .chatbot-close-button {
      background: rgba(255, 255, 255, 0.2);
      border: none;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s;
    }

    .chatbot-close-button:hover {
      background: rgba(255, 255, 255, 0.3);
    }

    .chatbot-close-button svg {
      width: 20px;
      height: 20px;
      fill: white;
    }

    .chatbot-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      background: #F9FAFB;
    }

    .chatbot-message {
      margin-bottom: 16px;
      display: flex;
      animation: fadeIn 0.3s ease;
    }

    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .chatbot-message.user {
      justify-content: flex-end;
    }

    .chatbot-message-bubble {
      max-width: 80%;
      padding: 12px 16px;
      border-radius: 16px;
      line-height: 1.5;
      font-size: 14px;
    }

    .chatbot-message.bot .chatbot-message-bubble {
      background: white;
      color: #1F2937;
      border: 1px solid #E5E7EB;
      border-bottom-left-radius: 4px;
    }

    .chatbot-message.user .chatbot-message-bubble {
      background: ${CONFIG.primaryColor};
      color: white;
      border-bottom-right-radius: 4px;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .chatbot-typing {
      display: flex;
      gap: 4px;
      padding: 12px 16px;
      background: white;
      border-radius: 16px;
      border-bottom-left-radius: 4px;
      width: fit-content;
      border: 1px solid #E5E7EB;
    }

    .chatbot-typing span {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #9CA3AF;
      animation: bounce 1.4s infinite;
    }

    .chatbot-typing span:nth-child(2) {
      animation-delay: 0.2s;
    }

    .chatbot-typing span:nth-child(3) {
      animation-delay: 0.4s;
    }

    @keyframes bounce {
      0%, 60%, 100% {
        transform: translateY(0);
      }
      30% {
        transform: translateY(-10px);
      }
    }

    .chatbot-input-container {
      padding: 16px;
      background: white;
      border-top: 1px solid #E5E7EB;
      display: flex;
      align-items: flex-end;
      gap: 8px;
    }

    .chatbot-input {
      flex: 1;
      min-height: 44px;
      max-height: ${CONFIG.inputMaxHeightPx}px;
      border: 1px solid #E5E7EB;
      border-radius: 16px;
      padding: 11px 16px;
      font-size: 14px;
      font-family: inherit;
      line-height: 1.45;
      outline: none;
      resize: none;
      overflow-x: hidden;
      overflow-y: hidden;
      transition: border-color 0.2s;
      box-sizing: border-box;
    }

    .chatbot-input:focus {
      border-color: ${CONFIG.primaryColor};
    }

    .chatbot-send-button {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: none;
      background: ${CONFIG.primaryColor};
      color: white;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s, transform 0.2s;
    }

    .chatbot-send-button:hover:not(:disabled) {
      background: ${CONFIG.accentColor};
      transform: scale(1.05);
    }

    .chatbot-send-button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .chatbot-send-button svg {
      width: 20px;
      height: 20px;
      fill: white;
    }

    .chatbot-sources {
      margin-top: 8px;
      font-size: 12px;
      color: #6B7280;
    }

    .chatbot-sources strong {
      color: #374151;
    }

    /* Markdown formatting styles */
    .chatbot-message-bubble h1,
    .chatbot-message-bubble h2,
    .chatbot-message-bubble h3,
    .chatbot-message-bubble h4,
    .chatbot-message-bubble h5,
    .chatbot-message-bubble h6 {
      margin: 0.5em 0 0.3em 0;
      font-weight: 600;
      line-height: 1.3;
    }

    .chatbot-message-bubble h1 { font-size: 1.4em; }
    .chatbot-message-bubble h2 { font-size: 1.3em; }
    .chatbot-message-bubble h3 { font-size: 1.2em; }
    .chatbot-message-bubble h4 { font-size: 1.1em; }

    .chatbot-message-bubble p {
      margin: 0.5em 0;
    }

    .chatbot-message-bubble p:first-child {
      margin-top: 0;
    }

    .chatbot-message-bubble p:last-child {
      margin-bottom: 0;
    }

    .chatbot-message-bubble strong {
      font-weight: 600;
    }

    .chatbot-message-bubble em {
      font-style: italic;
    }

    .chatbot-message-bubble code {
      background: rgba(0, 0, 0, 0.05);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
      font-size: 0.9em;
    }

    .chatbot-message.user .chatbot-message-bubble code {
      background: rgba(255, 255, 255, 0.2);
    }

    .chatbot-message-bubble pre {
      background: #F3F4F6;
      border: 1px solid #E5E7EB;
      border-radius: 8px;
      padding: 12px;
      overflow-x: auto;
      margin: 0.8em 0;
    }

    .chatbot-message-bubble pre code {
      background: none;
      padding: 0;
      border-radius: 0;
      font-size: 0.85em;
    }

    .chatbot-message.user .chatbot-message-bubble pre {
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.3);
    }

    .chatbot-message-bubble ul,
    .chatbot-message-bubble ol {
      margin: 0.8em 0;
      padding-left: 24px;
    }

    .chatbot-message-bubble ul {
      list-style-type: disc;
    }

    .chatbot-message-bubble ol {
      list-style-type: decimal;
    }

    .chatbot-message-bubble li {
      margin: 0.3em 0;
    }

    .chatbot-message-bubble a {
      color: ${CONFIG.primaryColor};
      text-decoration: underline;
    }

    .chatbot-message.user .chatbot-message-bubble a {
      color: white;
      text-decoration: underline;
    }

    .chatbot-message-bubble blockquote {
      border-left: 3px solid #E5E7EB;
      margin: 0.8em 0;
      padding-left: 12px;
      color: #6B7280;
      font-style: italic;
    }

    .chatbot-message-bubble hr {
      border: none;
      border-top: 1px solid #E5E7EB;
      margin: 1em 0;
    }

    .chatbot-message-bubble table {
      border-collapse: collapse;
      width: 100%;
      margin: 0.8em 0;
      font-size: 0.9em;
    }

    .chatbot-message-bubble th,
    .chatbot-message-bubble td {
      border: 1px solid #E5E7EB;
      padding: 8px;
      text-align: left;
    }

    .chatbot-message-bubble th {
      background: #F3F4F6;
      font-weight: 600;
    }

    /* Mobile responsive */
    @media (max-width: 480px) {
      .chatbot-window {
        width: calc(100vw - 40px);
        height: calc(100vh - 100px);
      }
    }
  `;

  // ========================================================================
  // HTML TEMPLATE
  // ========================================================================

  const templateFloating = `
    <div class="chatbot-widget-container">
      <button class="chatbot-toggle-button" id="chatbot-toggle">
        <svg viewBox="0 0 24 24">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
        </svg>
      </button>

      <div class="chatbot-window" id="chatbot-window">
        <div class="chatbot-header">
          <div class="chatbot-header-content">
            <h3>${CONFIG.title}</h3>
            <p>${CONFIG.subtitle}</p>
          </div>
          <button class="chatbot-close-button" id="chatbot-close">
            <svg viewBox="0 0 24 24">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        <div class="chatbot-messages" id="chatbot-messages">
          <div class="chatbot-message bot">
            <div class="chatbot-message-bubble">
              ¡Hola! Soy tu asistente del curso prueba. Puedo ayudarte con preguntas sobre el contenido. ¿En qué puedo ayudarte hoy?
            </div>
          </div>
        </div>

        <div class="chatbot-input-container">
          <textarea
            class="chatbot-input"
            id="chatbot-input"
            rows="1"
            placeholder="${CONFIG.placeholder}"
            aria-label="${CONFIG.placeholder}"
          ></textarea>
          <button class="chatbot-send-button" id="chatbot-send">
            <svg viewBox="0 0 24 24">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  `;

  const templateColumn = `
    <div class="chatbot-window column-mode" id="chatbot-window">
      <div class="chatbot-header">
        <div class="chatbot-header-content">
          <h3>${CONFIG.title}</h3>
          <p>${CONFIG.subtitle}</p>
        </div>
        <button class="chatbot-close-button" id="chatbot-close">
          <svg viewBox="0 0 24 24">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>
      </div>

      <div class="chatbot-messages" id="chatbot-messages">
        <div class="chatbot-message bot">
          <div class="chatbot-message-bubble">
            ¡Hola! Soy tu asistente del curso prueba. Puedo ayudarte con preguntas sobre el contenido. ¿En qué puedo ayudarte hoy?
          </div>
        </div>
      </div>

      <div class="chatbot-input-container">
        <input
          type="text"
          class="chatbot-input"
          id="chatbot-input"
          placeholder="${CONFIG.placeholder}"
        />
        <button class="chatbot-send-button" id="chatbot-send">
          <svg viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>
  `;

  // ========================================================================
  // FUNCIONALIDAD
  // ========================================================================

  class ChatbotWidget {
    constructor() {
      this.isOpen = false;
      this.isProcessing = false;
      this.historyPrefetchDone = false;
      // Requirement: always keep the view pinned to the latest message.
      this._autoScrollEnabled = true;
      this._initScheduled = false;
      try {
        this.init();
      } catch (err) {
        console.error('❌ Chatbot widget: init crashed.', err);
      }
    }

    init() {
      // Some platforms/themes inject this script in <head> very early.
      // If body/head are not ready yet, retry shortly instead of crashing.
      if (!document.body || !document.head) {
        if (!this._initScheduled) {
          this._initScheduled = true;
          setTimeout(() => {
            this._initScheduled = false;
            this.init();
          }, 50);
        }
        return;
      }

      // Inyectar estilos
      const styleElement = document.createElement('style');
      styleElement.textContent = styles;
      document.head.appendChild(styleElement);

      // Inyectar HTML
      const container = document.createElement('div');
      container.innerHTML = template;
      const root = container.firstElementChild;
      if (!root) {
        console.error('❌ Chatbot widget: template produced no root element.');
        return;
      }
      document.body.appendChild(root);

      // Obtener elementos
      this.elements = {
        toggle: document.getElementById('chatbot-toggle') || document.getElementById('chat-toggle-floating'),
        window: document.getElementById('chatbot-window'),
        close: document.getElementById('chatbot-close'),
        messages: document.getElementById('chatbot-messages'),
        input: document.getElementById('chatbot-input'),
        send: document.getElementById('chatbot-send'),
      };

      // Guardar referencia a la columna si existe
      this.chatColumn = chatColumn;

      // Configurar event listeners
      this.setupEventListeners();
      this._autogrowInput();
      this._restorePanelOpenIfSaved();
      this.prefetchHistory();
    }

    _panelOpenStorageKey() {
      return 'chatbot_panel_open:' + String(resolveCourseId() || 'default');
    }

    _persistPanelOpen(open) {
      try {
        const k = this._panelOpenStorageKey();
        if (open) {
          localStorage.setItem(k, '1');
        } else {
          localStorage.removeItem(k);
        }
      } catch (e) {
        /* storage lleno o deshabilitado */
      }
    }

    _restorePanelOpenIfSaved() {
      if (!this.elements || !this.elements.window) {
        return;
      }
      try {
        if (localStorage.getItem(this._panelOpenStorageKey()) !== '1') {
          return;
        }
        this.isOpen = true;
        this.elements.window.classList.add('open');
        this._autogrowInput();
        this.scrollToBottom(true);
      } catch (e) {
        /* ignore */
      }
    }

    /** Ajusta la altura del textarea según el contenido (hasta inputMaxHeightPx). */
    _autogrowInput() {
      const el = this.elements && this.elements.input;
      if (!el || el.tagName !== 'TEXTAREA') return;
      const max = CONFIG.inputMaxHeightPx;
      el.style.height = '0px';
      const sh = el.scrollHeight;
      const next = Math.min(sh, max);
      el.style.height = next + 'px';
      el.style.overflowY = sh > max ? 'auto' : 'hidden';
    }

    /**
     * Carga mensajes guardados (misma sesión de usuario/curso) para mostrar tras F5.
     * Requiere JWT; si no hay historial, se mantiene el saludo por defecto.
     * tail=true pide la página más reciente (no los primeros 40 cronológicos).
     */
    async prefetchHistory() {
      if (!resolveToken() || !CONFIG.historyUrl || this.historyPrefetchDone) {
        return;
      }
      try {
        // Sin "limit": el servidor aplica CHAT_MAX_MESSAGES_SAFETY (p. ej. 40).
        // Enviar limit=500 provoca 422 porque FastAPI valida le=MAX_MESSAGES_SAFETY.
        const params = new URLSearchParams({ offset: '0', tail: 'true' });
        const res = await fetch(`${CONFIG.historyUrl}?${params.toString()}`, {
          method: 'GET',
          headers: authHeaders({ Accept: 'application/json' }),
        });
        if (!res.ok) {
          return;
        }
        const data = await res.json();
        this.historyPrefetchDone = true;
        if (!data.messages || data.messages.length === 0) {
          return;
        }
        this.elements.messages.innerHTML = '';
        data.messages.forEach(function (m) {
          var isUser = m.role === 'user';
          this.addMessage(m.content, isUser, null);
        }, this);
        this.scrollToBottom(true);
      } catch (err) {
        console.warn('No se pudo cargar el historial del chat:', err);
      }
    }

    setupEventListeners() {
      this.elements.toggle.addEventListener('click', () => this.toggleWindow());
      this.elements.close.addEventListener('click', () => this.closeWindow());
      this.elements.send.addEventListener('click', () => this.sendMessage());

      this.elements.input.addEventListener('input', () => this._autogrowInput());
      this.elements.input.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' || e.shiftKey || this.isProcessing) {
          return;
        }
        e.preventDefault();
        this.sendMessage();
      });
    }

    toggleWindow() {
      if (this.isOpen) {
        // Solo el botón X cierra; el FAB no alterna a cerrado.
        return;
      }
      this.isOpen = true;
      this.elements.window.classList.add('open');
      this._persistPanelOpen(true);
      this.elements.input.focus();
      this._autogrowInput();
      this.scrollToBottom(true);
    }

    closeWindow() {
      this.isOpen = false;
      this.elements.window.classList.remove('open');
      this._persistPanelOpen(false);
    }

    addMessage(text, isUser = false, sources = null) {
      const messageDiv = document.createElement('div');
      messageDiv.className = `chatbot-message ${isUser ? 'user' : 'bot'}`;

      const bubbleDiv = document.createElement('div');
      bubbleDiv.className = 'chatbot-message-bubble';

      // Usar markdown solo para mensajes del bot
      if (!isUser && text) {
        bubbleDiv.innerHTML = parseMarkdown(text);
      } else {
        bubbleDiv.textContent = text;
      }

      messageDiv.appendChild(bubbleDiv);

      // Agregar fuentes si existen
      if (sources && sources.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'chatbot-sources';
        sourcesDiv.innerHTML = `<strong>Fuentes:</strong> ${sources.join(', ')}`;
        bubbleDiv.appendChild(sourcesDiv);
      }

      this.elements.messages.appendChild(messageDiv);
      this.scrollToBottom(true);
    }

    showTyping() {
      const typingDiv = document.createElement('div');
      typingDiv.className = 'chatbot-message bot';
      typingDiv.id = 'typing-indicator';
      typingDiv.innerHTML = `
        <div class="chatbot-typing">
          <span></span>
          <span></span>
          <span></span>
        </div>
      `;
      this.elements.messages.appendChild(typingDiv);
      this.scrollToBottom(true);
    }

    hideTyping() {
      const typingIndicator = document.getElementById('typing-indicator');
      if (typingIndicator) {
        typingIndicator.remove();
      }
    }

    /**
     * Scroll chat to bottom, robust to late layout changes (Markdown/reflow).
     * force=true keeps the view pinned to the latest message.
     */
    scrollToBottom(force = false) {
      if (!this.elements || !this.elements.messages) return;
      if (!force && !this._autoScrollEnabled) return;

      const el = this.elements.messages;

      // Immediate scroll for synchronous DOM updates.
      el.scrollTop = el.scrollHeight;

      // Next frame (after layout).
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });

      // Small delayed scroll (late reflow: fonts/markdown rendering).
      setTimeout(() => {
        el.scrollTop = el.scrollHeight;
      }, 60);
    }

    async sendMessage() {
      const message = this.elements.input.value.trim();

      if (!message || this.isProcessing) {
        return;
      }

      const courseId = resolveCourseId();
      const token = resolveToken();

      if (!courseId) {
        console.error('❌ Cannot send message: CHATBOT_COURSE_ID is not configured');
        this.addMessage(
          'Error de configuración: El ID del curso no está configurado. Por favor contacta al administrador.',
          false
        );
        return;
      }

      if (!token) {
        console.error('❌ Cannot send message: CHATBOT_TOKEN is not configured');
        this.addMessage(
          'Error de autenticación: falta el token de acceso. Por favor recarga la página o contacta al administrador.',
          false
        );
        return;
      }

      // Agregar mensaje del usuario
      this.addMessage(message, true);
      this.elements.input.value = '';
      this._autogrowInput();

      // Deshabilitar input
      this.isProcessing = true;
      this.elements.send.disabled = true;
      this.elements.input.disabled = true;

      // Mostrar indicador de escritura
      this.showTyping();

      try {
        // Preparar el payload con course_id y user_id
        const requestBody = {
          question: message,
          course_id: courseId,
        };

        // Agregar user_id si está configurado
        if (CONFIG.userId) {
          requestBody.user_id = CONFIG.userId;
        }

        const response = await fetch(CONFIG.apiUrl, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        this.hideTyping();

        if (data.answer) {
          this.addMessage(data.answer, false, data.sources);
        } else {
          this.addMessage('Lo siento, no pude obtener una respuesta.', false);
        }
      } catch (error) {
        console.error('Error al enviar mensaje:', error);
        this.hideTyping();
        this.addMessage(
          'Lo siento, hubo un error al conectar con el servidor. Por favor, intenta de nuevo.',
          false
        );
      } finally {
        // Habilitar input
        this.isProcessing = false;
        this.elements.send.disabled = false;
        this.elements.input.disabled = false;
        this.elements.input.focus();
      }
    }
  }

  // ========================================================================
  // INICIALIZACIÓN
  // ========================================================================

  // Esperar a que el DOM esté listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      new ChatbotWidget();
    });
  } else {
    new ChatbotWidget();
  }
})();
