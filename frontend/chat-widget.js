/**
 * Widget de Chat para el Chatbot Educativo
 * =========================================
 *
 * Un widget de chat ligero, sin dependencias, completamente personalizable.
 *
 * Uso:
 * 1. Incluye este script en tu HTML:
 *    <script src="chat-widget.js"></script>
 *
 * 2. Configura la URL de la API (opcional):
 *    <script>
 *      window.CHATBOT_API_URL = 'http://localhost:8080/api/chat';
 *    </script>
 */

(function() {
  'use strict';

  // ========================================================================
  // CONFIGURACIÓN
  // ========================================================================

  const CONFIG = {
    apiUrl: window.CHATBOT_API_URL || 'http://localhost:8080/api/chat',
    title: window.CHATBOT_TITLE || 'Asistente del Curso',
    subtitle: window.CHATBOT_SUBTITLE || 'Pregúntame sobre el curso',
    placeholder: window.CHATBOT_PLACEHOLDER || 'Escribe tu pregunta...',
    position: window.CHATBOT_POSITION || 'bottom-right', // bottom-right, bottom-left
    primaryColor: window.CHATBOT_PRIMARY_COLOR || '#4F46E5',
    accentColor: window.CHATBOT_ACCENT_COLOR || '#6366F1',
  };

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
      transition: transform 0.3s ease, box-shadow 0.3s ease;
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
      gap: 8px;
    }

    .chatbot-input {
      flex: 1;
      border: 1px solid #E5E7EB;
      border-radius: 24px;
      padding: 12px 16px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
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

  const template = `
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
              ¡Hola! Soy tu asistente del curso. Puedo ayudarte con preguntas sobre el contenido. ¿En qué puedo ayudarte hoy?
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
    </div>
  `;

  // ========================================================================
  // FUNCIONALIDAD
  // ========================================================================

  class ChatbotWidget {
    constructor() {
      this.isOpen = false;
      this.isProcessing = false;
      this.init();
    }

    init() {
      // Inyectar estilos
      const styleElement = document.createElement('style');
      styleElement.textContent = styles;
      document.head.appendChild(styleElement);

      // Inyectar HTML
      const container = document.createElement('div');
      container.innerHTML = template;
      document.body.appendChild(container.firstElementChild);

      // Obtener elementos
      this.elements = {
        toggle: document.getElementById('chatbot-toggle'),
        window: document.getElementById('chatbot-window'),
        close: document.getElementById('chatbot-close'),
        messages: document.getElementById('chatbot-messages'),
        input: document.getElementById('chatbot-input'),
        send: document.getElementById('chatbot-send'),
      };

      // Configurar event listeners
      this.setupEventListeners();
    }

    setupEventListeners() {
      this.elements.toggle.addEventListener('click', () => this.toggleWindow());
      this.elements.close.addEventListener('click', () => this.closeWindow());
      this.elements.send.addEventListener('click', () => this.sendMessage());

      this.elements.input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !this.isProcessing) {
          this.sendMessage();
        }
      });
    }

    toggleWindow() {
      this.isOpen = !this.isOpen;
      this.elements.window.classList.toggle('open', this.isOpen);

      if (this.isOpen) {
        this.elements.input.focus();
      }
    }

    closeWindow() {
      this.isOpen = false;
      this.elements.window.classList.remove('open');
    }

    addMessage(text, isUser = false, sources = null) {
      const messageDiv = document.createElement('div');
      messageDiv.className = `chatbot-message ${isUser ? 'user' : 'bot'}`;

      const bubbleDiv = document.createElement('div');
      bubbleDiv.className = 'chatbot-message-bubble';
      bubbleDiv.textContent = text;

      messageDiv.appendChild(bubbleDiv);

      // Agregar fuentes si existen
      if (sources && sources.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'chatbot-sources';
        sourcesDiv.innerHTML = `<strong>Fuentes:</strong> ${sources.join(', ')}`;
        bubbleDiv.appendChild(sourcesDiv);
      }

      this.elements.messages.appendChild(messageDiv);
      this.scrollToBottom();
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
      this.scrollToBottom();
    }

    hideTyping() {
      const typingIndicator = document.getElementById('typing-indicator');
      if (typingIndicator) {
        typingIndicator.remove();
      }
    }

    scrollToBottom() {
      this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    async sendMessage() {
      const message = this.elements.input.value.trim();

      if (!message || this.isProcessing) {
        return;
      }

      // Agregar mensaje del usuario
      this.addMessage(message, true);
      this.elements.input.value = '';

      // Deshabilitar input
      this.isProcessing = true;
      this.elements.send.disabled = true;
      this.elements.input.disabled = true;

      // Mostrar indicador de escritura
      this.showTyping();

      try {
        const response = await fetch(CONFIG.apiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ question: message }),
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
