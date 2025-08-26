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
  loadSettingsData().then(() => {
    // Setup modals after settings are loaded
    setupUpstoxModal();
    setupTelegramModal();
    // Load threshold values
    loadThresholds();
  });
  
  const saveBtn = document.getElementById("save-settings");
  
  if (saveBtn) {
    // Remove any existing event listeners
    saveBtn.replaceWith(saveBtn.cloneNode(true));
    const newSaveBtn = document.getElementById("save-settings");
    
    newSaveBtn.addEventListener("click", () => {
      saveThresholds();
    });
  }
}

async function loadSettingsData() {
  try {
    const s = await getJSON("/settings");
    
    const telegramStatus = document.getElementById("telegram-status");
    if (telegramStatus) {
      telegramStatus.textContent = `Telegram: ${s.telegram_linked ? "linked" : "not linked"}`;
    }
    
    // Update Telegram button and status
    const telegramBtn = document.getElementById("link-telegram");
    const telegramStatusEl = document.getElementById("telegram-status");
    
    if (telegramBtn) {
      telegramBtn.textContent = s.telegram_linked ? "Reconfigure" : "Link";
    }
    
    if (telegramStatusEl) {
      if (s.telegram_linked) {
        telegramStatusEl.innerHTML = `<span class="wf-status-indicator connected">Connected - Alerts Active</span> Bot ready to send notifications`;
      } else {
        telegramStatusEl.innerHTML = `Send alerts to your chat.`;
      }
    }
    
    // Update Upstox status
    const statusEl = document.getElementById("upstox-status");
    const configBtn = document.getElementById("upstox-config");
    
    if (statusEl && configBtn) {
      if (s.upstox_connected) {
        const expiryDate = new Date(s.upstox_token_expiry).toLocaleDateString();
        statusEl.innerHTML = `<span class="wf-status-indicator connected">Connected - Real Data</span> Token expires: ${expiryDate}`;
        configBtn.textContent = "Reconfigure";
      } else {
        statusEl.innerHTML = `<span class="wf-status-indicator disconnected">Not Connected - Mock Data</span> Configure for real-time market data`;
        configBtn.textContent = "Configure";
      }
    }
  } catch (error) {
    console.error("Error loading settings:", error);
  }
}

function setupUpstoxModal() {
  const modal = document.getElementById("upstox-modal");
  const configBtn = document.getElementById("upstox-config");
  const closeBtn = document.getElementById("close-modal");
  const cancelBtn = document.getElementById("cancel-upstox");
  const saveBtn = document.getElementById("save-upstox");
  const disconnectBtn = document.getElementById("disconnect-upstox");
  const testBtn = document.getElementById("test-upstox");

  if (!modal || !configBtn) {
    return;
  }

  // Prevent duplicate event listeners
  if (configBtn.dataset.listenerAttached === "true") {
    return;
  }

  // Open modal
  configBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    
    // Set a flag to prevent immediate closing
    window.modalJustOpened = true;
    
    // Show modal with proper CSS classes
    modal.style.display = "flex";
    modal.classList.add("show");
    
    // Clear the flag after a short delay
    setTimeout(() => {
      window.modalJustOpened = false;
    }, 500);
    
    // Show buttons if Upstox is connected
    if (disconnectBtn) {
      disconnectBtn.style.display = "inline-block";
    }
    if (testBtn) {
      testBtn.style.display = "inline-block";
    }
    
    // Check if already configured
    try {
      const settings = await getJSON("/settings");
      if (!settings.upstox_connected) {
        if (disconnectBtn) disconnectBtn.style.display = "none";
        if (testBtn) testBtn.style.display = "none";
      }
    } catch (error) {
      // Keep buttons visible on error
    }
  });

  // Mark event listener as attached
  configBtn.dataset.listenerAttached = "true";

  // Close modal function
  const closeModal = () => {
    // Prevent closing if modal was just opened
    if (window.modalJustOpened) {
      return;
    }
    
    if (modal) {
      modal.classList.remove("show");
      setTimeout(() => {
        modal.style.display = "none";
      }, 300);
    }
    
    // Clear form
    const accessToken = document.getElementById("access-token");
    const apiKey = document.getElementById("api-key");
    const apiSecret = document.getElementById("api-secret");
    
    if (accessToken) accessToken.value = "";
    if (apiKey) apiKey.value = "";
    if (apiSecret) apiSecret.value = "";
    
    if (disconnectBtn) {
      disconnectBtn.style.display = "none";
    }
  };

  // Close button events
  if (closeBtn) {
    closeBtn.addEventListener("click", closeModal);
  }
  
  if (cancelBtn) {
    cancelBtn.addEventListener("click", closeModal);
  }

  // Save configuration
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      console.log("Save button clicked!");
      
      const accessTokenEl = document.getElementById("access-token");
      const apiKeyEl = document.getElementById("api-key");
      const apiSecretEl = document.getElementById("api-secret");
      
      if (!accessTokenEl) {
        alert("Form elements not found!");
        return;
      }
      
      const accessToken = accessTokenEl.value.trim();
      
      if (!accessToken) {
        alert("Access token is required!");
        return;
      }

      try {
        console.log("Sending configuration...");
        const response = await fetch("/api/settings/upstox", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            access_token: accessToken,
            api_key: apiKeyEl ? apiKeyEl.value.trim() : "",
            api_secret: apiSecretEl ? apiSecretEl.value.trim() : "",
          }),
        });

        const result = await response.json();
        console.log("Response:", result);

        if (response.ok) {
          alert("Upstox configuration saved successfully!");
          closeModal();
          loadSettingsData(); // Refresh status
        } else {
          alert(`Error: ${result.detail}`);
        }
      } catch (error) {
        console.error("Network error:", error);
        alert(`Network error: ${error.message}`);
      }
    });
  }

  // Disconnect
  if (disconnectBtn) {
    disconnectBtn.addEventListener("click", async () => {
      if (confirm("Are you sure you want to disconnect Upstox?")) {
        try {
          const response = await fetch("/api/settings/upstox", {
            method: "DELETE",
          });

          const result = await response.json();

          if (response.ok) {
            alert("Upstox disconnected successfully!");
            closeModal();
            loadSettingsData(); // Refresh status
          } else {
            alert(`Error: ${result.detail}`);
          }
        } catch (error) {
          alert(`Network error: ${error.message}`);
        }
      }
    });
  }

  // Test connection
  if (testBtn) {
    testBtn.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/settings/upstox/test", {
          method: "POST",
        });

        const result = await response.json();

        if (response.ok && result.success) {
          alert(`✅ Connection successful!\n\nUser: ${result.user_name || 'Unknown'}\nBroker: ${result.broker || 'Unknown'}\n\nUpstox API is working correctly!`);
        } else {
          alert(`❌ Connection failed!\n\n${result.message || 'Unknown error'}\n\nPlease check your access token.`);
        }
      } catch (error) {
        alert(`❌ Network error: ${error.message}`);
      }
    });
  }

  // Close modal on outside click
  if (modal) {
    modal.addEventListener("click", (e) => {
      // Only close if clicking the modal backdrop (not the content)
      // AND the modal wasn't just opened
      if (e.target === modal && !window.modalJustOpened) {
        closeModal();
      }
    });
  }
}

