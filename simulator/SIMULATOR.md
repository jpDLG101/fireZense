# Firezense Node Simulator

Herramienta CLI para simular lecturas de sensores IoT en cualquier nodo registrado.
Genera datos de suelo (EM500-SMTC) y luz (EM500-LGT) y los envía al backend via HTTP.

---

## Requisitos

```bash
pip install requests
```

El backend debe estar corriendo antes de ejecutar el simulador.

---

## Uso básico

```bash
python3 simulator.py [opciones]
```

| Opción | Descripción | Default |
|---|---|---|
| `--node ID` | ID del nodo a simular | Selección interactiva |
| `--level` | Nivel de riesgo: `green` `yellow` `orange` `red` | `green` |
| `--interval N` | Segundos entre lecturas (modo continuo) | `300` (5 min) |
| `--backfill N` | Insertar N días de histórico | — |
| `--url URL` | URL base del backend | `http://localhost:8000` |

---

## Ejemplos

### Selección interactiva de nodo

```bash
python3 simulator.py
```

Muestra una tabla con todos los nodos activos y su riesgo actual, luego pide seleccionar el ID.

```
  🔥 Firezense Node Simulator
  ───────────────────────────

  ID  │ Nombre                      │ Riesgo actual
  ────┼─────────────────────────────┼───────────────
  1   │ Nodo Bosque Norte           │ 🟢 GREEN
  2   │ NodoSim                     │ ⚪ SIN DATOS

  Selecciona el ID del nodo: 
```

---

### Modo continuo

Envía lecturas cada N segundos indefinidamente. `Ctrl+C` para detener.

```bash
# Nodo 2, nivel green, cada 5 minutos (default)
python3 simulator.py --node 2

# Nodo 2, nivel orange, cada 10 segundos
python3 simulator.py --node 2 --level orange --interval 10

# Nodo 1, nivel crítico, cada 30 segundos
python3 simulator.py --node 1 --level red --interval 30
```

Salida en pantalla:

```
  Nodo   : [2] NodoSim
  Nivel  : ORANGE
  Ciclo  : cada 10s  (Ctrl+C para detener)

  #    Hora      Temp   Hum    EC      Lux       Riesgo
  ──────────────────────────────────────────────────────────
  1    14:32:05   52.3°C  24.1%   78.4µS   45231lx  🟠 ORANGE (55)
  2    14:32:15   48.7°C  27.8%   91.2µS   52100lx  🟠 ORANGE (50)
  3    14:32:25   55.1°C  21.3°C  65.9µS   48760lx  🟠 ORANGE (60)
```

---

### Modo backfill

Inserta datos históricos a partir de hoy hacia atrás N días, con una lectura cada 5 minutos (288 ciclos/día × 2 sensores = 576 lecturas/día).

```bash
# 5 días de datos normales en nodo 2
python3 simulator.py --node 2 --backfill 5

# 3 días de datos críticos en nodo 1
python3 simulator.py --node 1 --backfill 3 --level red

# 7 días de riesgo bajo en nodo 2, contra servidor remoto
python3 simulator.py --node 2 --backfill 7 --level yellow --url http://192.168.1.10:8000
```

Salida en pantalla:

```
  Nodo     : [2] NodoSim
  Nivel    : RED
  Días     : 3  (864 ciclos × 2 sensores = 1728 lecturas)
  Desde    : 2026-05-04 09:15 MX
  Hasta    : 2026-05-07 09:15 MX

  [████████████████░░░░░░░░░░░░░░]  55.2%  478/864
```

---

## Niveles de riesgo y rangos de datos

Cada nivel genera valores aleatorios estrictamente dentro del rango indicado.
Los rangos están calibrados para que el motor de riesgo del backend devuelva siempre el nivel correcto.

### GREEN — Normal
| Sensor | Campo | Rango |
|---|---|---|
| Suelo | Temperatura | 15 – 30 °C |
| Suelo | Humedad | 40 – 80 % |
| Suelo | Conductividad eléctrica | 250 – 600 µS/cm |
| Luz | Lux (día) | 1,000 – 30,000 lx |
| Luz | Lux (noche) | 0 – 5 lx |

### YELLOW — Riesgo bajo
| Sensor | Campo | Rango |
|---|---|---|
| Suelo | Temperatura | 35 – 44.9 °C |
| Suelo | Humedad | 30 – 39.9 % |
| Suelo | Conductividad eléctrica | 100 – 200 µS/cm |
| Luz | Lux (día) | 30,000 – 50,000 lx |
| Luz | Lux (noche) | 10 – 50 lx |

### ORANGE — Riesgo alto
| Sensor | Campo | Rango |
|---|---|---|
| Suelo | Temperatura | 45 – 59.9 °C |
| Suelo | Humedad | 20 – 29.9 % |
| Suelo | Conductividad eléctrica | 50 – 100 µS/cm |
| Luz | Lux (día) | 40,000 – 60,000 lx |
| Luz | Lux (noche) | 50 – 100 lx |

### RED — Incendio posible
| Sensor | Campo | Rango |
|---|---|---|
| Suelo | Temperatura | 60 – 80 °C |
| Suelo | Humedad | 5 – 20 % |
| Suelo | Conductividad eléctrica | 10 – 50 µS/cm |
| Luz | Lux (día) | 50,000 – 100,000 lx |
| Luz | Lux (noche) | 100 – 500 lx |

> El simulador detecta automáticamente si el timestamp corresponde a horario nocturno (20:00–06:00 hora México, UTC-6) y ajusta el rango de lux en consecuencia.

---

## Crear un nodo de simulación

Si aún no tienes un nodo de prueba, créalo con este curl antes de ejecutar el simulador:

```bash
curl -X POST http://localhost:8000/api/v1/nodes \
  -H "X-API-Key: tu_api_key_local" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "NodoSim",
    "latitude": 28.6740034,
    "longitude": -106.0794209,
    "light_eui": "24E124FFAA000002",
    "soil_eui":  "24E124FFBB000002",
    "description": "NODO DE SIMULACION · CHIHUAHUA, MX"
  }'
```

---

## Endpoint del backend utilizado

El simulador usa un endpoint dedicado que acepta `node_id` explícito y `timestamp` opcional (necesario para backfill):

```
POST /api/v1/simulate/uplink
X-API-Key: tu_api_key_local

{
  "node_id": 2,
  "sensor_object": { "temperature": 52.3, "moisture": 24.1, "electricity": 78.4, "battery": 55 },
  "timestamp": "2026-05-07T20:32:05+00:00"   ← opcional, default: ahora
}
```

La documentación interactiva del backend está en `http://localhost:8000/docs`.
