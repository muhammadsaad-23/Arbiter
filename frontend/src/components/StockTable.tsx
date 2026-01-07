import { Asset } from '../types'
import './StockTable.css'

interface StockTableProps {
  assets: Asset[]
}

function formatPrice(price: number): string {
  return price.toFixed(2)
}

function formatVolume(vol: number): string {
  if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(1) + 'M'
  if (vol >= 1_000) return (vol / 1_000).toFixed(1) + 'K'
  return vol.toString()
}

export default function StockTable({ assets }: StockTableProps) {
  return (
    <div className="card stock-table-card">
      <div className="card-header">
        <span className="card-title">Market Watch</span>
        <span className="stock-count">{assets.length} symbols</span>
      </div>
      
      <div className="table-wrapper">
        <table className="stock-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="right">Price</th>
              <th className="right">Change</th>
              <th className="right">%</th>
              <th className="right">Volume</th>
              <th className="right">High</th>
              <th className="right">Low</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {assets.map(asset => (
              <tr key={asset.symbol} className={asset.isHalted ? 'halted' : ''}>
                <td className="symbol-cell">
                  <span className="symbol mono">{asset.symbol}</span>
                </td>
                <td className="right mono price-cell">
                  ${formatPrice(asset.price)}
                </td>
                <td className={`right mono ${asset.change >= 0 ? 'positive' : 'negative'}`}>
                  {asset.change >= 0 ? '+' : ''}{formatPrice(asset.change)}
                </td>
                <td className={`right mono ${asset.changePct >= 0 ? 'positive' : 'negative'}`}>
                  {asset.changePct >= 0 ? '+' : ''}{asset.changePct.toFixed(2)}%
                </td>
                <td className="right mono volume-cell">
                  {formatVolume(asset.volume)}
                </td>
                <td className="right mono">
                  ${formatPrice(asset.high)}
                </td>
                <td className="right mono">
                  ${formatPrice(asset.low)}
                </td>
                <td>
                  {asset.isHalted ? (
                    <span className="status-badge halted">HALT</span>
                  ) : (
                    <span className="status-badge active">LIVE</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