function setupTelegramModal() {
  console.log("Setting up Telegram modal...");
  
  const modal = document.getElementById("telegram-modal");
  const telegramBtn = document.getElementById("link-telegram");
  const closeBtn = document.getElementById("close-telegram-modal");
  const cancelBtn = document.getElementById("cancel-telegram");
  const saveBtn = document.getElementById("save-telegram");
  const disconnectBtn = document.getElementById("disconnect-telegram");
  const testBtn = document.getElementById("test-telegram");

  console.log("Telegram modal elements:", {
    modal: !!modal,
    telegramBtn: !!telegramBtn,
    closeBtn: !!closeBtn,
    cancelBtn: !!cancelBtn,
    saveBtn: !!saveBtn,
    disconnectBtn: !!disconnectBtn,
    testBtn: !!testBtn
  });

  if (!modal || !telegramBtn) {
    console.error("Required Telegram modal elements not found!");
    return;
  }

  const botTokenInput = document.getElementById("bot-token");
  const chatIdInput = document.getElementById("chat-id");

  function closeModal() {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.style.display = "none";
      // Clear form
      if (botTokenInput) botTokenInput.value = "";
      if (chatIdInput) chatIdInput.value = "";
      // Hide disconnect button
      if (disconnectBtn) disconnectBtn.style.display = "none";
    }, 300);
  }

  // Open modal
  telegramBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    console.log("Telegram button clicked!");
    
    try {
      // Check current status
      const status = await getJSON("/settings/telegram/status");
      console.log("Telegram status:", status);
      
      if (status.connected) {
        // Show disconnect and test buttons for existing config
        if (disconnectBtn) disconnectBtn.style.display = "inline-block";
        if (testBtn) testBtn.style.display = "inline-block";
      } else {
        // Hide disconnect and test buttons for new config
        if (disconnectBtn) disconnectBtn.style.display = "none";
        if (testBtn) testBtn.style.display = "none";
      }
      
      // Show modal
      modal.style.display = "flex";
      setTimeout(() => modal.classList.add("show"), 10);
    } catch (error) {
      console.error("Error checking Telegram status:", error);
      modal.style.display = "flex";
      setTimeout(() => modal.classList.add("show"), 10);
    }
  });

  // Close buttons
  if (closeBtn) {
    closeBtn.addEventListener("click", closeModal);
  }
  if (cancelBtn) {
    cancelBtn.addEventListener("click", closeModal);
  }

  // Save configuration
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const botToken = botTokenInput?.value.trim();
      const chatId = chatIdInput?.value.trim();

      if (!botToken || !chatId) {
        alert("Please fill in all required fields");
        return;
      }

      try {
        const response = await fetch("/api/settings/telegram", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            bot_token: botToken,
            chat_id: chatId,
          }),
        });

        const result = await response.json();

        if (response.ok) {
          alert("Telegram configuration saved successfully!");
          closeModal();
          loadSettingsData(); // Refresh status
        } else {
          alert(`Error: ${result.detail}`);
        }
      } catch (error) {
        console.error("Network error:", error);
        alert(`Network error: ${error.message}`);
      }
    });
  }

  // Disconnect
  if (disconnectBtn) {
    disconnectBtn.addEventListener("click", async () => {
      if (confirm("Are you sure you want to disconnect Telegram?")) {
        try {
          const response = await fetch("/api/settings/telegram", {
            method: "DELETE",
          });

          const result = await response.json();

          if (response.ok) {
            alert("Telegram disconnected successfully!");
            closeModal();
            loadSettingsData(); // Refresh status
          } else {
            alert(`Error: ${result.detail}`);
          }
        } catch (error) {
          alert(`Network error: ${error.message}`);
        }
      }
    });
  }

  // Test message
  if (testBtn) {
    testBtn.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/settings/telegram/test", {
          method: "POST",
        });

        const result = await response.json();

        if (response.ok) {
          alert("Test message sent! Check your Telegram chat.");
        } else {
          alert(`Error: ${result.detail}`);
        }
      } catch (error) {
        alert(`Network error: ${error.message}`);
      }
    });
  }

  // Close modal on outside click
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        closeModal();
      }
    });
  }
}

