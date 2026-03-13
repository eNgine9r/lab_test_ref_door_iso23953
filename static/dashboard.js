const statusEl = document.getElementById('status');
const runningEl = document.getElementById('running');
const eventEl = document.getElementById('event');
const errorEl = document.getElementById('error');
const doorsEl = document.getElementById('doors');

const chartCtx = document.getElementById('cyclesChart');
const chart = new Chart(chartCtx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [1, 2, 3, 4].map((n, i) => ({
      label: `Door ${n}`,
      data: [],
      borderColor: ['#2d6cdf', '#00a87e', '#c84f4f', '#9662d9'][i],
      fill: false,
      tension: 0.2
    }))
  },
  options: { responsive: true }
});

async function postJson(url, body = {}) {
  return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

document.getElementById('start').onclick = async () => {
  await postJson('/start', {
    open_time: parseFloat(document.getElementById('open_time').value),
    delay_between_doors: parseFloat(document.getElementById('delay_between_doors').value),
    door_count: parseInt(document.getElementById('door_count').value, 10),
    showcase_type: document.getElementById('showcase_type').value
  });
};
document.getElementById('stop').onclick = () => postJson('/stop');
document.getElementById('reset').onclick = () => postJson('/reset');
document.querySelectorAll('[data-door]').forEach(btn => {
  btn.onclick = () => postJson(`/open/${btn.dataset.door}`);
});

async function refresh() {
  const status = await (await fetch('/status')).json();
  const cycles = await (await fetch('/cycles')).json();

  statusEl.textContent = status.system_status;
  runningEl.textContent = status.test_running ? 'running' : 'stopped';
  eventEl.textContent = status.last_event;
  errorEl.textContent = status.error_message || '-';

  doorsEl.innerHTML = '';
  Object.entries(status.doors).slice(0, 4).forEach(([name, state]) => {
    const div = document.createElement('div');
    div.className = `door ${state}`;
    div.textContent = `${name} ● ${state}`;
    doorsEl.appendChild(div);
  });

  chart.data.labels = cycles.history.map(x => x.timestamp);
  for (let i = 1; i <= 4; i++) {
    chart.data.datasets[i - 1].data = cycles.history.map(x => x[`door${i}`] ?? 0);
  }
  chart.update();
}

refresh();
setInterval(refresh, 5000);
