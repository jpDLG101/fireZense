// Bottom detail panel — opens when a node is selected.
// Cuatro métricas grandes (T. suelo, Humedad, Luz, EC) + gráfica de temperatura del suelo 24h.

function fmtHour(hoursAgo) {
  const d = new Date();
  d.setMinutes(0, 0, 0);
  d.setHours(d.getHours() - hoursAgo);
  return `${String(d.getHours()).padStart(2, "0")}:00`;
}

// Enviar alerta por WhatsApp al backend
async function sendWhatsAppAlert(nodeName, riskLevel, message) {
  try {
    const payload = {
      node_name: nodeName,
      message: message,
      severity: riskLevel === "critico" ? "critical" : "warning",
    };

    const res = await fetch("/api/v1/send-alert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    console.log("✓ Alerta enviada:", data);
    return data.success;
  } catch (err) {
    console.error("✗ Error enviando alerta:", err);
    return false;
  }
}

function SoilTempChart({ history, riskColor }) {
  const W = 720;
  const H = 180;
  const PAD_L = 44;
  const PAD_R = 16;
  const PAD_T = 18;
  const PAD_B = 28;
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;

  const temps = history.map((h) => h.soilTemperature);
  const min = Math.floor(Math.min(...temps) - 2);
  const max = Math.ceil(Math.max(...temps) + 2);
  const range = max - min || 1;

  const points = history.map((h, i) => {
    const x = PAD_L + (i / (history.length - 1)) * innerW;
    const y = PAD_T + innerH - ((h.soilTemperature - min) / range) * innerH;
    return { x, y, t: h.soilTemperature, hour: h.hoursAgo };
  });

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const area = `${path} L ${points[points.length - 1].x.toFixed(1)} ${PAD_T + innerH} L ${points[0].x.toFixed(1)} ${PAD_T + innerH} Z`;

  const yTicks = [];
  const tickStep = range <= 10 ? 2 : range <= 20 ? 5 : 10;
  for (let v = Math.ceil(min / tickStep) * tickStep; v <= max; v += tickStep) {
    const y = PAD_T + innerH - ((v - min) / range) * innerH;
    yTicks.push({ v, y });
  }

  const lastPoint = points[points.length - 1];

  return (
    <svg className="fz-chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="fz-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={riskColor} stopOpacity="0.35" />
          <stop offset="100%" stopColor={riskColor} stopOpacity="0" />
        </linearGradient>
      </defs>

      {yTicks.map((t) => (
        <g key={t.v}>
          <line x1={PAD_L} y1={t.y} x2={W - PAD_R} y2={t.y} className="fz-chart-grid" />
          <text x={PAD_L - 8} y={t.y + 3} className="fz-chart-axis" textAnchor="end">
            {t.v}°
          </text>
        </g>
      ))}

      {points.map((p, i) => {
        if (i % 4 !== 0 && i !== points.length - 1) return null;
        return (
          <text key={i} x={p.x} y={H - 8} className="fz-chart-axis" textAnchor="middle">
            {p.hour === 0 ? "ahora" : `−${p.hour}h`}
          </text>
        );
      })}

      <path d={area} fill="url(#fz-grad)" />
      <path d={path} fill="none" stroke={riskColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastPoint.x} cy={lastPoint.y} r="5" fill={riskColor} />
      <circle cx={lastPoint.x} cy={lastPoint.y} r="9" fill="none" stroke={riskColor} strokeOpacity="0.4" strokeWidth="1" />
    </svg>
  );
}

function BigMetric({ label, value, unit, sub, accent }) {
  return (
    <div className="fz-big-metric" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="fz-big-metric-label">{label}</div>
      <div className="fz-big-metric-value">
        {value}
        {unit && <span className="fz-big-metric-unit">{unit}</span>}
      </div>
      {sub && <div className="fz-big-metric-sub">{sub}</div>}
    </div>
  );
}

function DetailPanel({ node, onClose }) {
  if (!node) return null;
  const meta = window.fireZenseAPI.RISK_META[node.risk];
  const first = node.history[0].soilTemperature;
  const last = node.history[node.history.length - 1].soilTemperature;
  const delta = +(last - first).toFixed(1);
  const peak = Math.max(...node.history.map((h) => h.soilTemperature));
  const peakLight = Math.max(...node.history.map((h) => h.light));

  // Efecto para enviar alerta automática si es crítico
  React.useEffect(() => {
    if (node.risk === "critico") {
      const alertMessage = `🔴 ALERTA CRÍTICA DE INCENDIO\n\nNodo: ${node.name}\nTemperatura: ${node.soilTemperature.toFixed(1)}°C\nHumedad: ${node.soilHumidity.toFixed(1)}%\nIluminación: ${node.light.toFixed(0)} lux`;
      console.log("🚨 Detectado riesgo CRÍTICO - Enviando alerta...");
      sendWhatsAppAlert(node.name, node.risk, alertMessage);
    }
  }, [node.risk, node._backendId]);
  
  const handleSendAlert = () => {
    const alertMessage = `🔴 ALERTA DE INCENDIO\n\nNodo: ${node.name}\nTemperatura: ${node.soilTemperature.toFixed(1)}°C\nHumedad: ${node.soilHumidity.toFixed(1)}%\nIluminación: ${node.light.toFixed(0)} lux`;
    sendWhatsAppAlert(node.name, node.risk, alertMessage);
  };

  return (
    <section className="fz-detail" data-risk={node.risk}>
      <div className="fz-detail-head">
        <div className="fz-detail-title">
          <div className="fz-detail-id">{node.id}</div>
          <h2>{node.name}</h2>
          <div className="fz-detail-area">{node.area}</div>
        </div>
        <div className="fz-detail-tags">
          <div className="fz-badge fz-badge-lg" style={{ background: meta.bg, color: meta.textColor }}>
            RIESGO {meta.label}
          </div>
          {node.risk === "critico" && (
            <button
              type="button"
              className="fz-alert-btn"
              onClick={handleSendAlert}
              title="Enviar alerta por WhatsApp"
              style={{
                background: "#dc2626",
                color: "white",
                border: "none",
                padding: "8px 12px",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: "bold",
              }}
            >
              📱 ENVIAR ALERTA WHATSAPP
            </button>
          )}
          <div className="fz-detail-meta">
            <span>BAT.S {node.batterySoil != null ? node.batterySoil + '%' : '—'}</span>
            <span>BAT.L {node.batteryLight != null ? node.batteryLight + '%' : '—'}</span>
            <span>VISTO HACE {node.lastSeen} MIN</span>
          </div>
          <button type="button" className="fz-close" onClick={onClose} aria-label="Cerrar">×</button>
        </div>
      </div>

      <div className="fz-detail-body">
        <div className="fz-big-metrics">
          <BigMetric label="Temp. suelo" value={node.soilTemperature.toFixed(1)} unit="°C" sub={`Δ24h ${delta > 0 ? "+" : ""}${delta}° · pico ${peak.toFixed(1)}°`} accent={meta.color} />
          <BigMetric label="Humedad suelo" value={node.soilHumidity.toFixed(1)} unit="%" sub={node.soilHumidity < 20 ? "Vegetación seca" : "Dentro de rango"} accent={meta.color} />
          <BigMetric label="Iluminación" value={node.light.toFixed(0)} unit="lux" sub={`Pico ${peakLight.toFixed(0)} lux`} accent={meta.color} />
          <BigMetric label="Electrocond." value={node.ec.toFixed(2)} unit="dS/m" sub={node.ec < 0.3 ? "Suelo muy seco" : node.ec < 0.6 ? "Marginal" : "Normal"} accent={meta.color} />
        </div>

        <div className="fz-chart-wrap">
          <div className="fz-chart-head">
            <div>
              <div className="fz-chart-title">TEMP. DEL SUELO — ÚLTIMAS 24H</div>
              <div className="fz-chart-sub">Lectura cada hora · LoRaWAN · UTC−6</div>
            </div>
            <div className="fz-chart-legend">
              <span className="fz-chart-dot" style={{ background: meta.color }} />
              {node.id}
            </div>
          </div>
          <SoilTempChart history={node.history} riskColor={meta.color} />
        </div>
      </div>
    </section>
  );
}

window.DetailPanel = DetailPanel;
