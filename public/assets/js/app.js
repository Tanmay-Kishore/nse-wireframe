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
  // Helper function to safely format numbers
  const formatNumber = (value, decimals = 2) => {
    if (value == null || value === undefined || isNaN(value)) return "-";
    return Number(value).toFixed(decimals);
  };
  
  const formatVolume = (volume) => {
    if (!volume || volume === 0) return "-";
    return Number(volume).toLocaleString();
  };
  
  return `<div class="wf-stock-card">
    <div class="wf-stock-head">
      <div><strong>${s.symbol}</strong> <span class="wf-tag">${s.name || ""}</span></div>
      <div class="wf-pill ${s.signal?.direction === "BUY" ? "buy" : (s.signal?.direction === "SELL" ? "sell" : "")}">
        ${s.signal?.direction || "HOLD"}
      </div>
    </div>
    <div class="wf-metrics">
      <div class="wf-kv"><span>Price</span><span>₹${formatNumber(s.price, 2)}</span></div>
      <div class="wf-kv"><span>Volume</span><span>${formatVolume(s.volume)}</span></div>
      <div class="wf-kv"><span>Gap</span><span>${formatNumber(s.gap, 2)}%</span></div>
      <div class="wf-kv"><span>VWAP</span><span>₹${formatNumber(s.vwap, 2)}</span></div>
      <div class="wf-kv"><span>RSI</span><span>${formatNumber(s.rsi, 1)}</span></div>
      <div class="wf-kv compact"><span>Bollinger</span><span>${formatNumber(s.bb_upper, 0)}/${formatNumber(s.bb_lower, 0)}</span></div>
      <div class="wf-kv compact wf-metrics-wide"><span>MA20/50/200</span><span>${formatNumber(s.ma20, 0)}/${formatNumber(s.ma50, 0)}/${formatNumber(s.ma200, 0)}</span></div>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:auto">
      <span class="wf-tag">Entry: ${formatNumber(s.signal?.entry, 2)}</span>
      <span class="wf-tag">SL: ${formatNumber(s.signal?.sl, 2)}</span>
      <span class="wf-tag">Target: ${formatNumber(s.signal?.target, 2)}</span>
      <a class="wf-btn" href="/stock.html?symbol=${encodeURIComponent(s.symbol)}">Open</a>
      <button class="wf-pill-btn remove" onclick="removeFromWatchlist('${s.symbol}')">Remove</button>
    </div>
  </div>`;
}

