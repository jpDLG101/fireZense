// Map component using MapLibre GL JS.
// Loads via window.maplibregl which the host page imports from CDN.

const RISK_PRIORITY = { critico: 0, alto: 1, medio: 2, bajo: 3 };

const MAP_STYLES = {
  oscuro: {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      "raster-tiles": {
        type: "raster",
        tiles: ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap © CARTO",
      },
    },
    layers: [{ id: "tiles", type: "raster", source: "raster-tiles" }],
  },
  claro: {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      "raster-tiles": {
        type: "raster",
        tiles: ["https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap © CARTO",
      },
    },
    layers: [{ id: "tiles", type: "raster", source: "raster-tiles" }],
  },
  satelite: {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      "raster-tiles": {
        type: "raster",
        tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        tileSize: 256,
        attribution: "© Esri World Imagery",
      },
    },
    layers: [{ id: "tiles", type: "raster", source: "raster-tiles" }],
  },
  terreno: {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      "raster-tiles": {
        type: "raster",
        tiles: ["https://a.tile.opentopomap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap © OpenTopoMap",
      },
    },
    layers: [{ id: "tiles", type: "raster", source: "raster-tiles" }],
  },
};

function MapView({ nodes, selectedId, onSelect, mapStyle: mapStyleProp, dark }) {
  const containerRef = React.useRef(null);
  const mapRef = React.useRef(null);
  const markersRef = React.useRef(new Map());
  const [ready, setReady] = React.useState(false);

  // Internal style state — initialized from localStorage, then user-controlled via in-map UI.
  // "default" follows the current UI theme (oscuro/claro).
  const [mapStyle, setMapStyle] = React.useState(() => {
    return localStorage.getItem("fz-map-style") || "default";
  });
  React.useEffect(() => {
    localStorage.setItem("fz-map-style", mapStyle);
  }, [mapStyle]);

  // Resolve "default" → oscuro/claro based on current theme. Recomputes when `dark` flips.
  const resolvedStyle = React.useMemo(() => {
    if (mapStyle === "default") return dark ? "oscuro" : "claro";
    return mapStyle;
  }, [mapStyle, dark]);

  // Init map once
  React.useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new window.maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLES[resolvedStyle] || MAP_STYLES.oscuro,
      center: [-107.5, 28.4],
      zoom: 6.4,
      attributionControl: false,
    });
    map.addControl(new window.maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new window.maplibregl.AttributionControl({ compact: true }));
    mapRef.current = map;
    map.on("load", () => setReady(true));
    map.on("click", () => onSelect(null));
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Style swap
  React.useEffect(() => {
    if (!mapRef.current || !ready) return;
    mapRef.current.setStyle(MAP_STYLES[resolvedStyle] || MAP_STYLES.oscuro);
  }, [resolvedStyle, ready]);

  // Render markers
  React.useEffect(() => {
    if (!mapRef.current || !ready) return;
    const map = mapRef.current;
    const seen = new Set();

    // Sort so critical markers render on top
    const ordered = [...nodes].sort((a, b) => RISK_PRIORITY[b.risk] - RISK_PRIORITY[a.risk]);

    ordered.forEach((node) => {
      seen.add(node.id);
      let entry = markersRef.current.get(node.id);
      const meta = window.fireZenseAPI.RISK_META[node.risk];
      if (!entry) {
        const el = document.createElement("div");
        el.className = "fz-marker";
        el.innerHTML = `
          <div class="fz-marker-pulse"></div>
          <div class="fz-marker-dot"></div>
        `;
        el.addEventListener("click", (e) => { e.stopPropagation(); onSelect(node.id); });
        const marker = new window.maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat([node.lng, node.lat])
          .addTo(map);
        const popup = new window.maplibregl.Popup({
          offset: 18,
          closeButton: false,
          className: "fz-popup",
          maxWidth: "260px",
        });
        marker.setPopup(popup);
        entry = { el, marker, popup };
        markersRef.current.set(node.id, entry);
      }
      // Update color + content
      entry.el.style.setProperty("--fz-risk", meta.color);
      entry.el.dataset.risk = node.risk;
      entry.el.dataset.selected = String(node.id === selectedId);
      entry.popup.setHTML(`
        <div class="fz-popup-inner">
          <div class="fz-popup-head">
            <span class="fz-popup-id">${node.id}</span>
            <span class="fz-popup-badge" style="background:${meta.bg};color:${meta.textColor}">${meta.label}</span>
          </div>
          <div class="fz-popup-name">${node.name}</div>
          <div class="fz-popup-area">${node.area}</div>
          <div class="fz-popup-grid">
            <div><span class="fz-popup-label">T. SUELO</span><b>${node.soilTemperature}°C</b></div>
            <div><span class="fz-popup-label">HUMEDAD</span><b>${node.soilHumidity}%</b></div>
            <div><span class="fz-popup-label">LUZ</span><b>${node.light.toFixed(0)} lux</b></div>
            <div><span class="fz-popup-label">EC</span><b>${node.ec.toFixed(2)} dS/m</b></div>
          </div>
          <a class="fz-popup-cta" href="nodo.html?id=${encodeURIComponent(node.id)}">
            VER MÁS INFO
            <span class="fz-popup-cta-arrow">→</span>
          </a>
        </div>
      `);
    });

    // Remove markers no longer present
    markersRef.current.forEach((entry, id) => {
      if (!seen.has(id)) {
        entry.marker.remove();
        markersRef.current.delete(id);
      }
    });
  }, [nodes, selectedId, ready]);

  // Open popup + center on selection. Close every other popup first.
  React.useEffect(() => {
    if (!mapRef.current || !ready) return;
    markersRef.current.forEach((entry, id) => {
      if (id !== selectedId && entry.popup.isOpen()) entry.popup.remove();
    });
    if (!selectedId) return;
    const entry = markersRef.current.get(selectedId);
    if (!entry) return;
    if (!entry.popup.isOpen()) entry.marker.togglePopup();
    const node = nodes.find((n) => n.id === selectedId);
    if (node) {
      mapRef.current.flyTo({ center: [node.lng, node.lat], zoom: 13, speed: 1.4 });
    }
  }, [selectedId, ready]);

  return (
    <div className="fz-map-wrap">
      <div ref={containerRef} className="fz-map" data-dark={dark ? "true" : "false"} />
      <div className="fz-map-styles" role="tablist" aria-label="Estilo del mapa">
        {[
          { v: "default",  label: "Default"  },
          { v: "terreno",  label: "Terreno"  },
          { v: "satelite", label: "Satélite" },
        ].map((opt) => (
          <button
            key={opt.v}
            type="button"
            role="tab"
            className="fz-map-style-btn"
            data-active={mapStyle === opt.v}
            onClick={() => setMapStyle(opt.v)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

window.MapView = MapView;
