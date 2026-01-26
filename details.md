# Arbiter - Stock Market Simulator: Interview Preparation

## Project Overview

**What is it?**
A full-stack stock market simulation engine with algorithmic trading bots. It simulates realistic market behavior and runs autonomous trading strategies in real-time.

**Why did you build it?**
To learn about:
- Order matching engines (how exchanges work)
- Algorithmic trading strategies (momentum, mean reversion, arbitrage)
- Real-time systems with WebSockets
- Financial mathematics (price models, technical indicators)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + TypeScript)                │
│              WebSocket connection for real-time data            │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    API Layer (FastAPI)                          │
│        REST endpoints + WebSocket server for streaming          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                     Trading Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Broker    │  │  Order Book │  │      Portfolio          │ │
│  │  (routing)  │  │ (matching)  │  │   (position tracking)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Engine Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Market    │  │   Assets    │  │      Events             │ │
│  │  (engine)   │  │ (prices/GBM)│  │   (news, halts)         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                       Bots Layer                                │
│  ┌─────────────┐  ┌───────────────┐  ┌─────────────────────┐   │
│  │  Momentum   │  │Mean Reversion │  │     Arbitrage       │   │
│  │     Bot     │  │      Bot      │  │       Bot           │   │
│  └─────────────┘  └───────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technologies & Languages

### Backend (Python)

| Technology | Purpose | Why This Choice? |
|------------|---------|------------------|
| Python 3.13 | Core language | Excellent for financial computations, NumPy/pandas ecosystem |
| asyncio | Async concurrency | Handle 10,000+ concurrent events without thread overhead |
| FastAPI | REST API + WebSocket | Modern, fast, native async support, auto-documentation |
| NumPy | Numerical computations | Optimized array operations for indicators/price models |
| pandas | Data manipulation | Time series handling for price history |
| PyYAML | Configuration | Human-readable config files |
| uvicorn | ASGI server | Production-ready async server |

### Frontend (TypeScript)

| Technology | Purpose | Why This Choice? |
|------------|---------|------------------|
| React 18 | UI framework | Component-based, excellent for real-time updates |
| TypeScript | Type safety | Catch errors at compile time, better IDE support |
| Vite | Build tool | Fast HMR, modern ES modules |
| Recharts | Charts | D3-based, works well with React |
| WebSocket | Real-time data | Push updates without polling |

---

## Key Algorithms & Concepts

### 1. Geometric Brownian Motion (GBM) - Price Simulation

```python
def update_price_gbm(self, dt: float = 1.0) -> float:
    dW = random.gauss(0, 1) * math.sqrt(dt)
    drift_component = (self.drift - 0.5 * self.volatility ** 2) * dt
    diffusion_component = self.volatility * dW
    log_return = drift_component + diffusion_component
    new_price = self.price * math.exp(log_return)
```

**Interview Answer:**
I used GBM because it's the industry standard for modeling stock prices. The formula dS = μS*dt + σS*dW combines deterministic drift (μ) with random Brownian motion (σ*dW). The key insight is that stock returns are log-normally distributed, which means prices can't go negative - unlike simple random walks.

### 2. Order Book with Price-Time Priority

```python
# Uses heap for O(log n) best price lookup
self._bid_prices: List[float] = []  # negative for max-heap
self._ask_prices: List[float] = []  # min-heap

# Matching: best price first, then earliest order at that price
```

**Interview Answer:**
The order book uses heaps for efficient best bid/ask lookup. Python's heapq gives us O(log n) insertion and O(1) best price. For time priority at the same price level, orders are stored in a list - first in, first matched. This mimics how real exchanges work with FIFO matching.

### 3. Trading Strategies

#### Momentum Bot

```python
# Entry: ROC > threshold, RSI not overbought, MACD bullish, volume spike
if score >= 3:  # Multi-factor confirmation
    return {'action': 'buy', 'confidence': score/5}
```

**Interview Answer:**
The momentum strategy uses multiple indicator confirmation to reduce false signals. It looks for Rate of Change (ROC) above threshold, RSI between 30-60 (not overbought), bullish MACD crossover, and volume confirmation. The scoring system requires at least 3 factors to align before entering.

