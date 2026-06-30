import { useState, useRef, useEffect } from "react";
import { parseCoordinateQuery, reverseGeocode, searchPlaces } from "../lib/api";

const HISTORY_KEY = "reverse-geocode-search-history";

export default function SearchBar({ onResolveAddress, onSelectPlace }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const debounceRef = useRef(null);

  async function runSearch(q) {
    const trimmed = q.trim();
    if (!trimmed) {
      setResults([]);
      setError("");
      return;
    }

    // "lat, lon" -> straight to the existing reverse-geocode endpoint
    const coords = parseCoordinateQuery(trimmed);
    if (coords) {
      setLoading(true);
      setError("");
      try {
        const addr = await reverseGeocode(coords.lat, coords.lon);
        onResolveAddress(addr);
        setResults([]);
      } catch (e) {
        console.warn(
          "Reverse geocode failed, falling back to search:",
          e.message,
        );
        try {
          const fallback = await searchPlaces(trimmed);
          setResults(fallback);
          if (fallback.length === 0) {
            setError("Could not reach the backend for reverse geocoding.");
          }
        } catch (fallbackError) {
          setError("Could not reach the backend for reverse geocoding.");
        }
      } finally {
        setLoading(false);
      }
      return;
    }

    // Otherwise, treat it as a place-name search
    setLoading(true);
    setError("");
    try {
      const r = await searchPlaces(trimmed);
      setResults(r);
      if (r.length === 0) setError("No matches found.");
    } catch (e) {
      setError("Could not reach the backend for search.");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(e) {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(val), 350);
  }

  function handleSubmit(e) {
    e.preventDefault();
    clearTimeout(debounceRef.current);
    runSearch(query);
  }

  function handleSelect(result) {
    try {
      console.debug("Search select:", result);
    } catch (e) {}
    setQuery(result.name);
    setResults([]);
    onSelectPlace(result);
  }

  return (
    <div className="w-full max-w-md">
      <form onSubmit={handleSubmit} className="relative">
        <input
          value={query}
          onChange={handleChange}
          placeholder="Search a place, road, or “14.41, 121.05”"
          className="w-full rounded-md border border-chart-line bg-chart-800/95 px-4 py-2.5 text-paper placeholder:text-chart-500 font-sans text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 shadow-lg"
        />
        {loading && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-chart-500 font-mono">
            ...
          </span>
        )}
      </form>

      {error && (
        <p className="mt-2 text-xs text-amber-400 font-mono px-1">{error}</p>
      )}

      {results.length > 0 && (
        <div className="mt-2 rounded-md border border-chart-line bg-chart-800/95 shadow-lg">
          <div className="px-4 py-2 border-b border-chart-line text-xs uppercase text-chart-500 font-mono">
            Search results
          </div>
          <ul className="max-h-72 overflow-y-auto divide-y divide-chart-line">
            {results.map((r, i) => (
              <li
                key={`${r.name}-${r.type}-${r.lon}-${r.lat}-${r.subtitle}-${i}`}
              >
                <button
                  type="button"
                  onClick={() => handleSelect(r)}
                  className="w-full text-left px-4 py-2.5 hover:bg-chart-700/70 transition-colors"
                >
                  <div className="text-paper text-sm font-medium">{r.name}</div>
                  <div className="text-chart-500 text-xs font-mono uppercase tracking-wide">
                    {r.subtitle || `${r.type}${r.bbox ? " • area" : ""}`}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
