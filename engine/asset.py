import asyncio
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np


class PriceModel(Enum):
    RANDOM_WALK = "random_walk"
    GBM = "gbm"
    HYBRID = "hybrid"


@dataclass
class PriceTick:
    timestamp: datetime
    price: float
    bid: float
    ask: float
    volume: int
    open: float
    high: float
    low: float


@dataclass
class Asset:
    symbol: str
    name: str
    initial_price: float
    volatility: float = 0.02
    sector: str = "General"
    
    price: float = field(init=False)
    bid: float = field(init=False)
    ask: float = field(init=False)
    volume: int = field(default=0)
    
    open_price: float = field(init=False)
    high_price: float = field(init=False)
    low_price: float = field(init=False)
    prev_close: float = field(init=False)
    
    bid_depth: int = field(default=0)
    ask_depth: int = field(default=0)
    liquidity_score: float = field(default=1.0)
    
    drift: float = 0.0001
    mean_reversion_speed: float = 0.1
    long_term_mean: float = field(init=False)
    
    price_history: List[PriceTick] = field(default_factory=list)
    max_history: int = 1000
    
    is_halted: bool = field(default=False)
    halt_reason: str = field(default="")
    
    def __post_init__(self):
        self.price = self.initial_price
        self.open_price = self.initial_price
        self.high_price = self.initial_price
        self.low_price = self.initial_price
        self.prev_close = self.initial_price
        self.long_term_mean = self.initial_price
        self._update_bid_ask()
        self._tick_count = 0
        self._cumulative_volume = 0
        
    def _update_bid_ask(self):
        # spread widens with vol, narrows with liquidity
        base_spread = max(0.01, self.price * self.volatility * 0.1)
        spread_adjustment = base_spread / max(0.1, self.liquidity_score)
        half_spread = spread_adjustment / 2
        
        self.bid = round(self.price - half_spread, 2)
        self.ask = round(self.price + half_spread, 2)

    def get_spread(self) -> float:
        return self.ask - self.bid

    def get_spread_pct(self) -> float:
        return (self.get_spread() / self.price) * 100 if self.price > 0 else 0

    def update_price_random_walk(self, dt: float = 1.0) -> float:
        if self.is_halted:
            return self.price
            
        epsilon = random.gauss(0, 1)
        change = self.volatility * epsilon * math.sqrt(dt) * self.price
        
        new_price = max(0.01, self.price + change)
        self._apply_price_update(new_price)
        return self.price

    def update_price_gbm(self, dt: float = 1.0) -> float:
        # geometric brownian motion - the classic
        if self.is_halted:
            return self.price
            
        dW = random.gauss(0, 1) * math.sqrt(dt)
        
        drift_component = (self.drift - 0.5 * self.volatility ** 2) * dt
        diffusion_component = self.volatility * dW
        
        log_return = drift_component + diffusion_component
        new_price = self.price * math.exp(log_return)
        
        new_price = max(0.01, new_price)
        self._apply_price_update(new_price)
        return self.price

    def update_price_hybrid(self, dt: float = 1.0) -> float:
        # gbm + mean reversion so prices dont go crazy
        if self.is_halted:
            return self.price
            
        dW = random.gauss(0, 1) * math.sqrt(dt)
        gbm_return = (self.drift - 0.5 * self.volatility ** 2) * dt + self.volatility * dW
        
        mean_reversion = self.mean_reversion_speed * (
            math.log(self.long_term_mean) - math.log(self.price)
        ) * dt
        
        total_return = gbm_return + mean_reversion
        new_price = self.price * math.exp(total_return)
        
        new_price = max(0.01, new_price)
        self._apply_price_update(new_price)
        return self.price

    def apply_shock(self, magnitude: float, is_positive: bool = True):
        if self.is_halted:
            return
            
        multiplier = 1 + magnitude if is_positive else 1 - magnitude
        new_price = max(0.01, self.price * multiplier)
        
        # bump up volatility temporarily
        self.volatility = min(0.5, self.volatility * 1.5)
        
        self._apply_price_update(new_price)

    def _apply_price_update(self, new_price: float):
        old_price = self.price
        self.price = round(new_price, 2)
        
        self.high_price = max(self.high_price, self.price)
        self.low_price = min(self.low_price, self.price)
        
        # volume correlates with price movement (kinda realistic)
        price_change_pct = abs(new_price - old_price) / old_price if old_price > 0 else 0
        base_volume = random.randint(100, 10000)
        volume_multiplier = 1 + (price_change_pct * 50)
        self.volume = int(base_volume * volume_multiplier * self.liquidity_score)
        self._cumulative_volume += self.volume
        
        self._update_bid_ask()
        self._record_tick()
        self._tick_count += 1
        
        # vol decay back to normal
        self.volatility = max(0.005, self.volatility * 0.999)

    def _record_tick(self):
        tick = PriceTick(
            timestamp=datetime.now(),
            price=self.price,
            bid=self.bid,
            ask=self.ask,
            volume=self.volume,
            open=self.open_price,
            high=self.high_price,
            low=self.low_price
        )
        self.price_history.append(tick)
        
        if len(self.price_history) > self.max_history:
            self.price_history = self.price_history[-self.max_history:]

    def halt(self, reason: str = "Circuit breaker"):
        self.is_halted = True
        self.halt_reason = reason

    def resume(self):
        self.is_halted = False
        self.halt_reason = ""

    def new_session(self):
        self.prev_close = self.price
        self.open_price = self.price
        self.high_price = self.price
        self.low_price = self.price
        self._cumulative_volume = 0

    def get_daily_change(self) -> Tuple[float, float]:
        change = self.price - self.prev_close
        pct = (change / self.prev_close) * 100 if self.prev_close > 0 else 0
        return change, pct

    def get_stats(self) -> Dict:
        change, pct = self.get_daily_change()
        return {
            'symbol': self.symbol,
            'name': self.name,
            'price': self.price,
            'bid': self.bid,
            'ask': self.ask,
            'spread': self.get_spread(),
            'spread_pct': self.get_spread_pct(),
            'volume': self.volume,
            'cumulative_volume': self._cumulative_volume,
            'open': self.open_price,
            'high': self.high_price,
            'low': self.low_price,
            'prev_close': self.prev_close,
            'change': change,
            'change_pct': pct,
            'volatility': self.volatility,
            'liquidity': self.liquidity_score,
            'is_halted': self.is_halted,
            'tick_count': self._tick_count
        }

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'name': self.name,
            'price': self.price,
            'bid': self.bid,
            'ask': self.ask,
            'volume': self.volume,
            'volatility': self.volatility,
            'sector': self.sector,
            'is_halted': self.is_halted
        }


