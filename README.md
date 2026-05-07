# fireZense — Detección de Incendios Forestales IoT

Sistema de detección temprana de incendios para bosques ejidales mexicanos.
Usa sensores LoRaWAN Milesight (luz + suelo) conectados a un gateway UG65 para calcular niveles de riesgo GREEN / YELLOW / ORANGE / RED en tiempo real.

---

## Prerrequisitos

- **Python 3.10+** instalado y disponible como `python3`
- No se necesita Node.js, Docker ni nada más — el frontend corre directamente en el navegador

---

## 1. Instalación

```bash
# Clona el repositorio
git clone <url-del-repo>
cd fireZense

# Mac / Linux — primera vez
chmod +x START.sh
./START.sh

# Windows — primera vez
START.bat
```

El script crea el entorno virtual, instala dependencias y arranca el servidor.
Las siguientes veces basta con `./START.sh`.

Cuando veas esto, el servidor está listo:

```
→ Iniciando servidor...
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 2. Configuración

El archivo `backend/.env` contiene las variables de entorno:

```env
API_KEY=tu_api_key_local
DATABASE=../database/monitoreo_forestal.db
ENVIRONMENT=local
```

**`API_KEY`** — clave que protege los endpoints de escritura (uplink del gateway y registro de nodos).
Puedes dejarla como está para desarrollo local. Si la cambias, actualiza también el header `X-API-Key` en la configuración del gateway.

---

## 3. Registrar nodos

**Este paso es obligatorio antes de conectar el gateway o correr el simulador.**
Cada nodo agrupa un sensor de suelo (EM500-SMTC) y un sensor de luz (EM500-LGT915M).

```bash
curl -X POST http://localhost:8000/api/v1/nodes \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu_api_key_local" \
  -d '{
    "name": "Nodo Norte",
    "latitude": 19.4326,
    "longitude": -99.1332,
    "light_eui": "24E124000001",
    "soil_eui":  "24E124000002",
    "description": "Sector norte del ejido"
  }'
```

- **`light_eui`** y **`soil_eui`** están impresos en la etiqueta física de cada sensor.
- Repite el comando por cada nodo del sistema.
- Verifica los nodos registrados: `curl http://localhost:8000/api/v1/nodes`

---

## 4. Conectar el gateway

Ver `docs/GATEWAY_LOCAL_SETUP.md` para configurar el UG65 (HTTP Push, codec, IP).

Resumen:

1. Obtén la IP de tu laptop: `ifconfig | grep "inet " | grep -v 127.0.0.1`
2. En la interfaz web del gateway (`https://192.168.1.1`):
   - **HTTP Push URL:** `http://<TU_IP>:8000/api/v1/lorawan/uplink`
   - **Header:** `X-API-Key: tu_api_key_local`
   - Activa el codec del fabricante en cada sensor (sin codec el payload llega en hex)

---

## 5. Simular datos sin hardware

Si no tienes sensores físicos, el simulador genera lecturas para cualquier nivel de riesgo.
Usa el mismo entorno virtual que el backend (ya tiene `requests` instalado):

```bash
# Activa el venv antes de correr el simulador
source backend/venv/bin/activate   # Mac / Linux
backend\venv\Scripts\activate      # Windows

# Modo interactivo — selecciona nodo y nivel
python3 simulator/simulator.py

# Modo continuo — nodo 1, nivel ORANGE, cada 10 segundos
python3 simulator/simulator.py --node 1 --level orange --interval 10

# Backfill — inserta 7 días de histórico en nodo 2
python3 simulator/simulator.py --node 2 --backfill 7 --level green
```

Ver `simulator/SIMULATOR.md` para la referencia completa.

---

## URLs

| URL | Descripción |
|---|---|
| http://localhost:8000/ | Dashboard de monitoreo (mapa + panel de alertas) |
| http://localhost:8000/nodo.html?id=1 | Detalle de un nodo (gráficas 24h, alertas paginadas) |
| http://localhost:8000/docs | Documentación interactiva de la API (Swagger) |

---

## Endpoints API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/v1/health` | Estado del servidor |
| `POST` | `/api/v1/nodes` | Registrar un nodo |
| `GET` | `/api/v1/nodes` | Todos los nodos con riesgo actual |
| `GET` | `/api/v1/nodes/{id}` | Detalle + historial de un nodo |
| `DELETE` | `/api/v1/nodes/{id}` | Desactivar nodo |
| `POST` | `/api/v1/lorawan/uplink` | Recibe datos del gateway (requiere `X-API-Key`) |
| `GET` | `/api/v1/fire-risk/current` | Último riesgo por nodo |
| `GET` | `/api/v1/fire-risk/history` | Historial de eventos de riesgo |
| `GET` | `/api/v1/readings/light` | Lecturas de iluminación |
| `GET` | `/api/v1/readings/soil` | Lecturas de suelo |
| `GET` | `/api/v1/alerts` | Alertas activas (ORANGE y RED) |
| `GET` | `/api/v1/stats` | Estadísticas generales |

---

## Estructura del proyecto

```
fireZense/
├── START.sh / START.bat       ← punto de entrada
├── simulator/
│   ├── simulator.py           ← simulador de lecturas IoT
│   └── SIMULATOR.md           ← documentación del simulador
├── backend/
│   ├── main.py                ← API FastAPI + motor de riesgo
│   ├── requirements.txt
│   ├── .env                   ← API_KEY y config local
│   └── venv/                  ← se genera automáticamente
├── database/
│   └── monitoreo_forestal.db  ← se genera automáticamente al arrancar
├── docs/
│   ├── GATEWAY_LOCAL_SETUP.md ← configuración del UG65
│   ├── ARCHITECTURE.md        ← diagrama de arquitectura y motor de riesgo
│   └── DATABASE_DIAGRAM.md    ← esquema de base de datos
└── frontend/                  ← servido por FastAPI, sin build step
    ├── index.html             ← dashboard principal (mapa + paneles)
    ├── nodo.html              ← detalle de nodo (charts 24h, alertas paginadas)
    ├── data.jsx               ← adaptador de API compartido
    ├── map-view.jsx           ← mapa interactivo MapLibre
    ├── side-panel.jsx         ← panel lateral de nodos y alertas
    ├── detail-panel.jsx       ← panel inferior del dashboard
    ├── tweaks-panel.jsx       ← configuración de tema y ajustes
    ├── styles.css             ← estilos del dashboard
    ├── node-detail.css        ← estilos de la página de detalle
    └── vendor/                ← React, MapLibre, Babel, fuentes (offline)
```

---

## Resetear la base de datos

Si necesitas empezar desde cero:

```bash
rm database/monitoreo_forestal.db
./START.sh
```

La base de datos se recrea automáticamente al arrancar.
