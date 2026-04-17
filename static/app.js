/*
AuraRoom dashboard client logic.
What this file does:
- Polls backend APIs, updates live metric cards, and renders trend charts.
How it contributes to AuraRoom:
- Makes state transitions and behavior patterns visible in near real time.
Hardware interaction:
- None directly; consumes backend data derived from camera/microphone hardware.
*/

const MAX_TREND_POINTS = 30;
const MAX_FEED_ITEMS = 18;
const MAX_TIMELINE_BLOCKS = 20;

const STATE_META = {
  focused: {
    text: "Focused",
    signal: "🟢",
    desc: "Stable collaboration and controlled activity.",
    className: "state-focused",
  },
  discussion: {
    text: "Discussion",
    signal: "🟡",
    desc: "Voices and motion indicate active discussion.",
    className: "state-discussion",
  },
  chaotic: {
    text: "Chaotic",
    signal: "🔴",
    desc: "Noise and motion are elevated. Attention recommended.",
    className: "state-chaotic",
  },
  empty: {
    text: "Empty",
    signal: "⚫",
    desc: "No active occupants detected.",
    className: "state-empty",
  },
  unknown: {
    text: "Unknown",
    signal: "⚫",
    desc: "Awaiting telemetry.",
    className: "state-unknown",
  },
};

const el = {
  stateCard: document.getElementById("stateCard"),
  stateSignal: document.getElementById("stateSignal"),
  roomStateText: document.getElementById("roomStateText"),
  stateSubtext: document.getElementById("stateSubtext"),
  peopleHeadline: document.getElementById("peopleHeadline"),
  peopleIcons: document.getElementById("peopleIcons"),
  energyRing: document.getElementById("energyRing"),
  energyValue: document.getElementById("energyValue"),
  energyLabel: document.getElementById("energyLabel"),
  noiseFill: document.getElementById("noiseFill"),
  motionFill: document.getElementById("motionFill"),
  noiseMeta: document.getElementById("noiseMeta"),
  motionMeta: document.getElementById("motionMeta"),
  insightText: document.getElementById("insightText"),
  stateTimeline: document.getElementById("stateTimeline"),
  insightFeed: document.getElementById("insightFeed"),
  alertStack: document.getElementById("alertStack"),
  lastUpdated: document.getElementById("lastUpdated"),
  healthBadge: document.getElementById("healthBadge"),
};

const trendCtx = document.getElementById("trendChart").getContext("2d");
const trendChart = new Chart(trendCtx, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "Noise",
        data: [],
        borderColor: "#ff767a",
        backgroundColor: "rgba(255,118,122,0.12)",
        borderWidth: 2,
        tension: 0.27,
      },
      {
        label: "Motion",
        data: [],
        borderColor: "#58c5ff",
        backgroundColor: "rgba(88,197,255,0.10)",
        borderWidth: 2,
        tension: 0.27,
      },
      {
        label: "Energy Score",
        data: [],
        borderColor: "#1dd17b",
        backgroundColor: "rgba(29,209,123,0.1)",
        borderWidth: 2,
        tension: 0.25,
      },
    ],
  },
  options: {
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        labels: {
          color: "#d8ebff",
          boxWidth: 14,
          usePointStyle: true,
          pointStyle: "line",
        },
      },
    },
    scales: {
      x: {
        ticks: { maxTicksLimit: 9, color: "#8fb0cc" },
        grid: { color: "rgba(134,160,194,0.14)" },
      },
      y: {
        beginAtZero: true,
        suggestedMax: 100,
        ticks: { color: "#8fb0cc" },
        grid: { color: "rgba(134,160,194,0.14)" },
      },
    },
  },
});

const app = {
  previousState: "unknown",
  previousPeople: 0,
  previousEnergy: 0,
  displayedPeople: 0,
  displayedEnergy: 0,
  previousAudio: 0,
  previousMotion: 0,
  hasBaseline: false,
  seenFeedKeys: new Set(),
  feedItems: [],
  maxAudioSeen: 0.01,
  maxMotionSeen: 0.01,
  lastInsightText: "",
};

