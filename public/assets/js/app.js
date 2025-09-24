/* Simple wireframe JS to fetch mock API and render cards */
const API_BASE = "/api";

// Authentication helper functions
const auth = {
  // Store token
  setToken: (token) => {
    localStorage.setItem('jwt_token', token);
  },

  // Get token
  getToken: () => {
    return localStorage.getItem('jwt_token') || sessionStorage.getItem('jwt_token');
  },

  // Remove token (logout)
  removeToken: () => {
    localStorage.removeItem('jwt_token');
    sessionStorage.removeItem('jwt_token');
  },

  // Check if user is authenticated
  isAuthenticated: () => {
    const token = auth.getToken();
    if (!token) return false;

    try {
      // Basic check - decode payload to see if expired
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Date.now() / 1000;
      return payload.exp > currentTime;
    } catch (e) {
      return false;
    }
  }
};

// JWT token for WebSocket authentication
const getWebSocketToken = () => {
  // Production implementation: return auth.getToken();
  return auth.getToken();
};

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

  const formatPrice = (price) => {
    if (!price || price === 0) return "-";
    return "₹" + Number(price).toFixed(2);
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

  const formatChange = (change) => {
    if (change == null) return "-";
    const num = Number(change);
    const sign = num > 0 ? "+" : "";
    return `${sign}${num.toFixed(2)}%`;
  };

  // Determine signal badge
  let signalClass = "";
  let signalText = "HOLD";
  if (s.signal?.direction === "BUY") {
    signalClass = "gainer";
    signalText = "BUY";
  } else if (s.signal?.direction === "SELL") {
    signalClass = "loser";
    signalText = "SELL";
  }

  // Determine signal color for text
  let signalColorClass = "";
  if (s.signal?.direction === "BUY") {
    signalColorClass = "buy-signal";
  } else if (s.signal?.direction === "SELL") {
    signalColorClass = "sell-signal";
  }

  return `<div class="wf-screener-card">
    <div class="wf-mover-header">
      <div class="wf-mover-title">
        <span class="wf-mover-symbol ${signalColorClass}">${s.symbol}</span>
        ${s.name ? `<span class="wf-mover-company ${signalColorClass}">${s.name}</span>` : ''}
      </div>
      <button class="wf-pill-btn remove top-right" onclick="removeFromWatchlist('${s.symbol}')" title="Remove from watchlist">Remove</button>
    </div>
    <div class="wf-mover-metrics">
      <div class="wf-mover-metric">
        <span class="wf-mover-metric-label">Price</span>
        <span class="wf-mover-metric-value">${formatPrice(s.price)}</span>
      </div>
      <div class="wf-mover-metric">
        <span class="wf-mover-metric-label">Change</span>
        <span class="wf-mover-metric-value ${s.gap > 0 ? 'positive' : s.gap < 0 ? 'negative' : ''}">${formatChange(s.gap)}</span>
      </div>
      <div class="wf-mover-metric">
        <span class="wf-mover-metric-label">Volume</span>
        <span class="wf-mover-metric-value">${formatVolume(s.volume)}</span>
      </div>
      <div class="wf-mover-metric">
        <span class="wf-mover-metric-label">RSI</span>
        <span class="wf-mover-metric-value">${formatNumber(s.rsi, 1)}</span>
      </div>
      <div class="wf-mover-metric compact">
        <span class="wf-mover-metric-label">Bollinger</span>
        <span class="wf-mover-metric-value">${formatNumber(s.bb_upper, 0)}/${formatNumber(s.bb_lower, 0)}</span>
      </div>
      <div class="wf-mover-metric compact wf-metrics-wide">
        <span class="wf-mover-metric-label">MA20/50/200</span>
        <span class="wf-mover-metric-value">${formatNumber(s.ma20, 0)}/${formatNumber(s.ma50, 0)}/${formatNumber(s.ma200, 0)}</span>
      </div>
    </div>
    <a class="wf-btn details-bottom" href="/stock.html?symbol=${encodeURIComponent(s.symbol)}">Details</a>
  </div>`;
}

