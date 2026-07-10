import { useEffect, useState } from 'react'
import { getHealth } from './api/client'
import './App.css'

type Status = 'checking' | 'ok' | 'error'

function App() {
  const [status, setStatus] = useState<Status>('checking')

  useEffect(() => {
    getHealth()
      .then(() => setStatus('ok'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main className="status-card">
      <h1>Stu-Dent</h1>
      <p>
        API status:{' '}
        <span className={`status status-${status}`}>
          {status === 'checking' ? 'checking...' : status}
        </span>
      </p>
    </main>
  )
}

export default App
