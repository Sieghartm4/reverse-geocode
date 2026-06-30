import { useRef, useState, useEffect } from "react";
import MapView, { CITY_ZOOM } from "./components/MapView";
import SearchBar from "./components/SearchBar";
import AddressPanel from "./components/AddressPanel";
import CityPicker from "./components/CityPicker";
import { reverseGeocode } from "./lib/api";

export default function App() {
  const mapRef = useRef(null);
  const [address, setAddress] = useState(null);
  const [clickError, setClickError] = useState("");
  const [lastSelected, setLastSelected] = useState(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    const id = setInterval(() => {
      if (mapRef.current) {
        setMapReady(true);
        clearInterval(id);
      }
    }, 100);
    return () => clearInterval(id);
  }, []);

  function parseNumber(value) {
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  }

  function normalizeBBox(bbox) {
    if (!Array.isArray(bbox) || bbox.length !== 4) return null;
    const values = bbox.map(parseNumber);
    if (values.some((v) => v === null)) return null;

    const normalize = (a, b, c, d) => {
      const minLon = Math.min(a, c);
      const maxLon = Math.max(a, c);
      const minLat = Math.min(b, d);
      const maxLat = Math.max(b, d);
      if (minLon < -180 || maxLon > 180 || minLat < -90 || maxLat > 90) {
        return null;
      }
      return [
        [minLon, minLat],
        [maxLon, maxLat],
      ];
    };

    const [a, b, c, d] = values;
    return normalize(a, b, c, d) || normalize(b, a, d, c);
  }

  function isValidBounds(bounds) {
    return (
      Array.isArray(bounds) &&
      bounds.length === 2 &&
      Array.isArray(bounds[0]) &&
      Array.isArray(bounds[1]) &&
      bounds[0].length === 2 &&
      bounds[1].length === 2 &&
      isValidCoord(bounds[0][0], bounds[0][1]) &&
      isValidCoord(bounds[1][0], bounds[1][1])
    );
  }

  function isValidCoord(lon, lat) {
    return (
      typeof lon === "number" &&
      typeof lat === "number" &&
      Number.isFinite(lon) &&
      Number.isFinite(lat) &&
      lon >= -180 &&
      lon <= 180 &&
      lat >= -90 &&
      lat <= 90
    );
  }

  function handleResolveAddress(addr) {
    setAddress(addr);
    setClickError("");
    mapRef.current?.setMarker(addr.lon, addr.lat);
    mapRef.current?.flyTo(addr.lon, addr.lat, Math.max(CITY_ZOOM, 15));
  }

  function handleSelectPlace(place) {
    setClickError("");
    try {
      console.debug("App selectPlace:", place);
    } catch (e) {}
    setLastSelected(place && place.name ? place.name : JSON.stringify(place));

    let lon = place.lon;
    let lat = place.lat;
    if ((lon == null || lat == null) && place.bbox) {
      const normalized = normalizeBBox(place.bbox);
      if (normalized) {
        const [[minLon, minLat], [maxLon, maxLat]] = normalized;
        lon = (minLon + maxLon) / 2;
        lat = (minLat + maxLat) / 2;
      }
    }

    const bounds = normalizeBBox(place.bbox);
    if (isValidBounds(bounds)) {
      mapRef.current?.fitBounds(bounds);
    } else if (isValidCoord(lon, lat)) {
      mapRef.current?.flyTo(lon, lat);
    }

    if (!isValidCoord(lon, lat) && bounds) {
      const [[minLon, minLat], [maxLon, maxLat]] = bounds;
      lon = (minLon + maxLon) / 2;
      lat = (minLat + maxLat) / 2;
    }

    if (isValidCoord(lon, lat)) {
      mapRef.current?.setMarker(lon, lat);
      // Also pull the full structured address for this point so the panel
      // is populated, same as a coordinate search would.
      reverseGeocode(lat, lon)
        .then(setAddress)
        .catch(() => {});
    }
  }

  function handleCityPick(city) {
    setAddress(null);
    mapRef.current?.clearMarker();
    const bounds = normalizeBBox(city.bbox);
    if (isValidBounds(bounds)) {
      mapRef.current?.fitBounds(bounds);
    }
  }

  async function handleMapClick(lon, lat) {
    mapRef.current?.setMarker(lon, lat);
    try {
      const addr = await reverseGeocode(lat, lon);
      setAddress(addr);
      setClickError("");
    } catch (e) {
      setClickError("Could not reach the backend for this point.");
    }
  }

  return (
    <div className="relative h-screen w-screen overflow-hidden font-sans">
      <MapView ref={mapRef} onMapClick={handleMapClick} />

      {/* Debug banner to show last selection and map readiness */}
      <div className="absolute top-2 right-2 bg-chart-800/90 text-xs text-chart-400 px-3 py-1 rounded-md border border-chart-line z-50">
        <div>Selected: {lastSelected || "—"}</div>
        <div>Map ready: {mapReady ? "yes" : "no"}</div>
      </div>

      <div className="absolute top-4 left-4 right-4 flex flex-col sm:flex-row gap-3 items-start">
        <SearchBar
          onResolveAddress={handleResolveAddress}
          onSelectPlace={handleSelectPlace}
        />
        <CityPicker onPick={handleCityPick} />
      </div>

      {clickError && (
        <p
          className="absolute top-20 left-4 text-xs text-amber-400 font-mono
                       bg-chart-800/90 px-3 py-1.5 rounded-md border border-chart-line"
        >
          {clickError}
        </p>
      )}

      <AddressPanel
        address={address}
        onClose={() => {
          setAddress(null);
          mapRef.current?.clearMarker();
        }}
      />

      <p className="absolute bottom-2 right-3 text-[10px] font-mono text-chart-600">
        zoom in to a city to load detail · data: your PostGIS DB, not OSM
        servers
      </p>
    </div>
  );
}
