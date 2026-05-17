const state = {
  currentChatId: null,
  messages: [],
  chatHistory: [],
  isLoading: false,
  currentTheme: 'dark',
  currentPage: 'chat',
  uploadedFiles: []
};

document.addEventListener('DOMContentLoaded', () => {
  loadTheme();
  loadChatHistory();
  loadUploadedFiles();
  document.getElementById('messageInput').focus();
  setupSettingsModal();
  setupUploadZone();
  setupNavigation();
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

function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const page = btn.dataset.page;
      switchPage(page);
      
      navBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

function switchPage(page) {
  state.currentPage = page;
  
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`${page}Page`).classList.add('active');
  
  const titles = {
    chat: '新对话',
    knowledge: '知识库管理'
  };
  document.getElementById('headerTitle').textContent = titles[page] || '新对话';
}

function setupUploadZone() {
  const zone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('fileInput');
  const uploadBtn = document.getElementById('uploadBtn');

  zone.addEventListener('click', () => {
    fileInput.click();
  });

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });

  zone.addEventListener('dragleave', () => {
    zone.classList.remove('drag-over');
  });

  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });
}

async function handleFileUpload(file) {
  const progress = document.getElementById('uploadProgress');
  const progressFill = document.getElementById('progressFill');
  const progressFilename = document.getElementById('progressFilename');
  const progressPercent = document.getElementById('progressPercent');
  const progressMessage = document.getElementById('progressMessage');
  const uploadBtn = document.getElementById('uploadBtn');

  const allowedTypes = ['txt', 'pdf'];
  const extension = file.name.split('.').pop().toLowerCase();
  
  if (!allowedTypes.includes(extension)) {
    showNotification(`不支持的文件格式，仅支持 ${allowedTypes.join(', ')}`, 'error');
    return;
  }

  progress.classList.add('active');
  progressFilename.textContent = file.name;
  progressPercent.textContent = '0%';
  progressMessage.textContent = '准备上传...';
  uploadBtn.disabled = true;

  const formData = new FormData();
  formData.append('file', file);

  try {
    progressFill.style.width = '30%';
    progressPercent.textContent = '30%';
    progressMessage.textContent = '上传文件中...';

    const response = await fetch('/api/files/upload', {
      method: 'POST',
      body: formData
    });

    progressFill.style.width = '70%';
    progressPercent.textContent = '70%';
    progressMessage.textContent = '处理文件中...';

    if (response.ok) {
      const data = await response.json();
      
      progressFill.style.width = '100%';
      progressPercent.textContent = '100%';
      progressMessage.textContent = data.message;

      const fileInfo = {
        id: Date.now().toString(),
        name: file.name,
        size: formatFileSize(file.size),
        chunks: data.chunks || 0,
        status: 'success',
        uploadTime: new Date().toLocaleString('zh-CN')
      };

      state.uploadedFiles.unshift(fileInfo);
      saveUploadedFiles();
      renderFileList();

      showNotification(data.message, 'success');

      setTimeout(() => {
        progress.classList.remove('active');
      }, 2000);
    } else {
      const error = await response.json();
      throw new Error(error.detail || '上传失败');
    }
  } catch (error) {
    progressMessage.textContent = `错误：${error.message}`;
    progressFill.style.background = 'var(--accent-red)';
    showNotification(error.message, 'error');
  } finally {
    uploadBtn.disabled = false;
    document.getElementById('fileInput').value = '';
  }
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function loadUploadedFiles() {
  const saved = localStorage.getItem('uploadedFiles');
  if (saved) {
    state.uploadedFiles = JSON.parse(saved);
  }
  renderFileList();
}

function saveUploadedFiles() {
  localStorage.setItem('uploadedFiles', JSON.stringify(state.uploadedFiles));
}

function renderFileList() {
  const container = document.getElementById('fileListContainer');
  
  if (state.uploadedFiles.length === 0) {
    container.innerHTML = `
      <div class="file-list-empty">
        <div style="font-size: 48px; margin-bottom: 16px;">📂</div>
        <div>暂无上传文件</div>
        <div style="font-size: 12px; margin-top: 8px;">上传 TXT 或 PDF 文件开始构建知识库</div>
      </div>
    `;
    return;
  }

  container.innerHTML = state.uploadedFiles.map(file => `
    <div class="file-item">
      <div class="file-name">
        <span class="file-icon">${getFileIcon(file.name)}</span>
        <span>${file.name}</span>
      </div>
      <div class="file-size">${file.size}</div>
      <div class="file-chunks">${file.chunks} 个片段</div>
      <div class="file-actions">
        <button class="file-action-btn delete" onclick="deleteFile('${file.id}')" title="删除">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18"></path>
            <path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"></path>
            <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"></path>
          </svg>
        </button>
      </div>
    </div>
  `).join('');
}

function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const icons = {
    pdf: '📄',
    txt: '📝',
    md: '📋',
    doc: '📃',
    docx: '📃'
  };
  return icons[ext] || '📄';
}