function fmtTimestamp(ts) {
  if (!ts) return "--";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function safeNum(value, decimals = 4) {
  const n = Number(value || 0);
  return Number.isFinite(n) ? n.toFixed(decimals) : Number(0).toFixed(decimals);
}

function normalizeAudio(audio) {
  app.maxAudioSeen = Math.max(app.maxAudioSeen, audio);
  return clamp01(audio / Math.max(app.maxAudioSeen, 0.0025));
}

function normalizeMotion(motion) {
  app.maxMotionSeen = Math.max(app.maxMotionSeen, motion);
  return clamp01(motion / Math.max(app.maxMotionSeen, 0.003));
}

function computeEnergyScore(snapshot) {
  const peopleNorm = clamp01((Number(snapshot.people_count || 0) / 6));
  const audioNorm = normalizeAudio(Number(snapshot.audio_energy || 0));
  const motionNorm = normalizeMotion(Number(snapshot.motion_level || 0));

  const weighted = (audioNorm * 0.42) + (motionNorm * 0.33) + (peopleNorm * 0.25);
  return Math.round(weighted * 100);
}

function energyLabel(score) {
  if (score >= 75) return "High operational intensity";
  if (score >= 45) return "Active collaborative load";
  if (score >= 20) return "Moderate baseline";
  return "Calm baseline";
}

function peopleHeadlineText(count) {
  return `👥 ${count} ${count === 1 ? "Person" : "People"} Detected`;
}

function animateNumber(from, to, onFrame) {
  const start = performance.now();
  const duration = 320;

  function frame(now) {
    const p = clamp01((now - start) / duration);
    const value = from + (to - from) * p;
    onFrame(value);
    if (p < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

function renderPeopleIcons(count) {
  el.peopleIcons.innerHTML = "";
  const maxVisible = 8;
  const visible = Math.min(count, maxVisible);

  for (let i = 0; i < visible; i += 1) {
    const chip = document.createElement("span");
    chip.className = "person-chip";
    chip.setAttribute("aria-hidden", "true");
    el.peopleIcons.appendChild(chip);
  }

  if (count > maxVisible) {
    const overflow = document.createElement("span");
    overflow.className = "person-chip overflow";
    overflow.textContent = `+${count - maxVisible}`;
    el.peopleIcons.appendChild(overflow);
  }
}

function flashStateCard() {
  el.stateCard.classList.remove("state-flash");
  void el.stateCard.offsetWidth;
  el.stateCard.classList.add("state-flash");
}

function pushAlert(text, level = "ok") {
  const item = document.createElement("div");
  item.className = `alert ${level}`;
  item.textContent = text;
  el.alertStack.appendChild(item);

  setTimeout(() => {
    item.style.opacity = "0";
    item.style.transition = "opacity 250ms ease";
    setTimeout(() => item.remove(), 260);
  }, 2400);
}

function pushFeed(message, timestamp) {
  const key = `${timestamp}|${message}`;
  if (app.seenFeedKeys.has(key)) {
    return;
  }

  app.seenFeedKeys.add(key);
  app.feedItems.unshift({ message, timestamp });
  if (app.feedItems.length > MAX_FEED_ITEMS) {
    app.feedItems.length = MAX_FEED_ITEMS;
  }

  el.insightFeed.innerHTML = "";
  app.feedItems.forEach((entry) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="feed-time">${fmtTimestamp(entry.timestamp)}</span>${entry.message}`;
    el.insightFeed.appendChild(li);
  });
}

function applyStateVisuals(state) {
  const meta = STATE_META[state] || STATE_META.unknown;

  Object.values(STATE_META).forEach((entry) => {
    el.stateCard.classList.remove(entry.className);
  });
  el.stateCard.classList.add(meta.className);

  el.stateSignal.textContent = meta.signal;
  el.roomStateText.textContent = meta.text;
  el.stateSubtext.textContent = meta.desc;
}

function updateMeters(snapshot) {
  const audio = Number(snapshot.audio_energy || 0);
  const motion = Number(snapshot.motion_level || 0);

  const noisePct = Math.round(normalizeAudio(audio) * 100);
  const motionPct = Math.round(normalizeMotion(motion) * 100);

  el.noiseFill.style.width = `${noisePct}%`;
  el.motionFill.style.width = `${motionPct}%`;
  el.noiseMeta.textContent = `audio_energy: ${safeNum(audio, 4)}`;
  el.motionMeta.textContent = `motion_level: ${safeNum(motion, 4)}`;
}

function updateEnergy(score) {
  const ringDegrees = Math.round((score / 100) * 300);
  el.energyRing.style.setProperty("--score-deg", `${ringDegrees}deg`);
  el.energyLabel.textContent = energyLabel(score);

  animateNumber(app.displayedEnergy, score, (value) => {
    el.energyValue.textContent = String(Math.round(value));
  });
  app.displayedEnergy = score;
}

function updatePeople(count) {
  renderPeopleIcons(count);

  animateNumber(app.displayedPeople, count, (value) => {
    const rounded = Math.max(0, Math.round(value));
    el.peopleHeadline.textContent = peopleHeadlineText(rounded);
  });
  app.displayedPeople = count;
}

function renderStateTimeline(history) {
  const tail = history.slice(-MAX_TIMELINE_BLOCKS);
  el.stateTimeline.innerHTML = "";

  tail.forEach((row) => {
    const state = String(row.room_state || "unknown").toLowerCase();
    const block = document.createElement("div");
    block.className = `state-block ${state}`;
    block.title = `${fmtTimestamp(row.timestamp)} - ${state}`;
    el.stateTimeline.appendChild(block);
  });
}

function updateTrendChart(history) {
  const tail = history.slice(-MAX_TREND_POINTS);
  trendChart.data.labels = tail.map((item) => fmtTimestamp(item.timestamp));
  trendChart.data.datasets[0].data = tail.map((item) => Math.round(normalizeAudio(Number(item.audio_energy || 0)) * 100));
  trendChart.data.datasets[1].data = tail.map((item) => Math.round(normalizeMotion(Number(item.motion_level || 0)) * 100));
  trendChart.data.datasets[2].data = tail.map((item) => computeEnergyScore(item));
  trendChart.update();
}

function processEvents(snapshot, energyScore) {
  const state = String(snapshot.room_state || "unknown").toLowerCase();
  const people = Number(snapshot.people_count || 0);
  const audio = Number(snapshot.audio_energy || 0);
  const motion = Number(snapshot.motion_level || 0);
  const ts = snapshot.timestamp;

  if (!app.hasBaseline) {
    app.previousState = state;
    app.previousPeople = people;
    app.previousAudio = audio;
    app.previousMotion = motion;
    app.previousEnergy = energyScore;
    app.hasBaseline = true;
    return;
  }

  if (state !== app.previousState) {
    flashStateCard();
    pushAlert(`State changed: ${STATE_META[app.previousState]?.text || "Unknown"} -> ${STATE_META[state]?.text || "Unknown"}`, "warn");
    pushFeed(`State changed to ${STATE_META[state]?.text || "Unknown"}.`, ts);
  }

  if (people !== app.previousPeople) {
    const direction = people > app.previousPeople ? "entered" : "left";
    pushFeed(`Occupancy changed: ${Math.abs(people - app.previousPeople)} ${direction}.`, ts);
  }

  if (audio > app.previousAudio * 1.65 && audio > 0.003) {
    pushAlert("Activity spike detected", "danger");
    pushFeed("Audio spike detected.", ts);
  }

  if (motion > app.previousMotion * 1.8 && motion > 0.002) {
    pushFeed("Motion spike detected.", ts);
  }

  if (energyScore < 15 && app.previousEnergy > 30) {
    pushAlert("Room quieted down", "ok");
    pushFeed("Room activity dropped to calm baseline.", ts);
  }

  app.previousState = state;
  app.previousPeople = people;
  app.previousAudio = audio;
  app.previousMotion = motion;
  app.previousEnergy = energyScore;
}

async function refreshCurrent() {
  const res = await fetch("/api/current", { cache: "no-store" });
  if (!res.ok) {
    throw new Error("current endpoint unavailable");
  }

  const data = await res.json();
  const state = String(data.room_state || "unknown").toLowerCase();
  const people = Number(data.people_count || 0);
  const energyScore = computeEnergyScore(data);

  applyStateVisuals(state);
  updatePeople(people);
  updateMeters(data);
  updateEnergy(energyScore);

  if (data.insight_text) {
    el.insightText.textContent = data.insight_text;
    if (data.insight_text !== app.lastInsightText) {
      pushFeed(data.insight_text, data.timestamp);
      app.lastInsightText = data.insight_text;
    }
  }

  el.lastUpdated.textContent = `Last updated: ${fmtTimestamp(data.timestamp)}`;
  processEvents(data, energyScore);
}

async function refreshHistory() {
  const res = await fetch("/api/history", { cache: "no-store" });
  if (!res.ok) {
    throw new Error("history endpoint unavailable");
  }

  const data = await res.json();
  const history = Array.isArray(data.history) ? data.history : [];
  updateTrendChart(history);
  renderStateTimeline(history);
}

async function refreshHealth() {
  try {
    const res = await fetch("/api/health", { cache: "no-store" });
    const data = await res.json();

    el.healthBadge.classList.remove("issue", "offline");
    if (data.status === "ok") {
      el.healthBadge.textContent = "Health: OK";
    } else {
      el.healthBadge.classList.add("issue");
      el.healthBadge.textContent = "Health: Issue";
    }
  } catch (_err) {
    el.healthBadge.classList.remove("issue");
    el.healthBadge.classList.add("offline");
    el.healthBadge.textContent = "Health: Offline";
  }
}

async function tick() {
  try {
    await Promise.all([refreshCurrent(), refreshHistory()]);
  } catch (_err) {
    el.insightText.textContent = "Backend unreachable. Check service health and sensor access.";
  }
}

applyStateVisuals("unknown");
pushFeed("Console initialized. Waiting for live telemetry.", new Date().toISOString());

tick();
refreshHealth();
setInterval(tick, 1500);
setInterval(refreshHealth, 10000);
