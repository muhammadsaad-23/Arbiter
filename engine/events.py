"""
Market Event System
===================

Simulates market events that affect prices:
- Breaking news (earnings, mergers, crashes)
- Volatility spikes
- Market halts
- Pre-market and after-hours rules
- Sentiment-driven price impacts
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import math


class EventType(Enum):
    """Types of market events."""
    EARNINGS_REPORT = "earnings_report"
    MERGER_ANNOUNCEMENT = "merger_announcement"
    PRODUCT_LAUNCH = "product_launch"
    REGULATORY_ACTION = "regulatory_action"
    ANALYST_UPGRADE = "analyst_upgrade"
    ANALYST_DOWNGRADE = "analyst_downgrade"
    MARKET_CRASH = "market_crash"
    SECTOR_ROTATION = "sector_rotation"
    VOLATILITY_SPIKE = "volatility_spike"
    MARKET_HALT = "market_halt"
    TRADING_RESUME = "trading_resume"
    DIVIDEND_ANNOUNCEMENT = "dividend_announcement"
    STOCK_SPLIT = "stock_split"
    ECONOMIC_DATA = "economic_data"
    GEOPOLITICAL = "geopolitical"


class Sentiment(Enum):
    """Event sentiment classification."""
    VERY_BULLISH = 2.0
    BULLISH = 1.0
    NEUTRAL = 0.0
    BEARISH = -1.0
    VERY_BEARISH = -2.0


@dataclass
class MarketEvent:
    """
    Represents a market event that affects prices.
    
    Events have:
    - Type and description
    - Affected symbols
    - Sentiment score
    - Price impact magnitude
    - Duration of effect
    """
    event_id: str
    event_type: EventType
    title: str
    description: str
    affected_symbols: List[str]
    sentiment: Sentiment
    impact_magnitude: float  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    duration_seconds: int = 60
    is_market_wide: bool = False
    sector: Optional[str] = None
    
    def get_price_impact(self) -> float:
        """
        Calculate price impact percentage.
        
        Returns positive for bullish, negative for bearish.
        """
        base_impact = self.sentiment.value * self.impact_magnitude * 0.05
        # Add some randomness
        noise = random.gauss(0, 0.01)
        return base_impact + noise

    def to_dict(self) -> Dict:
        """Serialize event to dictionary."""
        return {
            'event_id': self.event_id,
            'type': self.event_type.value,
            'title': self.title,
            'description': self.description,
            'affected_symbols': self.affected_symbols,
            'sentiment': self.sentiment.name,
            'impact': self.impact_magnitude,
            'timestamp': self.timestamp.isoformat(),
            'is_market_wide': self.is_market_wide
        }


class EventGenerator:
    """Generates random market events."""
    
    # Event templates
    TEMPLATES = {
        EventType.EARNINGS_REPORT: [
            ("{symbol} Beats Earnings Expectations", Sentiment.BULLISH, 0.6),
            ("{symbol} Misses Earnings Estimates", Sentiment.BEARISH, 0.5),
            ("{symbol} Reports Record Revenue", Sentiment.VERY_BULLISH, 0.8),
            ("{symbol} Warns of Slowing Growth", Sentiment.VERY_BEARISH, 0.7),
        ],
        EventType.MERGER_ANNOUNCEMENT: [
            ("{symbol} Announces Acquisition", Sentiment.BULLISH, 0.7),
            ("{symbol} Merger Deal Falls Through", Sentiment.BEARISH, 0.6),
            ("Major Buyout Offer for {symbol}", Sentiment.VERY_BULLISH, 0.9),
        ],
        EventType.ANALYST_UPGRADE: [
            ("{symbol} Upgraded to Buy", Sentiment.BULLISH, 0.4),
            ("Major Bank Raises {symbol} Target", Sentiment.BULLISH, 0.5),
        ],
        EventType.ANALYST_DOWNGRADE: [
            ("{symbol} Downgraded to Sell", Sentiment.BEARISH, 0.4),
            ("Analysts Cut {symbol} Price Target", Sentiment.BEARISH, 0.5),
        ],
        EventType.PRODUCT_LAUNCH: [
            ("{symbol} Unveils New Product Line", Sentiment.BULLISH, 0.5),
            ("{symbol} Product Launch Delayed", Sentiment.BEARISH, 0.4),
        ],
        EventType.REGULATORY_ACTION: [
            ("{symbol} Faces Regulatory Investigation", Sentiment.VERY_BEARISH, 0.7),
            ("{symbol} Receives FDA Approval", Sentiment.VERY_BULLISH, 0.8),
            ("Antitrust Concerns for {symbol}", Sentiment.BEARISH, 0.6),
        ],
        EventType.VOLATILITY_SPIKE: [
            ("Unusual Options Activity in {symbol}", Sentiment.NEUTRAL, 0.3),
            ("Short Squeeze Developing in {symbol}", Sentiment.BULLISH, 0.7),
        ],
        EventType.DIVIDEND_ANNOUNCEMENT: [
            ("{symbol} Raises Dividend", Sentiment.BULLISH, 0.3),
            ("{symbol} Cuts Dividend", Sentiment.BEARISH, 0.5),
        ],
    }

    MARKET_WIDE_EVENTS = [
        (EventType.MARKET_CRASH, "Flash Crash Triggers Selling", Sentiment.VERY_BEARISH, 0.9),
        (EventType.ECONOMIC_DATA, "Fed Announces Rate Decision", Sentiment.NEUTRAL, 0.5),
        (EventType.ECONOMIC_DATA, "Jobs Report Beats Expectations", Sentiment.BULLISH, 0.4),
        (EventType.ECONOMIC_DATA, "Inflation Data Spooks Markets", Sentiment.BEARISH, 0.6),
        (EventType.GEOPOLITICAL, "Geopolitical Tensions Rise", Sentiment.BEARISH, 0.5),
        (EventType.SECTOR_ROTATION, "Sector Rotation Underway", Sentiment.NEUTRAL, 0.3),
    ]

    def __init__(self, symbols: List[str], sectors: Dict[str, List[str]]):
        self.symbols = symbols
        self.sectors = sectors
        self._event_counter = 0

    def _generate_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"EVT-{timestamp}-{self._event_counter:04d}"

    def generate_company_event(self, symbol: Optional[str] = None) -> MarketEvent:
        """Generate a random company-specific event."""
        if symbol is None:
            symbol = random.choice(self.symbols)
        
        event_type = random.choice(list(self.TEMPLATES.keys()))
        template = random.choice(self.TEMPLATES[event_type])
        title_template, sentiment, impact = template
        
        # Add randomness to impact
        impact = min(1.0, max(0.1, impact + random.gauss(0, 0.1)))
        
        return MarketEvent(
            event_id=self._generate_id(),
            event_type=event_type,
            title=title_template.format(symbol=symbol),
            description=f"Breaking news affecting {symbol}",
            affected_symbols=[symbol],
            sentiment=sentiment,
            impact_magnitude=impact,
            duration_seconds=random.randint(30, 300)
        )

    def generate_sector_event(self, sector: str) -> MarketEvent:
        """Generate an event affecting an entire sector."""
        if sector not in self.sectors:
            sector = random.choice(list(self.sectors.keys()))
        
        affected = self.sectors[sector]
        sentiment = random.choice([Sentiment.BULLISH, Sentiment.BEARISH])
        
        if sentiment == Sentiment.BULLISH:
            title = f"{sector} Sector Rallies on Positive News"
        else:
            title = f"Pressure on {sector} Sector"
        
        return MarketEvent(
            event_id=self._generate_id(),
            event_type=EventType.SECTOR_ROTATION,
            title=title,
            description=f"Sector-wide event affecting {sector}",
            affected_symbols=affected,
            sentiment=sentiment,
            impact_magnitude=random.uniform(0.3, 0.6),
            duration_seconds=random.randint(60, 600),
            sector=sector
        )

    def generate_market_event(self) -> MarketEvent:
        """Generate a market-wide event."""
        event_type, title, sentiment, impact = random.choice(self.MARKET_WIDE_EVENTS)
        
        return MarketEvent(
            event_id=self._generate_id(),
            event_type=event_type,
            title=title,
            description="Market-wide event affecting all assets",
            affected_symbols=self.symbols.copy(),
            sentiment=sentiment,
            impact_magnitude=impact + random.gauss(0, 0.1),
            duration_seconds=random.randint(120, 900),
            is_market_wide=True
        )


class TradingSession(Enum):
    """Trading session types."""
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    CLOSED = "closed"


class EventSystem:
    """
    Main event system that manages market events.
    
    Features:
    - Automatic event generation
    - Event processing and price impact
    - Trading session management
    - Event history and replay
    """

    def __init__(self, config: Dict, asset_manager: Any, logger: Any):
        self._config = config
        self._asset_manager = asset_manager
        self._logger = logger
        
        # Event settings
        events_config = config.get('market', {}).get('events', {})
        self._news_frequency = events_config.get('news_frequency', 0.05)
        self._crash_probability = events_config.get('crash_probability', 0.001)
        self._halt_threshold = events_config.get('halt_threshold', 0.10)
        self._halt_duration = events_config.get('halt_duration', 60)
        
        # Trading hours
        hours_config = config.get('market', {}).get('trading_hours', {})
        self._pre_market_start = self._parse_time(hours_config.get('pre_market_start', '04:00'))
        self._market_open = self._parse_time(hours_config.get('market_open', '09:30'))
        self._market_close = self._parse_time(hours_config.get('market_close', '16:00'))
        self._after_hours_end = self._parse_time(hours_config.get('after_hours_end', '20:00'))
        
        # State
        self._event_generator: Optional[EventGenerator] = None
        self._event_history: List[MarketEvent] = []
        self._active_events: List[MarketEvent] = []
        self._callbacks: List[Callable] = []
        self._halted_until: Dict[str, datetime] = {}
        self._is_running = False

    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object."""
        parts = time_str.split(':')
        return time(int(parts[0]), int(parts[1]))

    async def initialize(self):
        """Initialize event system."""
        symbols = self._asset_manager.get_symbols()
        sectors = {}
        for asset in self._asset_manager.get_all_assets():
            if asset.sector not in sectors:
                sectors[asset.sector] = []
            sectors[asset.sector].append(asset.symbol)
        
        self._event_generator = EventGenerator(symbols, sectors)

    def get_current_session(self) -> TradingSession:
        """Determine current trading session."""
        now = datetime.now().time()
        
        if self._pre_market_start <= now < self._market_open:
            return TradingSession.PRE_MARKET
        elif self._market_open <= now < self._market_close:
            return TradingSession.REGULAR
        elif self._market_close <= now < self._after_hours_end:
            return TradingSession.AFTER_HOURS
        else:
            return TradingSession.CLOSED

    def is_market_open(self) -> bool:
        """Check if regular market session is open."""
        return self.get_current_session() == TradingSession.REGULAR

    def can_trade(self, symbol: str) -> bool:
        """Check if trading is allowed for a symbol."""
        session = self.get_current_session()
        
        if session == TradingSession.CLOSED:
            return False
        
        # Check if symbol is halted
        if symbol in self._halted_until:
            if datetime.now() < self._halted_until[symbol]:
                return False
            else:
                del self._halted_until[symbol]
        
        asset = self._asset_manager.get_asset(symbol)
        if asset and asset.is_halted:
            return False
        
        return True

    def register_callback(self, callback: Callable[[MarketEvent], None]):
        """Register callback for event notifications."""
        self._callbacks.append(callback)

    async def generate_events(self) -> List[MarketEvent]:
        """
        Generate random events based on configured probabilities.
        
        Called each tick to potentially create new events.
        """
        if not self._event_generator:
            return []
        
        events = []
        
        # Check for market crash (rare)
        if random.random() < self._crash_probability:
            event = self._event_generator.generate_market_event()
            events.append(event)
        
        # Check for regular news
        if random.random() < self._news_frequency:
            # 70% company-specific, 20% sector, 10% market-wide
            roll = random.random()
            if roll < 0.7:
                event = self._event_generator.generate_company_event()
            elif roll < 0.9:
                sectors = list(self._asset_manager._sectors.keys())
                if sectors:
                    event = self._event_generator.generate_sector_event(random.choice(sectors))
                else:
                    event = self._event_generator.generate_company_event()
            else:
                event = self._event_generator.generate_market_event()
            
            events.append(event)
        
        # Process generated events
        for event in events:
            await self._process_event(event)
        
        return events

    async def _process_event(self, event: MarketEvent):
        """Process an event and apply its effects."""
        self._event_history.append(event)
        self._active_events.append(event)
        
        # Log the event
        self._logger.log_market_event(
            event_name=event.title,
            affected_symbols=event.affected_symbols,
            impact=event.event_type.value,
            sentiment_score=event.sentiment.value
        )
        
        # Apply price impact to affected symbols
        impact = event.get_price_impact()
        is_positive = impact > 0
        
        for symbol in event.affected_symbols:
            asset = self._asset_manager.get_asset(symbol)
            if asset and not asset.is_halted:
                # Apply shock with sentiment-adjusted magnitude
                asset.apply_shock(abs(impact), is_positive)
                
                # Increase volatility during events
                asset.volatility = min(0.5, asset.volatility * (1 + event.impact_magnitude))
        
        # Check for circuit breakers
        halted = self._asset_manager.check_circuit_breakers(self._halt_threshold)
        for symbol in halted:
            self._halted_until[symbol] = datetime.now()
            # Schedule resume
            asyncio.create_task(self._schedule_resume(symbol, self._halt_duration))
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass

    async def _schedule_resume(self, symbol: str, duration: int):
        """Schedule trading resume after halt."""
        await asyncio.sleep(duration)
        
        asset = self._asset_manager.get_asset(symbol)
        if asset:
            asset.resume()
            
            # Create resume event
            resume_event = MarketEvent(
                event_id=self._event_generator._generate_id(),
                event_type=EventType.TRADING_RESUME,
                title=f"Trading Resumes for {symbol}",
                description=f"Trading halt lifted for {symbol}",
                affected_symbols=[symbol],
                sentiment=Sentiment.NEUTRAL,
                impact_magnitude=0.1
            )
            self._event_history.append(resume_event)
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(resume_event)
                except Exception:
                    pass

    async def trigger_event(self, event_type: EventType, symbol: str,
                           sentiment: Sentiment, magnitude: float) -> MarketEvent:
        """Manually trigger a specific event."""
        if not self._event_generator:
            await self.initialize()
        
        event = MarketEvent(
            event_id=self._event_generator._generate_id(),
            event_type=event_type,
            title=f"Manual Event: {event_type.value}",
            description=f"Manually triggered event for {symbol}",
            affected_symbols=[symbol],
            sentiment=sentiment,
            impact_magnitude=magnitude
        )
        
        await self._process_event(event)
        return event

    async def trigger_market_halt(self, reason: str = "Emergency halt"):
        """Trigger market-wide trading halt."""
        for asset in self._asset_manager.get_all_assets():
            asset.halt(reason)
        
        event = MarketEvent(
            event_id=self._event_generator._generate_id() if self._event_generator else "HALT-001",
            event_type=EventType.MARKET_HALT,
            title="Market-Wide Trading Halt",
            description=reason,
            affected_symbols=self._asset_manager.get_symbols(),
            sentiment=Sentiment.VERY_BEARISH,
            impact_magnitude=1.0,
            is_market_wide=True
        )
        
        self._event_history.append(event)
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass

    def get_active_events(self) -> List[MarketEvent]:
        """Get currently active events."""
        now = datetime.now()
        # Filter out expired events
        self._active_events = [
            e for e in self._active_events
            if (now - e.timestamp).total_seconds() < e.duration_seconds
        ]
        return self._active_events

    def get_event_history(self, limit: int = 100) -> List[MarketEvent]:
        """Get recent event history."""
        return self._event_history[-limit:]

    def get_events_for_symbol(self, symbol: str, limit: int = 10) -> List[MarketEvent]:
        """Get events affecting a specific symbol."""
        events = [e for e in self._event_history if symbol in e.affected_symbols]
        return events[-limit:]

    def cleanup_expired_events(self):
        """Remove expired events from active list."""
        now = datetime.now()
        self._active_events = [
            e for e in self._active_events
            if (now - e.timestamp).total_seconds() < e.duration_seconds
        ]

