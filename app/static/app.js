const $ = (selector, context = document) => context.querySelector(selector);
const $$ = (selector, context = document) => Array.from(context.querySelectorAll(selector));

const loginSection = $('#loginSection');
const dashboardSection = $('#dashboardSection');
const messageBox = $('#messageBox');
const logoutButton = $('#logoutButton');
const accountsTable = $('#accountsTable');
const settingsTable = $('#settingsTable');
const logsTable = $('#logsTable');
const overviewGrid = $('#overviewGrid');
const serviceCards = $('#serviceCards');
const detailPhone = $('#detailPhone');
const detailName = $('#detailName');
const detailUsername = $('#detailUsername');
const detailPremium = $('#detailPremium');
const detailSession = $('#detailSession');
const detailLastSync = $('#detailLastSync');
const detailLogs = $('#detailLogs');
const selectedAccountLabel = $('#selectedAccountLabel');
const moduleScopeLabel = $('#moduleScopeLabel');
const tabs = $$('.tab-button');
const onlineBadge = $('#onlineBadge');
let selectedAccountId = null;

const buildAccountFilter = (path) => {
  if (!selectedAccountId) return path;
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}account_id=${selectedAccountId}`;
};

const updateAccountContext = () => {
  if (selectedAccountId) {
    selectedAccountLabel.textContent = `#${selectedAccountId}`;
    moduleScopeLabel.textContent = 'Локальный';
  } else {
    selectedAccountLabel.textContent = 'Все';
    moduleScopeLabel.textContent = 'Глобальный';
  }
};

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
      <tr data-account-id="${account.id}" class="account-row ${selectedAccountId === account.id ? 'selected' : ''}">
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

  if (!selectedAccountId && accounts[0]) {
    selectedAccountId = accounts[0].id;
  }
  updateAccountContext();
  if (selectedAccountId) {
    await loadAccountDetails(selectedAccountId);
  }
  return accounts;
};

