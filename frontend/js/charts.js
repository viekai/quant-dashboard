// Chart.js dark theme defaults
Chart.defaults.color = '#8892a4';
Chart.defaults.borderColor = 'rgba(42,58,92,0.5)';

const FACTOR_LABELS = {
  volatility_60d: '低波动率',
  pe_ttm: 'PE估值',
  momentum_12_1: '动量12-1',
  turnover_20d: '低换手率',
  profit_growth: '利润增速',
  pb: 'PB估值',
  debt_ratio: '资产负债率',
  revenue_growth: '营收增速',
  ps: 'PS估值',
  roe: 'ROE',
  industry_momentum: '行业动量',
};

const chartInstances = {};

function destroyChart(id) {
  if (chartInstances[id]) {
    chartInstances[id].destroy();
    delete chartInstances[id];
  }
}

function renderNavChart(canvasId, navData, backtestData) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx || !navData || !navData.length) return;

  const labels = navData.map(d => d.date);
  const values = navData.map(d => d.total_value);
  const returns = navData.map(d => (d.daily_return || 0) * 100);

  const datasets = [
    {
      label: '实盘净值',
      data: values,
      borderColor: '#4ecca3',
      backgroundColor: 'rgba(78,204,163,0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      yAxisID: 'y',
    },
    {
      label: '日收益%',
      type: 'bar',
      data: returns,
      backgroundColor: returns.map(r => r >= 0 ? 'rgba(78,204,163,0.3)' : 'rgba(233,69,96,0.3)'),
      yAxisID: 'y1',
    },
  ];

  // Overlay backtest NAV if available
  if (backtestData && backtestData.length) {
    const btMap = {};
    backtestData.forEach(d => { btMap[d.date] = d.total_value; });
    const btValues = labels.map(date => btMap[date] !== undefined ? btMap[date] : null);
    datasets.splice(1, 0, {
      label: '回测净值',
      data: btValues,
      borderColor: '#f0a500',
      borderDash: [6, 3],
      backgroundColor: 'transparent',
      fill: false,
      tension: 0.3,
      pointRadius: 0,
      yAxisID: 'y',
    });
  }

  chartInstances[canvasId] = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        tooltip: {
          callbacks: {
            label(ctx) {
              if (ctx.dataset.yAxisID === 'y') return `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()}`;
              return `日收益: ${ctx.parsed.y.toFixed(2)}%`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 10, font: { size: 11 } } },
        y: { position: 'left', ticks: { callback: v => (v / 10000).toFixed(0) + '万' } },
        y1: {
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: { callback: v => v.toFixed(1) + '%' },
        },
      },
    },
  });
}

function renderDrawdownChart(canvasId, navData) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx || !navData || !navData.length) return;

  const values = navData.map(d => d.total_value);
  let peak = values[0];
  const dd = values.map(v => {
    if (v > peak) peak = v;
    return ((v - peak) / peak) * 100;
  });

  chartInstances[canvasId] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: navData.map(d => d.date),
      datasets: [{
        label: '回撤%',
        data: dd,
        borderColor: '#e94560',
        backgroundColor: 'rgba(233,69,96,0.15)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          callbacks: { label: ctx => `回撤: ${ctx.parsed.y.toFixed(2)}%` },
        },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 10, font: { size: 11 } } },
        y: { ticks: { callback: v => v.toFixed(0) + '%' } },
      },
    },
  });
}

function renderFactorRadar(canvasId, weights) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx || !weights) return;

  const entries = Object.entries(weights).filter(([, v]) => v > 0);
  const labels = entries.map(([k]) => FACTOR_LABELS[k] || k);
  const data = entries.map(([, v]) => v);

  chartInstances[canvasId] = new Chart(ctx, {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: '因子权重%',
        data,
        backgroundColor: 'rgba(15,52,96,0.4)',
        borderColor: '#e94560',
        pointBackgroundColor: '#e94560',
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          beginAtZero: true,
          grid: { color: 'rgba(42,58,92,0.5)' },
          angleLines: { color: 'rgba(42,58,92,0.5)' },
          ticks: { backdropColor: 'transparent', font: { size: 10 } },
          pointLabels: { font: { size: 12 }, color: '#e0e0e0' },
        },
      },
    },
  });
}

function renderFactorBar(canvasId, weights) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx || !weights) return;

  const entries = Object.entries(weights)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);
  const labels = entries.map(([k]) => FACTOR_LABELS[k] || k);
  const data = entries.map(([, v]) => v);

  const gradient = data.map((_, i) => {
    const ratio = i / Math.max(data.length - 1, 1);
    const r = Math.round(233 - ratio * 100);
    const g = Math.round(69 + ratio * 60);
    const b = Math.round(96 + ratio * 60);
    return `rgba(${r},${g},${b},0.8)`;
  });

  chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '权重%',
        data,
        backgroundColor: gradient,
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.x.toFixed(1)}%` } },
      },
      scales: {
        x: { ticks: { callback: v => v + '%' } },
      },
    },
  });
}
