"""
SISTEMA DE DETECCIÓN DE INCENDIOS FORESTALES
IoT LoRaWAN — Milesight UG65 Network Server (formato ChirpStack)
Sensores por nodo: EM500-SMTC + EM500-LGT915M
"""

from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import sqlite3

# =====================================================================
# CONFIGURACIÓN
# =====================================================================

API_KEY  = "tu_api_key_local"
DATABASE = str(Path(__file__).parent.parent / "database" / "monitoreo_forestal.db")
MEXICO_OFFSET = timedelta(hours=-6)
RED_REMINDER_MINUTES  = 30
READ_COOLDOWN_MINUTES = 0  # sin cooldown: nueva alerta en el siguiente ciclo de lectura

# =====================================================================
# APLICACIÓN
# =====================================================================

app = FastAPI(
    title="Detección de Incendios Forestales IoT",
    description="Sistema multi-nodo — Milesight UG65 + EM500-SMTC + EM500-LGT915M",
    version="5.0.0",
    openapi_tags=[
        {
            "name": "Nodos",
            "description": "Gestión de nodos de monitoreo (tabla `nodes`).",
        },
        {
            "name": "LoRaWAN / Gateway",
            "description": "Recepción de uplinks reales desde el gateway Milesight UG65 (tabla `lorawan_transmissions`).",
        },
        {
            "name": "Simulador",
            "description": "Envío de uplinks sintéticos para pruebas (inserta en `lorawan_transmissions`, `light_readings` o `soil_readings`).",
        },
        {
            "name": "Lecturas de Luz",
            "description": "Historial de lecturas del sensor EM500-LGT915M (tabla `light_readings`).",
        },
        {
            "name": "Lecturas de Suelo",
            "description": "Historial de lecturas del sensor EM500-SMTC (tabla `soil_readings`).",
        },
        {
            "name": "Riesgo de Incendio",
            "description": "Evaluación y historial de riesgo calculado (tabla `fire_risk_events`).",
        },
        {
            "name": "Alertas",
            "description": "Alertas activas y gestión de estado de lectura (tabla `alerts`).",
        },
        {
            "name": "Sistema",
            "description": "Estado del servicio y estadísticas generales.",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# MODELOS
# =====================================================================

class NodeCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    light_eui: Optional[str] = None
    soil_eui:  Optional[str] = None
    description: Optional[str] = None

# =====================================================================
# BASE DE DATOS
# =====================================================================

def init_database():
    conn   = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            latitude    REAL NOT NULL,
            longitude   REAL NOT NULL,
            light_eui   TEXT,
            soil_eui    TEXT,
            description TEXT,
            active      INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lorawan_transmissions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            gateway_id       TEXT,
            device_eui       TEXT,
            node_id          INTEGER,
            timestamp        TEXT,
            rssi             INTEGER,
            snr              REAL,
            spreading_factor INTEGER,
            received_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS light_readings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            device_eui      TEXT,
            node_id         INTEGER,
            timestamp       TEXT,
            light_lux       REAL,
            battery_percent INTEGER,
            is_night        INTEGER,
            received_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS soil_readings (
            id                            INTEGER PRIMARY KEY AUTOINCREMENT,
            device_eui                    TEXT,
            node_id                       INTEGER,
            timestamp                     TEXT,
            soil_moisture_percent         REAL,
            soil_temperature_celsius      REAL,
            electrical_conductivity_us_cm REAL,
            battery_percent               INTEGER,
            delta_temp_per_min            REAL,
            received_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fire_risk_events (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id              INTEGER,
            device_eui           TEXT,
            risk_level           TEXT,
            risk_score           INTEGER,
            contributing_factors TEXT,
            delta_temp_per_min   REAL,
            sensor_type          TEXT,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id    INTEGER,
            device_eui TEXT,
            alert_type TEXT,
            severity   TEXT,
            message    TEXT,
            value      REAL,
            is_read    INTEGER DEFAULT 0,
            read_at    TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)
    # Migración para bases de datos existentes
    for col, definition in [("is_read", "INTEGER DEFAULT 0"), ("read_at", "TIMESTAMP")]:
        try:
            cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col} {definition}")
        except Exception:
            pass

    cursor.execute("SELECT COUNT(*) FROM nodes")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO nodes (name, latitude, longitude, light_eui, soil_eui, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "NodoTec",
            28.6754054561614,
            -106.075849754208,
            "24E124126E113360",
            "24E124126E174049",
            "Nodo de Prueba · Chihuahua, MX",
        ))
        print("✓ Nodo demo creado: NodoTec (id=1)")

    conn.commit()
    conn.close()
    print(f"✓ Base de datos: {DATABASE}")


# =====================================================================
# HELPERS
# =====================================================================

def is_night(timestamp: str) -> bool:
    """Noche = 20:00–06:00 hora México (UTC-6)."""
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        local_hour = (dt + MEXICO_OFFSET).hour
        return local_hour >= 20 or local_hour < 6
    except Exception:
        return False


def _parse_utc(ts: str) -> datetime:
    """Parsea un timestamp a datetime UTC-aware, sin importar si trae zona o no."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _elapsed_minutes(ts: str) -> Optional[float]:
    """Minutos transcurridos desde ts (UTC). None si no se puede parsear."""
    try:
        return (datetime.now(timezone.utc) - _parse_utc(ts)).total_seconds() / 60
    except Exception:
        return None


def get_delta_temp_per_min(cursor, device_eui: str, current_temp: float) -> Optional[float]:
    """ΔT/min respecto a la última lectura en BD. None si no hay lectura previa."""
    cursor.execute("""
        SELECT soil_temperature_celsius, received_at
        FROM soil_readings WHERE device_eui = ?
        ORDER BY received_at DESC LIMIT 1
    """, (device_eui,))
    last = cursor.fetchone()
    if not last or last[0] is None:
        return None
    elapsed_min = _elapsed_minutes(last[1])
    if elapsed_min is None or elapsed_min <= 0 or elapsed_min > 60:
        return None
    delta = (current_temp - last[0]) / elapsed_min
    return round(delta, 3) if delta > 0 else None


def should_create_alert(cursor, node_id: int, new_level: str) -> tuple[bool, str]:
    """Decide si insertar una alerta nueva.

    Reglas:
    - Sin alertas previas          → crear (transition)
    - Nivel cambió                 → crear (transition)
    - Mismo nivel, ya leída        → crear en el siguiente ciclo de lectura (sin cooldown)
    - Mismo nivel, no leída, RED   → crear después de RED_REMINDER_MINUTES desde created_at (reminder)
    - Mismo nivel, no leída, otros → suprimir
    """
    cursor.execute("""
        SELECT alert_type, created_at, is_read, read_at FROM alerts
        WHERE node_id = ? ORDER BY created_at DESC LIMIT 1
    """, (node_id,))
    last = cursor.fetchone()

    if last is None:
        return True, "transition"

    last_level, last_created_at, is_read, read_at = last
    last_level = last_level.split("_")[-1].upper()  # "fire_risk_orange" → "ORANGE"

    if last_level != new_level:
        return True, "transition"

    # Guard: evita duplicados del ciclo soil+light (ambas lecturas llegan en segundos)
    elapsed_since_last = _elapsed_minutes(last_created_at)
    if elapsed_since_last is not None and elapsed_since_last < 1:
        return False, ""

    if is_read:
        return True, "transition"

    if new_level == "RED":
        elapsed = _elapsed_minutes(last_created_at)
        if elapsed is not None and elapsed >= RED_REMINDER_MINUTES:
            return True, "reminder"

    return False, ""


def lookup_node(cursor, device_eui: str) -> tuple[Optional[int], Optional[str]]:
    """Busca el nodo al que pertenece el device_eui y qué tipo de sensor es."""
    cursor.execute("""
        SELECT id,
               CASE WHEN light_eui = ? THEN 'light_sensor'
                    WHEN soil_eui  = ? THEN 'soil_sensor'
                    ELSE 'unknown' END
        FROM nodes
        WHERE (light_eui = ? OR soil_eui = ?) AND active = 1
        LIMIT 1
    """, (device_eui, device_eui, device_eui, device_eui))
    row = cursor.fetchone()
    return (row[0], row[1]) if row else (None, None)


# =====================================================================
# PARSERS DE OBJETO DECODIFICADO POR EL GATEWAY
#
# El gateway Milesight UG65 ya decodifica el payload con su Payload Codec
# y envía el resultado en el campo "object" del JSON.
# No necesitamos decodificar hex — leemos directamente los valores.
#
# EM500-SMTC  → object: { temperature, moisture, electricity }
# EM500-LGT   → object: { illuminance }  (o light / lux según codec)
# =====================================================================

def identify_sensor_from_object(obj: dict) -> str:
    if any(k in obj for k in ("temperature", "moisture", "electricity",
                               "moisture_error", "electricity_error")):
        return "soil_sensor"
    if any(k in obj for k in ("illuminance", "light", "lux", "illumination")):
        return "light_sensor"
    return "unknown"


def parse_soil_object(obj: dict) -> dict:
    temp     = obj.get("temperature")
    moisture = obj.get("moisture") if not obj.get("moisture_error") else None
    ec       = obj.get("electricity") if not obj.get("electricity_error") else None
    return {
        "soil_temperature_celsius":      temp,
        "soil_moisture_percent":         moisture,
        "electrical_conductivity_us_cm": ec,
        "battery_percent":               obj.get("battery"),
        "valid": temp is not None,
    }


def parse_light_object(obj: dict) -> dict:
    lux = (obj.get("illuminance") or obj.get("light")
           or obj.get("lux") or obj.get("illumination"))
    return {
        "light_lux":       lux,
        "battery_percent": obj.get("battery"),
        "valid":           lux is not None,
    }


# =====================================================================
# MOTOR DE RIESGO
# =====================================================================

RISK_LEVELS = {
    "GREEN":  {"label": "Normal — solo monitoreo",              "emoji": "🟢"},
    "YELLOW": {"label": "Riesgo bajo — advertencia preventiva", "emoji": "🟡"},
    "ORANGE": {"label": "Riesgo alto — alerta al HUB",          "emoji": "🟠"},
    "RED":    {"label": "INCENDIO POSIBLE — alerta crítica",     "emoji": "🔴"},
}


def calculate_fire_risk(
    soil_data: Optional[dict]  = None,
    light_data: Optional[dict] = None,
    timestamp: Optional[str]   = None,
    delta_temp_per_min: Optional[float] = None,
) -> dict:
    score   = 0
    factors = []

    if soil_data:
        temp     = soil_data.get("soil_temperature_celsius") or 0
        moisture = soil_data.get("soil_moisture_percent") or 100
        ec       = soil_data.get("electrical_conductivity_us_cm")

        if temp > 60:
            score += 40; factors.append("temp_suelo_critica_>60C")
        elif temp > 45:
            score += 25; factors.append("temp_suelo_alta_>45C")
        elif temp > 35:
            score += 10; factors.append("temp_suelo_elevada_>35C")

        if moisture < 7:
            score += 30; factors.append("humedad_critica_<7pct")
        elif moisture < 8:
            score += 15; factors.append("humedad_baja_<8pct")

        if ec is not None:
            if ec < 100:
                score += 20; factors.append("suelo_muy_seco_ec<100")
            elif ec < 200:
                score += 10; factors.append("suelo_seco_ec<200")

    if delta_temp_per_min is not None:
        if delta_temp_per_min > 2:
            score += 45; factors.append(f"incremento_rapido_{delta_temp_per_min:.2f}C/min")
        elif delta_temp_per_min > 0.5:
            score += 20; factors.append(f"incremento_moderado_{delta_temp_per_min:.2f}C/min")

    if light_data and timestamp:
        lux   = light_data.get("light_lux") or 0
        night = is_night(timestamp)
        if night:
            if lux > 100:
                score += 35; factors.append("luz_nocturna_critica_>100lux")
            elif lux > 50:
                score += 20; factors.append("luz_nocturna_elevada_>50lux")
        else:
            if lux > 50_000:
                score += 15; factors.append("luz_diurna_extrema_>50klux")

    if score >= 70:   risk_level = "RED"
    elif score >= 45: risk_level = "ORANGE"
    elif score >= 20: risk_level = "YELLOW"
    else:             risk_level = "GREEN"

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "factors":    factors,
        "label":      RISK_LEVELS[risk_level]["label"],
        "emoji":      RISK_LEVELS[risk_level]["emoji"],
    }


def calculate_node_risk(cursor, node_id: int,
                         current_soil: Optional[dict]  = None,
                         current_light: Optional[dict] = None,
                         timestamp: Optional[str]      = None,
                         delta: Optional[float]        = None) -> dict:
    """Riesgo combinado del nodo usando la lectura actual + la última del sensor complementario."""
    soil_data  = current_soil
    light_data = current_light

    if soil_data is None:
        cursor.execute("""
            SELECT sr.soil_moisture_percent, sr.soil_temperature_celsius,
                   sr.electrical_conductivity_us_cm, sr.delta_temp_per_min, sr.timestamp
            FROM soil_readings sr
            JOIN nodes n ON sr.device_eui = n.soil_eui
            WHERE n.id = ? ORDER BY sr.received_at DESC LIMIT 1
        """, (node_id,))
        row = cursor.fetchone()
        if row:
            soil_data = {
                "soil_moisture_percent":         row[0],
                "soil_temperature_celsius":      row[1],
                "electrical_conductivity_us_cm": row[2],
            }
            if delta is None:     delta = row[3]
            if timestamp is None: timestamp = row[4]

    if light_data is None:
        cursor.execute("""
            SELECT lr.light_lux, lr.timestamp
            FROM light_readings lr
            JOIN nodes n ON lr.device_eui = n.light_eui
            WHERE n.id = ? ORDER BY lr.received_at DESC LIMIT 1
        """, (node_id,))
        row = cursor.fetchone()
        if row:
            light_data = {"light_lux": row[0]}
            if timestamp is None: timestamp = row[1]

    return calculate_fire_risk(
        soil_data=soil_data,
        light_data=light_data,
        timestamp=timestamp,
        delta_temp_per_min=delta,
    )


# =====================================================================
# ENDPOINTS — NODOS
# =====================================================================

@app.post("/api/v1/nodes", status_code=201, tags=["Nodos"])
async def create_node(node: NodeCreate, x_api_key: str = Header(None)):
    """Registrar un nuevo nodo con coordenadas y EUIs de sus sensores."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    conn   = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO nodes (name, latitude, longitude, light_eui, soil_eui, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (node.name, node.latitude, node.longitude,
          node.light_eui.upper() if node.light_eui else None,
          node.soil_eui.upper()  if node.soil_eui  else None,
          node.description))
    node_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"✓ Nodo creado: {node.name} ({node.latitude}, {node.longitude}) id={node_id}")
    return {"id": node_id, "name": node.name,
            "latitude": node.latitude, "longitude": node.longitude}