// Alert/notification function
function showAlert(message, type = "info") {
  // Create alert element using your existing design system
  const alert = document.createElement("div");
  alert.className = "wf-alert";
  
  // Add type-specific styling that matches your CSS variables
  if (type === "success") {
    alert.style.borderColor = "var(--buy)"; // Green border only
    alert.style.color = "var(--text)"; // Keep text in default color
  } else if (type === "error") {
    alert.style.borderColor = "var(--sell)"; // Red border
    alert.style.color = "var(--sell)"; // Red text for errors
  } else {
    alert.style.borderColor = "var(--outline)"; // Default border
    alert.style.color = "var(--text)";
  }
  
  // Position as toast notification
  alert.style.cssText += `
    position: fixed;
    top: 20px;
    right: 20px;
    background: var(--card);
    z-index: 1000;
    max-width: 300px;
    word-wrap: break-word;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  `;
  
  alert.textContent = message;
  
  // Add to page
  document.body.appendChild(alert);
  
  // Remove after 3 seconds
  setTimeout(() => {
    if (alert && alert.parentNode) {
      alert.parentNode.removeChild(alert);
    }
  }, 3000);
}

// Threshold management functions
async function saveThresholds() {
  try {
    const gapInput = document.getElementById("th-gap");
    const rsiInput = document.getElementById("th-rsi");
    
    if (!gapInput || !rsiInput) {
      showAlert("Threshold input fields not found", "error");
      return;
    }
    
    const gap = parseFloat(gapInput.value);
    const rsi = parseInt(rsiInput.value);
    
    // Validation
    if (isNaN(gap) || gap <= 0 || gap > 100) {
      showAlert("Gap % must be a number between 0 and 100", "error");
      return;
    }
    
    if (isNaN(rsi) || rsi < 1 || rsi > 100) {
      showAlert("RSI must be a number between 1 and 100", "error");
      return;
    }
    
    const response = await fetch("/api/settings/thresholds", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        gap: gap,
        rsi: rsi
      })
    });
    
    const result = await response.json();
    
    if (response.ok) {
      showAlert("Threshold settings saved successfully!", "success");
    } else {
      showAlert(result.detail || "Failed to save threshold settings", "error");
    }
  } catch (error) {
    console.error("Error saving thresholds:", error);
    showAlert("Error saving threshold settings", "error");
  }
}

async function loadThresholds() {
  try {
    const response = await fetch("/api/settings/thresholds");
    const thresholds = await response.json();
    
    if (response.ok) {
      const gapInput = document.getElementById("th-gap");
      const rsiInput = document.getElementById("th-rsi");
      
      if (gapInput) gapInput.value = thresholds.gap || 5.0;
      if (rsiInput) rsiInput.value = thresholds.rsi || 30;
    }
  } catch (error) {
    console.error("Error loading thresholds:", error);
    // Set default values if loading fails
    const gapInput = document.getElementById("th-gap");
    const rsiInput = document.getElementById("th-rsi");
    
    if (gapInput) gapInput.value = 5.0;
    if (rsiInput) rsiInput.value = 30;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM Content Loaded - JavaScript executing...");
  setActiveNav();
  const page = document.documentElement.getAttribute("data-page");
  console.log("Current page:", page);
  
  if (page === "overview") renderOverview();
  if (page === "screener") renderScreener();
  if (page === "stock") renderStock();
  if (page === "alerts") renderAlerts();
  if (page === "journal") renderJournal();
  if (page === "settings") {
    console.log("Loading settings page...");
    renderSettings();
  }
});

// Add window load event as backup
window.addEventListener("load", () => {
  console.log("Window loaded - backup initialization");
  const page = document.documentElement.getAttribute("data-page");
  if (page === "settings") {
    // Double check that settings is loaded
    const configBtn = document.getElementById("upstox-config");
    console.log("Settings page - config button found:", !!configBtn);
    if (!configBtn) {
      console.error("Configure button not found after window load!");
    }
  }
});
