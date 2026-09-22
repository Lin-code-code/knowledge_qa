const API_KEY_STORAGE_KEY = 'apiKey';

const state = {
  currentChatId: null,
  messages: [],
  chatHistory: [],
  isLoading: false,
  currentTheme: 'dark',
  currentPage: 'chat',
  uploadedFiles: [],
  currentTopicId: null,
  currentTopicLabel: '',
  topics: []
};

document.addEventListener('DOMContentLoaded', () => {
  loadTheme();
  loadChatHistory();
  loadUploadedFiles();
  document.getElementById('messageInput').focus();
  setupSettingsModal();
  setupUploadZone();
  setupNavigation();
  setupChatControls();
  setupClickDelegation();
  setupTopicModal();
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
  const apiKeyInput = document.getElementById('apiKeyInput');
  const apiKeySave = document.getElementById('apiKeySave');

  settingsBtn.addEventListener('click', openSettingsModal);
  closeBtn.addEventListener('click', () => { modalOverlay.classList.remove('active'); });
  modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) modalOverlay.classList.remove('active');
  });
  document.querySelectorAll('.theme-option').forEach(option => {
    option.addEventListener('click', () => setTheme(option.dataset.theme));
  });

  apiKeySave.addEventListener('click', () => {
    const value = apiKeyInput.value.trim();
    if (value) {
      localStorage.setItem(API_KEY_STORAGE_KEY, value);
    } else {
      localStorage.removeItem(API_KEY_STORAGE_KEY);
    }
    modalOverlay.classList.remove('active');
    showNotification(value ? 'API Key 已保存' : '已清除 API Key', 'success');
  });
}

function openSettingsModal() {
  const modalOverlay = document.getElementById('settingsModal');
  document.getElementById('apiKeyInput').value = localStorage.getItem(API_KEY_STORAGE_KEY) || '';
  modalOverlay.classList.add('active');
  updateThemeSelection(state.currentTheme);
}

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const apiKey = localStorage.getItem(API_KEY_STORAGE_KEY);
  if (apiKey) headers.set('X-API-Key', apiKey);
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    showNotification('API Key 无效或缺失，请在设置中填写', 'error');
    openSettingsModal();
  }
  return response;
}

function setupChatControls() {
  const input = document.getElementById('messageInput');
  input.addEventListener('keydown', handleKeyDown);
  input.addEventListener('input', (e) => autoResize(e.target));
  document.getElementById('sendBtn').addEventListener('click', sendMessage);
}