@app.get("/api/v1/nodes", tags=["Nodos"])
async def get_nodes():
    """Todos los nodos activos con riesgo actual — endpoint principal del mapa."""
    conn   = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nodes WHERE active=1 ORDER BY name")
    nodes  = cursor.fetchall()

    result = []
    for node in nodes:
        cursor.execute("""
            SELECT * FROM soil_readings WHERE device_eui=?
            ORDER BY received_at DESC LIMIT 1
        """, (node["soil_eui"],))
        soil_row  = cursor.fetchone()
        soil_data = dict(soil_row) if soil_row else None
        if soil_data and soil_data.get("battery_percent") is None:
            cursor.execute("""
                SELECT battery_percent FROM soil_readings
                WHERE device_eui=? AND battery_percent IS NOT NULL
                ORDER BY received_at DESC LIMIT 1
            """, (node["soil_eui"],))
            bat = cursor.fetchone()
            if bat:
                soil_data["battery_percent"] = bat[0]

        cursor.execute("""
            SELECT * FROM light_readings WHERE device_eui=?
            ORDER BY received_at DESC LIMIT 1
        """, (node["light_eui"],))
        light_row  = cursor.fetchone()
        light_data = dict(light_row) if light_row else None
        if light_data and light_data.get("battery_percent") is None:
            cursor.execute("""
                SELECT battery_percent FROM light_readings
                WHERE device_eui=? AND battery_percent IS NOT NULL
                ORDER BY received_at DESC LIMIT 1
            """, (node["light_eui"],))
            bat = cursor.fetchone()
            if bat:
                light_data["battery_percent"] = bat[0]

        cursor.execute("""
            SELECT MAX(received_at) FROM lorawan_transmissions
            WHERE device_eui IN (?, ?)
        """, (node["light_eui"], node["soil_eui"]))
        last_seen = cursor.fetchone()[0]

        risk = calculate_fire_risk(
            soil_data  = soil_data,
            light_data = light_data,
            timestamp  = (light_data or {}).get("timestamp"),
            delta_temp_per_min = (soil_data or {}).get("delta_temp_per_min"),
        )

        result.append({
            **dict(node),
            "risk_level":           risk["risk_level"],
            "risk_score":           risk["risk_score"],
            "risk_label":           risk["label"],
            "risk_emoji":           risk["emoji"],
            "contributing_factors": risk["factors"],
            "last_soil_reading":    soil_data,
            "last_light_reading":   light_data,
            "last_seen":            last_seen,
        })

    conn.close()
    return {"count": len(result), "nodes": result}


