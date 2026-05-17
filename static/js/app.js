const state = {
  currentChatId: null,
  messages: [],
  chatHistory: [],
  isLoading: false,
  currentTheme: 'dark'
};

document.addEventListener('DOMContentLoaded', () => {
  loadTheme();
  loadChatHistory();
  document.getElementById('messageInput').focus();
  setupSettingsModal();
});

function loadTheme() {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  setTheme(savedTheme);
}

function setTheme(theme) {
  state.currentTheme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  updateThemeSelection(theme);
}

function updateThemeSelection(theme) {
  document.querySelectorAll('.theme-option').forEach(option => {
    option.classList.toggle('active', option.dataset.theme === theme);
  });
}

function setupSettingsModal() {
  const settingsBtn = document.querySelector('.settings-btn');
  const modalOverlay = document.getElementById('settingsModal');
  const closeBtn = document.getElementById('modalClose');

  settingsBtn.addEventListener('click', () => {
    modalOverlay.classList.add('active');
    updateThemeSelection(state.currentTheme);
  });

  closeBtn.addEventListener('click', () => {
    modalOverlay.classList.remove('active');
  });

  modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) {
      modalOverlay.classList.remove('active');
    }
  });

  document.querySelectorAll('.theme-option').forEach(option => {
    option.addEventListener('click', () => {
      setTheme(option.dataset.theme);
    });
  });
}

async function loadChatHistory() {
  const container = document.getElementById('chatHistory');
  const history = JSON.parse(localStorage.getItem('chatHistory') || '[]');
  state.chatHistory = history;
  
  container.innerHTML = history.map(chat => `
    <div class="chat-history-item ${chat.id === state.currentChatId ? 'active' : ''}" onclick="loadChat('${chat.id}')">
      <span class="icon">💬</span>
      <span>${chat.title}</span>
    </div>
  `).join('');
}

function saveChatHistory() {
  localStorage.setItem('chatHistory', JSON.stringify(state.chatHistory));
}

function loadChat(chatId) {
  state.currentChatId = chatId;
  const chat = state.chatHistory.find(c => c.id === chatId);
  if (chat) {
    state.messages = chat.messages || [];
    document.getElementById('chatTitle').textContent = chat.title;
    renderMessages();
  }
  loadChatHistory();
}

function startNewChat() {
  state.currentChatId = null;
  state.messages = [];
  document.getElementById('chatTitle').textContent = '新对话';
  document.getElementById('messagesContainer').innerHTML = `
    <div class="welcome-screen" id="welcomeScreen">
      <div class="welcome-icon">🤖</div>
      <h2 class="welcome-title">知识库智能问答</h2>
      <p class="welcome-subtitle">基于您的知识库内容，提供精准的AI问答服务。选择以下示例问题开始，或直接输入您的问题。</p>
      
      <div class="quick-actions">
        <div class="quick-action-card" onclick="sendQuickQuestion('请介绍知识库的主要内容')">
          <div class="quick-action-icon">💡</div>
          <div class="quick-action-title">知识库概览</div>
          <div class="quick-action-desc">了解知识库的主要内容</div>
        </div>
        <div class="quick-action-card" onclick="sendQuickQuestion('如何使用这个问答系统？')">
          <div class="quick-action-icon">📖</div>
          <div class="quick-action-title">使用指南</div>
          <div class="quick-action-desc">学习系统的使用方法</div>
        </div>
        <div class="quick-action-card" onclick="sendQuickQuestion('支持哪些类型的文件？')">
          <div class="quick-action-icon">📄</div>
          <div class="quick-action-title">格式支持</div>
          <div class="quick-action-desc">查看支持的文件格式</div>
        </div>
        <div class="quick-action-card" onclick="sendQuickQuestion('数据来源是什么？')">
          <div class="quick-action-icon">🔍</div>
          <div class="quick-action-title">数据来源</div>
          <div class="quick-action-desc">了解知识库的数据来源</div>
        </div>
      </div>
    </div>
  `;
  loadChatHistory();
}