function setupClickDelegation() {
  document.addEventListener('click', (event) => {
    const actionEl = event.target.closest('[data-action]');
    if (!actionEl) return;
    const action = actionEl.dataset.action;
    if (action === 'delete-file') {
      handleDeleteFile(actionEl.dataset.id);
    } else if (action === 'load-chat') {
      handleLoadChat(actionEl.dataset.id);
    } else if (action === 'delete-chat') {
      event.stopPropagation();
      handleDeleteChat(actionEl.dataset.id);
    } else if (action === 'new-chat') {
      startNewChat();
    } else if (action === 'show-topics') {
      openTopicModal();
    }
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
  const titles = { chat: '新对话', knowledge: '知识库管理' };
  document.getElementById('headerTitle').textContent = titles[page] || '新对话';
  if (page === 'knowledge') {
    loadUploadedFiles();
  }
}

function setupUploadZone() {
  const zone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('fileInput');
  const uploadBtn = document.getElementById('uploadBtn');
  zone.addEventListener('click', () => fileInput.click());
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => { zone.classList.remove('drag-over'); });
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
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

    const response = await apiFetch('/api/files/upload', { method: 'POST', body: formData });
    progressFill.style.width = '70%';
    progressPercent.textContent = '70%';
    progressMessage.textContent = '处理文件中...';

    if (response.ok) {
      const data = await response.json();
      progressFill.style.width = '100%';
      progressPercent.textContent = '100%';
      progressMessage.textContent = data.message;
      await loadUploadedFiles();
      showNotification(data.message, 'success');
      setTimeout(() => progress.classList.remove('active'), 2000);
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


async function loadUploadedFiles() {
  try {
    const response = await apiFetch('/api/files/list');
    if (response.ok) {
      const data = await response.json();
      state.uploadedFiles = (data.files || []).map(file => ({
        id: file.id,
        name: file.filename || file.name || '未命名文件',
        size: formatBackendFileSize(file.size),
        chunks: file.chunks || 0
      }));
    } else {
      state.uploadedFiles = [];
      showNotification(`获取文件列表失败（${response.status}）`, 'error');
    }
  } catch (error) {
    state.uploadedFiles = [];
    showNotification('获取文件列表失败', 'error');
  }
  renderFileList();
}

function formatBackendFileSize(sizeInKb) {
  if (typeof sizeInKb !== 'number') return '-';
  if (sizeInKb < 1024) return `${sizeInKb} KB`;
  const mb = sizeInKb / 1024;
  return `${mb.toFixed(2)} MB`;
}

function renderFileList() {
  const container = document.getElementById('fileListContainer');
  container.textContent = '';
  if (state.uploadedFiles.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'file-list-empty';
    const icon = document.createElement('div');
    icon.style.fontSize = '48px';
    icon.style.marginBottom = '16px';
    icon.textContent = '📂';
    const text = document.createElement('div');
    text.textContent = '暂无上传文件';
    const hint = document.createElement('div');
    hint.style.fontSize = '12px';
    hint.style.marginTop = '8px';
    hint.textContent = '上传 TXT 或 PDF 文件开始构建知识库';
    empty.append(icon, text, hint);
    container.appendChild(empty);
    return;
  }

  state.uploadedFiles.forEach(file => {
    const item = document.createElement('div');
    item.className = 'file-item';

    const name = document.createElement('div');
    name.className = 'file-name';
    const icon = document.createElement('span');
    icon.className = 'file-icon';
    icon.textContent = getFileIcon(file.name);
    const nameText = document.createElement('span');
    nameText.textContent = file.name;
    name.append(icon, nameText);

    const size = document.createElement('div');
    size.className = 'file-size';
    size.textContent = file.size;

    const chunks = document.createElement('div');
    chunks.className = 'file-chunks';
    chunks.textContent = `${file.chunks} 个片段`;

    const actions = document.createElement('div');
    actions.className = 'file-actions';
    const del = document.createElement('button');
    del.className = 'file-action-btn delete';
    del.dataset.action = 'delete-file';
    del.dataset.id = file.id || '';
    del.title = '删除';
    del.appendChild(createTrashIcon());
    actions.appendChild(del);

    item.append(name, size, chunks, actions);
    container.appendChild(item);
  });
}

function createTrashIcon() {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '16');
  svg.setAttribute('height', '16');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  ['M3 6h18', 'M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2', 'M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6'].forEach(d => {
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', d);
    svg.appendChild(path);
  });
  return svg;
}

function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  return { pdf: '📄', txt: '📝', md: '📋', doc: '📃', docx: '📃' }[ext] || '📄';
}

async function handleDeleteFile(fileId) {
  if (!fileId) {
    showNotification('缺少文件 ID，无法删除', 'error');
    return;
  }
  if (!confirm('确定要删除这个文件吗？')) return;

  try {
    const response = await apiFetch(`/api/files/${fileId}`, { method: 'DELETE' });
    if (!response.ok && response.status !== 404) {
      const error = await response.json();
      throw new Error(error.detail || '删除失败');
    }
    await loadUploadedFiles();
    showNotification('文件记录已删除', 'success');
  } catch (error) {
    showNotification(error.message, 'error');
  }
}

function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed; top: 24px; right: 24px; padding: 16px 24px;
    background: ${type === 'success' ? 'var(--accent-green)' : type === 'error' ? 'var(--accent-red)' : 'var(--accent-blue)'};
    color: white; border-radius: var(--radius-md); box-shadow: var(--shadow-lg);
    z-index: 2000; animation: slideIn 0.3s ease-out; font-size: 14px;`;
  notification.textContent = message;
  document.body.appendChild(notification);
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

/* ========== 会话管理（纯后端 API，无 localStorage）========== */

async function loadChatHistory() {
  const container = document.getElementById('chatHistory');
  state.chatHistory = [];

  try {
    const response = await apiFetch('/api/conversations');
    if (response.ok) {
      const data = await response.json();
      state.chatHistory = data.conversations || [];
    }
  } catch (_) {}

  container.textContent = '';

  const title = document.createElement('div');
  title.className = 'chat-history-title';
  title.textContent = '最近对话';
  container.appendChild(title);

  if (state.chatHistory.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'chat-history-empty';
    empty.textContent = '暂无对话记录';
    container.appendChild(empty);
    return;
  }

  state.chatHistory.forEach(chat => {
    const item = document.createElement('div');
    item.className = 'chat-history-item' + (chat.conversation_id === state.currentChatId ? ' active' : '');
    item.dataset.action = 'load-chat';
    item.dataset.id = chat.conversation_id;

    const icon = document.createElement('span');
    icon.className = 'icon';
    icon.textContent = '💬';

    const text = document.createElement('span');
    text.className = 'chat-title-text';
    text.textContent = chat.title;

    const del = document.createElement('button');
    del.className = 'chat-history-delete';
    del.dataset.action = 'delete-chat';
    del.dataset.id = chat.conversation_id;
    del.title = '删除对话';
    del.textContent = '❌';

    item.append(icon, text, del);
    container.appendChild(item);
  });
}

function setupTopicModal() {
  const modal = document.getElementById('topicModal');
  const close = document.getElementById('topicModalClose');
  close.addEventListener('click', () => modal.classList.remove('active'));
  modal.addEventListener('click', (event) => {
    if (event.target === modal) modal.classList.remove('active');
  });
}

function updateTopicStatus(action = '') {
  const status = document.getElementById('topicStatus');
  const label = document.getElementById('currentTopicLabel');
  const notice = document.getElementById('topicActionNotice');
  const historyButton = document.querySelector('.topic-history-btn');
  const hasTopic = Boolean(state.currentChatId && state.currentTopicId);

  status.hidden = !hasTopic;
  historyButton.disabled = !state.currentChatId;
  label.textContent = state.currentTopicLabel || '服装咨询';
  notice.textContent = action === 'NEW_TOPIC'
    ? '已切换'
    : action === 'CLARIFY'
      ? '需要澄清'
      : action === 'OUT_OF_SCOPE'
        ? '已拒答'
        : '';
  notice.className = `topic-status-action ${action.toLowerCase()}`;
}

async function loadTopics(conversationId) {
  state.topics = [];
  if (!conversationId) {
    state.currentTopicId = null;
    state.currentTopicLabel = '';
    updateTopicStatus();
    return;
  }

  try {
    const response = await apiFetch(`/api/chat/${conversationId}/topics`);
    if (!response.ok) {
      throw new Error(`主题列表加载失败（${response.status}）`);
    }
    const data = await response.json();
    state.topics = data.topics || [];
    const active = state.topics.find(topic => topic.status === 'active');
    if (active) {
      state.currentTopicId = active.topic_id;
      state.currentTopicLabel = active.topic_label;
    }
  } catch (error) {
    state.topics = [];
    showNotification(error.message || '主题列表加载失败', 'error');
  }
  updateTopicStatus();
}

function openTopicModal() {
  if (!state.currentChatId) {
    showNotification('当前还没有会话主题', 'info');
    return;
  }
  renderTopicList();
  document.getElementById('topicModal').classList.add('active');
}

function renderTopicList() {
  const container = document.getElementById('topicListContainer');
  container.textContent = '';
  if (state.topics.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'topic-list-empty';
    empty.textContent = '暂无主题记录';
    container.appendChild(empty);
    return;
  }

  state.topics.forEach(topic => {
    const item = document.createElement('div');
    item.className = `topic-list-item${topic.topic_id === state.currentTopicId ? ' active' : ''}`;

    const heading = document.createElement('div');
    heading.className = 'topic-list-heading';
    const title = document.createElement('span');
    title.className = 'topic-list-title';
    title.textContent = topic.topic_label || '服装咨询';
    const badge = document.createElement('span');
    badge.className = `topic-status-badge ${topic.status}`;
    badge.textContent = topic.status === 'active' ? '进行中' : '已归档';
    heading.append(title, badge);

    const meta = document.createElement('div');
    meta.className = 'topic-list-meta';
    meta.textContent = formatTopicTime(topic.updated_at);

    item.append(heading, meta);
    container.appendChild(item);
  });
}

function formatTopicTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

async function handleLoadChat(conversationId) {
  state.currentChatId = conversationId;
  state.messages = [];
  state.currentTopicId = null;
  state.currentTopicLabel = '';
  updateTopicStatus();

  try {
    const response = await apiFetch(`/api/chat/${conversationId}/messages`);
    if (response.ok) {
      const data = await response.json();
      state.messages = (data.messages || []).map(m => ({
        role: m.role === 'human' ? 'user' : 'assistant',
        content: m.content
      }));
      const chat = state.chatHistory.find(c => c.conversation_id === conversationId);
      document.getElementById('headerTitle').textContent = chat ? chat.title : '对话';
      await loadTopics(conversationId);
    } else {
      showNotification(`获取消息失败（${response.status}）`, 'error');
    }
  } catch (_) {}

  renderMessages();
  loadChatHistory();
}

async function handleDeleteChat(chatId) {
  if (!confirm('确定要删除这个对话吗？')) return;

  try {
    const response = await apiFetch(`/api/chat/${chatId}`, { method: 'DELETE' });
    if (!response.ok && response.status !== 404) {
      const error = await response.json();
      throw new Error(error.detail || '删除失败');
    }
  } catch (error) {
    showNotification(error.message, 'error');
    return;
  }

  if (state.currentChatId === chatId) {
    startNewChat();
  }

  await loadChatHistory();
  showNotification('对话已删除', 'success');
}

function startNewChat() {
  state.currentChatId = null;
  state.messages = [];
  state.currentTopicId = null;
  state.currentTopicLabel = '';
  state.topics = [];
  document.getElementById('headerTitle').textContent = '新对话';
  const container = document.getElementById('messagesContainer');
  container.textContent = '';
  container.appendChild(createWelcomeScreen());
  updateTopicStatus();
  loadChatHistory();
}

function createWelcomeScreen() {
  const welcome = document.createElement('div');
  welcome.className = 'welcome-screen';
  welcome.id = 'welcomeScreen';
  const icon = document.createElement('div');
  icon.className = 'welcome-icon';
  icon.textContent = '🤖';
  const title = document.createElement('h2');
  title.className = 'welcome-title';
  title.textContent = '知识库智能问答';
  const subtitle = document.createElement('p');
  subtitle.className = 'welcome-subtitle';
  subtitle.textContent = '基于您的知识库内容，提供精准的AI问答服务。直接输入您的问题开始。';
  welcome.append(icon, title, subtitle);
  return welcome;
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
  if (welcomeScreen) welcomeScreen.remove();

  addMessage('user', message);
  input.value = '';
  input.style.height = 'auto';

  state.isLoading = true;
  updateSendButton();
  showTypingIndicator();

  try {
    const response = await apiFetch('/api/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, chatId: state.currentChatId })
    });

    hideTypingIndicator();

    if (response.ok) {
      const data = await response.json();
      addMessage('assistant', data.answer, data.sources);

      if (data.chatId) {
        state.currentChatId = data.chatId;
        state.currentTopicId = data.topicId || state.currentTopicId;
        const isNew = !state.chatHistory.some(c => c.conversation_id === data.chatId);

        if (isNew) {
          const chatTitle = message.substring(0, 15) + (message.length > 15 ? '...' : '');
          state.chatHistory.unshift({
            conversation_id: data.chatId,
            title: chatTitle
          });
        }

        const chat = state.chatHistory.find(c => c.conversation_id === data.chatId);
        document.getElementById('headerTitle').textContent = chat ? chat.title : '新对话';
        await loadTopics(data.chatId);
        updateTopicStatus(data.topicAction || '');
        loadChatHistory();
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
  container.appendChild(createMessageElement(role, content, sources, isError, time));
  scrollToBottom();
}

function createMessageElement(role, content, sources = null, isError = false, time = '') {
  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? '👤' : '🤖';

  const contentWrap = document.createElement('div');
  contentWrap.className = 'message-content';

  const header = document.createElement('div');
  header.className = 'message-header';
  const roleLabel = document.createElement('span');
  roleLabel.className = 'message-role';
  roleLabel.textContent = role === 'user' ? '您' : 'AI 助手';
  const timeLabel = document.createElement('span');
  timeLabel.className = 'message-time';
  timeLabel.textContent = time;
  header.append(roleLabel, timeLabel);

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble' + (isError ? ' error-message' : '');
  bubble.textContent = content;

  if (sources && sources.length > 0) {
    const refs = document.createElement('div');
    refs.className = 'source-references';
    const refTitle = document.createElement('div');
    refTitle.className = 'source-title';
    refTitle.textContent = '参考来源';
    const list = document.createElement('div');
    list.className = 'source-list';
    sources.forEach(source => {
      const tag = document.createElement('span');
      tag.className = 'source-tag';
      tag.textContent = source;
      list.appendChild(tag);
    });
    refs.append(refTitle, list);
    bubble.appendChild(refs);
  }

  contentWrap.append(header, bubble);
  msg.append(avatar, contentWrap);
  return msg;
}

function showTypingIndicator() {
  const container = document.getElementById('messagesContainer');
  const message = document.createElement('div');
  message.className = 'message assistant';
  message.id = 'typingIndicator';
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = '🤖';
  const content = document.createElement('div');
  content.className = 'message-content';
  const header = document.createElement('div');
  header.className = 'message-header';
  const role = document.createElement('span');
  role.className = 'message-role';
  role.textContent = 'AI 助手';
  header.appendChild(role);
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  const indicator = document.createElement('div');
  indicator.className = 'typing-indicator';
  for (let i = 0; i < 3; i += 1) indicator.appendChild(document.createElement('span'));
  bubble.appendChild(indicator);
  content.append(header, bubble);
  message.append(avatar, content);
  container.appendChild(message);
  scrollToBottom();
}

function hideTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) indicator.remove();
}

function scrollToBottom() {
  const container = document.getElementById('messagesContainer');
  container.scrollTop = container.scrollHeight;
}

function updateSendButton() {
  document.getElementById('sendBtn').disabled = state.isLoading;
}

function renderMessages() {
  const container = document.getElementById('messagesContainer');
  container.textContent = '';
  state.messages.forEach(msg => {
    container.appendChild(createMessageElement(msg.role, msg.content, msg.sources));
  });
}
