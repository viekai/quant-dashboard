// Tab routing
const TABS = ['status', 'portfolio', 'nav', 'factors'];
let refreshTimer = null;

// ---- Login ----
function showLogin() {
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('main-app').style.display = 'none';
}

function showApp() {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('main-app').style.display = '';
}

async function handleLogin() {
  const pw = document.getElementById('login-password').value;
  const errEl = document.getElementById('login-error');
  errEl.textContent = '';
  if (!pw) { errEl.textContent = '请输入密码'; return; }
  const ok = await API.login(pw);
  if (ok) {
    showApp();
    const hash = window.location.hash.slice(1);
    switchTab(TABS.includes(hash) ? hash : 'status');
  } else {
    errEl.textContent = '密码错误';
  }
}

// ---- Tabs ----
function switchTab(tab) {
  if (!TABS.includes(tab)) tab = 'status';
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.toggle('active', el.id === 'tab-' + tab);
  });
  window.location.hash = tab;
  loadTabData(tab);

  clearInterval(refreshTimer);
  if (tab === 'status') {
    refreshTimer = setInterval(() => loadTabData('status'), 60000);
  }
}

async function loadTabData(tab) {
  switch (tab) {
    case 'status': return loadStatus();
    case 'portfolio': return loadPortfolio();
    case 'nav': return loadNav();
    case 'factors': return loadFactors();
  }
}

// ---- Status ----
async function loadStatus(forceRefresh = false) {
  const el = document.getElementById('status-content');

  // Try live pull first, fallback to push
  let resp = await API.getLiveStatus(forceRefresh);
  let liveData = null;
  let isPull = false;

  if (resp && resp.data) {
    liveData = resp.data;
    isPull = resp.source === 'pull';
  }

  // If pull failed entirely, fallback to push endpoint
  if (!liveData) {
    const pushData = await API.getStatus();
    if (!pushData || pushData.message === 'no data') {
      el.innerHTML = '<div class="empty">暂无数据，等待 ser9 推送或检查 SSH 链路...</div>';
      return;
    }
    // Render legacy push format
    renderPushStatus(el, pushData);
    return;
  }

  renderLiveStatus(el, liveData, resp);
}

