# Diagrama de Base de Datos — Detección de Incendios

## Esquema Entidad-Relación

```mermaid
erDiagram
    NODES {
        INTEGER id PK
        TEXT name
        REAL latitude
        REAL longitude
        TEXT light_eui
        TEXT soil_eui
        TEXT description
        INTEGER active
        TIMESTAMP created_at
    }

    LORAWAN_TRANSMISSIONS {
        INTEGER id PK
        TEXT gateway_id
        TEXT device_eui
        INTEGER node_id FK
        TEXT timestamp
        TEXT payload_hex
        INTEGER rssi
        REAL snr
        INTEGER spreading_factor
        TIMESTAMP received_at
    }

    LIGHT_READINGS {
        INTEGER id PK
        TEXT device_eui
        INTEGER node_id FK
        TEXT timestamp
        INTEGER light_lux
        INTEGER battery_percent
        INTEGER is_night
        TIMESTAMP received_at
    }

    SOIL_READINGS {
        INTEGER id PK
        TEXT device_eui
        INTEGER node_id FK
        TEXT timestamp
        REAL soil_moisture_percent
        REAL soil_temperature_celsius
        INTEGER electrical_conductivity_us_cm
        INTEGER battery_percent
        REAL delta_temp_per_min
        TIMESTAMP received_at
    }

    FIRE_RISK_EVENTS {
        INTEGER id PK
        INTEGER node_id FK
        TEXT device_eui
        TEXT risk_level
        INTEGER risk_score
        TEXT contributing_factors
        REAL delta_temp_per_min
        TEXT sensor_type
        TIMESTAMP created_at
    }

    ALERTS {
        INTEGER id PK
        INTEGER node_id FK
        TEXT device_eui
        TEXT alert_type
        TEXT severity
        TEXT message
        REAL value
        INTEGER is_read
        TIMESTAMP read_at
        TIMESTAMP created_at
    }

    NODES ||--o{ LORAWAN_TRANSMISSIONS : "tiene"
    NODES ||--o{ LIGHT_READINGS        : "tiene"
    NODES ||--o{ SOIL_READINGS         : "tiene"
    NODES ||--o{ FIRE_RISK_EVENTS      : "genera"
    NODES ||--o{ ALERTS                : "genera"
    FIRE_RISK_EVENTS ||--o{ ALERTS     : "score ≥ 45"
```

## Flujo de escritura

```mermaid
flowchart TD
    GW["Gateway UG65\nSolo objeto decodificado\n{illumination} o {temperature...}"] --> ID{"identify_sensor_from_object()\n¿illumination o temperature?"}

    ID -- "illumination\nEM500-LGT" --> NL["SELECT nodo activo\ncon light_eui"] --> L["light_readings\nlux + is_night + node_id"]
    ID -- "temperature / moisture\nEM500-SMTC" --> NS["SELECT nodo activo\ncon soil_eui"] --> S["soil_readings\ntemp + humedad + EC\n+ delta_temp_per_min + node_id"]

    NL & NS --> RAW["lorawan_transmissions\ngateway_id=ug65 + node_id"]

    L --> COMB["calculate_node_risk()\nCombina con última lectura\ndel sensor complementario"]
    S --> COMB

    COMB -- "GREEN 0–19" --> FRE_G["fire_risk_events\nrisk_level=GREEN"]
    COMB -- "YELLOW 20–44" --> FRE_Y["fire_risk_events\nrisk_level=YELLOW"]
    COMB -- "ORANGE 45–69" --> FRE_O["fire_risk_events\nrisk_level=ORANGE"] --> CHK{"should_create_alert()\n¿nivel cambió o fue leída?"}
    COMB -- "RED 70+" --> FRE_R["fire_risk_events\nrisk_level=RED"] --> CHK
    CHK -- "Sí (transición)" --> AW["alerts\nseverity=warning/critical\nis_read=0"]
    CHK -- "No (mismo nivel,\nno leída)" --> SKIP["Suprimida\n(sin INSERT)"]
    CHK -- "RED sin leer\n> 30 min" --> REM["alerts\n[Recordatorio]\nseverity=critical"]

    style RAW fill:#e3f2fd,stroke:#1565c0
    style L fill:#fff9c4,stroke:#f9a825
    style S fill:#e8f5e9,stroke:#388e3c
    style COMB fill:#ffe0b2,stroke:#e65100
    style AW fill:#fff3e0,stroke:#e65100
    style AC fill:#ffcdd2,stroke:#b71c1c
```