function deleteFile(fileId) {
  if (!confirm('确定要删除这个文件吗？')) return;
  
  state.uploadedFiles = state.uploadedFiles.filter(f => f.id !== fileId);
  saveUploadedFiles();
  renderFileList();
  showNotification('文件已删除', 'success');
}

function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.style.cssText = `
    position: fixed;
    top: 24px;
    right: 24px;
    padding: 16px 24px;
    background: ${type === 'success' ? 'var(--accent-green)' : type === 'error' ? 'var(--accent-red)' : 'var(--accent-blue)'};
    color: white;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    z-index: 2000;
    animation: slideIn 0.3s ease-out;
    font-size: 14px;
  `;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

async function loadChatHistory() {
  const container = document.getElementById('chatHistory');
  const history = JSON.parse(localStorage.getItem('chatHistory') || '[]');
  state.chatHistory = history;
  
  container.innerHTML = `
    <div class="chat-history-title">最近对话</div>
    ${history.map(chat => `
      <div class="chat-history-item ${chat.id === state.currentChatId ? 'active' : ''}" onclick="loadChat('${chat.id}')">
        <span class="icon">💬</span>
        <span class="chat-title-text">${chat.title}</span>
        <button class="chat-history-delete" onclick="deleteChat('${chat.id}', event)" title="删除对话">❌</button>
      </div>
    `).join('')}
  `;
}

function saveChatHistory() {
  localStorage.setItem('chatHistory', JSON.stringify(state.chatHistory));
}

function loadChat(chatId) {
  state.currentChatId = chatId;
  const chat = state.chatHistory.find(c => c.id === chatId);
  if (chat) {
    state.messages = chat.messages || [];
    document.getElementById('headerTitle').textContent = chat.title;
    renderMessages();
  }
  loadChatHistory();
}

async function deleteChat(chatId, event) {
  if (event) {
    event.stopPropagation();
  }
  if (!confirm('确定要删除这个对话吗？')) return;

  try {
    const response = await fetch(`/api/chat/${chatId}`, {
      method: 'DELETE'
    });

    if (!response.ok && response.status !== 501) {
      const error = await response.json();
      throw new Error(error.detail || '删除失败');
    }
  } catch (error) {
    if (error.message === 'Failed to fetch') {
      showNotification('后端接口暂未实现，已本地删除', 'info');
    } else if (error.message !== '删除失败') {
      showNotification('后端接口暂未实现，已本地删除', 'info');
    } else {
      showNotification(error.message, 'error');
      return;
    }
  }

  state.chatHistory = state.chatHistory.filter(c => c.id !== chatId);
  saveChatHistory();

  if (state.currentChatId === chatId) {
    state.currentChatId = null;
    state.messages = [];
    document.getElementById('headerTitle').textContent = '新对话';
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
  }

  loadChatHistory();
  showNotification('对话已删除', 'success');
}

function startNewChat() {
  state.currentChatId = null;
  state.messages = [];
  document.getElementById('headerTitle').textContent = '新对话';
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
        document.getElementById('headerTitle').textContent = title;
        
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
