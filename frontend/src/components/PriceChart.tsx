import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'
import { PriceHistory, Asset } from '../types'
import './PriceChart.css'

interface PriceChartProps {
  priceHistory: PriceHistory
  assets: Asset[]
}

const COLORS = [
  '#06b6d4', '#22c55e', '#ef4444', '#eab308', '#3b82f6',
  '#0ea5e9', '#f97316', '#14b8a6', '#38bdf8', '#2dd4bf'
]

export default function PriceChart({ priceHistory, assets: _assets }: PriceChartProps) {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  const symbols = Object.keys(priceHistory)
  const displaySymbols = selectedSymbol ? [selectedSymbol] : symbols.slice(0, 5)

  // transform data for recharts
  const chartData = []
  const maxLen = Math.max(...Object.values(priceHistory).map(arr => arr.length), 0)
  
  for (let i = 0; i < maxLen; i++) {
    const point: Record<string, number> = { index: i }
    displaySymbols.forEach(sym => {
      const prices = priceHistory[sym] || []
      if (prices[i] !== undefined) {
        point[sym] = prices[i]
      }
    })
    chartData.push(point)
  }

  return (
    <div className="card chart-card">
      <div className="card-header">
        <span className="card-title">Price History</span>
        <div className="symbol-filters">
          <button 
            className={`filter-btn ${selectedSymbol === null ? 'active' : ''}`}
            onClick={() => setSelectedSymbol(null)}
          >
            All
          </button>
          {symbols.slice(0, 6).map(sym => (
            <button
              key={sym}
              className={`filter-btn ${selectedSymbol === sym ? 'active' : ''}`}
              onClick={() => setSelectedSymbol(selectedSymbol === sym ? null : sym)}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-container">
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <XAxis 
                dataKey="index" 
                stroke="#71717a"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: '#2a2a3a' }}
              />
              <YAxis 
                stroke="#71717a"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: '#2a2a3a' }}
                tickFormatter={(val) => `$${val.toFixed(0)}`}
                width={50}
                domain={['auto', 'auto']}
              />
              <Tooltip 
                contentStyle={{
                  background: '#1a1a24',
                  border: '1px solid #2a2a3a',
                  borderRadius: '8px',
                  fontSize: '12px'
                }}
                labelStyle={{ color: '#a1a1aa' }}
                formatter={(value: number) => [`$${value.toFixed(2)}`, '']}
              />
              {displaySymbols.map((sym, i) => (
                <Line
                  key={sym}
                  type="monotone"
                  dataKey={sym}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  name={sym}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="chart-placeholder">
            <p>Collecting price data...</p>
          </div>
        )}
      </div>
    </div>
  )
}

