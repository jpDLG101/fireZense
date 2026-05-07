# Configuración del Gateway Milesight UG65

## 1. Arrancar el backend

Desde la raíz del proyecto:

```bash
./START.sh       # Mac/Linux (primera vez: chmod +x START.sh primero)
START.bat        # Windows
```

## 2. Registrar los nodos

Antes de recibir datos, registra cada nodo con sus coordenadas y EUIs.
El EUI está impreso en la etiqueta física de cada sensor Milesight.

```bash
curl -X POST http://localhost:8000/api/v1/nodes \
  -H "Content-Type: application/json" \
  -H "x-api-key: tu_api_key_local" \
  -d '{
    "name": "Nodo Norte",
    "latitude": 19.4326,
    "longitude": -99.1332,
    "light_eui": "24E124000001",
    "soil_eui":  "24E124000002",
    "description": "Sector norte del ejido"
  }'
```

Repetir por cada nodo del sistema.

## 3. Obtener IP de tu laptop

```bash
# Mac/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# Windows
ipconfig | findstr IPv4
```

## 4. Configurar el gateway

En la interfaz web del gateway (`https://192.168.1.1`):

### 4a. HTTP Push (Application → Integrations)

1. Ir a **Applications → [tu app] → HTTP Push** (o Packet Forwarder → HTTP Push)
2. Llenar:
   - **URL:** `http://TU_IP:8000/api/v1/lorawan/uplink`
   - **Header:** `X-API-Key: tu_api_key_local`
   - **Method:** POST
3. Clic en **Test Connection** → debe decir Success
4. **Save & Apply**

### 4b. Payload Codec (obligatorio)

El gateway debe decodificar el payload antes de enviarlo. El backend recibe el objeto decodificado directamente como body del POST (sin wrapper, sin campo `object`).

En **Applications → [tu app] → Devices → [sensor] → Codec:**
- Selecciona el codec del fabricante (Milesight EM500-SMTC / EM500-LGT)

Sin codec activo, el gateway manda el payload en hex y el backend no puede interpretarlo.

## 5. Ajustar intervalo de transmisión (recomendado)

Con la app **Milesight ToolBox** (Bluetooth) se configura cada sensor:

| Intervalo | ΔT útil | Batería estimada |
|---|---|---|
| 10 min (default) | Limitado | ~3–5 años |
| 5 min | Moderado | ~1.5–2 años |
| 2 min | Bueno | ~6–12 meses |

Para el hackathon se recomienda **2–5 minutos**.

## 6. Verificar

```bash
# Estado del servidor
curl http://localhost:8000/api/v1/health

# Ver nodos registrados con su riesgo actual
curl http://localhost:8000/api/v1/nodes

# Alertas activas
curl http://localhost:8000/api/v1/alerts
```

## Enviar dato de prueba sin gateway

El gateway UG65 manda **solo el objeto decodificado** (sin devEUI ni metadata).
El backend identifica el sensor por las claves del payload.

**Sensor de suelo (EM500-SMTC):**
```bash
curl -X POST http://localhost:8000/api/v1/lorawan/uplink \
  -H "Content-Type: application/json" \
  -H "x-api-key: tu_api_key_local" \
  -d '{"temperature": 48.5, "moisture": 22.0, "electricity": 150}'
```

**Sensor de luz (EM500-LGT915M):**
```bash
curl -X POST http://localhost:8000/api/v1/lorawan/uplink \
  -H "Content-Type: application/json" \
  -H "x-api-key: tu_api_key_local" \
  -d '{"illumination": 120}'
```

> Los valores del ejemplo combinan para ORANGE (~score 60). Usa valores normales para ver GREEN.

### Claves reales del codec Milesight

| Sensor | Clave | Descripción |
|---|---|---|
| EM500-SMTC | `temperature` | Temperatura °C |
| EM500-SMTC | `moisture` | Humedad % (ausente si `moisture_error: 1`) |
| EM500-SMTC | `electricity` | EC µS/cm (ausente si `electricity_error: 1`) |
| EM500-LGT | `illumination` | Lux |

## Conectividad: internet mientras usas el gateway

El WiFi del gateway no tiene internet. Para tener ambos simultáneamente:

1. Conecta el iPhone por USB a la laptop
2. En iPhone: **Configuración → Personal Hotspot → activar**
3. En Mac: **Configuración del Sistema → Red → Set Service Order** — arrastra **iPhone USB** arriba de **Wi-Fi**
4. Conecta el WiFi al gateway normalmente

El Mac usará el iPhone para internet y el WiFi para comunicarse con el gateway.

## Nota: cambio de esquema de BD

Si tenías una base de datos anterior, bórrala antes de reiniciar:

```bash
rm database/monitoreo_forestal.db
./START.sh
```
