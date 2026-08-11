const $ = (selector, context = document) => context.querySelector(selector);
const $$ = (selector, context = document) => Array.from(context.querySelectorAll(selector));

const loginSection = $('#loginSection');
const dashboardSection = $('#dashboardSection');
const messageBox = $('#messageBox');
const logoutButton = $('#logoutButton');
const accountsTable = $('#accountsTable');
const settingsTable = $('#settingsTable');
const logsTable = $('#logsTable');
const tabs = $$('.tab-button');

const showMessage = (text, type = 'success') => {
  messageBox.textContent = text;
  messageBox.className = `message-box visible ${type}`;
  setTimeout(() => messageBox.classList.remove('visible'), 5000);
};

const hideAllTabs = () => tabs.forEach(btn => btn.classList.remove('tab-button--active'));
const switchTab = (name) => {
  hideAllTabs();
  $(`.tab-button[data-tab="${name}"]`).classList.add('tab-button--active');
  $$('.tab-panel').forEach(panel => panel.classList.add('hidden'));
  $(`#${name}Tab`).classList.remove('hidden');
};

const api = async (path, options = {}) => {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(error || res.statusText);
  }
  return res.json();
};

const loadAccounts = async () => {
  const accounts = await api('/api/accounts');
  accountsTable.innerHTML = accounts.map(account => `
    <tr>
      <td>${account.id}</td>
      <td>${account.phone}</td>
      <td>${account.is_active ? 'Активен' : 'Отключён'}</td>
      <td>${account.bot_enabled ? 'Включён' : 'Отключён'}</td>
      <td>
        <button class="button button--secondary" data-action="toggle" data-id="${account.id}">Переключить</button>
        <button class="button button--secondary" data-action="delete" data-id="${account.id}">Удалить</button>
      </td>
    </tr>
  `).join('');
};

const loadSettings = async () => {
  const settings = await api('/api/settings');
  settingsTable.innerHTML = settings.map(setting => `
    <tr>
      <td>${setting.module}</td>
      <td>${setting.key}</td>
      <td>${setting.value ?? ''}</td>
      <td>${setting.account_id ?? 'Все'}</td>
    </tr>
  `).join('');
};

const loadLogs = async () => {
  const logs = await api('/api/logs?limit=100');
  logsTable.innerHTML = logs.map(log => `
    <tr>
      <td>${log.id}</td>
      <td>${log.account_id ?? '-'}</td>
      <td>${log.event_type}</td>
      <td>${log.chat_id ?? '-'}</td>
      <td>${log.user_id ?? '-'}</td>
      <td>${log.message ?? '-'}</td>
    </tr>
  `).join('');
};

const refreshDashboard = async () => {
  await Promise.all([loadAccounts(), loadSettings(), loadLogs()]);
};

const init = async () => {
  $$('.tab-button').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.tab)));

  $('#loginForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const data = Object.fromEntries(new FormData(form));
    try {
      await api('/api/auth/login', { method: 'POST', body: JSON.stringify(data) });
      showMessage('Вход выполнен успешно');
      loginSection.classList.add('hidden');
      dashboardSection.classList.remove('hidden');
      logoutButton.classList.remove('hidden');
      await refreshDashboard();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  $('#sendCodeForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    try {
      await api('/api/accounts/send-code', { method: 'POST', body: JSON.stringify(data) });
      showMessage('Код отправлен. Введите его для подтверждения.');
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  $('#confirmCodeForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    try {
      await api('/api/accounts/confirm-code', { method: 'POST', body: JSON.stringify(data) });
      showMessage('Аккаунт успешно добавлен');
      await refreshDashboard();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  $('#settingsForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    data.account_id = data.account_id ? Number(data.account_id) : null;
    try {
      await api('/api/settings', { method: 'PUT', body: JSON.stringify(data) });
      showMessage('Настройки сохранены');
      await loadSettings();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  accountsTable.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const id = button.dataset.id;
    try {
      if (button.dataset.action === 'toggle') {
        await api(`/api/accounts/${id}/toggle`, { method: 'POST' });
        showMessage('Состояние аккаунта обновлено');
      } else if (button.dataset.action === 'delete') {
        await api(`/api/accounts/${id}`, { method: 'DELETE' });
        showMessage('Аккаунт удалён');
      }
      await loadAccounts();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  logoutButton.addEventListener('click', async () => {
    try {
      await api('/api/auth/logout', { method: 'POST' });
      showMessage('Выход выполнен');
      loginSection.classList.remove('hidden');
      dashboardSection.classList.add('hidden');
      logoutButton.classList.add('hidden');
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  dashboardSection.classList.add('hidden');
  switchTab('accounts');
};

window.addEventListener('DOMContentLoaded', init);
