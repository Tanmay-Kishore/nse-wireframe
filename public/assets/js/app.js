/* Simple wireframe JS to fetch mock API and render cards */
const API_BASE = "/api";

function setActiveNav() {
  const page = document.documentElement.getAttribute("data-page");
  document.querySelectorAll(".wf-nav a").forEach(a => {
    if (a.dataset.nav === page) a.classList.add("active");
  });
}

async function getJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error("API error " + res.status);
  return await res.json();
}

function stockCard(s) {
  return `<div class="wf-stock-card">
    <div class="wf-stock-head">
      <div><strong>${s.symbol}</strong> <span class="wf-tag">${s.name || ""}</span></div>
      <div class="wf-pill ${s.signal?.direction === "BUY" ? "buy" : (s.signal?.direction === "SELL" ? "sell" : "")}">
        ${s.signal?.direction || "-"}
      </div>
    </div>
    <div class="wf-metrics">
      <div class="wf-kv"><span>Price</span><span>${s.price?.toFixed(2)}</span></div>
      <div class="wf-kv"><span>% Gap</span><span>${s.gap?.toFixed(2)}%</span></div>
      <div class="wf-kv"><span>Vol</span><span>${s.volume}</span></div>
      <div class="wf-kv"><span>VWAP</span><span>${s.vwap?.toFixed(2)}</span></div>
      <div class="wf-kv"><span>RSI</span><span>${s.rsi?.toFixed(1)}</span></div>
      <div class="wf-kv"><span>MA20/50/200</span><span>${s.ma20?.toFixed(2)} / ${s.ma50?.toFixed(2)} / ${s.ma200?.toFixed(2)}</span></div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <span class="wf-tag">Sent: ${s.sentiment || "-"}</span>
      <span class="wf-tag">Entry: ${s.signal?.entry ?? "-"}</span>
      <span class="wf-tag">SL: ${s.signal?.sl ?? "-"}</span>
      <span class="wf-tag">Target: ${s.signal?.target ?? "-"}</span>
      <a class="wf-btn" href="/stock.html?symbol=${encodeURIComponent(s.symbol)}">Open</a>
    </div>
  </div>`;
}

function renderOverview() {
  // Snapshot + watchlist
  getJSON("/stocks?limit=9").then(data => {
    const grid = document.getElementById("watchlist-grid");
    grid.innerHTML = data.items.map(stockCard).join("");
  }).catch(console.error);

  // Alerts
  getJSON("/alerts").then(data => {
    const ul = document.getElementById("live-alerts");
    ul.innerHTML = data.items.map(a => `<li class="wf-alert ${a.severity}"><div><strong>${a.symbol}</strong> ${a.message}</div><div class="wf-tag">${new Date(a.ts).toLocaleTimeString()}</div></li>`).join("");
  }).catch(console.error);

  // Market snapshot placeholder
  const ms = document.getElementById("market-snapshot");
  if (ms) {
    ms.innerHTML = [0,1,2].map(i => `<div class="wf-stock-card">
      <div class="wf-stock-head"><div><strong>${i===0?"NIFTY 50": i===1?"BANK NIFTY":"INDIA VIX"}</strong></div><div class="wf-tag">index</div></div>
      <div class="wf-metrics">
        <div class="wf-kv"><span>Last</span><span>${(18000 + Math.random()*500).toFixed(2)}</span></div>
        <div class="wf-kv"><span>Change</span><span>${(Math.random()*2-1).toFixed(2)}%</span></div>
        <div class="wf-kv"><span>Vol</span><span>${(Math.random()*1e7|0)}</span></div>
      </div>
    </div>`).join("");
  }

  // News sentiment placeholder
  const ns = document.getElementById("news-stream");
  if (ns) {
    ns.innerHTML = ["Macro outlook improves", "RBI stance unchanged", "IT stocks under pressure"].map(h =>
      `<div class="wf-alert warn"><div>${h}</div><div class="wf-tag">neutral</div></div>`
    ).join("");
  }
}