function renderOverview() {
  // Indexes section
  getJSON("/index-quotes").then(data => {
    const grid = document.getElementById("indexes-grid");
    if (!grid) return;
    grid.innerHTML = Object.entries(data).map(([symbol, idx]) => {
      if (idx.error) {
        return `<div class="wf-stock-card"><div class="wf-stock-head"><strong>${symbol}</strong></div><div class="wf-metrics"><span class="wf-tag">Error: ${idx.error}</span></div></div>`;
      }
      const live = idx.live_ohlc || {};
      const prev = idx.prev_ohlc || {};
      // Determine price movement
        let pillClass = "";
        let pillText = "-";
        const last = Number(idx.last_price);
        const prevClose = Number(prev.close);
        const open = Number(live.open);
        if (!isNaN(last)) {
          if (!isNaN(prevClose)) {
            if (last > prevClose) {
              pillClass = "buy";
              pillText = "▲";
            } else if (last < prevClose) {
              pillClass = "sell";
              pillText = "▼";
            } else {
              pillClass = "";
              pillText = "■";
            }
          } else if (!isNaN(open)) {
            if (last > open) {
              pillClass = "buy";
              pillText = "▲";
            } else if (last < open) {
              pillClass = "sell";
              pillText = "▼";
            } else {
              pillClass = "";
              pillText = "■";
            }
          } else {
            pillClass = "";
            pillText = "■";
          }
        }
        return `<div class="wf-stock-card">
          <div class="wf-stock-head">
            <div><strong>${symbol}</strong></div>
            <div class="wf-pill ${pillClass}">${pillText}</div>
          </div>
          <div class="wf-metrics">
            <div class="wf-kv"><span>Last</span><span>${idx.last_price ?? '-'}</span></div>
            <div class="wf-kv"><span>Open</span><span>${live.open ?? '-'}</span></div>
            <div class="wf-kv"><span>High</span><span>${live.high ?? '-'}</span></div>
            <div class="wf-kv"><span>Low</span><span>${live.low ?? '-'}</span></div>
            <div class="wf-kv"><span>Close</span><span>${live.close ?? '-'}</span></div>
            <div class="wf-kv"><span>Volume</span><span>${live.volume ?? '-'}</span></div>
          </div>
        </div>`;
    }).join("");
  }).catch(console.error);


  // Market snapshot: NIFTY top gainers and losers
  const ms = document.getElementById("market-snapshot");
  if (ms) {
    getJSON("/nifty-movers").then(data => {
      // Format numbers nicely
      const formatPrice = (price) => {
        if (!price || price === 0) return "-";
        return "₹" + Number(price).toFixed(2);
      };

      const formatChange = (change) => {
        if (change == null) return "-";
        const num = Number(change);
        const sign = num > 0 ? "+" : "";
        return `${sign}${num.toFixed(2)}%`;
      };

      const formatVolume = (volume) => {
        if (!volume || volume === 0) return "-";
        const num = Number(volume);
        if (num >= 10000000) { // 1 crore
          return `${(num / 10000000).toFixed(1)}Cr`;
        } else if (num >= 100000) { // 1 lakh
          return `${(num / 100000).toFixed(1)}L`;
        } else if (num >= 1000) { // 1 thousand
          return `${(num / 1000).toFixed(1)}K`;
        }
        return num.toLocaleString();
      };

      let html = '';

      // Show top 8 gainers
      html += data.gainers.slice(0, 8).map(g => `<div class="wf-mover-card">
        <div class="wf-mover-header">
          <span class="wf-mover-symbol">${g.symbol}</span>
          <span class="wf-mover-badge gainer">Gainer</span>
        </div>
        <div class="wf-mover-metrics">
          <div class="wf-mover-metric">
            <span class="wf-mover-metric-label">Last</span>
            <span class="wf-mover-metric-value">${formatPrice(g.ltp)}</span>
          </div>
          <div class="wf-mover-metric">
            <span class="wf-mover-metric-label">Change</span>
            <span class="wf-mover-metric-value positive">${formatChange(g.perChange)}</span>
          </div>
          <div class="wf-mover-metric">
            <span class="wf-mover-metric-label">Volume</span>
            <span class="wf-mover-metric-value">${formatVolume(g.trade_quantity)}</span>
          </div>
        </div>
      </div>`).join("");

      // Show top 7 losers
      html += data.losers.slice(0, 7).map(l => `<div class="wf-mover-card">
        <div class="wf-mover-header">
          <span class="wf-mover-symbol">${l.symbol}</span>
          <span class="wf-mover-badge loser">Loser</span>
        </div>
        <div class="wf-mover-metrics">
          <div class="wf-mover-metric">
            <span class="wf-mover-metric-label">Last</span>
            <span class="wf-mover-metric-value">${formatPrice(l.ltp)}</span>
          </div>
          <div class="wf-mover-metric">
            <span class="wf-mover-metric-label">Change</span>
            <span class="wf-mover-metric-value negative">${formatChange(l.perChange)}</span>
          </div>
          <div class="wf-mover-metric">
            <span class="wf-mover-metric-label">Volume</span>
            <span class="wf-mover-metric-value">${formatVolume(l.trade_quantity)}</span>
          </div>
        </div>
      </div>`).join("");

      ms.innerHTML = html;
    }).catch(() => {
      ms.innerHTML = '<div class="wf-skel">Could not load NIFTY movers.</div>';
    });
  }

}