function renderLiveStatus(el, data, resp) {
  const sys = data.system || {};
  const db = data.database || {};
  const tasks = data.tasks || {};
  const holdings = data.holdings || {};

  let html = '';

  // A. Freshness banner
  const ageSeconds = resp.cache_age_seconds || 0;
  const ageText = ageSeconds < 0 ? '推送数据' :
    ageSeconds < 60 ? `${Math.round(ageSeconds)} 秒前` :
    `${Math.round(ageSeconds / 60)} 分钟前`;
  const freshClass = resp.error ? 'stale' :
    ageSeconds < 0 ? 'stale' :
    ageSeconds < 120 ? 'fresh' :
    ageSeconds < 600 ? 'warn' : 'stale';
  const sourceLabel = resp.source === 'push_fallback' ? '推送数据' : '实时数据';
  const errorNote = resp.error ? `<span class="freshness-error"> | ${resp.error}</span>` : '';

  html += `
    <div class="freshness-banner ${freshClass}">
      <div class="freshness-left">
        <span class="freshness-dot"></span>
        <span>${sourceLabel} — ${ageText}${errorNote}</span>
      </div>
      <button class="refresh-btn" onclick="loadStatus(true)" title="强制刷新">&#x21bb;</button>
    </div>`;

  // B. System health cards
  const qmtOk = sys.qmt_running;
  const today = new Date().toISOString().slice(0, 10);
  const klineDate = db.kline_last_date || '';
  const klineFresh = klineDate === today ? 'green' :
    klineDate >= today.replace(/\d{2}$/, m => String(Number(m) - 1).padStart(2, '0')) ? 'yellow' : 'red';

  html += `
    <div class="cards cards-4">
      <div class="card">
        <div class="card-label">QMT 状态</div>
        <div class="card-value sm"><span class="dot ${qmtOk ? 'green' : 'red'}"></span>${qmtOk ? '运行中' : '未运行'}</div>
      </div>
      <div class="card">
        <div class="card-label">磁盘空间</div>
        <div class="card-value sm">${sys.disk_free_gb || 0} GB</div>
      </div>
      <div class="card">
        <div class="card-label">K线日期</div>
        <div class="card-value sm"><span class="dot ${klineFresh}"></span>${klineDate || '-'}</div>
      </div>
      <div class="card">
        <div class="card-label">DB 一致性</div>
        <div class="card-value sm"><span class="dot ${db.kline_consistent ? 'green' : 'red'}"></span>${db.kline_consistent ? '正常' : 'meta 不一致'}</div>
      </div>
    </div>`;

  // C. Task cards
  const taskMeta = {
    rebalance: { label: 'QuantRebalance', icon: '&#9654;' },
    stoploss: { label: 'QuantStoploss', icon: '&#9632;' },
    sync: { label: 'QuantSync', icon: '&#8635;' },
  };
  const statusStyles = {
    done: ['badge-green', '已完成'],
    skipped: ['badge-gray', '跳过'],
    running: ['badge-yellow pulse', '执行中'],
    no_log: ['badge-gray-dashed', '未触发'],
    read_error: ['badge-red', '读取失败'],
  };

  html += '<div class="task-cards">';
  for (const [key, meta] of Object.entries(taskMeta)) {
    const t = tasks[key] || {};
    const [badgeClass, badgeLabel] = statusStyles[t.status] || ['badge-red', t.status || '未知'];
    const completedAt = t.completed_at ? ` ${t.completed_at}` : '';
    const subs = (t.subtasks || []);

    html += `
      <div class="task-card">
        <div class="task-card-header">
          <span class="task-card-title">${meta.label}</span>
          <span class="task-card-schedule">${t.schedule || ''}</span>
        </div>
        <div class="task-card-status">
          <span class="status-badge ${badgeClass}">${badgeLabel}</span>
          <span class="task-card-time">${completedAt}</span>
        </div>`;

    if (subs.length) {
      html += '<div class="task-card-steps">';
      for (const s of subs) {
        html += `<div class="task-step">${s.step}: <span class="task-step-result">${s.result}</span></div>`;
      }
      html += '</div>';
    }
    html += '</div>';
  }
  html += '</div>';

  // D. Holdings summary
  const nPos = holdings.n_positions || 0;
  const pendingSells = holdings.pending_sells || [];
  const blCount = holdings.blacklist_count || 0;

  html += `
    <div class="section">
      <div class="section-title">持仓摘要</div>
      <div class="holdings-summary">
        <span>${nPos} 只持仓</span>`;
  if (pendingSells.length > 0) {
    html += `<span class="holdings-alert">| 待卖出: ${pendingSells.join(', ')}</span>`;
  }
  if (blCount > 0) {
    html += `<span class="holdings-dim">| 止损冷却: ${blCount} 只</span>`;
  }
  html += `</div></div>`;

  // E. DB details (collapsible)
  const recentCounts = db.kline_recent_counts || {};
  const recentDates = Object.keys(recentCounts).sort().reverse();

  html += `
    <details class="collapsible">
      <summary class="collapsible-title">DB 详情</summary>
      <div class="collapsible-content">
        <table>
          <tr><th>日期</th><th>K线行数</th></tr>
          ${recentDates.map(d => `<tr><td>${d}</td><td>${recentCounts[d]}</td></tr>`).join('')}
        </table>
        <div class="db-meta">
          <span>财务最新: ${db.financial_last_yq || '-'}</span>
          <span>DB大小: ${db.db_size_mb || 0} MB</span>
          <span>meta日期: ${db.kline_last_date || '-'}</span>
          <span>实际日期: ${db.kline_max_date || '-'}</span>
        </div>
      </div>
    </details>`;

  el.innerHTML = html;
}