const loadSettings = async () => {
  const settings = await api(buildAccountFilter('/api/settings'));
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

let _allModules = [];
let _currentModuleFilter = 'all';
let _currentModuleSearch = '';

const loadModules = async () => {
  _allModules = await api(buildAccountFilter('/api/settings/modules'));
  renderModulesGrid();
  return _allModules;
};

const renderModulesGrid = () => {
  let filtered = _allModules;
  
  if (_currentModuleFilter === 'enabled') {
    filtered = filtered.filter(m => m.enabled);
  } else if (_currentModuleFilter === 'disabled') {
    filtered = filtered.filter(m => !m.enabled);
  }
  
  if (_currentModuleSearch) {
    const query = _currentModuleSearch.toLowerCase();
    filtered = filtered.filter(m => m.name.toLowerCase().includes(query) || m.commands.some(c => c.toLowerCase().includes(query)));
  }
  
  const modulesGrid = $('#modulesGrid');
  modulesGrid.innerHTML = filtered.length
    ? filtered.map(module => `
      <div class="module-card ${module.enabled ? 'enabled' : 'disabled'}">
        <div class="module-card-header">
          <div class="module-card-title">${module.name}</div>
          <div class="module-card-badge ${module.enabled ? 'enabled' : ''}">${module.command_count}</div>
        </div>
        <div class="module-card-commands">🔧 ${module.commands.slice(0, 3).join(', ')}${module.commands.length > 3 ? '...' : ''}</div>
        <button data-action="toggle-module" data-module="${module.name}" class="module-card-button">
          ${module.enabled ? '✓ Отключить' : '+ Включить'}
        </button>
      </div>
    `).join('')
    : '<div style="grid-column: 1/-1; text-align: center; color: var(--muted); padding: 40px 20px;">Модули не найдены</div>';
};

const loadProfile = async () => {
  const profile = await api('/api/settings/profile');
  document.getElementById('profileLogin').textContent = profile.admin_login;
  document.getElementById('profileAdminId').textContent = profile.admin_id;
  document.getElementById('profilePrefix').textContent = profile.default_prefix;
  document.getElementById('profileLang').textContent = profile.default_lang;
  document.getElementById('profileAccountsTotal').textContent = String(profile.total_accounts);
  document.getElementById('profileAccountsActive').textContent = String(profile.active_accounts);
  document.getElementById('profileLogsTotal').textContent = String(profile.total_logs);
  document.getElementById('profileModulesTotal').textContent = String(profile.module_count);
  return profile;
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

const loadOverview = async () => {
  const overview = await api('/api/settings/overview');
  overviewGrid.innerHTML = `
    <div class="status-tile"><span>Redis</span><strong>${overview.redis_status}</strong></div>
    <div class="status-tile"><span>Database</span><strong>${overview.database_status}</strong></div>
    <div class="status-tile"><span>Telegram API</span><strong>${overview.telegram_status}</strong></div>
    <div class="status-tile"><span>Worker</span><strong>${overview.worker_status}</strong></div>
    <div class="status-tile"><span>Аккаунты</span><strong>${overview.total_accounts}</strong></div>
    <div class="status-tile"><span>Активные</span><strong>${overview.active_accounts}</strong></div>
    <div class="status-tile"><span>Логи</span><strong>${overview.total_logs}</strong></div>
    <div class="status-tile"><span>Настройки</span><strong>${overview.total_settings}</strong></div>
  `;
  return overview;
};

const loadServices = async () => {
  const services = await api('/api/settings/services');
  serviceCards.innerHTML = services.map(service => `
    <div class="service-card ${service.status}">
      <span class="service-name">${service.name}</span>
      <strong>${service.status}</strong>
      <small>${service.detail}</small>
    </div>
  `).join('');
  return services;
};

const loadAccountDetails = async (accountId) => {
  if (!accountId) {
    detailPhone.textContent = '—';
    detailName.textContent = '—';
    detailUsername.textContent = '—';
    detailPremium.textContent = '—';
    detailSession.textContent = '—';
    detailLastSync.textContent = '—';
    detailLogs.innerHTML = '<div class="mini-log-item">Нет данных</div>';
    return null;
  }

  try {
    const data = await api(`/api/accounts/${accountId}/details`);
    const account = data.account || {};
    detailPhone.textContent = account.phone || '—';
    detailName.textContent = [account.first_name, account.last_name].filter(Boolean).join(' ') || '—';
    detailUsername.textContent = account.username || '—';
    detailPremium.textContent = account.premium ? 'Да' : 'Нет';
    detailSession.textContent = account.session_ready ? 'Готово' : 'Нет';
    detailLastSync.textContent = account.last_sync ? new Date(account.last_sync).toLocaleString('ru-RU') : '—';

    detailLogs.innerHTML = (data.logs || []).length
      ? data.logs.map(log => `
          <div class="mini-log-item">
            <span>${log.event_type}</span>
            <small>${log.message || '—'}</small>
          </div>
        `).join('')
      : '<div class="mini-log-item">Нет событий</div>';
    return data;
  } catch (error) {
    detailLogs.innerHTML = `<div class="mini-log-item error">${error.message}</div>`;
    return null;
  }
};

const refreshDashboard = async () => {
  const [accounts, settings, modules, overview, services, logs, profile] = await Promise.all([
    loadAccounts(),
    loadSettings(),
    loadModules(),
    loadOverview(),
    loadServices(),
    loadLogs(),
    loadProfile(),
  ]);
  updateMetrics(accounts, settings, logs);
  return { accounts, settings, modules, overview, services, logs, profile };
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

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    
    if (form.id === 'loginForm') {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      try {
        await api('/api/auth/login', { method: 'POST', body: JSON.stringify(data) });
        showMessage('Вход выполнен успешно');
        await showDashboard();
      } catch (error) {
        showMessage(error.message, 'error');
      }
    } else if (form.id === 'sendCodeForm') {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      try {
        await api('/api/accounts/send-code', { method: 'POST', body: JSON.stringify(data) });
        showMessage('Код отправлен. Введите его для подтверждения.');
      } catch (error) {
        showMessage(error.message, 'error');
      }
    } else if (form.id === 'confirmCodeForm') {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      try {
        await api('/api/accounts/confirm-code', { method: 'POST', body: JSON.stringify(data) });
        showMessage('Аккаунт успешно добавлен');
        await refreshDashboard();
      } catch (error) {
        showMessage(error.message, 'error');
      }
    } else if (form.id === 'settingsForm') {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      data.account_id = data.account_id ? Number(data.account_id) : null;
      try {
        await api('/api/settings', { method: 'PUT', body: JSON.stringify(data) });
        showMessage('Настройки сохранены');
        await loadSettings();
        updateMetrics(await loadAccounts(), await loadSettings(), await loadLogs());
      } catch (error) {
        showMessage(error.message, 'error');
      }
    }
  });

  const restartBtn = document.querySelector('[data-action="restart-worker"]');
  if (restartBtn) {
    restartBtn.addEventListener('click', async () => {
      try {
        const result = await api('/api/settings/system/restart', { method: 'POST' });
        showMessage(result.message || 'Перезапуск запрошен');
      } catch (error) {
        showMessage(error.message, 'error');
      }
    });
  }

  const refreshBtn = document.querySelector('[data-action="refresh-dashboard"]');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      try {
        await refreshDashboard();
        showMessage('Данные обновлены');
      } catch (error) {
        showMessage(error.message, 'error');
      }
    });
  }

  if (accountsTable) {
    accountsTable.addEventListener('click', async (event) => {
      const row = event.target.closest('tr[data-account-id]');
      if (row) {
        selectedAccountId = Number(row.dataset.accountId);
        updateAccountContext();
        await loadAccountDetails(selectedAccountId);
        await refreshDashboard();
        $$('.account-row').forEach(item => item.classList.toggle('selected', Number(item.dataset.accountId) === selectedAccountId));
      }

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
  }

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-action="toggle-module"]');
    if (!button) return;
    const moduleName = button.dataset.module;

    try {
      const url = buildAccountFilter(`/api/settings/modules/${encodeURIComponent(moduleName)}/toggle`);
      await api(url, { method: 'POST' });
      showMessage(`Модуль ${moduleName} обновлён`);
      await loadModules();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });
  
  const moduleFilter = $('#moduleFilter');
  if (moduleFilter) {
    moduleFilter.addEventListener('input', (event) => {
      _currentModuleSearch = event.target.value;
      renderModulesGrid();
    });
  }
  
  $$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.filter-btn').forEach(b => b.classList.remove('filter-btn--active'));
      btn.classList.add('filter-btn--active');
      _currentModuleFilter = btn.dataset.filter;
      renderModulesGrid();
    });
  });

  if (logoutButton) {
    logoutButton.addEventListener('click', async () => {
      try {
        await api('/api/auth/logout', { method: 'POST' });
        showMessage('Выход выполнен');
        showLogin();
      } catch (error) {
        showMessage(error.message, 'error');
      }
    });
  }

  switchTab('accounts');
  setBadge(false);
  await checkAuth();
};

window.addEventListener('DOMContentLoaded', init);
