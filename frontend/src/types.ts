export interface Asset {
  symbol: string
  price: number
  change: number
  changePct: number
  volume: number
  high: number
  low: number
  isHalted: boolean
}

export interface Bot {
  name: string
  pnl: number
  trades: number
  winRate: number
  portfolioValue: number
}

export interface MarketStats {
  totalVolume: number
  avgVolatility: number
  advancing: number
  declining: number
  halted: number
}

export interface TradingStats {
  totalOrders: number
  totalTrades: number
  tradeValue: number
}

export interface SimulationData {
  type: string
  assets: Asset[]
  bots: Bot[]
  market: MarketStats
  trading: TradingStats
}

export interface PriceHistory {
  [symbol: string]: number[]
}

