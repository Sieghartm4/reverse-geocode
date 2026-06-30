import { useEffect, useState } from 'react'
import { listCities } from '../lib/api'

export default function CityPicker({ onPick }) {
  const [cities, setCities] = useState([])
  const [open, setOpen] = useState(false)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    listCities().then(setCities).catch(() => setLoadError(true))
  }, [])

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="rounded-md border border-chart-line bg-chart-800/95 px-3 py-2.5
                   text-paper text-sm font-sans shadow-lg hover:bg-chart-700/70 transition-colors"
      >
        Cities ▾
      </button>
      {open && (
        <ul className="absolute mt-2 max-h-80 w-56 overflow-y-auto rounded-md border
                       border-chart-line bg-chart-800/95 shadow-2xl divide-y divide-chart-line z-10">
          {loadError && (
            <li className="px-4 py-2.5 text-xs text-amber-400">Couldn't load city list.</li>
          )}
          {cities.map((c) => (
            <li key={c.name}>
              <button
                onClick={() => { onPick(c); setOpen(false) }}
                className="w-full text-left px-4 py-2 text-sm text-paper hover:bg-chart-700/70 transition-colors"
              >
                {c.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
