import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

export function renderEquityChart(ctx, points) {
  const labels = points.map(p => p.timestamp);
  const data = points.map(p => p.equity);
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Equity',
          data,
          borderColor: '#4ade80',
          tension: 0.25,
        },
      ],
    },
  });
}

export function renderDrawdownChart(ctx, points) {
  const labels = points.map(p => p.timestamp);
  const data = points.map(p => p.drawdown_pct);
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Drawdown %',
          data,
          borderColor: '#f87171',
          tension: 0.25,
        },
      ],
    },
  });
}
