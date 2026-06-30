const FIELD_ORDER = [
  ['unit', 'Unit'], ['block', 'Block'], ['lot', 'Lot'], ['house_number', 'House no.'],
  ['building', 'Building'], ['road', 'Road'], ['neighbourhood', 'Neighbourhood'],
  ['suburb', 'Barangay'], ['district', 'District'], ['city', 'City'],
  ['county', 'County'], ['state', 'Region'], ['postcode', 'Postcode'],
]

export default function AddressPanel({ address, onClose }) {
  if (!address) return null
  const a = address.address || {}

  return (
    <div className="absolute bottom-4 left-4 right-4 sm:right-auto sm:w-96
                     rounded-md border border-chart-line bg-chart-800/95 shadow-2xl
                     backdrop-blur-sm overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-4 pt-3">
        <h2 className="font-display text-paper text-base leading-snug">
          {address.display_name}
        </h2>
        <button
          onClick={onClose}
          className="text-chart-500 hover:text-paper transition-colors text-lg leading-none mt-0.5"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      <div className="px-4 pb-3 pt-1 text-xs font-mono text-chart-500">
        {address.lat?.toFixed(5)}, {address.lon?.toFixed(5)} · resolved in {address.elapsed_ms}ms
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 px-4 pb-4 max-h-56 overflow-y-auto">
        {FIELD_ORDER.filter(([key]) => a[key]).map(([key, label]) => (
          <div key={key} className="contents">
            <dt className="text-chart-500 text-xs font-mono uppercase tracking-wide">{label}</dt>
            <dd className="text-paper text-sm">{a[key]}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