class AssetManager:
    def __init__(self, config: Dict):
        self._config = config
        self._assets: Dict[str, Asset] = {}
        self._sectors: Dict[str, List[str]] = {}
        self._correlations: Dict[Tuple[str, str], float] = {}
        self._price_model = PriceModel(
            config.get('market', {}).get('price_models', {}).get('default', 'gbm')
        )
        self._lock = asyncio.Lock()

    async def initialize(self):
        assets_config = self._config.get('assets', {})
        default_symbols = assets_config.get('default_symbols', [])
        
        for asset_def in default_symbols:
            await self.add_asset(
                symbol=asset_def['symbol'],
                name=asset_def['name'],
                initial_price=asset_def['initial_price'],
                volatility=asset_def.get('volatility', 0.02),
                sector=asset_def.get('sector', 'General')
            )
        
        await self._initialize_correlations()

    async def add_asset(self, symbol: str, name: str, initial_price: float,
                       volatility: float = 0.02, sector: str = "General") -> Asset:
        async with self._lock:
            if symbol in self._assets:
                raise ValueError(f"Asset {symbol} already exists")
            
            max_symbols = self._config.get('assets', {}).get('max_symbols', 100)
            if len(self._assets) >= max_symbols:
                raise ValueError("Maximum number of assets reached")
            
            drift = self._config.get('market', {}).get('price_models', {}).get('drift', 0.0001)
            
            asset = Asset(
                symbol=symbol,
                name=name,
                initial_price=initial_price,
                volatility=volatility,
                sector=sector,
                drift=drift
            )
            
            self._assets[symbol] = asset
            
            if sector not in self._sectors:
                self._sectors[sector] = []
            self._sectors[sector].append(symbol)
            
            return asset

    async def _initialize_correlations(self):
        # same sector = higher correlation
        for sector, symbols in self._sectors.items():
            for i, sym1 in enumerate(symbols):
                for sym2 in symbols[i+1:]:
                    self._correlations[(sym1, sym2)] = random.uniform(0.7, 0.9)
                    self._correlations[(sym2, sym1)] = self._correlations[(sym1, sym2)]
        
        # cross sector = lower
        sectors = list(self._sectors.keys())
        for i, sector1 in enumerate(sectors):
            for sector2 in sectors[i+1:]:
                for sym1 in self._sectors[sector1]:
                    for sym2 in self._sectors[sector2]:
                        corr = random.uniform(0.2, 0.5)
                        self._correlations[(sym1, sym2)] = corr
                        self._correlations[(sym2, sym1)] = corr

    def get_asset(self, symbol: str) -> Optional[Asset]:
        return self._assets.get(symbol)

    def get_all_assets(self) -> List[Asset]:
        return list(self._assets.values())

    def get_symbols(self) -> List[str]:
        return list(self._assets.keys())

    def get_sector_assets(self, sector: str) -> List[Asset]:
        symbols = self._sectors.get(sector, [])
        return [self._assets[s] for s in symbols if s in self._assets]

    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        return self._correlations.get((symbol1, symbol2), 0.0)

    def get_correlated_pairs(self, threshold: float = 0.8) -> List[Tuple[str, str, float]]:
        pairs = []
        seen = set()
        for (s1, s2), corr in self._correlations.items():
            if corr >= threshold and (s2, s1) not in seen:
                pairs.append((s1, s2, corr))
                seen.add((s1, s2))
        return sorted(pairs, key=lambda x: x[2], reverse=True)

    async def update_prices(self, dt: float = 1.0) -> Dict[str, float]:
        updates = {}
        
        for symbol, asset in self._assets.items():
            if asset.is_halted:
                updates[symbol] = asset.price
                continue
            
            if self._price_model == PriceModel.RANDOM_WALK:
                new_price = asset.update_price_random_walk(dt)
            elif self._price_model == PriceModel.GBM:
                new_price = asset.update_price_gbm(dt)
            else:
                new_price = asset.update_price_hybrid(dt)
            
            updates[symbol] = new_price
        
        await self._apply_correlation_effects()
        
        return updates

    async def _apply_correlation_effects(self):
        # if one stock moves big, correlated ones follow
        for symbol, asset in self._assets.items():
            if len(asset.price_history) < 2:
                continue
            
            recent_return = (asset.price - asset.price_history[-2].price) / asset.price_history[-2].price
            
            if abs(recent_return) > 0.02:  # >2% move
                for other_symbol, other_asset in self._assets.items():
                    if other_symbol == symbol or other_asset.is_halted:
                        continue
                    
                    corr = self.get_correlation(symbol, other_symbol)
                    if corr > 0.5:
                        spillover = recent_return * corr * 0.3
                        other_asset.apply_shock(abs(spillover), spillover > 0)

    def check_circuit_breakers(self, halt_threshold: float = 0.1) -> List[str]:
        halted = []
        
        for symbol, asset in self._assets.items():
            if asset.is_halted:
                continue
            
            change_abs, change_pct = asset.get_daily_change()
            
            if abs(change_pct) >= halt_threshold * 100:
                direction = "up" if change_pct > 0 else "down"
                asset.halt(f"Circuit breaker: {abs(change_pct):.1f}% move {direction}")
                halted.append(symbol)
        
        return halted

    def get_market_stats(self) -> Dict:
        if not self._assets:
            return {}
        
        prices = [a.price for a in self._assets.values()]
        volatilities = [a.volatility for a in self._assets.values()]
        volumes = [a._cumulative_volume for a in self._assets.values()]
        
        advancing = sum(1 for a in self._assets.values() if a.get_daily_change()[0] > 0)
        declining = len(self._assets) - advancing
        
        return {
            'total_assets': len(self._assets),
            'total_volume': sum(volumes),
            'avg_volatility': np.mean(volatilities),
            'max_volatility': max(volatilities),
            'advancing': advancing,
            'declining': declining,
            'halted': sum(1 for a in self._assets.values() if a.is_halted),
            'market_breadth': (advancing - declining) / len(self._assets) if self._assets else 0
        }