#### Mean Reversion Bot

```python
# Uses Z-score to detect extremes
z_score = (current - mean) / std
if z_score < -2.0:  # 2 std devs below mean
    return {'action': 'buy'}
```

**Purpose1:**
Mean reversion exploits the statistical tendency of prices to return to their mean. When a stock is 2+ standard deviations from its moving average (Z-score < -2), it's statistically oversold. The strategy buys these dips and exits when price reverts to the mean.

#### Arbitrage Bot

```python
# Pairs trading: correlated assets that diverge
spread = (price1 - price2) / ((price1 + price2) / 2)
z_score = (spread - mean_spread) / std_spread
if abs(z_score) > 2:  # Spread diverged
    # Long underperformer, short outperformer
```

**Purpose2:**
The arbitrage bot monitors correlated stock pairs (same sector usually have 0.7-0.9 correlation). When their spread diverges beyond 2 standard deviations, it goes long the underperformer expecting convergence. It's market-neutral - profits from the spread narrowing, not market direction.

### 4. Technical Indicators

```python
# RSI (Relative Strength Index)
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))

# MACD (Moving Average Convergence Divergence)
macd_line = ema_fast - ema_slow
signal_line = ema(macd_line)
histogram = macd_line - signal_line

# Bollinger Bands
upper = sma + (2 * std)
lower = sma - (2 * std)
percent_b = (price - lower) / (upper - lower)
```

**Purpose3:**
I implemented streaming indicators with O(1) updates where possible. The EMA uses incremental calculation: EMA_t = Price_t * k + EMA_{t-1} * (1-k) instead of recalculating from scratch. RSI and MACD use the standard formulas but are optimized for real-time updates with deques for rolling windows.

---

## Design Decisions & Rationale

### 1. Why async/await throughout?

The market simulation needs to handle thousands of concurrent operations: price updates, order processing, bot decisions, event generation. Using asyncio lets me handle this concurrently on a single thread without the complexity of locks. The asyncio.gather() pattern runs price updates, event processing, and bot cycles in parallel.

### 2. Why separate Market, Broker, and Bot layers?

Clean separation of concerns. The Market only cares about price simulation and events. The Broker handles order validation, routing, and settlement. Bots implement strategies. Each can be tested independently. This also mirrors real-world architecture where exchanges, brokerages, and trading firms are separate entities.

### 3. Why hash-chained audit logs?

In financial systems, audit trails must be tamper-evident. Each log entry includes a hash of the previous entry: [HASH:abc123|PREV:xyz789]. If anyone modifies historical logs, the chain breaks. The verify_chain_integrity() method can detect tampering. This is similar to how blockchain ensures data integrity.

### 4. Why WebSocket instead of REST polling?

Markets move fast. Polling would create latency and unnecessary load. WebSocket maintains a persistent connection and pushes updates immediately. The frontend receives 2 ticks/second with full market state. This gives a responsive real-time experience.

### 5. Why configurable via YAML?

I wanted to experiment with different parameters without changing code: volatility, bot thresholds, trading rules. YAML is human-readable and supports nested structures. You can run different simulations by just changing config values.

### 6. Why heap-based order book?

Real exchanges need O(log n) order insertion and O(1) best price lookup. A sorted list would give O(n) insertion. Two heaps (max-heap for bids, min-heap for asks) provide the right complexity. I use negative prices for the bid heap since Python only has min-heap.

---

## Challenges & Difficulties

### 1. Race Conditions in Async Code

**Problem:** Multiple bots could try to buy the same shares simultaneously.

**Solution:** Used asyncio.Lock in the broker to serialize order submission. Each critical section is protected.

### 2. Volatility Decay Bug

**Problem:** After a shock event, volatility should decay back to normal, but it was decaying too aggressively.

**Solution:** Tuned the decay factor: `volatility = max(0.005, volatility * 0.999)` - very gradual decay with a floor.

### 3. Order Book Price Staleness

**Problem:** Market maker quotes became stale as prices moved.

**Solution:** Added refresh_liquidity() that periodically cancels old quotes and adds new ones at current price levels.

### 4. Indicator Cold Start

**Problem:** Bots tried to trade before enough price history accumulated.

