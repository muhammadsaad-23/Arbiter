# Stock Market Simulator

A stock market simulation engine with AI trading bots. Built this to learn more about order matching and algorithmic trading.

## Quick Start

```bash
cd stock-sim

# create venv and install deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# run it
python main.py
```

## What it does

- Simulates 10 stocks with realistic price movements (GBM model)
- Full order book with price-time priority matching
- 3 trading bots that actually trade:
  - Momentum bot (trend following)
  - Mean reversion bot 
  - Arbitrage bot (pairs trading)
- Terminal dashboard showing live prices

## Running options

```bash
python main.py                    # default 5 min simulation
python main.py --duration 600     # 10 minutes
python main.py --tick-rate 2      # faster updates
python main.py --no-bots          # just market, no bots
python main.py --no-dashboard     # headless mode
```

## Historical Data Mode (NEW!)

Test your bots against **real historical stock prices** from Yahoo Finance:

```bash
# Use real historical data (last month, hourly)
python main.py --historical

# Customize the data range
python main.py --historical --period 3mo --interval 1d   # 3 months daily
python main.py --historical --period 1y --interval 1d    # 1 year daily
python main.py --historical --period 5d --interval 15m   # 5 days, 15-min bars
```

### Available Options

| Period | Description |
|--------|-------------|
| `1d` | Last day |
| `5d` | Last 5 days |
| `1mo` | Last month (default) |
| `3mo` | Last 3 months |
| `6mo` | Last 6 months |
| `1y` | Last year |
| `2y` | Last 2 years |

| Interval | Description | Max History |
|----------|-------------|-------------|
| `1m` | 1 minute | 7 days |
| `5m` | 5 minutes | 60 days |
| `15m` | 15 minutes | 60 days |
| `1h` | 1 hour (default) | 730 days |
| `1d` | 1 day | unlimited |

### Simulation vs Historical

| Mode | Command | Data Source |
|------|---------|-------------|
| **Simulation** | `python main.py` | Generated using GBM (fake prices) |
| **Historical** | `python main.py --historical` | Real data from Yahoo Finance |

## Web UI (React + TypeScript)

There's a real-time dashboard built with React and TypeScript:

```bash
# Terminal 1 - start the API server
source venv/bin/activate
pip install fastapi uvicorn websockets
python api/server.py

# Terminal 2 - start the frontend
cd frontend
npm install
npm run dev
```

Then go to http://localhost:3000

### Streamlit (alternative)

If you prefer something simpler:

```bash
streamlit run app.py
```

Then go to http://localhost:8501

## Project Structure

```
stock-sim/
├── engine/          # market simulation
│   ├── market.py    # main engine
│   ├── asset.py     # price models
│   └── events.py    # news/events
├── trading/         # order execution
│   ├── orderbook.py # matching engine
│   ├── broker.py    # order routing
│   └── portfolio.py # position tracking
├── bots/            # trading strategies
├── utils/           # logging, indicators
├── api/             # FastAPI backend
│   └── server.py    # websocket server
├── frontend/        # React + TypeScript UI
│   └── src/
└── main.py          # CLI entry point
```

## Price Models

Using Geometric Brownian Motion for price simulation:

```
dS = μS*dt + σS*dW
```

Where μ is drift and σ is volatility. Pretty standard stuff.

## How the order book works

- Price-time priority (best price first, then earliest order)
- Supports market, limit, stop-loss, take-profit orders
- Partial fills work
- Market maker quotes provide liquidity

## Bot strategies

**Momentum**: Buys when ROC > threshold and RSI not overbought. Uses MACD for confirmation. Basic trend following.

**Mean Reversion**: Looks for prices >2 std devs from mean. Buys oversold, exits when price reverts.

**Arbitrage**: Monitors correlated stock pairs. When spread diverges, goes long underperformer.

## Logs

Audit logs go to `logs/audit.log`. They're hash-chained so you can verify nothing was tampered with:

```python
from utils.logger import AuditLogger
logger = AuditLogger()
logger.verify_chain_integrity()  # returns True if ok
```

## Tests

```bash
pytest tests/ -v
```

## TODO

- [ ] better arbitrage detection
- [ ] add more indicators
- [x] websocket api 
- [x] historical data mode (Yahoo Finance)
- [ ] fix the volatility decay (its a bit aggressive)
- [ ] mobile responsive layout

## Sample output

```
══════════════════════════════════════════════════════════════════
                    SIMULATION COMPLETE
══════════════════════════════════════════════════════════════════
Duration:              60 seconds
Total Trades:          24
Trade Value:           $204,778.71

Most Profitable Bot: Mean Reversion Trader (+$17,026.92)
Portfolio Peak Value: $100,000.00
══════════════════════════════════════════════════════════════════
```
