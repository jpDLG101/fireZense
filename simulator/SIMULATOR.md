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

Los rangos de cada perfil están calibrados para que el motor `calculate_fire_risk()` devuelva **siempre** el nivel correcto. Los valores límite respetan los umbrales exactos del motor (ver tabla al final de esta sección).

**Temperatura de suelo:** se suaviza entre ciclos. La tasa máxima de cambio es `0.4 °C/min`, y el step real por ciclo se escala con el intervalo (`step = 0.4 × interval_sec / 60`). Esto garantiza que `delta_temp_per_min` nunca supere 0.5 °C/min en modo continuo, sin importar el intervalo configurado.

Los demás campos (humedad, EC, lux) se generan aleatoriamente dentro de su rango en cada ciclo.

### GREEN — Normal · score esperado: 0
| Sensor | Campo | Rango | Score |
|---|---|---|---|
| Suelo | Temperatura | 15.0 – 30.0 °C | 0 (≤ 35) |
| Suelo | Humedad | 10.0 – 16.0 % | 0 (≥ 8 %) |
| Suelo | Conductividad eléctrica | 250 – 600 µS/cm | 0 (≥ 200) |
| Luz | Lux (día) | 1,000 – 12,000 lx | 0 (≤ 50,000) — bajo dosel denso |
| Luz | Lux (noche) | 0 – 5 lx | 0 (≤ 50) |

### YELLOW — Riesgo bajo · score esperado: 20
| Sensor | Campo | Rango | Score |
|---|---|---|---|
| Suelo | Temperatura | 35.1 – 44.9 °C | **+10** (> 35) |
| Suelo | Humedad | 8.0 – 10.0 % | 0 (≥ 8 %) |
| Suelo | Conductividad eléctrica | 100 – 199 µS/cm | **+10** (< 200) |
| Luz | Lux (día) | 12,000 – 25,000 lx | 0 (≤ 50,000) — dosel ralo / claro forestal |
| Luz | Lux (noche) | 10 – 49 lx | 0 (≤ 50) |

### ORANGE — Riesgo alto · score esperado: 60
| Sensor | Campo | Rango | Score |
|---|---|---|---|
| Suelo | Temperatura | 45.0 – 59.9 °C | **+25** (> 45) |
| Suelo | Humedad | 7.0 – 7.9 % | **+15** (< 8 %) |
| Suelo | Conductividad eléctrica | 50 – 99 µS/cm | **+20** (< 100) |
| Luz | Lux (día) | 20,000 – 45,000 lx | 0 (< 50,000) — zona abierta/alta exposición |
| Luz | Lux (noche) | 20 – 49 lx | 0 (≤ 50) |

> El lux diurno de ORANGE se mantiene bajo 50,000 lx intencionalmente (no suma pts), y el nocturno bajo 50 lx para no cruzar a RED.

### RED — Incendio posible · score esperado: 90–105
| Sensor | Campo | Rango | Score |
|---|---|---|---|
| Suelo | Temperatura | 60.0 – 80.0 °C | **+40** (> 60) |
| Suelo | Humedad | 1.0 – 6.5 % | **+30** (< 7 %) |
| Suelo | Conductividad eléctrica | 10 – 50 µS/cm | **+20** (< 100) |
| Luz | Lux (día) | 45,000 – 75,000 lx | **0/+15** (> 50,000) — sol directo intenso |
| Luz | Lux (noche) | 100 – 500 lx | **+20/+35** (> 50 / > 100) |

---

### Umbrales del motor de riesgo

| Variable | Condición | Puntos |
|---|---|---|
| Temperatura suelo | > 35 °C | +10 |
| Temperatura suelo | > 45 °C | +25 (reemplaza) |
| Temperatura suelo | > 60 °C | +40 (reemplaza) |
| Humedad suelo | < 8 % | +15 |
| Humedad suelo | < 7 % | +30 (reemplaza) |
| Conductividad eléctrica | < 200 µS/cm | +10 |
| Conductividad eléctrica | < 100 µS/cm | +20 (reemplaza) |
| ΔT/min | > 0.5 °C/min | +20 |
| ΔT/min | > 2.0 °C/min | +45 (reemplaza) |
| Luz nocturna | > 50 lx | +20 |
| Luz nocturna | > 100 lx | +35 (reemplaza) |
| Luz diurna | > 50,000 lx | +15 |

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
