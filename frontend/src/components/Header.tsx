import './Header.css'

interface HeaderProps {
  connected: boolean
  tickCount: number
  totalTrades: number
}

export default function Header({ connected, tickCount, totalTrades }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="logo">
          <span className="logo-icon">◈</span>
          Arbiter
        </h1>
        <span className="tagline">Stock Market Simulator</span>
      </div>
      
      <div className="header-right">
        <div className="stat-pill">
          <span className="stat-label">Tick</span>
          <span className="stat-value mono">{tickCount}</span>
        </div>
        <div className="stat-pill">
          <span className="stat-label">Trades</span>
          <span className="stat-value mono">{totalTrades}</span>
        </div>
        <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          <span className="status-dot" />
          {connected ? 'Live' : 'Reconnecting...'}
        </div>
      </div>
    </header>
  )
}

