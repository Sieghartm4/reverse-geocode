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

const MapView = forwardRef(function MapView(
  { onMapClick, theme = "dark", onToggleTheme },
  ref,
) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const markerCoordRef = useRef(null);
  const themeControlRef = useRef(null);

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
        // Create a single SVG element for the pin with a pointy tail so it
        // remains visible and centered reliably across themes.
        const svgNS = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("width", "36");
        svg.setAttribute("height", "48");
        svg.setAttribute("viewBox", "0 0 36 48");
        svg.style.transform = "translateX(-50%) translateY(-100%)";
        svg.style.display = "block";
        svg.style.pointerEvents = "none";

        // marker group: circle + tail
        const g = document.createElementNS(svgNS, "g");

        const circle = document.createElementNS(svgNS, "circle");
        circle.setAttribute("cx", "18");
        circle.setAttribute("cy", "14");
        circle.setAttribute("r", "10");
        circle.setAttribute("fill", "#f59e0b");
        circle.setAttribute("stroke", "#ffffff");
        circle.setAttribute("stroke-width", "2");
        circle.setAttribute("filter", "none");

        const tail = document.createElementNS(svgNS, "path");
        tail.setAttribute(
          "d",
          "M18 26 C18 26 12 36 18 46 C24 36 18 26 18 26 Z",
        );
        tail.setAttribute("fill", "#d97706");

        g.appendChild(circle);
        g.appendChild(tail);
        svg.appendChild(g);

        markerRef.current = new maplibregl.Marker({ element: svg }).setLngLat([
          lon,
          lat,
        ]);
        markerRef.current.addTo(mapRef.current);
      } else {
        markerRef.current.setLngLat([lon, lat]);
      }
      markerCoordRef.current = [lon, lat];
    },
    clearMarker() {
      markerRef.current?.remove();
      markerRef.current = null;
    },
  }));

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: buildMapStyle(theme),
      center: PH_CENTER,
      zoom: COUNTRY_ZOOM,
      maxBounds: PH_BOUNDS,
      attributionControl: false,
    });
    mapRef.current = map;

    // Add a custom control for theme toggle so it sits beside the nav buttons
    const themeControl = {
      onAdd(mapInstance) {
        this._map = mapInstance;
        this._container = document.createElement("div");
        this._container.className = "maplibregl-ctrl maplibregl-ctrl-group";

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-theme";
        // sizing to match nav buttons and center icon
        btn.style.width = "36px";
        btn.style.height = "36px";
        btn.style.padding = "0";
        btn.style.margin = "0";
        btn.style.display = "inline-flex";
        btn.style.alignItems = "center";
        btn.style.justifyContent = "center";
        btn.style.boxSizing = "border-box";
        btn.style.borderRadius = "6px";
        btn.onclick = () => {
          const el = containerRef.current;
          if (el) el.dispatchEvent(new CustomEvent("reverse-geo-theme-click"));
        };
        // Show the opposite theme icon because this button switches themes.
        const moonSvg =
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" fill="currentColor"/></svg>';
        const sunSvg =
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none"><circle cx="12" cy="12" r="4" fill="currentColor"/><g stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M4.93 19.07l1.41-1.41"/><path d="M17.66 6.34l1.41-1.41"/></g></svg>';
        btn.innerHTML = theme === "dark" ? sunSvg : moonSvg;
        btn.title =
          theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
        btn.setAttribute(
          "aria-label",
          theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
        );
        // apply state-specific class so colors and hover work correctly
        btn.classList.add(
          theme === "dark" ? "btn-theme--sun" : "btn-theme--moon",
        );

        this._button = btn;
        this._container.appendChild(btn);
        return this._container;
      },
      onRemove() {
        if (this._container && this._container.parentNode)
          this._container.parentNode.removeChild(this._container);
        this._map = undefined;
      },
    };

    // add theme control first so it appears to the left of the nav group
    map.addControl(themeControl, "top-right");
    themeControlRef.current = themeControl;

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

    return () => {
      map.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update style when theme changes
  useEffect(() => {
    if (!mapRef.current) return;
    try {
      mapRef.current.setStyle(buildMapStyle(theme));
    } catch (e) {
      // ignore style set errors
    }
    // Re-add marker after style change (setStyle can replace map panes)
    try {
      if (markerRef.current && markerCoordRef.current) {
        // Re-attach marker to the new map style container
        markerRef.current.addTo(mapRef.current);
        markerRef.current.setLngLat(markerCoordRef.current);
      }
    } catch (e) {}
  }, [theme]);

  // Update the control button label when theme changes
  useEffect(() => {
    const c = themeControlRef.current;
    if (c && c._button) {
      const moonSvg =
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" fill="currentColor"/></svg>';
      const sunSvg =
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none"><circle cx="12" cy="12" r="4" fill="currentColor"/><g stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M4.93 19.07l1.41-1.41"/><path d="M17.66 6.34l1.41-1.41"/></g></svg>';
      c._button.innerHTML = theme === "dark" ? sunSvg : moonSvg;
      c._button.title =
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
      c._button.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
      );
      // toggle classes for visual states (sun shows -> light bg, moon shows -> dark bg)
      c._button.classList.remove("btn-theme--sun", "btn-theme--moon");
      c._button.classList.add(
        theme === "dark" ? "btn-theme--sun" : "btn-theme--moon",
      );
      // ensure sizing/centering
      c._button.style.width = "36px";
      c._button.style.height = "36px";
      c._button.style.display = "inline-flex";
      c._button.style.alignItems = "center";
      c._button.style.justifyContent = "center";
    }
  }, [theme]);

  // Listen for clicks from the control button and call onToggleTheme prop
  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const themeHandler = () => {
      try {
        if (typeof onToggleTheme === "function") onToggleTheme();
      } catch (e) {}
    };
    el.addEventListener("reverse-geo-theme-click", themeHandler);
    return () =>
      el.removeEventListener("reverse-geo-theme-click", themeHandler);
  }, [onToggleTheme]);

  return <div ref={containerRef} className="absolute inset-0" />;
});

export default MapView;