function renderScreener() {
  const btn = document.getElementById("apply-filters");
  const out = document.getElementById("screener-results");
  async function run() {
    const q = document.getElementById("q").value;
    const minGap = document.getElementById("min-gap").value;
    const minVol = document.getElementById("min-vol").value;
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (minGap) params.set("min_gap", minGap);
    if (minVol) params.set("min_volume", minVol);
    params.set("limit", "30");
    const data = await getJSON(`/stocks?${params.toString()}`);
    out.innerHTML = data.items.map(stockCard).join("");
  }
  btn.addEventListener("click", run);
  run();
}

function renderStock() {
  const params = new URLSearchParams(location.search);
  const symbol = params.get("symbol") || "RELIANCE";
  const title = document.getElementById("stock-title");
  title.textContent = `${symbol} · Stock Detail`;

  getJSON(`/stocks/${encodeURIComponent(symbol)}`).then(s => {
    const k = document.getElementById("stock-metrics");
    k.innerHTML = `
      <div class="wf-kv"><span>Price</span><span id="rt-price">${s.price.toFixed(2)}</span></div>
      <div class="wf-kv"><span>% Gap</span><span>${s.gap.toFixed(2)}%</span></div>
      <div class="wf-kv"><span>Volume</span><span>${s.volume}</span></div>
      <div class="wf-kv"><span>VWAP</span><span>${s.vwap.toFixed(2)}</span></div>
      <div class="wf-kv"><span>RSI</span><span>${s.rsi.toFixed(1)}</span></div>
      <div class="wf-kv"><span>MA20/50/200</span><span>${s.ma20.toFixed(2)} / ${s.ma50.toFixed(2)} / ${s.ma200.toFixed(2)}</span></div>
      <div class="wf-kv"><span>Entry/SL/Target</span><span>${s.signal.entry} / ${s.signal.sl} / ${s.signal.target}</span></div>
      <div class="wf-kv"><span>Sentiment</span><span>${s.sentiment}</span></div>
    `;
    // Alerts list
    const al = document.getElementById("stock-alerts");
    al.innerHTML = s.alerts.map(a => `<li class="wf-alert ${a.severity}"><div>${a.message}</div><div class="wf-tag">${new Date(a.ts).toLocaleTimeString()}</div></li>`).join("");
  });

  // WebSocket realtime simulation
  const badge = document.getElementById("realtime-badge");
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/price?symbol=${encodeURIComponent(symbol)}`);
  ws.onopen = () => { badge.textContent = "RT: live"; };
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    const el = document.getElementById("rt-price");
    if (el) el.textContent = data.price.toFixed(2);
  };
  ws.onclose = () => { badge.textContent = "RT: disconnected"; };
}

function renderAlerts() {
  getJSON("/alerts").then(data => {
    const ul = document.getElementById("alerts-list");
    ul.innerHTML = data.items.map(a => `<li class="wf-alert ${a.severity}"><div><strong>${a.symbol}</strong> ${a.message}</div><div class="wf-tag">${new Date(a.ts).toLocaleString()}</div></li>`).join("");
  });
}

function renderJournal() {
  const tbody = document.querySelector("#journal-table tbody");
  getJSON("/journal").then(data => {
    tbody.innerHTML = data.items.map(r => `<tr>
      <td>${new Date(r.date).toLocaleDateString()}</td>
      <td>${r.symbol}</td>
      <td>${r.direction}</td>
      <td>${r.entry}</td>
      <td>${r.sl}</td>
      <td>${r.target}</td>
      <td>${r.exit ?? "-"}</td>
      <td>${r.pnl}</td>
    </tr>`).join("");
  });
}

function renderSettings() {
  getJSON("/settings").then(s => {
    document.getElementById("telegram-status").textContent = `Telegram: ${s.telegram_linked ? "linked" : "not linked"}`;
  });
  document.getElementById("save-settings").addEventListener("click", () => alert("Saved (wireframe)"));
  document.getElementById("link-telegram").addEventListener("click", () => alert("Link flow (wireframe)"));
  document.getElementById("upstox-config").addEventListener("click", () => alert("Upstox config (wireframe)"));
}

document.addEventListener("DOMContentLoaded", () => {
  setActiveNav();
  const page = document.documentElement.getAttribute("data-page");
  if (page === "overview") renderOverview();
  if (page === "screener") renderScreener();
  if (page === "stock") renderStock();
  if (page === "alerts") renderAlerts();
  if (page === "journal") renderJournal();
  if (page === "settings") renderSettings();
});
