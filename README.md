# Stock Market Simulator

I built this to learn how stock markets work under the hood. It simulates a market with fake stocks, and you can watch trading bots compete against each other.

## What it does

- Runs a fake stock market with 10 stocks
- Prices move realistically using math (Geometric Brownian Motion)
- Three trading bots buy and sell automatically
- Shows everything in a live dashboard

## The bots

**Momentum bot** - follows trends. If a stock is going up, it buys.

**Mean reversion bot** - does the opposite. If a stock dropped too much, it buys expecting it to bounce back.

**Arbitrage bot** - watches pairs of similar stocks. If one gets cheaper than the other, it trades the gap.

## Getting started

```
cd stock-sim
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Run options

```
python main.py                   # runs for 5 minutes
python main.py --duration 600    # runs for 10 minutes
python main.py --tick-rate 2     # prices update faster
python main.py --no-bots         # no bots, just watch prices
```

## Using real stock data

You can run it with actual historical prices from Yahoo Finance instead of fake data:

```
python main.py --historical
python main.py --historical --period 3mo --interval 1d
python main.py --historical --period 1y --interval 1d
```

## Web dashboard

There's a nicer looking web version:

```
# terminal 1
source venv/bin/activate
python api/server.py

# terminal 2
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## How the order book works

When a bot wants to buy, it places an order. The order book matches buyers with sellers. Best price wins, and if prices are equal, whoever ordered first wins.

Supports market orders, limit orders, stop loss, and take profit.

## Folder structure
```
engine/    - price simulation and market logic
trading/   - order book and portfolio tracking
bots/      - the three trading strategies
api/       - backend server for web dashboard
frontend/  - react app
main.py    - run this to start
```

## Logs

Everything gets logged to logs/audit.log. The logs are hash-chained so you can check if anyone messed with them.

## Tech

Python for the simulation. FastAPI and WebSockets for real-time data. React and TypeScript for the dashboard.

## Still working on

- Better arbitrage detection
- More technical indicators
- Mobile friendly layout
