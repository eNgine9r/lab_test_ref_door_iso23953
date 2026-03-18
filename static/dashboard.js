const i18n = {
  uk: {
    title: 'Door Test Controller',
    subtitle: 'Запустіть сервер і натисніть одну кнопку нижче, щоб почати автоматичний тест дверей.',
    event: 'Last event:',
    error: 'Error:',
    quick_start: 'Швидкий запуск',
    quick_help: 'Оберіть режим тесту, кількість дверей і натисніть «Старт». Інші параметри вже підставляються автоматично.',
    mode: 'Режим тесту',
    door_count: 'Кількість дверей',
    duration: 'Тривалість тесту (год)',
    debug: 'Debug режим (час у 10 разів швидше)',
    start: 'Старт',
    stop: 'Стоп',
    status: 'Статус системи',
    system_status: 'System status:',
    test: 'Test:',
    light: 'Light relay:',
    doors: 'Стан дверей',
    manual_controls: 'Ручне керування',
    manual_help: 'Сервісні кнопки для перевірки конкретних дверей або світла.',
    light_on: 'Світло УВІМК',
    light_off: 'Світло ВИМК',
    reset: 'Скинути цикли',
    cycles: 'Цикли',
  },
  en: {
    title: 'Door Test Controller',
    subtitle: 'Start the server and press one button below to begin the automatic door test.',
    event: 'Last event:',
    error: 'Error:',
    quick_start: 'Quick start',
    quick_help: 'Choose the test mode and number of doors, then press Start. Other parameters are filled in automatically.',
    mode: 'Test mode',
    door_count: 'Door count',
    duration: 'Test duration (hours)',
    debug: 'Debug mode (10x faster timing)',
    start: 'Start',
    stop: 'Stop',
    status: 'System status',
    system_status: 'System status:',
    test: 'Test:',
    light: 'Light relay:',
    doors: 'Door states',
    manual_controls: 'Manual controls',
    manual_help: 'Service buttons for checking a specific door or the light relay.',
    light_on: 'Light ON',
    light_off: 'Light OFF',
    reset: 'Reset cycles',
    cycles: 'Cycles',
  },
};

function applyLang(lang) {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    if (i18n[lang]?.[key]) {
      if (el.tagName === 'INPUT') {
        el.value = i18n[lang][key];
      } else {
        const textNode = Array.from(el.childNodes).find((node) => node.nodeType === Node.TEXT_NODE);
        if (textNode) {
          textNode.nodeValue = i18n[lang][key];
        } else {
          el.textContent = i18n[lang][key];
        }
      }
    }
  });
}

async function postJson(url, body = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || payload.message || `Request failed: ${response.status}`);
  }
  return response.json().catch(() => ({}));
}

function updateDoorButtons(doorCount) {
  document.querySelectorAll('[data-door]').forEach((btn) => {
    btn.disabled = parseInt(btn.dataset.door, 10) > doorCount;
  });
}

async function startTest() {
  const payload = {
    mode: document.getElementById('mode').value,
    door_count: parseInt(document.getElementById('door_count').value, 10),
    test_duration_hours: parseInt(document.getElementById('test_duration_hours').value, 10),
    debug: document.getElementById('debug').checked,
  };
  await postJson('/start', payload);
  await refresh();
}

async function stopTest() {
  await postJson('/stop');
  await refresh();
}

document.getElementById('start').onclick = () => startTest().catch(showError);
document.getElementById('stop').onclick = () => stopTest().catch(showError);
document.getElementById('reset').onclick = () => postJson('/reset').then(refresh).catch(showError);
document.getElementById('lightOn').onclick = () => postJson('/light', { on: true }).then(refresh).catch(showError);
document.getElementById('lightOff').onclick = () => postJson('/light', { on: false }).then(refresh).catch(showError);
document.querySelectorAll('[data-door]').forEach((btn) => {
  btn.onclick = () => postJson(`/open/${btn.dataset.door}`).then(refresh).catch(showError);
});

function showError(error) {
  document.getElementById('error').textContent = error.message;
}

async function refresh() {
  const [status, cycles] = await Promise.all([
    fetch('/status').then((r) => r.json()),
    fetch('/cycles').then((r) => r.json()),
  ]);

  document.getElementById('status').textContent = status.system_status;
  document.getElementById('statusPill').textContent = status.system_status;
  document.getElementById('running').textContent = status.test_running ? 'running' : 'stopped';
  document.getElementById('event').textContent = status.last_event;
  document.getElementById('error').textContent = status.error_message || '-';
  document.getElementById('lightStatus').textContent = status.light_relay_on ? 'ON' : 'OFF';
  document.getElementById('modbusPort').textContent = status.modbus_port || '-';
  document.getElementById('modbusBackend').textContent = status.modbus_backend || '-';
  document.getElementById('activeMode').textContent = status.test_mode || '-';
  document.getElementById('activeDoorCount').textContent = status.door_count || '-';
  document.getElementById('activeDuration').textContent = status.test_duration_hours || '-';
  document.getElementById('activeDebug').textContent = status.debug ? 'ON' : 'OFF';

  document.getElementById('mode').value = status.test_mode || 'MT';
  document.getElementById('door_count').value = status.door_count || 4;
  document.getElementById('test_duration_hours').value = status.test_duration_hours || 12;
  document.getElementById('debug').checked = Boolean(status.debug);

  const doorsEl = document.getElementById('doors');
  doorsEl.innerHTML = '';
  Object.entries(status.doors).slice(0, status.door_count || 5).forEach(([name, state]) => {
    const div = document.createElement('div');
    div.className = `door ${state}`;
    div.textContent = `${name} ● ${state}`;
    doorsEl.appendChild(div);
  });

  updateDoorButtons(status.door_count || 5);
  document.getElementById('cyclesData').textContent = JSON.stringify({
    cycles: cycles.cycles,
    recent_events: (cycles.events || []).slice(-20),
  }, null, 2);
}

const userLang = navigator.language?.startsWith('uk') ? 'uk' : 'en';
applyLang(userLang);
refresh().catch(showError);
setInterval(() => refresh().catch(showError), 5000);