function sendQuickQuestion(question) {
  document.getElementById('messageInput').value = question;
  sendMessage();
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

function autoResize(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

async function sendMessage() {
  const input = document.getElementById('messageInput');
  const message = input.value.trim();
  
  if (!message || state.isLoading) return;

  const welcomeScreen = document.getElementById('welcomeScreen');
  if (welcomeScreen) {
    welcomeScreen.remove();
  }

  addMessage('user', message);
  input.value = '';
  input.style.height = 'auto';

  state.isLoading = true;
  updateSendButton();
  showTypingIndicator();

  try {
    const response = await fetch('/api/chat/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        chatId: state.currentChatId
      })
    });

    hideTypingIndicator();

    if (response.ok) {
      const data = await response.json();
      addMessage('assistant', data.answer, data.sources);
      
      if (data.chatId && !state.currentChatId) {
        state.currentChatId = data.chatId;
        const title = message.substring(0, 20) + (message.length > 20 ? '...' : '');
        document.getElementById('chatTitle').textContent = title;
        
        state.chatHistory.unshift({
          id: data.chatId,
          title: title,
          messages: [...state.messages, { role: 'user', content: message }, { role: 'assistant', content: data.answer, sources: data.sources }]
        });
        saveChatHistory();
        loadChatHistory();
      } else if (state.currentChatId) {
        const chat = state.chatHistory.find(c => c.id === state.currentChatId);
        if (chat) {
          chat.messages.push({ role: 'user', content: message }, { role: 'assistant', content: data.answer, sources: data.sources });
          saveChatHistory();
        }
      }
    } else {
      const error = await response.json();
      throw new Error(error.detail || '请求失败');
    }
  } catch (error) {
    hideTypingIndicator();
    addMessage('assistant', `⚠️ 请求失败：${error.message}\n\n请确保后端服务正在运行，并且知识库中已上传相关文档。`, null, true);
  } finally {
    state.isLoading = false;
    updateSendButton();
  }
}

function addMessage(role, content, sources = null, isError = false) {
  const container = document.getElementById('messagesContainer');
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  
  state.messages.push({ role, content, sources });
  
  const messageHTML = `
    <div class="message ${role}">
      <div class="message-avatar">${role === 'user' ? '👤' : '🤖'}</div>
      <div class="message-content">
        <div class="message-header">
          <span class="message-role">${role === 'user' ? '您' : 'AI 助手'}</span>
          <span class="message-time">${time}</span>
        </div>
        <div class="message-bubble ${isError ? 'error-message' : ''}">
          ${formatContent(content)}
          ${sources && sources.length > 0 ? `
            <div class="source-references">
              <div class="source-title">参考来源</div>
              <div class="source-list">
                ${sources.map(s => `<span class="source-tag">${s}</span>`).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      </div>
    </div>
  `;
  
  container.insertAdjacentHTML('beforeend', messageHTML);
  scrollToBottom();
}

function formatContent(content) {
  return content
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

function showTypingIndicator() {
  const container = document.getElementById('messagesContainer');
  const typingHTML = `
    <div class="message assistant" id="typingIndicator">
      <div class="message-avatar">🤖</div>
      <div class="message-content">
        <div class="message-header">
          <span class="message-role">AI 助手</span>
        </div>
        <div class="message-bubble">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>
  `;
  container.insertAdjacentHTML('beforeend', typingHTML);
  scrollToBottom();
}

function hideTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) {
    indicator.remove();
  }
}

function scrollToBottom() {
  const container = document.getElementById('messagesContainer');
  container.scrollTop = container.scrollHeight;
}

function updateSendButton() {
  const btn = document.getElementById('sendBtn');
  btn.disabled = state.isLoading;
}

function renderMessages() {
  const container = document.getElementById('messagesContainer');
  container.innerHTML = '';
  
  state.messages.forEach(msg => {
    addMessage(msg.role, msg.content, msg.sources);
  });
}
