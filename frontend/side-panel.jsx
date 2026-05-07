// Right-side panel: Nodos / Alertas tabs

function risgoSort(a, b) {
  const order = { critico: 0, alto: 1, medio: 2, bajo: 3 };
  return order[a.risk] - order[b.risk];
}

function NodeCard({ node, selected, onClick }) {
  const meta = window.fireZenseAPI.RISK_META[node.risk];
  return (
    <button
      type="button"
      className="fz-node-card"
      data-risk={node.risk}
      data-selected={selected ? "true" : "false"}
      onClick={() => onClick(node.id)}
      style={{ "--fz-risk": meta.color }}
    >
      <div className="fz-node-row">
        <div className="fz-node-id">{node.id}</div>
        <div className="fz-badge" style={{ background: meta.bg, color: meta.textColor }}>
          {meta.label}
        </div>
      </div>
      <div className="fz-node-name">{node.name}</div>
      <div className="fz-node-area">{node.area.toUpperCase()}</div>
      <div className="fz-node-metrics">
        <div className="fz-metric">
          <span className="fz-metric-label">T. SUELO</span>
          <span className="fz-metric-value">{node.soilTemperature.toFixed(1)}<small>°C</small></span>
        </div>
        <div className="fz-metric">
          <span className="fz-metric-label">HUM.</span>
          <span className="fz-metric-value">{node.soilHumidity.toFixed(0)}<small>%</small></span>
        </div>
        <div className="fz-metric">
          <span className="fz-metric-label">LUZ</span>
          <span className="fz-metric-value">{node.light.toFixed(0)}<small>lux</small></span>
        </div>
        <div className="fz-metric fz-metric-wide">
          <span className="fz-metric-label">EC</span>
          <span className="fz-metric-value">{node.ec.toFixed(2)}<small>dS/m</small></span>
        </div>
      </div>
    </button>
  );
}

function AlertItem({ alert, nodes, onJumpToNode, onDismiss }) {
  const node = nodes.find((n) => n.id === alert.nodoId);
  const tipoMeta = {
    critico:     { label: "CRÍTICO",     bg: "#7f1d1d", border: "#dc2626", text: "#fecaca" },
    advertencia: { label: "ADVERTENCIA", bg: "#7c2d12", border: "#ea580c", text: "#fed7aa" },
    info:        { label: "INFO",        bg: "transparent", border: "#404040", text: "#a3a3a3" },
  }[alert.tipo];

  return (
    <div
      className="fz-alert"
      data-tipo={alert.tipo}
      style={{ background: tipoMeta.bg, borderLeftColor: tipoMeta.border, cursor: node ? "pointer" : "default" }}
      onClick={() => node && onJumpToNode(node.id)}
    >
      <div className="fz-alert-head">
        <span className="fz-alert-tipo" style={{ color: tipoMeta.text, borderColor: tipoMeta.border }}>
          {tipoMeta.label}
        </span>
        <div className="fz-alert-head-right">
          <span className="fz-alert-time">hace {alert.hace} min</span>
          <button
            type="button"
            className="fz-alert-dismiss"
            title="Marcar como leída"
            onClick={(e) => { e.stopPropagation(); onDismiss(alert.id); }}
          >✕</button>
        </div>
      </div>
      <div className="fz-alert-title">{alert.titulo}</div>
      <div className="fz-alert-msg">{alert.mensaje}</div>
      <div className="fz-alert-foot">
        <span className="fz-alert-node">{alert.nodoId}</span>
        <span className="fz-alert-area">{alert.nodoNombre} · {alert.area}</span>
      </div>
    </div>
  );
}

function SidePanel({ nodes, alerts, selectedId, onSelect, tab, setTab, onDismiss, onDismissAll }) {
  const sortedNodes = React.useMemo(() => [...nodes].sort(risgoSort), [nodes]);
  const counts = React.useMemo(() => {
    const c = { critico: 0, alto: 0, medio: 0, bajo: 0 };
    nodes.forEach((n) => c[n.risk]++);
    return c;
  }, [nodes]);
  const alertCounts = React.useMemo(() => {
    const c = { critico: 0, advertencia: 0, info: 0 };
    alerts.forEach((a) => c[a.tipo]++);
    return c;
  }, [alerts]);

  return (
    <aside className="fz-side">
      <div className="fz-tabs">
        <button
          type="button"
          className="fz-tab"
          data-active={tab === "nodos"}
          onClick={() => setTab("nodos")}
        >
          <span>Nodos</span>
          <em>{nodes.length}</em>
        </button>
        <button
          type="button"
          className="fz-tab"
          data-active={tab === "alertas"}
          onClick={() => setTab("alertas")}
        >
          <span>Alertas</span>
          <em data-critical={alertCounts.critico > 0}>{alerts.length}</em>
        </button>
      </div>

      {tab === "nodos" && (
        <div className="fz-side-body">
          <div className="fz-side-summary">
            <div><b>{counts.critico}</b><span>Crítico</span></div>
            <div><b>{counts.alto}</b><span>Alto</span></div>
            <div><b>{counts.medio}</b><span>Medio</span></div>
            <div><b>{counts.bajo}</b><span>Bajo</span></div>
          </div>
          <div className="fz-list">
            {sortedNodes.map((n) => (
              <NodeCard key={n.id} node={n} selected={selectedId === n.id} onClick={onSelect} />
            ))}
          </div>
        </div>
      )}

      {tab === "alertas" && (
        <div className="fz-side-body">
          <div className="fz-side-summary">
            <div><b>{alertCounts.critico}</b><span>Críticas</span></div>
            <div><b>{alertCounts.advertencia}</b><span>Advert.</span></div>
            <div><b>{alertCounts.info}</b><span>Info</span></div>
          </div>
          {alerts.length > 0 && (
            <div className="fz-alerts-actions">
              <button type="button" className="fz-btn-dismiss-all" onClick={onDismissAll}>
                Marcar todas como leídas
              </button>
            </div>
          )}
          <div className="fz-list">
            {alerts.length === 0
              ? <div className="fz-alerts-empty">Sin alertas pendientes</div>
              : alerts.map((a) => (
                  <AlertItem key={a.id} alert={a} nodes={nodes} onJumpToNode={onSelect} onDismiss={onDismiss} />
                ))
            }
          </div>
        </div>
      )}
    </aside>
  );
}

window.SidePanel = SidePanel;
