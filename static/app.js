/*
AuraRoom dashboard client logic.
What this file does:
- Polls backend APIs, updates live metric cards, and renders trend charts.
How it contributes to AuraRoom:
- Makes state transitions and behavior patterns visible in near real time.
Hardware interaction:
- None directly; consumes backend data derived from camera/microphone hardware.
*/

const el = {
  peopleCount: document.getElementById("peopleCount"),
  roomState: document.getElementById("roomState"),
  noiseLevel: document.getElementById("noiseLevel"),
  motionLevel: document.getElementById("motionLevel"),
  insightText: document.getElementById("insightText"),
  lastUpdated: document.getElementById("lastUpdated"),
  healthBadge: document.getElementById("healthBadge"),
};

const trendCtx = document.getElementById("trendChart").getContext("2d");
const hourlyCtx = document.getElementById("hourlyChart").getContext("2d");

const trendChart = new Chart(trendCtx, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "People",
        data: [],
        borderColor: "#f06c3b",
        backgroundColor: "rgba(240,108,59,0.12)",
        borderWidth: 2,
        tension: 0.3,
      },
      {
        label: "Motion",
        data: [],
        borderColor: "#006e7f",
        backgroundColor: "rgba(0,110,127,0.12)",
        borderWidth: 2,
        tension: 0.3,
      },
      {
        label: "Audio Energy",
        data: [],
        borderColor: "#3b5b9a",
        backgroundColor: "rgba(59,91,154,0.12)",
        borderWidth: 2,
        tension: 0.3,
      },
    ],
  },
  options: {
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: { ticks: { maxTicksLimit: 7 } },
      y: { beginAtZero: true },
    },
  },
});

const hourlyChart = new Chart(hourlyCtx, {
  type: "bar",
  data: {
    labels: [],
    datasets: [
      {
        label: "Focused Samples",
        data: [],
        backgroundColor: "rgba(0,110,127,0.62)",
      },
      {
        label: "Discussion Samples",
        data: [],
        backgroundColor: "rgba(240,108,59,0.62)",
      },
      {
        label: "Chaotic Samples",
        data: [],
        backgroundColor: "rgba(166,49,33,0.68)",
      },
    ],
  },
  options: {
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: { stacked: true },
      y: { stacked: true, beginAtZero: true },
    },
  },
});

function fmtTimestamp(ts) {
  if (!ts) return "--";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function safeNum(value, decimals = 4) {
  const n = Number(value || 0);
  return Number.isFinite(n) ? n.toFixed(decimals) : "0.0000";
}

async function refreshCurrent() {
  try {
    const res = await fetch("/api/current", { cache: "no-store" });
    const data = await res.json();

    el.peopleCount.textContent = String(data.people_count ?? 0);
    el.roomState.textContent = String(data.room_state ?? "unknown");
    el.roomState.title = el.roomState.textContent;
    el.noiseLevel.textContent = String(data.noise_level_label ?? "low");
    el.motionLevel.textContent = safeNum(data.motion_level, 4);
    el.insightText.textContent = data.insight_text || "Waiting for room telemetry...";
    el.lastUpdated.textContent = `Last updated: ${fmtTimestamp(data.timestamp)}`;
  } catch (_err) {
    el.insightText.textContent = "Backend unreachable. Check service health and sensor access.";
  }
}

function updateTrendChart(history) {
  const tail = (history || []).slice(-30);
  trendChart.data.labels = tail.map((item) => fmtTimestamp(item.timestamp));
  trendChart.data.datasets[0].data = tail.map((item) => item.people_count ?? 0);
  trendChart.data.datasets[1].data = tail.map((item) => item.motion_level ?? 0);
  trendChart.data.datasets[2].data = tail.map((item) => item.audio_energy ?? 0);
  trendChart.update();
}

function updateHourlyChart(hourlySummary) {
  const rows = (hourlySummary || []).slice(-8);
  hourlyChart.data.labels = rows.map((r) => `${String(r.hour).padStart(2, "0")}:00`);
  hourlyChart.data.datasets[0].data = rows.map((r) => r.focused_count ?? 0);
  hourlyChart.data.datasets[1].data = rows.map((r) => r.discussion_count ?? 0);
  hourlyChart.data.datasets[2].data = rows.map((r) => r.chaotic_count ?? 0);
  hourlyChart.update();
}

async function refreshHistory() {
  try {
    const res = await fetch("/api/history", { cache: "no-store" });
    const data = await res.json();
    updateTrendChart(data.history);
    updateHourlyChart(data.hourly_summary);
  } catch (_err) {
    // Keep existing chart data if fetch fails.
  }
}

async function refreshHealth() {
  try {
    const res = await fetch("/api/health", { cache: "no-store" });
    const data = await res.json();
    if (data.status === "ok") {
      el.healthBadge.textContent = "Health: OK";
    } else {
      el.healthBadge.textContent = "Health: Issue";
    }
  } catch (_err) {
    el.healthBadge.textContent = "Health: Offline";
  }
}

async function tick() {
  await Promise.all([refreshCurrent(), refreshHistory()]);
}

tick();
refreshHealth();
setInterval(tick, 3000);
setInterval(refreshHealth, 10000);
