# Arquitectura — Detección de Incendios Forestales IoT

## Diagrama general

```mermaid
flowchart TB
    subgraph CAMPO["🌲 Campo (Bosque Ejidal)"]
        subgraph N1["Nodo 1"]
            S1A["💡 EM500-LGT915M"]
            S1B["🌱 EM500-SMTC"]
        end
        subgraph N2["Nodo 2"]
            S2A["💡 EM500-LGT915M"]
            S2B["🌱 EM500-SMTC"]
        end
        subgraph NN["Nodo N..."]
            SNA["💡 EM500-LGT915M"]
            SNB["🌱 EM500-SMTC"]
        end
    end

    subgraph LORAWAN["📶 Red LoRaWAN 915 MHz"]
        GW["📦 Gateway Milesight UG65"]
    end

    subgraph BACKEND["🖥️ Backend (FastAPI v5.0)"]
        direction TB

        subgraph PARSE["Parsers (objeto ya decodificado)"]
            ID["identify_sensor_from_object()\ndetecta soil / light por claves"]
            P1["parse_light_object()\nillumination → lux"]
            P2["parse_soil_object()\ntemperature / moisture / electricity\n(ignora _error flags)"]
        end

        subgraph ENGINE["Motor de Riesgo por Nodo"]
            LN["SELECT nodo activo\npor tipo de sensor → node_id + eui"]
            DT["get_delta_temp_per_min()"]
            NI["is_night() UTC-6"]
            CR["calculate_node_risk()\nCombina ambos sensores\n🟢 🟡 🟠 🔴"]
        end

        DB[("🗄️ SQLite\ndatabase/\n6 tablas")]
    end

    subgraph CLIENTES["👥 Frontend / Clientes"]
        MAP["🗺️ Dashboard\nlocalhost:8000/"]
        DOCS["📖 Swagger /docs"]
        CURL["💻 curl / HTTP"]
    end

    N1 & N2 & NN -- "LoRa 915 MHz" --> GW
    GW -- "POST /api/v1/lorawan/uplink\nX-API-Key\n(solo objeto decodificado)" --> PARSE
    PARSE --> ENGINE
    ENGINE --> DB
    DB --> CLIENTES

    style CAMPO fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    style LORAWAN fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    style BACKEND fill:#fff8e1,stroke:#f57f17,color:#e65100
    style CLIENTES fill:#fce4ec,stroke:#c62828,color:#b71c1c
    style ENGINE fill:#ffe0b2,stroke:#e65100
    style DECODE fill:#f3e5f5,stroke:#6a1b9a
```

## Motor de riesgo — puntuación por nodo

Cada uplink combina la lectura actual con la última del sensor complementario del mismo nodo.

```mermaid
flowchart LR
    subgraph SENSOR["Lectura entrante"]
        SL["💡 Luz\no\n🌱 Suelo"]
    end

    subgraph COMPLEMENTO["Última lectura complementaria\n(consultada en BD)"]
        CMP["Sensor del mismo nodo\nque no transmitió"]
    end

    subgraph SCORE["Score acumulado"]
        T["🌡️ Temp suelo\n>35°C +10\n>45°C +25\n>60°C +40"]
        H["💧 Humedad\n<30% +15\n<20% +30"]
        EC["⚡ EC\n<200 +10\n<100 +20"]
        DT["📈 ΔT/min\n>0.5 +20\n>2.0 +45"]
        L["💡 Luz noche\n>50lux +20\n>100lux +35"]
    end

    subgraph NIVEL["Nivel del nodo"]
        G["🟢 0–19\nNormal"]
        Y["🟡 20–44\nRiesgo bajo"]
        O["🟠 45–69\nRiesgo alto"]
        R["🔴 70+\nIncendio posible"]
    end

    SL & CMP --> T & H & EC & DT & L --> NIVEL
```

## Flujo de datos

```mermaid
sequenceDiagram
    participant S as Sensor IoT
    participant GW as Gateway UG65
    participant API as FastAPI
    participant DB as SQLite

    Note over S,GW: Cada 2–10 min (configurable)
    S->>GW: Transmisión LoRa 915 MHz
    GW->>API: POST /api/v1/lorawan/uplink
    Note over GW,API: Solo payload decodificado: {temperature, moisture...} o {illumination}

    API->>API: identify_sensor_from_object() → soil_sensor / light_sensor
    API->>DB: SELECT nodo activo por tipo de sensor → node_id + device_eui
    API->>API: parse_soil_object() o parse_light_object()
    API->>DB: INSERT lorawan_transmissions + lectura del sensor

    alt Sensor de suelo
        API->>DB: SELECT última lectura → ΔT/min
    else Sensor de luz
        API->>API: is_night(timestamp)
    end

    API->>DB: SELECT lectura complementaria del nodo
    API->>API: calculate_node_risk() — combina ambos sensores
    API->>DB: INSERT fire_risk_events (node_id)

    alt score ≥ 45
        API->>DB: INSERT alerts (node_id + coordenadas)
    end

    API-->>GW: 200 OK
```

## Endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/v1/health` | Estado del servidor |
| `POST` | `/api/v1/nodes` | Registrar un nodo |
| `GET` | `/api/v1/nodes` | Todos los nodos con riesgo actual → **mapa** |
| `GET` | `/api/v1/nodes/{id}` | Detalle + historial de un nodo |
| `DELETE` | `/api/v1/nodes/{id}` | Desactivar nodo |
| `POST` | `/api/v1/lorawan/uplink` | Recibe datos del gateway |
| `GET` | `/api/v1/fire-risk/current` | Último riesgo por nodo |
| `GET` | `/api/v1/fire-risk/history` | Historial de eventos |
| `GET` | `/api/v1/readings/light` | Lecturas de luz |
| `GET` | `/api/v1/readings/soil` | Lecturas de suelo |
| `GET` | `/api/v1/alerts` | Alertas ORANGE y RED (con coordenadas) |
| `GET` | `/api/v1/stats` | Estadísticas generales |

## Respuesta del endpoint de mapa `/api/v1/nodes`

```json
{
  "count": 2,
  "nodes": [
    {
      "id": 1,
      "name": "Nodo Norte",
      "latitude": 19.4326,
      "longitude": -99.1332,
      "light_eui": "24E124000001",
      "soil_eui": "24E124000002",
      "description": "Sector norte del ejido",
      "risk_level": "ORANGE",
      "risk_score": 55,
      "risk_label": "Riesgo alto — alerta al HUB",
      "risk_emoji": "🟠",
      "contributing_factors": ["temp_suelo_alta_>45C", "humedad_baja_<30pct"],
      "last_soil_reading": { "soil_temperature_celsius": 48, "soil_moisture_percent": 22 },
      "last_light_reading": { "light_lux": 12, "is_night": 1 },
      "last_seen": "2026-05-06T03:10:00"
    }
  ]
}
```

## Stack tecnológico

| Componente | Detalle |
|---|---|
| EM500-LGT915M | Luz — spike de lux detecta llamas |
| EM500-SMTC | Suelo — temperatura + humedad + EC |
| Gateway UG65 | Concentrador LoRaWAN 915 MHz |
| FastAPI | API REST + motor de riesgo + sirve el frontend |
| SQLite | BD local en `database/`, sin dependencias externas |
| React + Babel standalone | Dashboard — sin build step, recarga en el navegador |
| MapLibre GL JS | Mapa interactivo con marcadores por nivel de riesgo |
| venv | Entorno Python aislado en `backend/venv/` |

## Frontend — páginas y componentes

### `index.html` — Dashboard principal

| Componente | Archivo | Descripción |
|---|---|---|
| Mapa interactivo | `map-view.jsx` | Marcadores por nivel de riesgo (GREEN/YELLOW/ORANGE/RED), popups con métricas actuales |
| Panel lateral | `side-panel.jsx` | Lista de nodos ordenada por riesgo + alertas globales con dismiss |
| Panel inferior | `detail-panel.jsx` | Se abre al seleccionar un nodo: 4 métricas grandes + gráfica de temperatura 24h |
| Tweaks | `tweaks-panel.jsx` | Selector de tema claro/oscuro y ajustes de visualización |

### `nodo.html` — Detalle de nodo

Página completa accesible desde `/nodo.html?id=NODE-001`. Componentes principales:

| Componente | Descripción |
|---|---|
| Hero + estado | Nombre, área, coordenadas, nivel de riesgo, baterías, último visto |
| 4 métricas grandes | Temp. suelo, Humedad, Iluminación, Electroconductividad (valor actual + contexto) |
| Series temporales 24h | 4 charts independientes en grid 2×2, cada una con eje Y en unidades reales (`°C`, `%`, `lux`, `dS/m`) |
| Tendencias por variable | 4 sparklines con rango min→max de las últimas 24h |
| Alertas del nodo | Lista paginada (3 por página) con dismiss individual y "marcar todas como leídas" |
| Especificaciones | EUIs de sensores y coordenadas GPS |

### Datos compartidos — `data.jsx`

Módulo global (`window.fireZenseAPI`) que expone:
- `getNodes()` — GET `/api/v1/nodes`, transforma al modelo de UI
- `getAlerts()` — GET `/api/v1/alerts`, normaliza campos
- `RISK_META` — mapa de nivel → color, label, bg para badges y gráficas
