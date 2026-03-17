const i18n = {
  uk: {
    title: 'Door Test Controller', lang: 'Мова', params: 'Параметри', showcase: 'Тип вітрини', door_count: 'Кількість дверей',
    open_time: 'Open time (s)', delay: 'Delay (s)', mode: 'Режим тесту', day: 'День', night: 'Ніч', status: 'Статус',
    system_status: 'System status:', test: 'Test:', event: 'Last event:', error: 'Error:', light: 'Light relay:',
    start: 'Старт тесту', stop: 'Стоп тесту', reset: 'Скинути цикли', light_on: 'Світло УВІМК', light_off: 'Світло ВИМК', doors: 'Стан дверей', cycles: 'Цикли'
  },
  en: {
    title: 'Door Test Controller', lang: 'Language', params: 'Parameters', showcase: 'Showcase type', door_count: 'Door count',
    open_time: 'Open time (s)', delay: 'Delay (s)', mode: 'Test mode', day: 'Day', night: 'Night', status: 'Status',
    system_status: 'System status:', test: 'Test:', event: 'Last event:', error: 'Error:', light: 'Light relay:',
    start: 'Start test', stop: 'Stop test', reset: 'Reset cycles', light_on: 'Light ON', light_off: 'Light OFF', doors: 'Door states', cycles: 'Cycles'
  }
};

function applyLang(lang) {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    if (i18n[lang]?.[key]) el.childNodes[0].nodeValue = i18n[lang][key];
  });
}

async function postJson(url, body = {}) {
  return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

document.getElementById('langSelect').addEventListener('change', (e) => applyLang(e.target.value));

document.getElementById('start').onclick = async () => {
  await postJson('/start', {
    open_time: parseFloat(document.getElementById('open_time').value),
    delay_between_doors: parseFloat(document.getElementById('delay_between_doors').value),
    door_count: parseInt(document.getElementById('door_count').value, 10),
    showcase_type: document.getElementById('showcase_type').value,
    test_mode: document.getElementById('test_mode').value,
  });
};
document.getElementById('stop').onclick = () => postJson('/stop');
document.getElementById('reset').onclick = () => postJson('/reset');
document.getElementById('lightOn').onclick = () => postJson('/light', { on: true });
document.getElementById('lightOff').onclick = () => postJson('/light', { on: false });
document.querySelectorAll('[data-door]').forEach((btn) => {
  btn.onclick = () => postJson(`/open/${btn.dataset.door}`);
});

async function refresh() {
  const status = await (await fetch('/status')).json();
  const cycles = await (await fetch('/cycles')).json();
  document.getElementById('status').textContent = status.system_status;
  document.getElementById('running').textContent = status.test_running ? 'running' : 'stopped';
  document.getElementById('event').textContent = status.last_event;
  document.getElementById('error').textContent = status.error_message || '-';
  document.getElementById('lightStatus').textContent = status.light_relay_on ? 'ON' : 'OFF';
  document.getElementById('cyclesData').textContent = JSON.stringify(cycles.cycles, null, 2);

  const doorsEl = document.getElementById('doors');
  doorsEl.innerHTML = '';
  Object.entries(status.doors).slice(0, 8).forEach(([name, state]) => {
    const div = document.createElement('div');
    div.className = `door ${state}`;
    div.textContent = `${name} ● ${state}`;
    doorsEl.appendChild(div);
  });
}

const userLang = navigator.language?.startsWith('uk') ? 'uk' : 'en';
document.getElementById('langSelect').value = userLang;
applyLang(userLang);
refresh();
setInterval(refresh, 5000);