@app.get("/api/v1/nodes/{node_id}", tags=["Nodos"])
async def get_node(node_id: int):
    """Detalle de un nodo: info + últimas lecturas + historial de riesgo."""
    conn   = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nodes WHERE id=?", (node_id,))
    node = cursor.fetchone()
    if not node:
        conn.close()
        raise HTTPException(status_code=404, detail="Nodo no encontrado")

    cursor.execute("""
        SELECT * FROM soil_readings WHERE device_eui=?
        ORDER BY received_at DESC LIMIT 20
    """, (node["soil_eui"],))
    soil_history = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT * FROM light_readings WHERE device_eui=?
        ORDER BY received_at DESC LIMIT 20
    """, (node["light_eui"],))
    light_history = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT * FROM fire_risk_events WHERE node_id=?
        ORDER BY created_at DESC LIMIT 20
    """, (node_id,))
    risk_history = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        "node":          dict(node),
        "soil_history":  soil_history,
        "light_history": light_history,
        "risk_history":  risk_history,
    }


@app.delete("/api/v1/nodes/{node_id}", tags=["Nodos"])
async def deactivate_node(node_id: int, x_api_key: str = Header(None)):
    """Desactivar un nodo (no lo borra, solo lo marca inactivo)."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    conn   = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("UPDATE nodes SET active=0 WHERE id=?", (node_id,))
    conn.commit()
    conn.close()
    return {"success": True, "node_id": node_id}


# =====================================================================
# ENDPOINT — SIMULADOR (targeting explícito por node_id)
# =====================================================================

class SimulatePayload(BaseModel):
    node_id: int
    sensor_object: dict
    timestamp: Optional[str] = None


@app.post("/api/v1/simulate/uplink", tags=["Simulador"])
async def simulate_uplink(payload: SimulatePayload, x_api_key: str = Header(None)):
    """Uplink de simulación — acepta node_id explícito y timestamp opcional para backfill."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    sensor_object = payload.sensor_object
    node_id       = payload.node_id
    timestamp     = payload.timestamp or datetime.now(timezone.utc).isoformat()

    sensor_type = identify_sensor_from_object(sensor_object)
    if sensor_type == "unknown":
        return {"success": False, "message": f"Tipo de sensor no reconocido: {sensor_object}"}

    conn   = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id, light_eui, soil_eui FROM nodes WHERE id=? AND active=1", (node_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Nodo {node_id} no encontrado o inactivo")

        if sensor_type == "light_sensor":
            device_eui = row[1] or f"SIM-N{node_id}-LGT"
        else:
            device_eui = row[2] or f"SIM-N{node_id}-SOIL"

        cursor.execute("""
            INSERT INTO lorawan_transmissions
            (gateway_id, device_eui, node_id, timestamp, rssi, snr, spreading_factor)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("simulator", device_eui, node_id, timestamp, -75, 7.5, 7))

        decoded = None
        delta   = None

        if sensor_type == "light_sensor":
            decoded = parse_light_object(sensor_object)
            if decoded["valid"]:
                night = is_night(timestamp)
                cursor.execute("""
                    INSERT INTO light_readings
                    (device_eui, node_id, timestamp, light_lux, battery_percent, is_night)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (device_eui, node_id, timestamp,
                      decoded["light_lux"], decoded["battery_percent"], int(night)))

        elif sensor_type == "soil_sensor":
            decoded = parse_soil_object(sensor_object)
            if decoded["valid"]:
                delta = get_delta_temp_per_min(
                    cursor, device_eui, decoded["soil_temperature_celsius"] or 0
                )
                cursor.execute("""
                    INSERT INTO soil_readings
                    (device_eui, node_id, timestamp, soil_moisture_percent,
                     soil_temperature_celsius, electrical_conductivity_us_cm,
                     battery_percent, delta_temp_per_min)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (device_eui, node_id, timestamp,
                      decoded["soil_moisture_percent"],
                      decoded["soil_temperature_celsius"],
                      decoded["electrical_conductivity_us_cm"],
                      decoded["battery_percent"], delta))

        risk_info = {}
        if decoded and decoded.get("valid"):
            risk = calculate_node_risk(
                cursor, node_id,
                current_soil  = decoded if sensor_type == "soil_sensor"  else None,
                current_light = decoded if sensor_type == "light_sensor" else None,
                timestamp     = timestamp,
                delta         = delta,
            )
            cursor.execute("""
                INSERT INTO fire_risk_events
                (node_id, device_eui, risk_level, risk_score,
                 contributing_factors, delta_temp_per_min, sensor_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (node_id, device_eui, risk["risk_level"], risk["risk_score"],
                  ", ".join(risk["factors"]) or "ninguno", delta, sensor_type))

            if risk["risk_level"] in ("ORANGE", "RED"):
                alert_ok, reason = should_create_alert(cursor, node_id, risk["risk_level"])
                if alert_ok:
                    severity = "critical" if risk["risk_level"] == "RED" else "warning"
                    prefix   = "[Recordatorio] " if reason == "reminder" else ""
                    cursor.execute("""
                        INSERT INTO alerts
                        (node_id, device_eui, alert_type, severity, message, value)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (node_id, device_eui,
                          f"fire_risk_{risk['risk_level'].lower()}",
                          severity,
                          f"{prefix}{risk['emoji']} {risk['label']}: {', '.join(risk['factors'])}",
                          risk["risk_score"]))

            risk_info = {
                "risk_level": risk["risk_level"],
                "risk_score": risk["risk_score"],
                "risk_emoji": risk["emoji"],
                "factors":    risk["factors"],
            }

        conn.commit()
        return {
            "success":     True,
            "node_id":     node_id,
            "device_eui":  device_eui,
            "sensor_type": sensor_type,
            "timestamp":   timestamp,
            **risk_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# =====================================================================
# ENDPOINT — UPLINK GATEWAY (formato Milesight UG65 / ChirpStack)
# =====================================================================

@app.post("/api/v1/lorawan/uplink", tags=["LoRaWAN / Gateway"])
async def receive_uplink(
    payload: dict = Body(...),
    x_api_key: str = Header(None),
):
    """
    Recibe uplinks del gateway Milesight UG65.
    El gateway manda directamente el objeto decodificado (sin devEUI ni metadata).
    Se identifica el sensor por las claves del payload y se asigna al nodo activo.
    """
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    sensor_object = payload
    if not sensor_object:
        return {"success": False, "message": "Payload vacío"}

    sensor_type = identify_sensor_from_object(sensor_object)
    if sensor_type == "unknown":
        print(f"  ✗ Sensor no reconocido: {sensor_object}")
        return {"success": False, "message": f"Tipo de sensor no reconocido: {sensor_object}"}

    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] UPLINK  {sensor_type}")
    print(f"  Object: {sensor_object}")

    conn   = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:
        # Sin devEUI: buscar el nodo activo por tipo de sensor
        if sensor_type == "light_sensor":
            cursor.execute(
                "SELECT id, light_eui FROM nodes WHERE light_eui IS NOT NULL AND active=1 LIMIT 1"
            )
        else:
            cursor.execute(
                "SELECT id, soil_eui FROM nodes WHERE soil_eui IS NOT NULL AND active=1 LIMIT 1"
            )
        row        = cursor.fetchone()
        node_id    = row[0] if row else None
        device_eui = row[1] if row else "unknown"

        print(f"  Nodo: {node_id or 'sin asignar'} | EUI: {device_eui}")

        cursor.execute("""
            INSERT INTO lorawan_transmissions
            (gateway_id, device_eui, node_id, timestamp, rssi, snr, spreading_factor)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("ug65", device_eui, node_id, timestamp, None, None, None))

        decoded = None
        delta   = None

        if sensor_type == "light_sensor":
            decoded = parse_light_object(sensor_object)
            if decoded["valid"]:
                night = is_night(timestamp)
                print(f"  ✓ Luz: {decoded['light_lux']} lux "
                      f"({'NOCHE' if night else 'DÍA'})")
                cursor.execute("""
                    INSERT INTO light_readings
                    (device_eui, node_id, timestamp, light_lux, battery_percent, is_night)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (device_eui, node_id, timestamp,
                      decoded["light_lux"], decoded["battery_percent"], int(night)))

        elif sensor_type == "soil_sensor":
            decoded = parse_soil_object(sensor_object)
            if decoded["valid"]:
                delta = get_delta_temp_per_min(
                    cursor, device_eui, decoded["soil_temperature_celsius"] or 0
                )
                delta_str = f"{delta:.2f}°C/min" if delta is not None else "primera lectura"
                print(f"  ✓ Temp: {decoded['soil_temperature_celsius']}°C "
                      f"(ΔT: {delta_str}) | "
                      f"Humedad: {decoded['soil_moisture_percent']}% | "
                      f"EC: {decoded['electrical_conductivity_us_cm']} µS/cm")
                cursor.execute("""
                    INSERT INTO soil_readings
                    (device_eui, node_id, timestamp, soil_moisture_percent,
                     soil_temperature_celsius, electrical_conductivity_us_cm,
                     battery_percent, delta_temp_per_min)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (device_eui, node_id, timestamp,
                      decoded["soil_moisture_percent"],
                      decoded["soil_temperature_celsius"],
                      decoded["electrical_conductivity_us_cm"],
                      decoded["battery_percent"], delta))

        # Calcular riesgo
        if decoded and decoded.get("valid"):
            if node_id:
                risk = calculate_node_risk(
                    cursor, node_id,
                    current_soil  = decoded if sensor_type == "soil_sensor"  else None,
                    current_light = decoded if sensor_type == "light_sensor" else None,
                    timestamp     = timestamp,
                    delta         = delta,
                )
            else:
                risk = calculate_fire_risk(
                    soil_data  = decoded if sensor_type == "soil_sensor"  else None,
                    light_data = decoded if sensor_type == "light_sensor" else None,
                    timestamp  = timestamp,
                    delta_temp_per_min = delta,
                )

            cursor.execute("""
                INSERT INTO fire_risk_events
                (node_id, device_eui, risk_level, risk_score,
                 contributing_factors, delta_temp_per_min, sensor_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (node_id, device_eui, risk["risk_level"], risk["risk_score"],
                  ", ".join(risk["factors"]) or "ninguno", delta, sensor_type))

            print(f"  {risk['emoji']} {risk['risk_level']} (score={risk['risk_score']})"
                  + (f": {', '.join(risk['factors'])}" if risk["factors"] else ""))

            if risk["risk_level"] in ("ORANGE", "RED"):
                alert_ok, reason = should_create_alert(cursor, node_id, risk["risk_level"])
                if alert_ok:
                    severity = "critical" if risk["risk_level"] == "RED" else "warning"
                    prefix   = "[Recordatorio] " if reason == "reminder" else ""
                    cursor.execute("""
                        INSERT INTO alerts
                        (node_id, device_eui, alert_type, severity, message, value)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (node_id, device_eui,
                          f"fire_risk_{risk['risk_level'].lower()}",
                          severity,
                          f"{prefix}{risk['emoji']} {risk['label']}: {', '.join(risk['factors'])}",
                          risk["risk_score"]))

        conn.commit()
        print(f"{'='*60}\n")
        return {"success": True, "sensor_type": sensor_type, "timestamp": timestamp}

    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# =====================================================================
# ENDPOINTS — LECTURAS, ALERTAS Y STATS
# =====================================================================

@app.get("/api/v1/health", tags=["Sistema"])
async def health():
    return {"status": "ok", "service": "Detección de Incendios Forestales IoT",
            "version": "5.0.0", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/fire-risk/current", tags=["Riesgo de Incendio"])
async def get_current_fire_risk():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fre.*, n.name as node_name, n.latitude, n.longitude
        FROM fire_risk_events fre
        LEFT JOIN nodes n ON fre.node_id = n.id
        WHERE fre.id IN (SELECT MAX(id) FROM fire_risk_events GROUP BY node_id)
        ORDER BY fre.risk_score DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "fire_risk": [dict(r) for r in rows]}


@app.get("/api/v1/fire-risk/history", tags=["Riesgo de Incendio"])
async def get_fire_risk_history(limit: int = 50):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fre.*, n.name as node_name FROM fire_risk_events fre
        LEFT JOIN nodes n ON fre.node_id = n.id
        ORDER BY fre.created_at DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "history": [dict(r) for r in rows]}


