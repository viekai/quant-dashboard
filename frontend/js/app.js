// Tab routing
const TABS = ['status', 'portfolio', 'nav', 'factors'];
let refreshTimer = null;

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
async function loadStatus() {
  const data = await API.getStatus();
  const el = document.getElementById('status-content');
  if (!data || data.message === 'no data') {
    el.innerHTML = '<div class="empty">暂无数据，等待 ser9 推送...</div>';
    return;
  }

  const qmtClass = data.qmt_running ? 'green' : 'red';
  const qmtText = data.qmt_running ? '运行中' : '未运行';
  const taskClass = data.daily_task_done ? 'green' : 'yellow';
  const taskText = data.daily_task_done ? '已完成' : '未执行';

  let html = `
    <div class="timestamp">更新时间: ${data.timestamp || '-'}</div>
    <div class="cards">
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

  if (data.stoploss_count > 0) {
    html += `
    <div class="section">
      <div class="section-title">止损黑名单 (${data.stoploss_count})</div>
      <table>
        <tr><th>股票代码</th></tr>
        ${data.stoploss_list.map(c => `<tr><td>${c}</td></tr>`).join('')}
      </table>
    </div>`;
  }

  if (data.signal_latest) {
    html += `<div class="section"><div class="section-title">最新信号文件</div><div>${data.signal_latest}</div></div>`;
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
        <tr><th>代码</th><th>股数</th><th>成本价</th><th>现价</th><th>盈亏%</th></tr>
        ${portfolio.positions.map(p => {
          const cls = p.pnl_pct >= 0 ? 'pnl-pos' : 'pnl-neg';
          return `<tr>
            <td>${p.code}</td><td>${p.shares}</td>
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
        <tr><th>代码</th><th>权重</th></tr>
        ${signal.signals.slice(0, 20).map(s =>
          `<tr><td>${s.code || '-'}</td><td>${s.weight ? (s.weight * 100).toFixed(1) + '%' : '-'}</td></tr>`
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
  const navData = await API.getNav(currentPeriod === 0 ? 99999 : currentPeriod);
  const el = document.getElementById('nav-content');

  // Update period buttons
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.days) === currentPeriod);
  });

  if (!navData || !navData.length) {
    el.innerHTML = '<div class="empty">暂无净值数据</div>';
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

  renderNavChart('nav-chart', navData);
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
document.addEventListener('DOMContentLoaded', () => {
  // Service worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }

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
});
