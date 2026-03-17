const t = {
  uk: {
    title: 'Door Test Controller Demo', language: 'Мова', showcase: 'Тип вітрини', doors: 'Кількість дверей', open_time: 'Open time (s)',
    delay: 'Delay (s)', mode: 'Режим', day: 'День', night: 'Ніч', sim_hours: 'Симуляція годин тесту',
    start: 'Старт тесту', stop: 'Стоп тесту', reset: 'Скинути цикли', light_title: 'Реле освітлення', light_status: 'Стан:',
    door_states: 'Стан дверей', cycles: 'Цикли', light_auto: 'Day mode: авто-вимкнення після 12 годин'
  },
  en: {
    title: 'Door Test Controller Demo', language: 'Language', showcase: 'Showcase type', doors: 'Door count', open_time: 'Open time (s)',
    delay: 'Delay (s)', mode: 'Mode', day: 'Day', night: 'Night', sim_hours: 'Simulated test hours',
    start: 'Start test', stop: 'Stop test', reset: 'Reset cycles', light_title: 'Light relay', light_status: 'State:',
    door_states: 'Door states', cycles: 'Cycles', light_auto: 'Day mode: auto OFF after 12 hours'
  }
};

const state = { running: false, timer: null, cycles: Array(6).fill(0), doors: Array(6).fill('closed'), lightOn: true };

function applyLang(lang) {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    if (t[lang]?.[key]) el.childNodes[0].nodeValue = t[lang][key];
  });
  document.getElementById('lightInfo').textContent = t[lang].light_auto;
}

function doorCount() {
  return Math.max(1, Math.min(6, Number(document.getElementById('doorCount').value) || 4));
}

function render() {
  const count = doorCount();
  const grid = document.getElementById('doorsGrid');
  grid.innerHTML = '';
  for (let i = 0; i < count; i += 1) {
    const d = document.createElement('div');
    d.className = `door ${state.doors[i]}`;
    d.textContent = `Door ${i + 1} ● ${state.doors[i]} | cycles: ${state.cycles[i]}`;
    grid.appendChild(d);
  }
  document.getElementById('cyclesOut').textContent = JSON.stringify(
    Object.fromEntries(Array.from({ length: count }, (_, i) => [`door${i + 1}`, state.cycles[i]])),
    null,
    2,
  );
  const ls = document.getElementById('lightState');
  ls.textContent = state.lightOn ? 'ON' : 'OFF';
  ls.className = state.lightOn ? 'on' : 'off';
}

function testTick() {
  const count = doorCount();
  const mode = document.getElementById('testMode').value;
  const simulatedHours = Number(document.getElementById('simHours').value) || 0;

  for (let i = 0; i < count; i += 1) {
    const pulse = Math.random() > (mode === 'day' ? 0.4 : 0.55);
    state.doors[i] = pulse ? 'open' : 'closed';
    if (pulse) state.cycles[i] += 1;
  }

  if (mode === 'day' && simulatedHours >= 12) {
    state.lightOn = false;
  }

  render();
}

function start() {
  stop(false);
  state.running = true;
  state.lightOn = true;
  testTick();
  state.timer = setInterval(testTick, 2000);
}

function stop(withRender = true) {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  state.running = false;
  if (withRender) render();
}

function reset() {
  stop(false);
  state.cycles.fill(0);
  state.doors.fill('closed');
  state.lightOn = true;
  render();
}

document.getElementById('startBtn').addEventListener('click', start);
document.getElementById('stopBtn').addEventListener('click', () => stop(true));
document.getElementById('resetBtn').addEventListener('click', reset);
document.getElementById('langSelect').addEventListener('change', (e) => applyLang(e.target.value));

document.getElementById('doorCount').addEventListener('change', render);

const lang = navigator.language?.startsWith('uk') ? 'uk' : 'en';
document.getElementById('langSelect').value = lang;
applyLang(lang);
reset();