## Detalle de tablas

### `nodes` — Catálogo de nodos (tabla central)
| Campo | Tipo | Descripción |
|---|---|---|
| `name` | TEXT | Nombre del nodo, ej. "Nodo Norte" |
| `latitude` | REAL | Latitud GPS |
| `longitude` | REAL | Longitud GPS |
| `light_eui` | TEXT | EUI del EM500-LGT915M asignado |
| `soil_eui` | TEXT | EUI del EM500-SMTC asignado |
| `description` | TEXT | Notas del sitio |
| `active` | INTEGER | 1 = activo, 0 = desactivado |

### `lorawan_transmissions` — Raw de todos los uplinks
| Campo | Tipo | Descripción |
|---|---|---|
| `node_id` | INTEGER FK | Nodo al que pertenece (null si no registrado) |
| `device_eui` | TEXT | EUI del sensor |
| `payload_hex` | TEXT | Payload crudo en hex |
| `rssi` | INTEGER | Potencia de señal (dBm) |
| `snr` | REAL | Relación señal/ruido (dB) |

### `light_readings` — EM500-LGT915M
| Campo | Tipo | Descripción |
|---|---|---|
| `node_id` | INTEGER FK | Nodo al que pertenece |
| `light_lux` | INTEGER | Intensidad de luz |
| `is_night` | INTEGER | 1 si era de noche en hora México (UTC-6) |
| `battery_percent` | INTEGER | Batería del sensor |

**Umbrales:** noche >50 lux +20pts / >100 lux +35pts · día >50,000 lux +15pts

### `soil_readings` — EM500-SMTC
| Campo | Tipo | Descripción |
|---|---|---|
| `node_id` | INTEGER FK | Nodo al que pertenece |
| `soil_temperature_celsius` | REAL | Normal 15–28°C · score >35°C (+10) / >45°C (+25) / >60°C (+40) |
| `soil_moisture_percent` | REAL | Normal 8–16 % · alerta <8% (+15) · crítico <7% (+30) |
| `electrical_conductivity_us_cm` | INTEGER | Normal ≥200 µS/cm · seco <200 (+10) · muy seco <100 (+20) |
| `delta_temp_per_min` | REAL | ΔT respecto a lectura anterior · >0.5°C/min (+20) · >2°C/min (+45) |
| `battery_percent` | INTEGER | Batería del sensor |

### `fire_risk_events` — Riesgo calculado a nivel nodo
| Campo | Tipo | Descripción |
|---|---|---|
| `node_id` | INTEGER FK | Nodo evaluado |
| `risk_level` | TEXT | GREEN / YELLOW / ORANGE / RED |
| `risk_score` | INTEGER | Score acumulado 0–100+ |
| `contributing_factors` | TEXT | Factores que sumaron puntos |
| `delta_temp_per_min` | REAL | ΔT de esa lectura |
| `sensor_type` | TEXT | Sensor que disparó el cálculo |

### `alerts` — Alertas accionables (ORANGE y RED)
| Campo | Tipo | Descripción |
|---|---|---|
| `node_id` | INTEGER FK | Nodo en alerta (incluye lat/lng al consultar) |
| `alert_type` | TEXT | `fire_risk_orange` / `fire_risk_red` |
| `severity` | TEXT | `warning` / `critical` |
| `message` | TEXT | Descripción legible con emoji y factores. Prefijo `[Recordatorio]` en alertas RED periódicas |
| `value` | REAL | Score que disparó la alerta |
| `is_read` | INTEGER | `0` = no leída, `1` = leída. El GET filtra solo `is_read=0` por defecto |
| `read_at` | TIMESTAMP | Momento en que fue marcada como leída (UTC) |

**Lógica de deduplicación (`should_create_alert`):**
- Sin alertas previas → crear
- El nivel cambió respecto a la última alerta → crear
- Mismo nivel, última alerta creada hace < 1 min → suprimir (guard anti-duplicados soil+light)
- Mismo nivel, alerta leída → crear nueva después de 15 min desde `read_at`
- Mismo nivel, no leída, RED → recordatorio cada 30 min
- Mismo nivel, no leída, ORANGE → suprimir