function renderOverview() {
  // Indexes section
  getJSON("/index-quotes").then(data => {
    const grid = document.getElementById("indexes-grid");
    if (!grid) return;

    // Format numbers nicely for indexes
    const formatIndexPrice = (price) => {
      if (!price || price === 0) return "-";
      return Number(price).toFixed(2);
    };

    const formatIndexVolume = (volume) => {
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

    grid.innerHTML = Object.entries(data).map(([symbol, idx]) => {
      if (idx.error) {
        return `<div class="wf-index-card">
          <div class="wf-index-header">
            <span class="wf-index-symbol">${symbol}</span>
            <span class="wf-index-badge error">Error</span>
          </div>
          <div class="wf-index-metrics">
            <div class="wf-index-metric">
              <span class="wf-index-metric-label">Status</span>
              <span class="wf-index-metric-value">${idx.error}</span>
            </div>
          </div>
        </div>`;
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

      return `<div class="wf-index-card">
        <div class="wf-index-header">
          <span class="wf-index-symbol">${symbol}</span>
          <span class="wf-index-badge ${pillClass}">${pillText}</span>
        </div>
        <div class="wf-index-metrics">
          <div class="wf-index-metric">
            <span class="wf-index-metric-label">Last</span>
            <span class="wf-index-metric-value">${formatIndexPrice(idx.last_price)}</span>
          </div>
          <div class="wf-index-metric">
            <span class="wf-index-metric-label">Change</span>
            <span class="wf-index-metric-value ${last > (prevClose || open) ? 'positive' : last < (prevClose || open) ? 'negative' : ''}">${prevClose ? (last - prevClose > 0 ? '+' : '') + (last - prevClose).toFixed(2) : '-'}</span>
          </div>
          <div class="wf-index-metric">
            <span class="wf-index-metric-label">Volume</span>
            <span class="wf-index-metric-value">${formatIndexVolume(live.volume)}</span>
          </div>
          <div class="wf-index-metric">
            <span class="wf-index-metric-label">High</span>
            <span class="wf-index-metric-value">${formatIndexPrice(live.high)}</span>
          </div>
          <div class="wf-index-metric">
            <span class="wf-index-metric-label">Low</span>
            <span class="wf-index-metric-value">${formatIndexPrice(live.low)}</span>
          </div>
          <div class="wf-index-metric">
            <span class="wf-index-metric-label">Open</span>
            <span class="wf-index-metric-value">${formatIndexPrice(live.open)}</span>
          </div>
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
          <div class="wf-mover-title">
            <span class="wf-mover-symbol">${g.symbol}</span>
            ${g.company_name ? `<span class="wf-mover-company">${g.company_name}</span>` : ''}
          </div>
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
          <div class="wf-mover-title">
            <span class="wf-mover-symbol">${l.symbol}</span>
            ${l.company_name ? `<span class="wf-mover-company">${l.company_name}</span>` : ''}
          </div>
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
    const token = getWebSocketToken();
    screenerWebSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/screener?token=${encodeURIComponent(token)}`);

    screenerWebSocket.onopen = () => {
      console.log("Screener WebSocket connected");
      if (badge) badge.textContent = "RT: live";
    };

    screenerWebSocket.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      
      // Handle authentication errors
      if (data.error) {
        console.error("Screener WebSocket authentication error:", data.error);
        if (badge) badge.textContent = "RT: auth failed";
        screenerWebSocket.close();
        return;
      }
      
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

  try {
    console.log(`Setting up custom chart for ${symbol}...`);

    // Fetch chart data
    const chartData = await getJSON(`/stocks/${encodeURIComponent(symbol)}/chart`);
    console.log("Chart data received:", chartData);

    if (!chartData || !chartData.data || chartData.data.length === 0) {
      console.log("No chart data available");
      chartContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text);">No chart data available</div>';
      return;
    }

    // Clear container first
    chartContainer.innerHTML = '';

    // Create custom chart
    createCustomChart(chartContainer, chartData.data, symbol);

  } catch (error) {
    console.error("Error setting up custom chart:", error);
    chartContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text);">Failed to load chart: ' + error.message + '</div>';
  }
}

function createCustomChart(container, data, symbol) {
  // Store data for resize
  container._chartData = { data, symbol };

  function renderChart() {
    // Clear existing content
    container.innerHTML = '';

    // Get container dimensions
    const rect = container.getBoundingClientRect();
    const width = rect.width || 400;
    const height = rect.height || 300;

    // Create SVG element
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.style.background = 'transparent';

    // Process data for simple line chart
    const prices = data.map(d => parseFloat(d.close)).filter(p => !isNaN(p));
    if (prices.length === 0) {
      container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text);">No valid price data</div>';
      return;
    }

    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice || 1;

    // Create path for price line
    let pathData = '';
    prices.forEach((price, index) => {
      const x = 40 + (index / (prices.length - 1)) * (width - 80);
      const y = height - 40 - ((price - minPrice) / priceRange) * (height - 80);
      pathData += (index === 0 ? 'M' : 'L') + x + ',' + y;
    });

    // Create path element
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', pathData);
    path.setAttribute('stroke', 'var(--buy)');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('fill', 'none');
    path.style.filter = 'drop-shadow(0 0 4px rgba(16, 185, 129, 0.3))';

    // Add grid lines
    for (let i = 0; i <= 5; i++) {
      const y = 20 + (i * (height - 40) / 5);
      const gridLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      gridLine.setAttribute('x1', '40');
      gridLine.setAttribute('y1', y);
      gridLine.setAttribute('x2', width - 20);
      gridLine.setAttribute('y2', y);
      gridLine.setAttribute('stroke', 'var(--outline)');
      gridLine.setAttribute('stroke-dasharray', '2,2');
      gridLine.setAttribute('opacity', '0.3');
      svg.appendChild(gridLine);
    }

    // Add price labels
    for (let i = 0; i <= 4; i++) {
      const price = minPrice + (priceRange * (4 - i) / 4);
      const y = 25 + (i * (height - 45) / 4);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', '5');
      text.setAttribute('y', y + 3);
      text.setAttribute('fill', 'var(--muted)');
      text.setAttribute('font-size', '10px');
      text.setAttribute('font-family', 'Inter, sans-serif');
      text.textContent = '₹' + price.toFixed(2);
      svg.appendChild(text);
    }

    // Add current price indicator
    const currentPrice = prices[prices.length - 1];
    const currentY = height - 40 - ((currentPrice - minPrice) / priceRange) * (height - 80);

    const currentPriceLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    currentPriceLine.setAttribute('x1', '40');
    currentPriceLine.setAttribute('y1', currentY);
    currentPriceLine.setAttribute('x2', width - 20);
    currentPriceLine.setAttribute('y2', currentY);
    currentPriceLine.setAttribute('stroke', 'var(--accent)');
    currentPriceLine.setAttribute('stroke-width', '1');
    currentPriceLine.setAttribute('stroke-dasharray', '4,4');
    svg.appendChild(currentPriceLine);

    const currentPriceText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    currentPriceText.setAttribute('x', width - 80);
    currentPriceText.setAttribute('y', currentY - 5);
    currentPriceText.setAttribute('fill', 'var(--accent)');
    currentPriceText.setAttribute('font-size', '11px');
    currentPriceText.setAttribute('font-family', 'Inter, sans-serif');
    currentPriceText.setAttribute('font-weight', 'bold');
    currentPriceText.textContent = '₹' + currentPrice.toFixed(2);
    svg.appendChild(currentPriceText);

    // Add path to SVG
    svg.appendChild(path);

    // Add SVG to container
    container.appendChild(svg);
  }

  // Initial render
  renderChart();

  // Make chart responsive
  function resizeChart() {
    renderChart();
  }

  window.addEventListener('resize', resizeChart);
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

function renderStockDetail() {
  const params = new URLSearchParams(location.search);
  const symbol = params.get("symbol") || "RELIANCE";

  // Setup candlestick chart
  setupCandlestickChart(symbol);
  
  getJSON(`/stocks/${encodeURIComponent(symbol)}`).then(s => {
    console.log("Stock data received:", s); // Debug log
    console.log("Stock data received:", s); // Debug log
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
    
    const k = document.getElementById("stock-detail-content");
    k.innerHTML = `
      <div class="wf-stock-header">
        <div class="wf-stock-title-section">
          <div class="wf-stock-symbol-large ${s.signal?.direction === "BUY" ? "buy-signal" : s.signal?.direction === "SELL" ? "sell-signal" : ""}">${s.symbol}</div>
          ${s.name ? `<div class="wf-stock-name ${s.signal?.direction === "BUY" ? "buy-signal" : s.signal?.direction === "SELL" ? "sell-signal" : ""}">${s.name}</div>` : ''}
          <div class="wf-stock-price-large ${s.sentiment === 'BULLISH' ? 'buy-signal' : s.sentiment === 'BEARISH' ? 'sell-signal' : ''}">₹${formatNumber(s.price, 2)}</div>
          <div class="wf-stock-change ${s.gap > 0 ? 'positive' : s.gap < 0 ? 'negative' : ''}">${formatNumber(s.gap, 2)}%</div>
        </div>
        <div class="wf-stock-actions">
          <button id="watchlist-btn" class="wf-btn" style="font-size:12px;">${s.watchlist ? 'Remove from Watchlist' : 'Add to Watchlist'}</button>
          <span id="realtime-badge" class="wf-tag">RT: live</span>
        </div>
      </div>
      
      <div class="wf-stock-metrics-grid">
        <div class="wf-metric-group">
          <div class="wf-metric-card">
            <div class="wf-metric-label">Volume</div>
            <div class="wf-metric-value">${formatVolume(s.volume)}</div>
          </div>
          <div class="wf-metric-card">
            <div class="wf-metric-label">VWAP</div>
            <div class="wf-metric-value">₹${formatNumber(s.vwap, 2)}</div>
          </div>
        </div>
        
        <div class="wf-metric-group">
          <div class="wf-metric-card">
            <div class="wf-metric-label">RSI</div>
            <div class="wf-metric-value">${formatNumber(s.rsi, 1)}</div>
          </div>
          <div class="wf-metric-card">
            <div class="wf-metric-label">Bollinger Bands</div>
            <div class="wf-metric-value">${formatNumber(s.bb_upper, 0)} / ${formatNumber(s.bb_lower, 0)}</div>
          </div>
        </div>
        
        <div class="wf-metric-group wf-metric-full">
          <div class="wf-metric-card">
            <div class="wf-metric-label">Moving Averages (20/50/200)</div>
            <div class="wf-metric-value">${formatNumber(s.ma20, 0)} / ${formatNumber(s.ma50, 0)} / ${formatNumber(s.ma200, 0)}</div>
          </div>
        </div>
        
        <div class="wf-metric-group">
          ${s.sentiment === 'BULLISH' || s.sentiment === 'BEARISH' ? `
          <div class="wf-metric-card">
            <div class="wf-metric-label">Entry Price</div>
            <div class="wf-metric-value">₹${formatNumber(s.signal?.entry, 2)}</div>
          </div>
          <div class="wf-metric-card">
            <div class="wf-metric-label">Stop Loss</div>
            <div class="wf-metric-value">₹${formatNumber(s.signal?.sl, 2)}</div>
          </div>
          <div class="wf-metric-card">
            <div class="wf-metric-label">Target</div>
            <div class="wf-metric-value">₹${formatNumber(s.signal?.target, 2)}</div>
          </div>
          ` : ''}
          <div class="wf-metric-card">
            <div class="wf-metric-label">Sentiment</div>
            <div class="wf-metric-value ${s.sentiment === 'BULLISH' ? 'buy-signal' : s.sentiment === 'BEARISH' ? 'sell-signal' : ''}">${s.sentiment || "NEUTRAL"}</div>
          </div>
        </div>
      </div>
      
      <div class="wf-stock-note">
        <div class="wf-note">Signals (wireframe): Entry / SL / Target are placeholders for demonstration.</div>
      </div>
    `;
    
    // Setup watchlist button after HTML is rendered
    setupWatchlistButton(symbol);
    
    // Alerts list - handle missing alerts gracefully
    const al = document.getElementById("stock-alerts");
    if (al && s.alerts && Array.isArray(s.alerts)) {
      al.innerHTML = s.alerts.map(a => `<li class="wf-alert ${a.severity}"><div>${a.message}</div><div class="wf-tag">${new Date(a.ts).toLocaleTimeString()}</div></li>`).join("");
    } else if (al) {
      al.innerHTML = "<li>No alerts yet</li>";
    }
  }).catch(error => {
    console.error("Error loading stock data:", error);
    const k = document.getElementById("stock-detail-content");
    if (k) {
      k.innerHTML = `<div class="wf-metric-card"><div class="wf-metric-label">Error</div><div class="wf-metric-value">Failed to load stock data</div></div>`;
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

    const token = getWebSocketToken();
    stockDetailWebSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/price?symbol=${encodeURIComponent(symbol)}&token=${encodeURIComponent(token)}`);

    stockDetailWebSocket.onopen = () => {
      badge.textContent = "RT: live";
      console.log("Stock detail WebSocket connected for", symbol);
    };

    stockDetailWebSocket.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      
      // Handle authentication errors
      if (data.error) {
        console.error("Stock detail WebSocket authentication error:", data.error);
        badge.textContent = "RT: auth failed";
        stockDetailWebSocket.close();
        return;
      }
      
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

  setupStockWebSocket();
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
  if (page === "stock") {
    renderStock();
    renderStockDetail();
  }
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

// Authentication functionality
function initAuth() {
  const authSection = document.getElementById('auth-section');
  if (!authSection) return;

  // Check if user is already authenticated
  updateAuthUI();

  // Add login form HTML
  authSection.innerHTML = `
    <div class="wf-login-form">
      <input type="text" id="username" placeholder="Username" class="wf-input">
      <input type="password" id="password" placeholder="Password" class="wf-input">
      <button id="login-btn" class="wf-login-btn">Login</button>
    </div>
    <div class="wf-user-info">
      <span id="user-display">Welcome!</span>
      <button id="logout-btn" class="wf-logout-btn">Logout</button>
    </div>
  `;

  // Add event listeners
  const loginBtn = document.getElementById('login-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');

  loginBtn.addEventListener('click', async () => {
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();

    if (!username || !password) {
      alert('Please enter both username and password');
      return;
    }

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        auth.setToken(data.access_token);
        updateAuthUI();
        usernameInput.value = '';
        passwordInput.value = '';

        // Reconnect WebSockets with new token
        if (typeof setupScreenerWebSocket === 'function') setupScreenerWebSocket();
        if (typeof setupPriceWebSocket === 'function') setupPriceWebSocket();

        alert('Login successful!');
      } else {
        alert(data.detail || 'Login failed');
      }
    } catch (error) {
      console.error('Login error:', error);
      alert('Login failed. Please try again.');
    }
  });

  logoutBtn.addEventListener('click', () => {
    auth.removeToken();
    updateAuthUI();

    // Disconnect WebSockets
    if (screenerWebSocket) {
      screenerWebSocket.close();
      screenerWebSocket = null;
    }
    if (priceWebSocket) {
      priceWebSocket.close();
      priceWebSocket = null;
    }

    alert('Logged out successfully');
  });

  // Handle Enter key in password field
  passwordInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      loginBtn.click();
    }
  });
}

function updateAuthUI() {
  const authSection = document.getElementById('auth-section');
  if (!authSection) return;

  const isAuthenticated = auth.isAuthenticated();

  if (isAuthenticated) {
    authSection.classList.remove('logged-out');
    authSection.classList.add('logged-in');

    // Try to get user info
    const token = auth.getToken();
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const userId = payload.user_id || 'User';
        document.getElementById('user-display').textContent = `Welcome, ${userId}!`;
      } catch (e) {
        document.getElementById('user-display').textContent = 'Welcome!';
      }
    }
  } else {
    authSection.classList.remove('logged-in');
    authSection.classList.add('logged-out');
  }
}

// Initialize auth when DOM is loaded
document.addEventListener('DOMContentLoaded', initAuth);