function renderScreener() {
  const out = document.getElementById("screener-results");
  let stocksData = {};

  function run() {
    const params = new URLSearchParams();
    params.set("limit", "30");
    getJSON(`/stocks?${params.toString()}`).then(data => {
      // Store initial data
      data.items.forEach(stock => {
        stocksData[stock.symbol] = stock;
      });
      out.innerHTML = data.items.map(stockCard).join("");
      
      // Setup WebSocket for real-time updates
      setupScreenerWebSocket();
    });
  }

  // Global WebSocket references for cleanup
  let screenerWebSocket = null;
  let stockDetailWebSocket = null;

  function setupScreenerWebSocket() {
    // Close existing WebSocket if any
    if (screenerWebSocket) {
      screenerWebSocket.close();
      screenerWebSocket = null;
    }

    const badge = document.getElementById("screener-realtime-badge");
    screenerWebSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/screener`);

    screenerWebSocket.onopen = () => {
      console.log("Screener WebSocket connected");
      if (badge) badge.textContent = "RT: live";
    };

    screenerWebSocket.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.type === "stock_update" && data.symbol && data.data) {
        // Update stored data
        stocksData[data.symbol] = data.data;

        // Find the stock card element and update it
        updateStockCard(data.symbol, data.data);
      }
    };

    screenerWebSocket.onclose = () => {
      console.log("Screener WebSocket disconnected");
      if (badge) badge.textContent = "RT: disconnected";

      // Only attempt to reconnect if still on screener page
      setTimeout(() => {
        if (document.documentElement.getAttribute("data-page") === "screener" && screenerWebSocket && screenerWebSocket.readyState === WebSocket.CLOSED) {
          if (badge) badge.textContent = "RT: reconnecting";
          setupScreenerWebSocket();
        }
      }, 3000);
    };

    screenerWebSocket.onerror = (error) => {
      console.error("Screener WebSocket error:", error);
      if (badge) badge.textContent = "RT: error";
    };
  }

  function cleanupScreenerWebSocket() {
    if (screenerWebSocket) {
      console.log("Cleaning up screener WebSocket");
      screenerWebSocket.close();
      screenerWebSocket = null;

      const badge = document.getElementById("screener-realtime-badge");
      if (badge) badge.textContent = "RT: disconnected";
    }
  }

  function updateStockCard(symbol, stockData) {
    // Find the existing card by looking for the symbol in the stock cards
    const cards = out.querySelectorAll('.wf-stock-card');
    for (let card of cards) {
      const symbolElement = card.querySelector('strong');
      if (symbolElement && symbolElement.textContent === symbol) {
        // Replace the entire card with updated data
        const newCardHTML = stockCard(stockData);
        card.outerHTML = newCardHTML;
        break;
      }
    }
  }

  run();
}

async function removeFromWatchlist(symbol) {
  try {
    const result = await fetch(`${API_BASE}/watchlist/remove?symbol=${encodeURIComponent(symbol)}`, {
      method: "POST"
    });
    
    if (result.ok) {
      // Reload the page to refresh the watchlist
      location.reload();
    } else {
      console.error("Failed to remove from watchlist");
      alert("Failed to remove from watchlist");
    }
  } catch (error) {
    console.error("Error removing from watchlist:", error);
    alert("Error removing from watchlist");
  }
}

async function setupCandlestickChart(symbol) {
  const chartContainer = document.getElementById('chart-container');
  if (!chartContainer) {
    console.log("Chart container not found");
    return;
  }

  // Check if LightweightCharts is available
  if (!window.LightweightCharts) {
    console.log("LightweightCharts not loaded, waiting...");
    // Wait for the library to load
    setTimeout(() => setupCandlestickChart(symbol), 500);
    return;
  }
  
  console.log("LightweightCharts available:", typeof window.LightweightCharts);
  console.log("createChart method:", typeof window.LightweightCharts.createChart);

  try {
    console.log(`Setting up chart for ${symbol}...`);
    
    // Fetch chart data
    const chartData = await getJSON(`/stocks/${encodeURIComponent(symbol)}/chart`);
    console.log("Chart data received:", chartData);
    
    if (!chartData || !chartData.data || chartData.data.length === 0) {
      console.log("No chart data available");
      chartContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">No chart data available</div>';
      return;
    }

    // Clear container first
    chartContainer.innerHTML = '';

    // Create chart
    const chart = LightweightCharts.createChart(chartContainer, {
      width: chartContainer.offsetWidth,
      height: 400,
      layout: {
        backgroundColor: '#222',
        textColor: '#DDD',
      },
      grid: {
        vertLines: { 
          color: 'rgba(70, 130, 180, 0.5)',
          style: 1,
        },
        horzLines: { 
          color: 'rgba(70, 130, 180, 0.5)',
          style: 1,
        },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {
          color: '#758696',
        },
        horzLine: {
          color: '#758696',
        },
      },
      priceScale: {
        borderColor: '#485c7b',
      },
      timeScale: {
        borderColor: '#485c7b',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#4bffb5',
      downColor: '#ff4976',
      borderDownColor: '#ff4976',
      borderUpColor: '#4bffb5',
      wickDownColor: '#ff4976',
      wickUpColor: '#4bffb5',
    });

    // Process and set data
    const processedData = chartData.data
      .map(item => {
        console.log("Processing data item:", item);
        
        // Ensure all values are valid numbers
        const open = parseFloat(item.open);
        const high = parseFloat(item.high);
        const low = parseFloat(item.low);
        const close = parseFloat(item.close);
        
        // Skip invalid data points
        if (isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
          console.warn("Skipping invalid data point:", item);
          return null;
        }
        
        // Ensure high >= max(open, close) and low <= min(open, close)
        const actualHigh = Math.max(high, open, close);
        const actualLow = Math.min(low, open, close);
        
        return {
          time: item.time, // Date format: YYYY-MM-DD
          open: open,
          high: actualHigh,
          low: actualLow,
          close: close,
        };
      })
      .filter(item => item !== null) // Remove invalid items
      .sort((a, b) => a.time.localeCompare(b.time)); // Sort by date

    console.log("Processed data for chart:", processedData);
    console.log("Sample data point:", processedData[0]);
    
    if (processedData.length === 0) {
      chartContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">No valid chart data available</div>';
      return;
    }
    
    candlestickSeries.setData(processedData);

    // Fit content to show the data
    chart.timeScale().fitContent();

    // Make chart responsive
    const resizeChart = () => {
      chart.applyOptions({ width: chartContainer.offsetWidth });
    };

    window.addEventListener('resize', resizeChart);

    console.log(`Chart created successfully for ${symbol} with ${processedData.length} data points`);
    
    // Add a small delay to ensure the chart renders properly
    setTimeout(() => {
      chart.timeScale().fitContent();
    }, 100);

  } catch (error) {
    console.error("Error setting up candlestick chart:", error);
    chartContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">Failed to load chart: ' + error.message + '</div>';
  }
}

async function setupWatchlistButton(symbol) {
  const btn = document.getElementById("watchlist-btn");
  if (!btn) return;
  
  try {
    // Check current watchlist status
    const response = await getJSON(`/watchlist/check/${encodeURIComponent(symbol)}`);
    const inWatchlist = response.in_watchlist;
    
    // Set button text and style
    if (inWatchlist) {
      btn.textContent = "Remove from Watchlist";
      btn.className = "wf-pill-btn remove";
      btn.style.background = "";
      btn.style.borderColor = "";
      btn.style.color = "";
    } else {
      btn.textContent = "Add to Watchlist";
      btn.className = "wf-pill-btn add";
      btn.style.background = "";
      btn.style.borderColor = "";
      btn.style.color = "";
    }
    
    // Add click handler
    btn.onclick = async () => {
      try {
        btn.disabled = true;
        btn.textContent = "Loading...";
        
        if (inWatchlist) {
          // Remove from watchlist
          const result = await fetch(`${API_BASE}/watchlist/remove?symbol=${encodeURIComponent(symbol)}`, {
            method: "POST"
          });
          if (result.ok) {
            btn.textContent = "Add to Watchlist";
            btn.className = "wf-pill-btn add";
            btn.onclick = () => location.reload(); // Quick refresh
          }
        } else {
          // Add to watchlist  
          const result = await fetch(`${API_BASE}/watchlist/add?symbol=${encodeURIComponent(symbol)}`, {
            method: "POST"
          });
          if (result.ok) {
            btn.textContent = "Remove from Watchlist";
            btn.className = "wf-pill-btn remove";
            btn.onclick = () => location.reload(); // Quick refresh
          }
        }
        
        btn.disabled = false;
      } catch (error) {
        console.error("Error updating watchlist:", error);
        btn.disabled = false;
        btn.textContent = "Error";
      }
    };
    
  } catch (error) {
    console.error("Error setting up watchlist button:", error);
    btn.textContent = "Error";
  }
}

function renderStock() {
  // Search bar suggestions logic (older screener style)
  const qInput = document.getElementById("q");
  const suggestionsBox = document.getElementById("search-suggestions");
  let instruments = [];

  // Load instruments.json for suggestions
  fetch("/data/instruments.json")
    .then(res => res.json())
    .then(data => { instruments = data; })
    .catch(() => { instruments = []; });

  let suggestionIndex = -1;
  let currentSuggestions = [];
  let suggestionsOpen = false;

  function showSuggestions(query) {
    if (!query || !instruments.length) {
      suggestionsBox.style.display = "none";
      suggestionsBox.innerHTML = "";
      currentSuggestions = [];
      suggestionIndex = -1;
      suggestionsOpen = false;
      return;
    }
    const q = query.trim().toLowerCase();
    const matches = instruments.filter(inst =>
      inst.tradingsymbol.toLowerCase().includes(q) ||
      (inst.name && inst.name.toLowerCase().includes(q))
    ).slice(0, 8);
    currentSuggestions = matches;
    suggestionIndex = matches.length ? 0 : -1;
    if (!matches.length) {
      suggestionsBox.style.display = "none";
      suggestionsBox.innerHTML = "";
      suggestionsOpen = false;
      return;
    }
    suggestionsBox.innerHTML = matches.map((inst, i) =>
      `<div class="wf-suggestion-item${i === suggestionIndex ? ' active' : ''}" data-symbol="${inst.tradingsymbol}">
        <strong>${inst.tradingsymbol}</strong> <span style=\"color:#aaa\">${inst.name}</span>
      </div>`
    ).join("");
    suggestionsBox.style.display = "block";
    suggestionsOpen = true;
  }

  function run(selectedSymbol) {
    const q = selectedSymbol || qInput.value;
    window.location.href = `/stock.html?symbol=${encodeURIComponent(q)}`;
    suggestionsBox.style.display = "none";
  }

  if (qInput && suggestionsBox) {
    qInput.addEventListener("input", e => {
      showSuggestions(e.target.value);
    });
    suggestionsBox.addEventListener("mousedown", e => {
      const item = e.target.closest(".wf-suggestion-item");
      if (item) {
        qInput.value = item.dataset.symbol;
        run(item.dataset.symbol);
        suggestionsBox.style.display = "none";
        suggestionsOpen = false;
      }
    });
    qInput.addEventListener("keydown", e => {
      if (!currentSuggestions.length || !suggestionsOpen) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        suggestionIndex = (suggestionIndex + 1) % currentSuggestions.length;
        showSuggestions(qInput.value);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        suggestionIndex = (suggestionIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
        showSuggestions(qInput.value);
      } else if (e.key === "Enter") {
        if (suggestionIndex >= 0) {
          qInput.value = currentSuggestions[suggestionIndex].tradingsymbol;
          run(currentSuggestions[suggestionIndex].tradingsymbol);
          suggestionsBox.style.display = "none";
          suggestionsOpen = false;
        } else {
          run(qInput.value);
          suggestionsBox.style.display = "none";
          suggestionsOpen = false;
        }
      }
    });
    document.addEventListener("mousedown", e => {
      if (suggestionsOpen && !suggestionsBox.contains(e.target) && e.target !== qInput) {
        suggestionsBox.style.display = "none";
        suggestionsOpen = false;
      }
    });
  }
}

function renderStock() {
  // Search bar suggestions logic (older screener style)
  const qInput = document.getElementById("q");
  const suggestionsBox = document.getElementById("search-suggestions");
  let instruments = [];

  // Load instruments.json for suggestions
  fetch("/data/instruments.json")
    .then(res => res.json())
    .then(data => { instruments = data; })
    .catch(() => { instruments = []; });

  let suggestionIndex = -1;
  let currentSuggestions = [];
  let suggestionsOpen = false;

  function showSuggestions(query) {
    if (!query || !instruments.length) {
      suggestionsBox.style.display = "none";
      suggestionsBox.innerHTML = "";
      currentSuggestions = [];
      suggestionIndex = -1;
      suggestionsOpen = false;
      return;
    }
    const q = query.trim().toLowerCase();
    const matches = instruments.filter(inst =>
      inst.tradingsymbol.toLowerCase().includes(q) ||
      (inst.name && inst.name.toLowerCase().includes(q))
    ).slice(0, 8);
    currentSuggestions = matches;
    suggestionIndex = matches.length ? 0 : -1;
    if (!matches.length) {
      suggestionsBox.style.display = "none";
      suggestionsBox.innerHTML = "";
      suggestionsOpen = false;
      return;
    }
    suggestionsBox.innerHTML = matches.map((inst, i) =>
      `<div class="wf-suggestion-item${i === suggestionIndex ? ' active' : ''}" data-symbol="${inst.tradingsymbol}">
        <strong>${inst.tradingsymbol}</strong> <span style=\"color:#aaa\">${inst.name}</span>
      </div>`
    ).join("");
    suggestionsBox.style.display = "block";
    suggestionsOpen = true;
  }

  function run(selectedSymbol) {
    const q = selectedSymbol || qInput.value;
    window.location.href = `/stock.html?symbol=${encodeURIComponent(q)}`;
    suggestionsBox.style.display = "none";
  }

  if (qInput && suggestionsBox) {
    qInput.addEventListener("input", e => {
      showSuggestions(e.target.value);
    });
    suggestionsBox.addEventListener("mousedown", e => {
      const item = e.target.closest(".wf-suggestion-item");
      if (item) {
        qInput.value = item.dataset.symbol;
        run(item.dataset.symbol);
        suggestionsBox.style.display = "none";
        suggestionsOpen = false;
      }
    });
    qInput.addEventListener("keydown", e => {
      if (!currentSuggestions.length || !suggestionsOpen) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        suggestionIndex = (suggestionIndex + 1) % currentSuggestions.length;
        showSuggestions(qInput.value);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        suggestionIndex = (suggestionIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
        showSuggestions(qInput.value);
      } else if (e.key === "Enter") {
        if (suggestionIndex >= 0) {
          qInput.value = currentSuggestions[suggestionIndex].tradingsymbol;
          run(currentSuggestions[suggestionIndex].tradingsymbol);
          suggestionsBox.style.display = "none";
          suggestionsOpen = false;
        } else {
          run(qInput.value);
          suggestionsBox.style.display = "none";
          suggestionsOpen = false;
        }
      }
    });
    document.addEventListener("mousedown", e => {
      if (suggestionsOpen && !suggestionsBox.contains(e.target) && e.target !== qInput) {
        suggestionsBox.style.display = "none";
        suggestionsOpen = false;
      }
    });
  }
  const params = new URLSearchParams(location.search);
  const symbol = params.get("symbol") || "RELIANCE";
  const title = document.getElementById("stock-title");
  title.textContent = `${symbol} · Stock Detail`;

  // Setup watchlist button
  setupWatchlistButton(symbol);
  
  // Setup candlestick chart
  setupCandlestickChart(symbol);
  
  getJSON(`/stocks/${encodeURIComponent(symbol)}`).then(s => {
    console.log("Stock data received:", s); // Debug log
    
    // Helper function to safely format numbers
    const formatNumber = (value, decimals = 2) => {
      if (value == null || value === undefined || isNaN(value)) return "-";
      return Number(value).toFixed(decimals);
    };
    
    const formatVolume = (volume) => {
      if (!volume || volume === 0) return "-";
      return Number(volume).toLocaleString();
    };
    
    const k = document.getElementById("stock-metrics");
    k.innerHTML = `
      <div class="wf-kv"><span>Price</span><span id="rt-price">₹${formatNumber(s.price, 2)}</span></div>
      <div class="wf-kv"><span>Gap</span><span id="rt-gap">${formatNumber(s.gap, 2)}%</span></div>
      <div class="wf-kv"><span>Volume</span><span id="rt-volume">${formatVolume(s.volume)}</span></div>
      <div class="wf-kv"><span>VWAP</span><span id="rt-vwap">₹${formatNumber(s.vwap, 2)}</span></div>
      <div class="wf-kv"><span>RSI</span><span id="rt-rsi">${formatNumber(s.rsi, 1)}</span></div>
      <div class="wf-kv"><span>Bollinger</span><span>${formatNumber(s.bb_upper, 0)}/${formatNumber(s.bb_lower, 0)}</span></div>
      <div class="wf-kv"><span>MA20/50/200</span><span id="rt-ma">${formatNumber(s.ma20, 0)}/${formatNumber(s.ma50, 0)}/${formatNumber(s.ma200, 0)}</span></div>
      <div class="wf-kv"><span>Entry/SL/Target</span><span>${formatNumber(s.signal?.entry, 2)}/${formatNumber(s.signal?.sl, 2)}/${formatNumber(s.signal?.target, 2)}</span></div>
      <div class="wf-kv"><span>Sentiment</span><span>${s.sentiment || "NEUTRAL"}</span></div>
    `;
    
    // Alerts list - handle missing alerts gracefully
    const al = document.getElementById("stock-alerts");
    if (al && s.alerts && Array.isArray(s.alerts)) {
      al.innerHTML = s.alerts.map(a => `<li class="wf-alert ${a.severity}"><div>${a.message}</div><div class="wf-tag">${new Date(a.ts).toLocaleTimeString()}</div></li>`).join("");
    } else if (al) {
      al.innerHTML = "<li>No alerts yet</li>";
    }
  }).catch(error => {
    console.error("Error loading stock data:", error);
    const k = document.getElementById("stock-metrics");
    if (k) {
      k.innerHTML = `<div class="wf-kv"><span>Error</span><span>Failed to load stock data</span></div>`;
    }
  });

  // WebSocket setup for stock detail page
  function setupStockWebSocket() {
    // Close existing WebSocket if any
    if (stockDetailWebSocket) {
      stockDetailWebSocket.close();
      stockDetailWebSocket = null;
    }

    const badge = document.getElementById("realtime-badge");
    if (!badge) return; // No badge element, not on stock page

    stockDetailWebSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/price?symbol=${encodeURIComponent(symbol)}`);

    stockDetailWebSocket.onopen = () => {
      badge.textContent = "RT: live";
      console.log("Stock detail WebSocket connected for", symbol);
    };

    stockDetailWebSocket.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.price !== undefined) {
        const el = document.getElementById("rt-price");
        if (el) el.textContent = Number(data.price).toFixed(2);
      }
      if (data.tick) {
        if (data.tick.gap !== undefined) {
          const gapEl = document.getElementById("rt-gap");
          if (gapEl) gapEl.textContent = Number(data.tick.gap).toFixed(2) + "%";
        }
        if (data.tick.volume !== undefined) {
          const volEl = document.getElementById("rt-volume");
          if (volEl) volEl.textContent = data.tick.volume;
        }
        if (data.tick.vwap !== undefined) {
          const vwapEl = document.getElementById("rt-vwap");
          if (vwapEl) vwapEl.textContent = Number(data.tick.vwap).toFixed(2);
        }
        if (data.tick.rsi !== undefined) {
          const rsiEl = document.getElementById("rt-rsi");
          if (rsiEl) rsiEl.textContent = Number(data.tick.rsi).toFixed(1);
        }
        if (data.tick.ma20 !== undefined && data.tick.ma50 !== undefined && data.tick.ma200 !== undefined) {
          const maEl = document.getElementById("rt-ma");
          if (maEl) maEl.textContent = `${Number(data.tick.ma20).toFixed(2)} / ${Number(data.tick.ma50).toFixed(2)} / ${Number(data.tick.ma200).toFixed(2)}`;
        }
      }
    };

    stockDetailWebSocket.onclose = () => {
      badge.textContent = "RT: disconnected";
      console.log("Stock detail WebSocket disconnected");
    };

    stockDetailWebSocket.onerror = (error) => {
      console.error("Stock detail WebSocket error:", error);
      badge.textContent = "RT: error";
    };
  }

  function cleanupStockWebSocket() {
    if (stockDetailWebSocket) {
      console.log("Cleaning up stock detail WebSocket");
      stockDetailWebSocket.close();
      stockDetailWebSocket = null;

      const badge = document.getElementById("realtime-badge");
      if (badge) badge.textContent = "RT: disconnected";
    }
  }

  // Initialize stock WebSocket if on stock page
  if (document.getElementById("realtime-badge")) {
    setupStockWebSocket();
  }
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
    tbody.innerHTML = data.items.map(r => {
      // Format current price with status color
      const currentPrice = r.current_price || 0;
      const currentPnL = r.current_pnl || 0;

      // Use the correct P&L value - current_pnl for open trades, pnl for closed trades
      const displayPnL = r.status === 'OPEN' ? currentPnL : (r.pnl || 0);
      const statusClass = displayPnL > 0 ? 'profit' : displayPnL < 0 ? 'loss' : '';

      return `<tr>
        <td>${new Date(r.date).toLocaleDateString()}</td>
        <td>${r.symbol}</td>
        <td>${r.direction}</td>
        <td>${r.quantity || 1}</td>
        <td>₹${r.entry}</td>
        <td class="${statusClass}">₹${currentPrice.toFixed(2)}</td>
        <td>₹${r.sl}</td>
        <td>₹${r.target}</td>
        <td>${r.exit ? '₹' + r.exit : "-"}</td>
        <td class="${statusClass}">${displayPnL > 0 ? '+' : ''}₹${displayPnL.toFixed(2)}</td>
      </tr>`;
    }).join("");
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
    const telegramBadge = document.getElementById("telegram-status-badge");
    const telegramTitle = document.querySelector('.wf-integration:nth-child(1) .wf-title');
    
    if (telegramBtn) {
      telegramBtn.textContent = s.telegram_linked ? "Reconfigure" : "Link";
    }
    
    if (telegramStatusEl) {
      if (s.telegram_linked) {
        telegramStatusEl.innerHTML = `<span class="wf-status-indicator connected">Connected - Alerts Active</span> Bot ready to send notifications`;
        if (telegramBadge) {
          telegramBadge.textContent = "Connected";
          telegramBadge.className = "wf-status-indicator connected";
        }
        if (telegramTitle) telegramTitle.classList.add('connected');
      } else {
        telegramStatusEl.innerHTML = `<span class="wf-status-indicator disconnected">Not Connected - No Alerts</span> Click 'Link' to connect & receive notifications`;
        if (telegramBadge) {
          telegramBadge.textContent = "Disconnected";
          telegramBadge.className = "wf-status-indicator disconnected";
        }
        if (telegramTitle) telegramTitle.classList.remove('connected');
      }
    }
    
    // Update Upstox status
    const statusEl = document.getElementById("upstox-status");
    const configBtn = document.getElementById("upstox-config");
    const upstoxBadge = document.getElementById("upstox-status-badge");
    const upstoxTitle = document.querySelector('.wf-integration:nth-child(2) .wf-title');
    
    if (statusEl && configBtn) {
      if (s.upstox_connected) {
      const expiry = new Date(s.upstox_token_expiry);
      const expiryDate = expiry.toLocaleDateString() + " " + expiry.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
      statusEl.innerHTML = `<span class="wf-status-indicator connected">Connected - Real Data</span> Token expires: ${expiryDate}`;
      configBtn.textContent = "Reconfigure";
      if (upstoxBadge) {
        upstoxBadge.textContent = "Connected";
        upstoxBadge.className = "wf-status-indicator connected";
      }
      if (upstoxTitle) upstoxTitle.classList.add('connected');
      } else {
        statusEl.innerHTML = `<span class="wf-status-indicator disconnected">Not Connected - Mock Data</span> Configure for real-time market data`;
        configBtn.textContent = "Configure";
        if (upstoxBadge) {
          upstoxBadge.textContent = "Disconnected";
          upstoxBadge.className = "wf-status-indicator disconnected";
        }
        if (upstoxTitle) upstoxTitle.classList.remove('connected');
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
  const disconnectBtn = document.getElementById("disconnect-upstox");
  const testBtn = document.getElementById("test-upstox");
  const oauthBtn = document.getElementById("connect-upstox-oauth");

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

    // Check if already configured and pre-fill form fields
    try {
      const settings = await getJSON("/settings");
      if (!settings.upstox_connected) {
        if (disconnectBtn) disconnectBtn.style.display = "none";
        if (testBtn) testBtn.style.display = "none";
      }
      
      // Pre-fill API credentials if they exist
      const oauthApiKeyEl = document.getElementById("oauth-api-key");
      const oauthApiSecretEl = document.getElementById("oauth-api-secret");
      
      if (oauthApiKeyEl && settings.upstox_api_key) {
        oauthApiKeyEl.value = settings.upstox_api_key;
      }
      if (oauthApiSecretEl && settings.upstox_api_secret) {
        oauthApiSecretEl.value = settings.upstox_api_secret;
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
    const oauthApiKey = document.getElementById("oauth-api-key");
    const oauthApiSecret = document.getElementById("oauth-api-secret");

    if (oauthApiKey) oauthApiKey.value = "";
    if (oauthApiSecret) oauthApiSecret.value = "";

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

  // OAuth Connect button
  if (oauthBtn) {
    oauthBtn.addEventListener("click", async () => {
      const oauthApiKeyEl = document.getElementById("oauth-api-key");
      const oauthApiSecretEl = document.getElementById("oauth-api-secret");

      if (!oauthApiKeyEl || !oauthApiSecretEl) {
        alert("Form elements not found!");
        return;
      }

      const apiKey = oauthApiKeyEl.value.trim();
      const apiSecret = oauthApiSecretEl.value.trim();

      if (!apiKey || !apiSecret) {
        alert("API Key and API Secret are required for OAuth!");
        return;
      }

      try {
        // Store credentials temporarily for OAuth flow
        const tempResponse = await fetch("/api/settings/upstox/oauth/temp", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            api_key: apiKey,
            api_secret: apiSecret,
          }),
        });

        if (!tempResponse.ok) {
          const error = await tempResponse.json();
          alert(`Error storing credentials: ${error.detail}`);
          return;
        }

        // Initiate OAuth flow
        const response = await fetch("/api/settings/upstox/oauth/initiate", {
          method: "POST",
        });

        if (response.ok) {
          const data = await response.json();
          // Redirect to Upstox authorization URL
          window.location.href = data.authorization_url;
        } else {
          const error = await response.json();
          alert(`OAuth initiation failed: ${error.detail}`);
        }
      } catch (error) {
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



// Threshold management functions
async function saveThresholds() {
  try {
    const gapInput = document.getElementById("th-gap");
    const rsiInput = document.getElementById("th-rsi");
    
    if (!gapInput || !rsiInput) {
    alert("Threshold input fields not found");
      return;
    }
    
    const gap = parseFloat(gapInput.value);
    const rsi = parseInt(rsiInput.value);
    
    // Validation
    if (isNaN(gap) || gap <= 0 || gap > 100) {
    alert("Gap % must be a number between 0 and 100");
      return;
    }
    
    if (isNaN(rsi) || rsi < 1 || rsi > 100) {
    alert("RSI must be a number between 1 and 100");
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
    alert("Threshold settings saved successfully!");
    } else {
    alert(result.detail || "Failed to save threshold settings");
    }
  } catch (error) {
    console.error("Error saving thresholds:", error);
    alert("Error saving threshold settings");
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

// WebSocket cleanup on page navigation/close
window.addEventListener("beforeunload", () => {
  console.log("Page unloading - cleaning up all WebSockets");
  if (typeof cleanupScreenerWebSocket === 'function') {
    cleanupScreenerWebSocket();
  }
  if (typeof cleanupStockWebSocket === 'function') {
    cleanupStockWebSocket();
  }
});

// Cleanup when navigating between pages (for SPAs or when links are clicked)
document.addEventListener("click", (event) => {
  const link = event.target.closest("a");
  if (link && link.href && !link.href.includes(window.location.pathname)) {
    // Navigating to a different page
    console.log("Navigating away from current page - cleaning up WebSockets");
    if (typeof cleanupScreenerWebSocket === 'function') {
      cleanupScreenerWebSocket();
    }
    if (typeof cleanupStockWebSocket === 'function') {
      cleanupStockWebSocket();
    }
  }
});

// Additional cleanup on page visibility change (when user switches tabs/apps)
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    // Page is now hidden
    const currentPage = document.documentElement.getAttribute("data-page");
    if (currentPage === "screener" && screenerWebSocket && screenerWebSocket.readyState === WebSocket.OPEN) {
      console.log("Page hidden - keeping WebSocket open but noting state");
      // Keep connection open for background updates, just log the state
    }
  } else {
    // Page is now visible
    const currentPage = document.documentElement.getAttribute("data-page");
    if (currentPage === "screener" && (!screenerWebSocket || screenerWebSocket.readyState !== WebSocket.OPEN)) {
      console.log("Page visible and screener WebSocket not connected - reconnecting");
      setupScreenerWebSocket();
    }
  }
});
