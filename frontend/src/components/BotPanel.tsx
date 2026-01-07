import { Bot } from '../types'
import './BotPanel.css'

interface BotPanelProps {
  bots: Bot[]
}

function formatCurrency(val: number): string {
  const abs = Math.abs(val)
  const sign = val >= 0 ? '+' : '-'
  return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const BOT_ICONS: Record<string, string> = {
  'momentum': '⚡',
  'mean_reversion': '↔',
  'arbitrage': '⇄',
}

function getBotIcon(name: string): string {
  const key = name.toLowerCase().replace(/[^a-z]/g, '_')
  for (const [k, v] of Object.entries(BOT_ICONS)) {
    if (key.includes(k)) return v
  }
  return '🤖'
}

export default function BotPanel({ bots }: BotPanelProps) {
  const totalPnl = bots.reduce((sum, b) => sum + b.pnl, 0)
  const totalTrades = bots.reduce((sum, b) => sum + b.trades, 0)

  return (
    <div className="card bot-panel">
      <div className="card-header">
        <span className="card-title">AI Trading Bots</span>
        <span className={`total-pnl ${totalPnl >= 0 ? 'positive' : 'negative'}`}>
          {formatCurrency(totalPnl)}
        </span>
      </div>

      <div className="bot-summary">
        <div className="summary-item">
          <span className="summary-label">Total Trades</span>
          <span className="summary-value mono">{totalTrades}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Active Bots</span>
          <span className="summary-value mono">{bots.length}</span>
        </div>
      </div>

      <div className="bot-list">
        {bots.map(bot => (
          <div key={bot.name} className="bot-card">
            <div className="bot-header">
              <span className="bot-icon">{getBotIcon(bot.name)}</span>
              <span className="bot-name">{bot.name}</span>
            </div>
            
            <div className="bot-stats">
              <div className="bot-stat">
                <span className="stat-label">P&L</span>
                <span className={`stat-value mono ${bot.pnl >= 0 ? 'positive' : 'negative'}`}>
                  {formatCurrency(bot.pnl)}
                </span>
              </div>
              <div className="bot-stat">
                <span className="stat-label">Trades</span>
                <span className="stat-value mono">{bot.trades}</span>
              </div>
              <div className="bot-stat">
                <span className="stat-label">Win Rate</span>
                <span className="stat-value mono">{(bot.winRate * 100).toFixed(1)}%</span>
              </div>
            </div>

            <div className="bot-portfolio">
              <span className="portfolio-label">Portfolio Value</span>
              <span className="portfolio-value mono">
                ${bot.portfolioValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

