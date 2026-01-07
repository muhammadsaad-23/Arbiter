from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.market import MarketEngine
from trading.broker import Broker
from bots.base import BotManager
from bots.momentum import MomentumBot
from bots.mean_reversion import MeanReversionBot
from bots.arbitrage import ArbitrageBot
from utils.logger import AuditLogger
from utils.indicators import TechnicalIndicators
import yaml

app = FastAPI(title="Stock Market Simulator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# global state
sim_state = {
    "running": False,
    "market": None,
    "broker": None,
    "bot_manager": None,
    "indicators": None,
    "config": None,
    "logger": None
}

clients: list[WebSocket] = []


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def broadcast(data: dict):
    dead = []
    for client in clients:
        try:
            await client.send_json(data)
        except:
            dead.append(client)
    for d in dead:
        clients.remove(d)


async def init_simulation():
    config = load_config()
    logger = AuditLogger(config)
    indicators = TechnicalIndicators()
    
    market = MarketEngine(config, logger)
    await market.initialize()
    
    broker = Broker(config, market, logger)
    await broker.initialize()
    
    bot_manager = BotManager(config, broker, market, indicators, logger)
    
    bot_manager.register_bot(MomentumBot('BOT-MOM', config, broker, market, indicators, logger))
    bot_manager.register_bot(MeanReversionBot('BOT-MR', config, broker, market, indicators, logger))
    bot_manager.register_bot(ArbitrageBot('BOT-ARB', config, broker, market, indicators, logger))
    
    sim_state.update({
        "config": config,
        "logger": logger,
        "indicators": indicators,
        "market": market,
        "broker": broker,
        "bot_manager": bot_manager
    })
    
    return True


async def run_simulation_tick():
    market = sim_state["market"]
    broker = sim_state["broker"]
    bot_manager = sim_state["bot_manager"]
    indicators = sim_state["indicators"]
    
    if not market:
        return None
    
    # update prices
    updates = await market.asset_manager.update_prices(0.2)
    
    # feed indicators
    for symbol, price in updates.items():
        asset = market.asset_manager.get_asset(symbol)
        if asset:
            indicators.update(symbol, price, asset.volume)
    
    # run bots
    await bot_manager.run_trading_cycle()
    
    # settlement
    await broker.run_settlement_cycle()
    await broker.refresh_liquidity()
    
    # build response
    assets_data = []
    for asset in market.asset_manager.get_all_assets():
        change, pct = asset.get_daily_change()
        assets_data.append({
            "symbol": asset.symbol,
            "price": asset.price,
            "change": change,
            "changePct": pct,
            "volume": asset.volume,
            "high": asset.high_price,
            "low": asset.low_price,
            "isHalted": asset.is_halted
        })
    
    bots_data = []
    for bot in bot_manager.get_all_bots():
        s = bot.get_summary()
        bots_data.append({
            "name": s["name"],
            "pnl": s["stats"]["total_pnl"],
            "trades": s["stats"]["trades"],
            "winRate": s["stats"]["win_rate"],
            "portfolioValue": s["portfolio_value"]
        })
    
    market_stats = market.asset_manager.get_market_stats()
    broker_stats = broker.get_broker_stats()
    
    return {
        "type": "tick",
        "assets": assets_data,
        "bots": bots_data,
        "market": {
            "totalVolume": market_stats.get("total_volume", 0),
            "avgVolatility": market_stats.get("avg_volatility", 0) * 100,
            "advancing": market_stats.get("advancing", 0),
            "declining": market_stats.get("declining", 0),
            "halted": market_stats.get("halted", 0)
        },
        "trading": {
            "totalOrders": broker_stats.get("total_orders", 0),
            "totalTrades": broker_stats.get("total_trades", 0),
            "tradeValue": broker_stats.get("total_trade_value", 0)
        }
    }


@app.get("/")
async def root():
    return {"status": "ok", "message": "Stock Market Simulator API"}


@app.post("/simulation/init")
async def init_sim():
    await init_simulation()
    return {"status": "initialized"}


@app.post("/simulation/start")
async def start_sim():
    if not sim_state["market"]:
        await init_simulation()
    
    sim_state["running"] = True
    await sim_state["bot_manager"].start_all()
    return {"status": "started"}


@app.post("/simulation/stop")
async def stop_sim():
    sim_state["running"] = False
    if sim_state["bot_manager"]:
        await sim_state["bot_manager"].stop_all()
    return {"status": "stopped"}


@app.get("/simulation/state")
async def get_state():
    if not sim_state["market"]:
        return {"running": False, "initialized": False}
    
    data = await run_simulation_tick()
    data["running"] = sim_state["running"]
    data["initialized"] = True
    return data


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    
    try:
        # init if needed
        if not sim_state["market"]:
            await init_simulation()
            await sim_state["bot_manager"].start_all()
        
        sim_state["running"] = True
        
        while True:
            if sim_state["running"]:
                data = await run_simulation_tick()
                if data:
                    await websocket.send_json(data)
            
            await asyncio.sleep(0.5)  # 2 ticks per second
            
    except WebSocketDisconnect:
        clients.remove(websocket)
    except Exception as e:
        print(f"ws error: {e}")
        if websocket in clients:
            clients.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

