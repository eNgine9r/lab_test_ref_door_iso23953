const refs = {
  showcaseType: document.getElementById('showcaseType'),
  doorCount: document.getElementById('doorCount'),
  openTime: document.getElementById('openTime'),
  delayTime: document.getElementById('delayTime'),
  tickSeconds: document.getElementById('tickSeconds'),
  startBtn: document.getElementById('startBtn'),
  stopBtn: document.getElementById('stopBtn'),
  resetBtn: document.getElementById('resetBtn'),
  doors: document.getElementById('doors'),
  modeValue: document.getElementById('modeValue'),
  doorsValue: document.getElementById('doorsValue'),
  totalCycles: document.getElementById('totalCycles'),
  lastEvent: document.getElementById('lastEvent'),
  chartHint: document.getElementById('chartHint'),
  systemBadge: document.getElementById('systemBadge'),
  testBadge: document.getElementById('testBadge'),
};

const MAX_POINTS = 40;
const state = {
  running: false,
  timer: null,
  labels: [],
  cycles: new Array(8).fill(0),
  doorStates: new Array(8).fill('closed'),
};

const ctx = document.getElementById('chart').getContext('2d');
const gradient = ctx.createLinearGradient(0, 0, 0, 260);
gradient.addColorStop(0, 'rgba(108,125,255,.45)');
gradient.addColorStop(1, 'rgba(108,125,255,0)');

const palette = ['#7c8cff', '#20d3b4', '#ff7f7f', '#ffca63', '#be8bff', '#60a5fa', '#34d399', '#f472b6'];
const chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: [],
    datasets: palette.map((color, i) => ({
      label: `Door ${i + 1}`,
      data: [],
      borderColor: color,
      backgroundColor: i === 0 ? gradient : 'transparent',
      fill: i === 0,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.35,
      hidden: i >= 4,
    })),
  },
  options: {
    responsive: true,
    plugins: {
      legend: { labels: { color: '#d7e2ff' } },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: { ticks: { color: '#9aaad6' }, grid: { color: 'rgba(255,255,255,.08)' } },
      y: { beginAtZero: true, ticks: { color: '#9aaad6' }, grid: { color: 'rgba(255,255,255,.08)' } },
    },
  },
});

function uiDoorCount() {
  return Math.max(1, Math.min(8, Number(refs.doorCount.value) || 4));
}

function setEvent(text) {
  refs.lastEvent.textContent = text;
}

function renderDoors() {
  refs.doors.innerHTML = '';
  const doorCount = uiDoorCount();

  for (let i = 0; i < doorCount; i += 1) {
    const stateText = state.doorStates[i];
    const node = document.createElement('article');
    node.className = `door ${stateText}`;
    node.innerHTML = `<span class="name">Door ${i + 1}</span><span class="state">● ${stateText}</span><div>cycles: ${state.cycles[i]}</div>`;
    refs.doors.appendChild(node);
  }

  refs.modeValue.textContent = refs.showcaseType.value;
  refs.doorsValue.textContent = String(doorCount);
  refs.totalCycles.textContent = String(state.cycles.slice(0, doorCount).reduce((a, b) => a + b, 0));
}

function updateChart() {
  const doorCount = uiDoorCount();
  chart.data.labels = state.labels;
  chart.data.datasets.forEach((dataset, i) => {
    dataset.hidden = i >= doorCount;
    dataset.data = state.historyByDoor?.[i] || [];
  });
  chart.update();
}

function addDataPoint() {
  const doorCount = uiDoorCount();
  const tick = Math.max(1, Number(refs.tickSeconds.value) || 5);
  const openTime = Math.max(0.5, Number(refs.openTime.value) || 2);
  const delay = Math.max(0.5, Number(refs.delayTime.value) || 1);
  const isLT = refs.showcaseType.value === 'LT';

  state.labels.push(new Date().toLocaleTimeString());
  if (state.labels.length > MAX_POINTS) state.labels.shift();

  if (!state.historyByDoor) state.historyByDoor = Array.from({ length: 8 }, () => []);

  for (let i = 0; i < doorCount; i += 1) {
    const chance = isLT ? 0.45 : 0.62;
    const impulse = Math.random() < chance ? 1 : 0;
    state.cycles[i] += impulse;
    state.doorStates[i] = impulse ? 'open' : 'closed';

    state.historyByDoor[i].push(state.cycles[i]);
    if (state.historyByDoor[i].length > MAX_POINTS) state.historyByDoor[i].shift();
  }

  setEvent(`Cycle tick • open ${openTime}s • delay ${delay}s • interval ${tick}s`);
  renderDoors();
  updateChart();
}

function stopSimulation(withEvent = true) {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
  state.running = false;
  refs.testBadge.className = 'badge muted';
  refs.testBadge.textContent = 'TEST STOPPED';
  if (withEvent) setEvent('Test stopped');
}

function startSimulation() {
  stopSimulation(false);
  const tickMs = Math.max(1, Number(refs.tickSeconds.value) || 5) * 1000;
  state.running = true;
  refs.testBadge.className = 'badge run';
  refs.testBadge.textContent = 'TEST RUNNING';
  refs.chartHint.textContent = `Оновлення кожні ${tickMs / 1000} сек`;
  setEvent('Test started');
  addDataPoint();
  state.timer = setInterval(addDataPoint, tickMs);
}

function resetSimulation() {
  state.labels = [];
  state.cycles.fill(0);
  state.doorStates.fill('closed');
  state.historyByDoor = Array.from({ length: 8 }, () => []);
  chart.data.labels = [];
  chart.data.datasets.forEach((x) => { x.data = []; });
  chart.update();
  setEvent('Cycles reset');
  renderDoors();
}

refs.startBtn.addEventListener('click', startSimulation);
refs.stopBtn.addEventListener('click', () => stopSimulation());
refs.resetBtn.addEventListener('click', resetSimulation);
refs.showcaseType.addEventListener('change', renderDoors);
refs.doorCount.addEventListener('change', renderDoors);

renderDoors();
resetSimulation();
