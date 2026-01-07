import { useState, useEffect, useRef } from 'react'
import { SimulationData, PriceHistory } from './types'
import Header from './components/Header'
import StockTable from './components/StockTable'
import PriceChart from './components/PriceChart'
import BotPanel from './components/BotPanel'
import MarketStats from './components/MarketStats'
import './App.css'

function App() {
  const [data, setData] = useState<SimulationData | null>(null)
  const [connected, setConnected] = useState(false)
  const [priceHistory, setPriceHistory] = useState<PriceHistory>({})
  const [tickCount, setTickCount] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    connectWs()
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const connectWs = () => {
    const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws`)
    
    ws.onopen = () => {
      console.log('connected to sim')
      setConnected(true)
    }

    ws.onmessage = (event) => {
      const newData: SimulationData = JSON.parse(event.data)
      setData(newData)
      setTickCount(prev => prev + 1)

      // update price history
      setPriceHistory(prev => {
        const updated = { ...prev }
        newData.assets.forEach(asset => {
          if (!updated[asset.symbol]) {
            updated[asset.symbol] = []
          }
          updated[asset.symbol] = [...updated[asset.symbol].slice(-99), asset.price]
        })
        return updated
      })
    }

    ws.onclose = () => {
      console.log('disconnected')
      setConnected(false)
      // try reconnect after 2s
      setTimeout(connectWs, 2000)
    }

    ws.onerror = (err) => {
      console.error('ws error:', err)
    }

    wsRef.current = ws
  }

  if (!data) {
    return (
      <div className="loading-screen">
        <div className="loading-content">
          <div className="loading-spinner" />
          <h2>Connecting to simulation...</h2>
          <p>Make sure the API server is running on port 8000</p>
          <code>cd api && python server.py</code>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <Header 
        connected={connected} 
        tickCount={tickCount}
        totalTrades={data.trading.totalTrades}
      />
      
      <main className="main-content">
        <div className="left-panel">
          <StockTable assets={data.assets} />
          <PriceChart priceHistory={priceHistory} assets={data.assets} />
        </div>
        
        <div className="right-panel">
          <MarketStats market={data.market} trading={data.trading} />
          <BotPanel bots={data.bots} />
        </div>
      </main>
    </div>
  )
}

export default App