function renderPushStatus(el, data) {
  // Legacy push format rendering (simplified)
  const qmtClass = data.qmt_running ? 'green' : 'red';
  const qmtText = data.qmt_running ? '运行中' : '未运行';
  const taskClass = data.daily_task_done ? 'green' : 'yellow';
  const taskText = data.daily_task_done ? '已完成' : '未执行';

  let html = `
    <div class="freshness-banner stale">
      <div class="freshness-left">
        <span class="freshness-dot"></span>
        <span>推送数据 — ${data.timestamp || '-'}</span>
      </div>
      <button class="refresh-btn" onclick="loadStatus(true)" title="强制刷新">&#x21bb;</button>
    </div>
    <div class="cards cards-4">
      <div class="card">
        <div class="card-label">QMT 状态</div>
        <div class="card-value sm"><span class="dot ${qmtClass}"></span>${qmtText}</div>
      </div>
      <div class="card">
        <div class="card-label">K线数据日期</div>
        <div class="card-value sm">${data.kline_date || '-'}</div>
      </div>
      <div class="card">
        <div class="card-label">磁盘剩余</div>
        <div class="card-value sm">${data.disk_free_gb || 0} GB</div>
      </div>
      <div class="card">
        <div class="card-label">每日任务</div>
        <div class="card-value sm"><span class="dot ${taskClass}"></span>${taskText}</div>
      </div>
    </div>`;

  if (data.tasks && data.tasks.length) {
    const statusMap = {
      done: ['green', '已完成'],
      skipped: ['', '跳过'],
      running: ['yellow', '执行中'],
      no_log: ['', '未触发'],
      unknown: ['red', '异常'],
      read_error: ['red', '日志读取失败'],
    };
    const taskNames = { Rebalance: '盘前任务 (09:31)', Stoploss: '盘后任务 (21:00)', Sync: '数据同步 (03:00/05:00)' };

    html += `<div class="section"><div class="section-title">定时任务明细</div><table><tr><th>任务</th><th>状态</th><th>执行时间</th><th>子步骤</th></tr>`;
    for (const t of data.tasks) {
      const [cls, label] = statusMap[t.status] || ['red', t.status];
      const name = taskNames[t.name] || t.name;
      const subs = (t.subtasks || []).map(s => `${s.step}: ${s.result}`).join('<br>') || '-';
      const time = t.time || '-';
      html += `<tr><td>${name}</td><td><span class="dot ${cls}"></span>${label}</td><td>${time}</td><td>${subs}</td></tr>`;
    }
    html += `</table></div>`;
  }

  el.innerHTML = html;
}

// ---- Portfolio ----
async function loadPortfolio() {
  const [portfolio, trades, signal] = await Promise.all([
    API.getPortfolio(),
    API.getTrades(20),
    API.getSignal(),
  ]);
  const el = document.getElementById('portfolio-content');
  let html = '';

  // Positions
  if (portfolio && portfolio.positions && portfolio.positions.length) {
    html += `
    <div class="section">
      <div class="section-title">当前持仓 (${portfolio.positions.length})</div>
      <div class="timestamp">更新: ${portfolio.timestamp || '-'}</div>
      <table>
        <tr><th>代码</th><th>名称</th><th>股数</th><th>成本价</th><th>现价</th><th>盈亏%</th></tr>
        ${portfolio.positions.map(p => {
          const cls = p.pnl_pct >= 0 ? 'pnl-pos' : 'pnl-neg';
          return `<tr>
            <td>${p.code}</td><td>${p.name || '-'}</td><td>${p.shares}</td>
            <td>${p.cost_price.toFixed(2)}</td><td>${p.current_price.toFixed(2)}</td>
            <td class="${cls}">${(p.pnl_pct * 100).toFixed(2)}%</td>
          </tr>`;
        }).join('')}
      </table>
    </div>`;
  }

  // Blacklist
  if (portfolio && portfolio.blacklist && Object.keys(portfolio.blacklist).length) {
    html += `
    <div class="section">
      <div class="section-title">止损冷却</div>
      <table>
        <tr><th>代码</th><th>剩余天数</th></tr>
        ${Object.entries(portfolio.blacklist).map(([c, d]) =>
          `<tr><td>${c}</td><td>${d}</td></tr>`
        ).join('')}
      </table>
    </div>`;
  }

  // Trades
  if (trades && trades.length) {
    html += `
    <div class="section">
      <div class="section-title">最近交易</div>
      <table>
        <tr><th>时间</th><th>详情</th></tr>
        ${trades.map(t => `<tr><td>${t.timestamp || '-'}</td><td>${JSON.stringify(t.trades || []).slice(0, 100)}</td></tr>`).join('')}
      </table>
    </div>`;
  }

  // Signal
  if (signal && signal.signals && signal.signals.length) {
    html += `
    <div class="section">
      <div class="section-title">最新信号 (${signal.timestamp || '-'})</div>
      <table>
        <tr><th>代码</th><th>名称</th><th>权重</th></tr>
        ${signal.signals.slice(0, 20).map(s =>
          `<tr><td>${s.code || '-'}</td><td>${s.name || '-'}</td><td>${s.weight ? (s.weight * 100).toFixed(1) + '%' : '-'}</td></tr>`
        ).join('')}
      </table>
    </div>`;
  }

  el.innerHTML = html || '<div class="empty">暂无持仓数据</div>';
}