@app.get("/api/v1/readings/light", tags=["Lecturas de Luz"])
async def get_light_readings(limit: int = 10):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT lr.*, n.name as node_name FROM light_readings lr
        LEFT JOIN nodes n ON lr.node_id = n.id
        ORDER BY lr.received_at DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "readings": [dict(r) for r in rows]}


@app.get("/api/v1/readings/soil", tags=["Lecturas de Suelo"])
async def get_soil_readings(limit: int = 10):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sr.*, n.name as node_name FROM soil_readings sr
        LEFT JOIN nodes n ON sr.node_id = n.id
        ORDER BY sr.received_at DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "readings": [dict(r) for r in rows]}


@app.get("/api/v1/alerts", tags=["Alertas"])
async def get_alerts(limit: int = 20, include_read: bool = False):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    where = "" if include_read else "WHERE a.is_read = 0"
    cursor.execute(f"""
        SELECT a.*, n.name as node_name, n.latitude, n.longitude
        FROM alerts a LEFT JOIN nodes n ON a.node_id = n.id
        {where}
        ORDER BY a.created_at DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "alerts": [dict(r) for r in rows]}


@app.patch("/api/v1/alerts/{alert_id}/read", tags=["Alertas"])
async def mark_alert_read(alert_id: int):
    conn    = sqlite3.connect(DATABASE)
    cursor  = conn.cursor()
    cursor.execute(
        "UPDATE alerts SET is_read=1, read_at=? WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), alert_id),
    )
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    conn.commit()
    conn.close()
    return {"success": True, "alert_id": alert_id}


@app.patch("/api/v1/alerts/read-all")
async def mark_all_alerts_read():
    """Marca TODAS las alertas no leídas como leídas."""
    now = datetime.now(timezone.utc).isoformat()
    conn   = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE alerts SET is_read=1, read_at=? WHERE is_read=0", (now,)
    )
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    return {"success": True, "marked_read": updated}


@app.get("/api/v1/stats", tags=["Sistema"])
async def get_stats():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM nodes WHERE active=1")
    active_nodes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM light_readings")
    light_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM soil_readings")
    soil_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM fire_risk_events WHERE risk_level='RED'")
    red_events = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM fire_risk_events WHERE risk_level='ORANGE'")
    orange_events = cursor.fetchone()[0]
    conn.close()
    return {
        "nodes":     {"active": active_nodes},
        "sensors":   {"light_readings": light_count, "soil_readings": soil_count},
        "fire_risk": {"red_events": red_events, "orange_events": orange_events},
        "timestamp": datetime.now().isoformat(),
    }


# =====================================================================
# MAIN
# =====================================================================

FRONTEND = str(Path(__file__).parent.parent / "frontend")
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("🔥 DETECCIÓN DE INCENDIOS FORESTALES — IoT LoRaWAN")
    print("   Multi-nodo | Milesight UG65 Network Server")
    print("="*60)
    print(f"API Key:       {API_KEY}")
    print(f"Base de datos: {DATABASE}")
    print()
    print("Formato de uplink esperado: Milesight UG65 / ChirpStack")
    print("  devEUI    → identificador del sensor")
    print("  object    → payload ya decodificado por el gateway")
    print("    EM500-SMTC : { temperature, moisture, electricity }")
    print("    EM500-LGT  : { illuminance }")
    print("  rxInfo[0] → rssi, loRaSNR, time")
    print()
    print("Niveles de riesgo:")
    print("  🟢 GREEN   ( 0–19)  Normal")
    print("  🟡 YELLOW  (20–44)  Riesgo bajo")
    print("  🟠 ORANGE  (45–69)  Riesgo alto → alerta")
    print("  🔴 RED     (70+)    Incendio posible → alerta crítica")
    print()
    print("Documentación: http://localhost:8000/docs")
    print("="*60 + "\n")

    init_database()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
