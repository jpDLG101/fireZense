// data.jsx — Real API adapter for fireZense dashboard
// Calls the FastAPI backend and converts to the shape the components expect.

const API_BASE = "/api/v1";

const RISK_MAP = {
  GREEN:  "bajo",
  YELLOW: "medio",
  ORANGE: "alto",
  RED:    "critico",
};

const RISK_META = {
  bajo:    { label: "BAJO",    color: "#16a34a", bg: "#16a34a", textColor: "#ffffff" },
  medio:   { label: "MEDIO",   color: "#eab308", bg: "#eab308", textColor: "#1a1a1a" },
  alto:    { label: "ALTO",    color: "#ea580c", bg: "#ea580c", textColor: "#ffffff" },
  critico: { label: "CRÍTICO", color: "#dc2626", bg: "#dc2626", textColor: "#ffffff" },
};

function parseUTC(ts) {
  // SQLite CURRENT_TIMESTAMP is UTC but has no timezone marker — force UTC parsing
  return new Date(ts.replace(' ', 'T') + 'Z');
}

function minutesAgo(ts) {
  if (!ts) return 0;
  try { return Math.max(0, Math.round((Date.now() - parseUTC(ts).getTime()) / 60000)); }
  catch (e) { return 0; }
}

// Build 24-point history from raw DB readings (newest-first from backend).
function buildHistory(soilHistory, lightHistory) {
  const soil  = [...soilHistory].reverse().slice(-24);
  const light = [...lightHistory].reverse();
  if (soil.length < 2) return [];

  const now = Date.now();
  return soil.map((s, i) => {
    const lux = (light[i] || {}).light_lux ?? 0;
    const ecRaw = s.electrical_conductivity_us_cm;
    const rawTs = s.received_at || s.timestamp;
    const ts = rawTs ? parseUTC(rawTs) : new Date(now);
    const hoursAgo = Math.round((now - ts.getTime()) / 3600000);
    return {
      hoursAgo:        Math.max(0, hoursAgo),
      timestamp:       ts.getTime(),
      soilTemperature: s.soil_temperature_celsius   ?? 25,
      soilHumidity:    s.soil_moisture_percent      ?? 50,
      light:           lux,
      ec:              ecRaw != null ? ecRaw / 1000 : 0.5,
      batterySoil:     s.battery_percent ?? null,
      batteryLight:    (light[i] || {}).battery_percent ?? null,
    };
  });
}

// Fallback synthetic history when real data is scarce.
function syntheticHistory(node) {
  const { soilTemperature: baseT, soilHumidity: baseH, light: baseL, ec: baseEc, lat } = node;
  const history = [];
  for (let h = 23; h >= 0; h--) {
    const hourOfDay = (new Date().getHours() - h + 24) % 24;
    const sun   = Math.max(0, Math.sin(((hourOfDay - 6) / 12) * Math.PI));
    const noise = Math.sin(h * 7.3 + lat) * 0.5;
    history.push({
      hoursAgo:        h,
      timestamp:       Date.now() - h * 3600000,
      soilTemperature: +(baseT - 4 + sun * 8 + noise).toFixed(1),
      soilHumidity:    +Math.max(0, baseH + noise - sun).toFixed(1),
      light:           Math.round(Math.max(0, baseL * sun)),
      ec:              +Math.max(0.01, baseEc + noise * 0.05).toFixed(2),
    });
  }
  return history;
}

// Friendly alert title from backend alert_type
function alertTitle(alertType) {
  const map = {
    fire_risk_red:    "Riesgo crítico de incendio",
    fire_risk_orange: "Riesgo alto — posible incendio",
  };
  return map[alertType] || "Alerta del sistema";
}

// ── Main fetch functions ──────────────────────────────────────────────────────

async function fetchNodes() {
  const res = await fetch(`${API_BASE}/nodes`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const { nodes: rawNodes } = await res.json();

  return Promise.all(rawNodes.map(async (n) => {
    const soilR  = n.last_soil_reading  || {};
    const lightR = n.last_light_reading || {};
    const ecRaw  = soilR.electrical_conductivity_us_cm;

    const node = {
      id:              `NODE-${String(n.id).padStart(3, "0")}`,
      _backendId:      n.id,
      name:            n.name,
      area:            n.description || "",
      lat:             n.latitude,
      lng:             n.longitude,
      soilEui:         n.soil_eui  || null,
      lightEui:        n.light_eui || null,
      soilTemperature: soilR.soil_temperature_celsius ?? 25,
      soilHumidity:    soilR.soil_moisture_percent    ?? 50,
      light:           lightR.light_lux               ?? 0,
      ec:              ecRaw != null ? ecRaw / 1000   : 0.5,
      batterySoil:     soilR.battery_percent  ?? null,
      batteryLight:    lightR.battery_percent ?? null,
      lastSeen:        minutesAgo(n.last_seen),
      lastSeenIso:     n.last_seen || null,
      risk:            RISK_MAP[n.risk_level] || "bajo",
      history:         [],
    };

    try {
      const dRes = await fetch(`${API_BASE}/nodes/${n.id}`);
      if (dRes.ok) {
        const detail = await dRes.json();
        const h = buildHistory(detail.soil_history || [], detail.light_history || []);
        node.history = h.length >= 2 ? h : syntheticHistory(node);
      } else {
        node.history = syntheticHistory(node);
      }
    } catch (_) {
      node.history = syntheticHistory(node);
    }

    return node;
  }));
}

async function fetchAlerts(nodes) {
  const res = await fetch(`${API_BASE}/alerts`);
  if (!res.ok) return [];
  const { alerts: rawAlerts } = await res.json();

  const nodeMap = {};
  nodes.forEach((n) => { nodeMap[n._backendId] = n; });

  return rawAlerts.map((a) => {
    const n    = nodeMap[a.node_id] || {};
    const tipo = a.severity === "critical" ? "critico"
               : a.severity === "warning"  ? "advertencia"
               : "info";
    return {
      id:          `ALT-${String(a.id).padStart(4, "0")}`,
      _backendId:  a.id,
      tipo,
      titulo:      alertTitle(a.alert_type),
      mensaje:     a.message.replace(/^(\[Recordatorio\]\s*)?[🟠🔴]\s*/u, "$1"),
      nodoId:      n.id   || `NODE-${String(a.node_id).padStart(3, "0")}`,
      nodoNombre:  n.name || "Nodo",
      area:        n.area || "",
      hace:        minutesAgo(a.created_at),
    };
  });
}

// ── Shared promise cache so parallel calls share one network request ──────────

let _nodesPromise = null;

function getNodes(force = false) {
  if (force || !_nodesPromise) _nodesPromise = fetchNodes().catch((e) => {
    _nodesPromise = null;
    throw e;
  });
  return _nodesPromise;
}

async function dismissAlert(backendId) {
  try {
    await fetch(`${API_BASE}/alerts/${backendId}/read`, { method: "PATCH" });
  } catch (_) {}
}

async function dismissAllAlerts() {
  try {
    await fetch(`${API_BASE}/alerts/read-all`, { method: "PATCH" });
  } catch (_) {}
}

// ── Public API ────────────────────────────────────────────────────────────────

window.fireZenseAPI = {
  async getNodes(force)  { return getNodes(force); },
  async getAlerts(force) {
    const nodes = await getNodes(force);
    return fetchAlerts(nodes);
  },
  async dismissAlert(backendId)  { return dismissAlert(backendId); },
  async dismissAllAlerts()       { return dismissAllAlerts(); },
  RISK_META,
};