// ---- NAV ----
let currentPeriod = 90;

async function loadNav(days) {
  if (days !== undefined) currentPeriod = days;
  const queryDays = currentPeriod === 0 ? 99999 : currentPeriod;
  const [navData, backtestData] = await Promise.all([
    API.getNav(queryDays),
    API.getBacktestNav(queryDays),
  ]);

  // Update period buttons
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.days) === currentPeriod);
  });

  if (!navData || !navData.length) {
    document.getElementById('nav-stats').innerHTML = '';
    renderNavChart('nav-chart', [], []);
    renderDrawdownChart('dd-chart', []);
    return;
  }

  // Stats
  const first = navData[0].total_value;
  const last = navData[navData.length - 1].total_value;
  const totalReturn = ((last - first) / first * 100).toFixed(2);
  const days_count = navData.length;
  const annReturn = (Math.pow(last / first, 252 / Math.max(days_count, 1)) - 1) * 100;

  let peak = first;
  let maxDD = 0;
  navData.forEach(d => {
    if (d.total_value > peak) peak = d.total_value;
    const dd = (d.total_value - peak) / peak;
    if (dd < maxDD) maxDD = dd;
  });

  const returns = navData.map(d => d.daily_return || 0);
  const avgRet = returns.reduce((a, b) => a + b, 0) / returns.length;
  const stdRet = Math.sqrt(returns.reduce((a, r) => a + (r - avgRet) ** 2, 0) / returns.length);
  const sharpe = stdRet > 0 ? (avgRet / stdRet * Math.sqrt(252)).toFixed(2) : '-';

  document.getElementById('nav-stats').innerHTML = `
    <div class="card"><div class="card-label">总收益</div><div class="card-value sm ${totalReturn >= 0 ? 'pnl-pos' : 'pnl-neg'}">${totalReturn}%</div></div>
    <div class="card"><div class="card-label">年化收益</div><div class="card-value sm">${annReturn.toFixed(1)}%</div></div>
    <div class="card"><div class="card-label">最大回撤</div><div class="card-value sm pnl-neg">${(maxDD * 100).toFixed(1)}%</div></div>
    <div class="card"><div class="card-label">Sharpe</div><div class="card-value sm">${sharpe}</div></div>
  `;

  renderNavChart('nav-chart', navData, backtestData);
  renderDrawdownChart('dd-chart', navData);
}

// ---- Factors ----
async function loadFactors() {
  const weights = await API.getFactorWeights();
  if (!weights) {
    document.getElementById('factors-content').innerHTML = '<div class="empty">暂无数据</div>';
    return;
  }

  // Table
  const entries = Object.entries(weights).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const tableHtml = `
    <table>
      <tr><th>因子</th><th>权重</th></tr>
      ${entries.map(([k, v]) => `<tr><td>${FACTOR_LABELS[k] || k}</td><td>${v.toFixed(1)}%</td></tr>`).join('')}
    </table>`;
  document.getElementById('factor-table').innerHTML = tableHtml;

  renderFactorRadar('radar-chart', weights);
  renderFactorBar('bar-chart', weights);
}

// ---- Init ----
document.addEventListener('DOMContentLoaded', async () => {
  // Service worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js', { scope: './' }).catch(() => {});
  }

  // Login handlers
  document.getElementById('login-btn').addEventListener('click', handleLogin);
  document.getElementById('login-password').addEventListener('keydown', e => {
    if (e.key === 'Enter') handleLogin();
  });

  // Check existing session
  const authed = await API.checkAuth();
  if (authed) {
    showApp();
    // Tab clicks
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', () => switchTab(el.dataset.tab));
    });
    // Period buttons
    document.querySelectorAll('.period-btn').forEach(btn => {
      btn.addEventListener('click', () => loadNav(parseInt(btn.dataset.days)));
    });
    // Hash routing
    const hash = window.location.hash.slice(1);
    switchTab(TABS.includes(hash) ? hash : 'status');
  } else {
    showLogin();
    // Still bind event listeners for after login
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', () => switchTab(el.dataset.tab));
    });
    document.querySelectorAll('.period-btn').forEach(btn => {
      btn.addEventListener('click', () => loadNav(parseInt(btn.dataset.days)));
    });
  }
});
