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
const onlineBadge = $('#onlineBadge');

const setBadge = (online) => {
  onlineBadge.innerHTML = `<span class="status-dot"></span>${online ? 'Online' : 'Offline'}`;
  onlineBadge.style.background = online ? 'rgba(49, 208, 170, 0.12)' : 'rgba(251, 191, 36, 0.12)';
  onlineBadge.style.borderColor = online ? 'rgba(49, 208, 170, 0.25)' : 'rgba(251, 191, 36, 0.25)';
  onlineBadge.style.color = online ? '#d5fff4' : '#fff0c4';
};

const showMessage = (text, type = 'success') => {
  messageBox.textContent = text;
  messageBox.className = `message-box visible ${type}`;
  setTimeout(() => messageBox.classList.remove('visible'), 5000);
};

const hideAllTabs = () => tabs.forEach(btn => btn.classList.remove('tab-button--active'));
const switchTab = (name) => {
  hideAllTabs();
  const target = $(`.tab-button[data-tab="${name}"]`);
  if (target) target.classList.add('tab-button--active');
  $$('.tab-panel').forEach(panel => panel.classList.add('hidden'));
  const panel = $(`#${name}Tab`);
  if (panel) panel.classList.remove('hidden');
};

const api = async (path, options = {}) => {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  });

  if (!res.ok) {
    const content = await res.text();
    let message = content || res.statusText;
    if (message.startsWith('{')) {
      try {
        const parsed = JSON.parse(message);
        if (parsed.detail) message = parsed.detail;
      } catch (err) {
        // ignore
      }
    }
    throw new Error(message || 'Ошибка запроса');
  }

  const text = await res.text();
  return text ? JSON.parse(text) : {};
};

const updateMetrics = (accounts, settings, logs) => {
  const activeCount = accounts.filter(account => account.is_active && account.bot_enabled).length;
  document.getElementById('accountsCount').textContent = String(accounts.length);
  document.getElementById('activeCount').textContent = String(activeCount);
  document.getElementById('settingsCount').textContent = String(settings.length);
  document.getElementById('logsCount').textContent = String(logs.length);

  document.getElementById('heroAccountsCount').textContent = String(accounts.length || 0);
  document.getElementById('heroSettingsCount').textContent = String(settings.length || 0);
  document.getElementById('heroLogsCount').textContent = String(logs.length || 0);
};

const loadAccounts = async () => {
  const accounts = await api('/api/accounts');
  accountsTable.innerHTML = accounts.length
    ? accounts.map(account => `
      <tr>
        <td>${account.id}</td>
        <td>${account.phone}</td>
        <td><span class="badge ${account.is_active ? 'success' : 'neutral'}">${account.is_active ? 'Активен' : 'Отключён'}</span></td>
        <td><span class="badge ${account.bot_enabled ? 'success' : 'neutral'}">${account.bot_enabled ? 'Включён' : 'Отключён'}</span></td>
        <td>
          <button data-action="toggle" data-id="${account.id}">${account.bot_enabled ? 'Откл.' : 'Вкл.'}</button>
          <button data-action="delete" data-id="${account.id}">Удалить</button>
        </td>
      </tr>
    `).join('')
    : '<tr><td colspan="5">Аккаунты не найдены.</td></tr>';
  return accounts;
};

const loadSettings = async () => {
  const settings = await api('/api/settings');
  settingsTable.innerHTML = settings.length
    ? settings.map(setting => `
      <tr>
        <td>${setting.module}</td>
        <td>${setting.key}</td>
        <td>${setting.value ?? ''}</td>
        <td>${setting.account_id ?? 'Все'}</td>
      </tr>
    `).join('')
    : '<tr><td colspan="4">Настроек пока нет.</td></tr>';
  return settings;
};

const loadLogs = async () => {
  const logs = await api('/api/logs?limit=100');
  logsTable.innerHTML = logs.length
    ? logs.map(log => `
      <tr>
        <td>${log.id}</td>
        <td>${log.account_id ?? '-'}</td>
        <td>${log.event_type}</td>
        <td>${log.chat_id ?? '-'}</td>
        <td>${log.user_id ?? '-'}</td>
        <td>${log.message ?? '-'}</td>
      </tr>
    `).join('')
    : '<tr><td colspan="6">Логи отсутствуют.</td></tr>';
  return logs;
};

const refreshDashboard = async () => {
  const [accounts, settings, logs] = await Promise.all([loadAccounts(), loadSettings(), loadLogs()]);
  updateMetrics(accounts, settings, logs);
};

const showDashboard = async () => {
  loginSection.classList.add('hidden');
  dashboardSection.classList.remove('hidden');
  logoutButton.classList.remove('hidden');
  setBadge(true);
  await refreshDashboard();
};

const showLogin = () => {
  loginSection.classList.remove('hidden');
  dashboardSection.classList.add('hidden');
  logoutButton.classList.add('hidden');
  setBadge(false);
};

const checkAuth = async () => {
  try {
    await api('/api/accounts');
    await showDashboard();
    return true;
  } catch (error) {
    showLogin();
    return false;
  }
};

const init = async () => {
  $$('.tab-button').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.tab)));

  $('#loginForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    try {
      await api('/api/auth/login', { method: 'POST', body: JSON.stringify(data) });
      showMessage('Вход выполнен успешно');
      await showDashboard();
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
      updateMetrics(await loadAccounts(), await loadSettings(), await loadLogs());
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
      await refreshDashboard();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  logoutButton.addEventListener('click', async () => {
    try {
      await api('/api/auth/logout', { method: 'POST' });
      showMessage('Выход выполнен');
      showLogin();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  switchTab('accounts');
  setBadge(false);
  await checkAuth();
};

window.addEventListener('DOMContentLoaded', init);