**Solution:** Indicators return None if insufficient data. Bots check for None and skip trading until enough history exists.

### 5. Memory Growth from Price History

**Problem:** Storing all price ticks would grow unbounded.

**Solution:** Used deque(maxlen=500) for bounded history and periodic truncation in price_history lists.

---

## Common Questions & Answers

### Technical Questions

**Q: How does my order matching algorithm work?**

"It's price-time priority. Best price always matches first. At the same price, earlier orders get priority. For a market buy, I scan the ask side from lowest price up. For limit orders, I first try to match against the opposite side, then add unfilled quantity to the book."

**Q: How do I handle partial fills?**

"Each order tracks filled_quantity and remaining_quantity. When matching, I fill the minimum of what's available and what's needed. The order status changes to PARTIALLY_FILLED if some quantity remains."

**Q: Why did I choose these specific trading strategies?**

"They represent three fundamental approaches: (1) Momentum - trend following, buy strength; (2) Mean reversion - contrarian, buy weakness; (3) Arbitrage - market-neutral, exploit mispricings. Together they demonstrate different edge sources in markets."

**Q: How would I scale this system?**

"For horizontal scaling: separate the order book into a dedicated matching engine service. Use Redis/Kafka for pub/sub of price updates. Each bot could run as a separate process. The current design already separates concerns cleanly, making microservice extraction straightforward."

**Q: What would I add in a production system?**

"(1) Persistence - database for orders and positions; (2) Authentication - user accounts and API keys; (3) Risk management - position limits, buying power checks; (4) Monitoring - Prometheus metrics, Grafana dashboards; (5) More order types - iceberg, trailing stop."

### General Questions

**Q: What was the hardest bug I encountered?**

"The race condition between bots placing orders. Two bots would see the same opportunity and both try to buy, exceeding available cash. I solved it with async locks and balance checks at order submission time."

**Q: What would I do differently?**

"I'd add persistence earlier. Currently everything is in-memory, so a restart loses state. Also, I'd use a proper message queue for event distribution instead of callbacks."

**Q: How did I test this?**

"Unit tests for the order book cover matching, partial fills, cancellation, and price-time priority. I also ran stress tests with 10,000+ concurrent events to verify performance. The bots were tested by running simulations and analyzing P&L."

---

## Key Metrics to Mention

- 10 stocks simulated with realistic price movements
- 3 trading strategies with measurable P&L
- Price-time priority matching like real exchanges
- Hash-chained audit logs for tamper detection
- WebSocket streaming at 2 ticks/second
- Configurable parameters via YAML
- Comprehensive test suite with pytest

---

## One-Liner Pitch

"I built a real-time stock market simulator with autonomous trading bots. It has a proper order matching engine with price-time priority, uses Geometric Brownian Motion for realistic prices, and implements three classic strategies: momentum, mean reversion, and pairs arbitrage. The frontend shows everything live via WebSocket."

---

## Project Structure Quick Reference

```
stock-sim/
├── engine/           # Market simulation
│   ├── market.py     # Main async engine, coordinates everything
│   ├── asset.py      # Price models (GBM, random walk, hybrid)
│   └── events.py     # News, halts, sentiment system
├── trading/          # Order execution
│   ├── orderbook.py  # Matching engine with heap-based book
│   ├── broker.py     # Order routing, validation, settlement
│   └── portfolio.py  # Position tracking, P&L calculation
├── bots/             # Trading strategies
│   ├── base.py       # Abstract bot class, bot manager
│   ├── momentum.py   # Trend following strategy
│   ├── mean_reversion.py  # Buy oversold, sell overbought
│   └── arbitrage.py  # Pairs trading on correlated assets
├── utils/
│   ├── indicators.py # SMA, EMA, RSI, MACD, Bollinger, etc.
│   └── logger.py     # Hash-chained audit logging
├── api/
│   └── server.py     # FastAPI + WebSocket server
├── frontend/         # React + TypeScript UI
│   └── src/
│       ├── App.tsx
│       └── components/
├── tests/            # pytest test suite
├── config.yaml       # All configurable parameters
└── main.py           # CLI entry point
```

---

Good luck with your interview!
