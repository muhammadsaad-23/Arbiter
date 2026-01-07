import { MarketStats as MarketStatsType, TradingStats } from '../types'
import './MarketStats.css'

interface MarketStatsProps {
  market: MarketStatsType
  trading: TradingStats
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toString()
}

export default function MarketStats({ market, trading }: MarketStatsProps) {
  return (
    <div className="card market-stats">
      <div className="card-header">
        <span className="card-title">Market Overview</span>
      </div>

      <div className="stats-grid">
        <div className="stat-box">
          <div className="stat-icon green">▲</div>
          <div className="stat-content">
            <span className="stat-value mono">{market.advancing}</span>
            <span className="stat-label">Advancing</span>
          </div>
        </div>
        
        <div className="stat-box">
          <div className="stat-icon red">▼</div>
          <div className="stat-content">
            <span className="stat-value mono">{market.declining}</span>
            <span className="stat-label">Declining</span>
          </div>
        </div>
        
        <div className="stat-box">
          <div className="stat-icon yellow">◆</div>
          <div className="stat-content">
            <span className="stat-value mono">{market.halted}</span>
            <span className="stat-label">Halted</span>
          </div>
        </div>
        
        <div className="stat-box">
          <div className="stat-icon purple">◎</div>
          <div className="stat-content">
            <span className="stat-value mono">{market.avgVolatility.toFixed(2)}%</span>
            <span className="stat-label">Volatility</span>
          </div>
        </div>
      </div>

      <div className="divider" />

      <div className="trading-stats">
        <div className="trading-stat">
          <span className="trading-label">Total Volume</span>
          <span className="trading-value mono">{formatNumber(market.totalVolume)}</span>
        </div>
        <div className="trading-stat">
          <span className="trading-label">Orders Placed</span>
          <span className="trading-value mono">{trading.totalOrders}</span>
        </div>
        <div className="trading-stat">
          <span className="trading-label">Trades Executed</span>
          <span className="trading-value mono">{trading.totalTrades}</span>
        </div>
        <div className="trading-stat">
          <span className="trading-label">Trade Value</span>
          <span className="trading-value mono">${formatNumber(trading.tradeValue)}</span>
        </div>
      </div>
    </div>
  )
}

