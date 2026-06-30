import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import maplibregl from "maplibre-gl";
import { buildMapStyle } from "../lib/mapStyle";

// Whole-Philippines bounds — used as a soft maxBounds so users don't pan
// off into the open ocean with no data.
const PH_BOUNDS = [
  [116.0, 4.5],
  [127.0, 21.5],
];
// Default starting view is San Pedro City.
const PH_CENTER = [121.0465, 14.3363];
const COUNTRY_ZOOM = 13.2;
export const CITY_ZOOM = 14.0;

const MapView = forwardRef(function MapView({ onMapClick }, ref) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);

  const isValidCoord = (lon, lat) =>
    typeof lon === "number" &&
    typeof lat === "number" &&
    Number.isFinite(lon) &&
    Number.isFinite(lat) &&
    lon >= -180 &&
    lon <= 180 &&
    lat >= -90 &&
    lat <= 90;

  useImperativeHandle(ref, () => ({
    flyTo(lon, lat, zoom = CITY_ZOOM) {
      if (!isValidCoord(lon, lat)) return;
      mapRef.current?.flyTo({ center: [lon, lat], zoom, duration: 900 });
    },
    fitBounds(bbox) {
      if (!Array.isArray(bbox) || bbox.length !== 2) return;
      const [[minLon, minLat], [maxLon, maxLat]] = bbox;
      if (!isValidCoord(minLon, minLat) || !isValidCoord(maxLon, maxLat))
        return;
      mapRef.current?.fitBounds(
        [
          [minLon, minLat],
          [maxLon, maxLat],
        ],
        { padding: 60, duration: 900, maxZoom: 16 },
      );
    },
    setMarker(lon, lat) {
      if (!mapRef.current) return;
      if (!markerRef.current) {
        const pin = document.createElement("div");
        pin.style.position = "relative";
        pin.style.width = "28px";
        pin.style.height = "38px";
        pin.style.transform = "translateX(-50%) translateY(-100%)";

        const head = document.createElement("div");
        head.style.width = "22px";
        head.style.height = "22px";
        head.style.borderRadius = "50%";
        head.style.background =
          "radial-gradient(circle at 30% 30%, #fbbf24, #f59e0b 40%, #d97706 100%)";
        head.style.boxShadow = "0 6px 14px rgba(15, 23, 42, 0.35)";
        head.style.border = "2px solid rgba(255,255,255,0.9)";
        head.style.position = "absolute";
        head.style.left = "50%";
        head.style.top = "0";
        head.style.transform = "translateX(-50%)";

        const stem = document.createElement("div");
        stem.style.width = "10px";
        stem.style.height = "18px";
        stem.style.background =
          "linear-gradient(180deg, rgba(245,158,11,0.9), rgba(194,65,12,0.95))";
        stem.style.borderRadius = "6px 6px 10px 10px";
        stem.style.position = "absolute";
        stem.style.left = "50%";
        stem.style.top = "16px";
        stem.style.transform = "translateX(-50%)";
        stem.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.35)";

        const glow = document.createElement("div");
        glow.style.position = "absolute";
        glow.style.left = "50%";
        glow.style.top = "4px";
        glow.style.width = "28px";
        glow.style.height = "28px";
        glow.style.transform = "translateX(-50%)";
        glow.style.borderRadius = "50%";
        glow.style.background =
          "radial-gradient(circle, rgba(245,158,11,0.35), transparent 55%)";

        pin.appendChild(glow);
        pin.appendChild(stem);
        pin.appendChild(head);

        markerRef.current = new maplibregl.Marker({ element: pin }).setLngLat([
          lon,
          lat,
        ]);
        markerRef.current.addTo(mapRef.current);
      } else {
        markerRef.current.setLngLat([lon, lat]);
      }
    },
    clearMarker() {
      markerRef.current?.remove();
      markerRef.current = null;
    },
  }));

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: buildMapStyle(),
      center: PH_CENTER,
      zoom: COUNTRY_ZOOM,
      maxBounds: PH_BOUNDS,
      attributionControl: false,
    });
    mapRef.current = map;

    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );

    map.on("click", (e) => {
      onMapClick?.(e.lngLat.lng, e.lngLat.lat);
    });

    map.on("mouseenter", "buildings-fill", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "buildings-fill", () => {
      map.getCanvas().style.cursor = "";
    });

    return () => map.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={containerRef} className="absolute inset-0" />;
});

export default MapView;
