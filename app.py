"""
Stock Market Simulator - Web Dashboard
======================================

Beautiful Streamlit-based web UI for the stock market simulator.
Run with: streamlit run app.py
"""

import streamlit as st
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
import time
import threading
import yaml
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.market import MarketEngine
from trading.broker import Broker
from bots.base import BotManager
from bots.momentum import MomentumBot
from bots.mean_reversion import MeanReversionBot
from bots.arbitrage import ArbitrageBot
from utils.logger import AuditLogger
from utils.indicators import TechnicalIndicators

# Page configuration
st.set_page_config(
    page_title="Stock Market Simulator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        border-radius: 12px;
        padding: 1rem;
        color: white;
    }
    .price-up { color: #00ff88; font-weight: bold; }
    .price-down { color: #ff4757; font-weight: bold; }
    .stMetric { 
        background-color: #1e1e2e;
        border-radius: 10px;
        padding: 10px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
</style>
""", unsafe_allow_html=True)


# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.running = False
    st.session_state.price_history = {}
    st.session_state.bot_stats = []
    st.session_state.market_events = []
    st.session_state.trades = []
    st.session_state.tick_count = 0


def load_config():
    """Load configuration."""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)


@st.cache_resource
def initialize_simulation():
    """Initialize simulation components (cached)."""
    config = load_config()
    logger = AuditLogger(config)
    indicators = TechnicalIndicators()
    return config, logger, indicators


def run_simulation_step(market, broker, bot_manager, indicators):
    """Run one simulation step."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def step():
        # Update prices
        updates = await market.asset_manager.update_prices(1.0)
        
        # Update indicators
        for symbol, price in updates.items():
            asset = market.asset_manager.get_asset(symbol)
            if asset:
                indicators.update(symbol, price, asset.volume)
        
        # Run bot cycle
        await bot_manager.run_trading_cycle()
        
        # Run settlement
        await broker.run_settlement_cycle()
        await broker.refresh_liquidity()
        
        return updates
    
    result = loop.run_until_complete(step())
    loop.close()
    return result


def main():
    # Header
    st.markdown('<h1 class="main-header">📈 Stock Market Simulator</h1>', unsafe_allow_html=True)
    
    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Controls")
        
        tick_rate = st.slider("Tick Rate (updates/sec)", 1, 10, 2)
        duration = st.slider("Duration (seconds)", 30, 300, 60)
        
        col1, col2 = st.columns(2)
        with col1:
            start_btn = st.button("▶️ Start", use_container_width=True)
        with col2:
            stop_btn = st.button("⏹️ Stop", use_container_width=True)
        
        st.divider()
        st.header("📊 Settings")
        enable_momentum = st.checkbox("Momentum Bot", value=True)
        enable_mr = st.checkbox("Mean Reversion Bot", value=True)
        enable_arb = st.checkbox("Arbitrage Bot", value=True)
    
    # Initialize simulation on first run or start button
    if start_btn and not st.session_state.running:
        st.session_state.running = True
        st.session_state.price_history = {sym: [] for sym in ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'JPM', 'NVDA', 'META', 'BRK.B', 'V']}
        st.session_state.tick_count = 0
        st.rerun()
    
    if stop_btn:
        st.session_state.running = False
        st.rerun()
    
    # Main content
    if st.session_state.running:
        config, logger, indicators = initialize_simulation()
        
        # Initialize components
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def init():
            market = MarketEngine(config, logger)
            market._tick_rate = tick_rate
            market._tick_interval = 1.0 / tick_rate
            await market.initialize()
            
            broker = Broker(config, market, logger)
            await broker.initialize()
            
            bot_manager = BotManager(config, broker, market, indicators, logger)
            
            if enable_momentum:
                bot_manager.register_bot(MomentumBot('BOT-MOM', config, broker, market, indicators, logger))
            if enable_mr:
                bot_manager.register_bot(MeanReversionBot('BOT-MR', config, broker, market, indicators, logger))
            if enable_arb:
                bot_manager.register_bot(ArbitrageBot('BOT-ARB', config, broker, market, indicators, logger))
            
            await bot_manager.start_all()
            
            return market, broker, bot_manager
        
        market, broker, bot_manager = loop.run_until_complete(init())
        
        # Create placeholders for live updates
        status_placeholder = st.empty()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📊 Live Stock Prices")
            price_table = st.empty()
            
            st.subheader("📈 Price Chart")
            chart_placeholder = st.empty()
        
        with col2:
            st.subheader("🤖 Bot Performance")
            bot_placeholder = st.empty()
            
            st.subheader("📰 Market Events")
            events_placeholder = st.empty()
        
        # Run simulation loop
        progress = st.progress(0)
        start_time = time.time()
        
        for tick in range(duration * tick_rate):
            if not st.session_state.running:
                break
            
            # Run simulation step
            updates = run_simulation_step(market, broker, bot_manager, indicators)
            st.session_state.tick_count += 1
            
            # Update price history
            for symbol, price in updates.items():
                if symbol in st.session_state.price_history:
                    st.session_state.price_history[symbol].append(price)
                    # Keep last 100 points
                    if len(st.session_state.price_history[symbol]) > 100:
                        st.session_state.price_history[symbol] = st.session_state.price_history[symbol][-100:]
            
            # Update progress
            elapsed = time.time() - start_time
            progress.progress(min(1.0, elapsed / duration))
            
            # Update status
            summary = market.get_market_summary()
            with status_placeholder.container():
                cols = st.columns(5)
                cols[0].metric("⏱️ Tick", f"{st.session_state.tick_count}")
                cols[1].metric("📊 Events", f"{summary['events_processed']}")
                cols[2].metric("📈 Advancing", f"{summary['advancing']}")
                cols[3].metric("📉 Declining", f"{summary['declining']}")
                cols[4].metric("⚡ Volatility", f"{summary['avg_volatility']*100:.1f}%")
            
            # Update price table
            price_data = []
            for asset in market.asset_manager.get_all_assets():
                change, pct = asset.get_daily_change()
                price_data.append({
                    'Symbol': asset.symbol,
                    'Price': f"${asset.price:.2f}",
                    'Change': f"{'+' if change >= 0 else ''}{change:.2f}",
                    'Change %': f"{'+' if pct >= 0 else ''}{pct:.2f}%",
                    'Volume': f"{asset.volume:,}",
                    'Status': '🔴 HALTED' if asset.is_halted else '🟢 ACTIVE'
                })
            
            df = pd.DataFrame(price_data)
            price_table.dataframe(df, use_container_width=True, hide_index=True)
            
            # Update chart
            chart_data = pd.DataFrame(st.session_state.price_history)
            if not chart_data.empty:
                # Normalize to show percentage change
                normalized = chart_data / chart_data.iloc[0] * 100 - 100
                chart_placeholder.line_chart(normalized, height=300)
            
            # Update bot performance
            bot_data = []
            for bot in bot_manager.get_all_bots():
                s = bot.get_summary()
                pnl = s['stats']['total_pnl']
                bot_data.append({
                    'Bot': s['name'],
                    'P&L': f"{'+'if pnl >= 0 else ''}{pnl:,.2f}",
                    'Trades': s['stats']['trades'],
                    'Win Rate': f"{s['stats']['win_rate']:.1f}%"
                })
            
            if bot_data:
                bot_placeholder.dataframe(pd.DataFrame(bot_data), use_container_width=True, hide_index=True)
            
            # Update events
            events = market.event_system.get_event_history(5) if market.event_system else []
            if events:
                event_texts = [f"📢 {e.title}" for e in events[-5:]]
                events_placeholder.markdown("\n\n".join(event_texts))
            
            # Sleep for tick interval
            time.sleep(1.0 / tick_rate)
        
        # Simulation complete
        st.session_state.running = False
        progress.progress(1.0)
        
        st.success("✅ Simulation Complete!")
        
        # Final summary
        st.subheader("📋 Final Summary")
        
        summary = market.get_market_summary()
        broker_stats = broker.get_broker_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Ticks", f"{summary['tick_count']:,}")
        col2.metric("Total Trades", f"{broker_stats['total_trades']:,}")
        col3.metric("Trade Value", f"${broker_stats['total_trade_value']:,.2f}")
        col4.metric("Avg Volatility", f"{summary['avg_volatility']*100:.2f}%")
        
        # Best bot
        leaderboard = bot_manager.get_leaderboard()
        if leaderboard:
            best = leaderboard[0]
            st.info(f"🏆 **Most Profitable Bot:** {best['name']} (+${best['stats']['total_pnl']:,.2f})")
        
        loop.close()
    
    else:
        # Not running - show welcome screen
        st.info("👋 Welcome to the Stock Market Simulator! Click **Start** in the sidebar to begin.")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            ### 📊 Market Simulation
            - 10 major stocks
            - Real-time price updates
            - GBM price model
            - Market events & news
            """)
        
        with col2:
            st.markdown("""
            ### 🤖 AI Trading Bots
            - Momentum strategy
            - Mean reversion
            - Arbitrage trading
            - Technical indicators
            """)
        
        with col3:
            st.markdown("""
            ### 📈 Features
            - Live price charts
            - P&L tracking
            - Order book simulation
            - Audit logging
            """)


if __name__ == "__main__":
    main()

