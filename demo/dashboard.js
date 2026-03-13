const ctx = document.getElementById('chart');
const doors = document.getElementById('doors');
const labels = [];
const series = [0, 0, 0, 0];
const chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels,
    datasets: series.map((_, i) => ({ label: `Door ${i+1}`, data: [], borderColor: ['#2d6cdf','#00a87e','#c84f4f','#9662d9'][i] }))
  }
});

function tick() {
  const now = new Date().toLocaleTimeString();
  labels.push(now);
  if (labels.length > 20) labels.shift();
  series[0] += 1;
  series[1] += Math.random() > 0.8 ? 1 : 0;
  series[2] += Math.random() > 0.6 ? 1 : 0;
  series[3] += Math.random() > 0.7 ? 1 : 0;

  chart.data.datasets.forEach((ds, i) => {
    ds.data.push(series[i]);
    if (ds.data.length > 20) ds.data.shift();
  });
  chart.update();

  doors.innerHTML = '';
  for (let i = 1; i <= 4; i++) {
    const d = document.createElement('div');
    d.className = 'card';
    d.textContent = `Door${i} ${Math.random() > 0.5 ? '● open' : '● closed'}`;
    doors.appendChild(d);
  }
}

setInterval(tick, 5000);
tick();
