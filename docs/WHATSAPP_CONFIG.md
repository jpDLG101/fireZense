# Configuración de WhatsApp API en Meta

## 📋 Requisitos

- Cuenta de Meta (Facebook)
- Teléfono para verificación (WhatsApp Business)
- Acceso a Meta Developers

## 🚀 Pasos de Configuración

### 1. Crear Aplicación en Meta

1. Ve a [Meta Developers](https://developers.facebook.com)
2. Click en "Mis aplicaciones"
3. Click en "Crear aplicación"
4. Selecciona tipo: **Business**
5. Rellena los datos:
   - Nombre de la aplicación: `fireZense`
   - Email de contacto: tu@email.com
   - Propósito: Alertas de incendios forestales
6. Click en "Crear"

### 2. Agregar Producto WhatsApp

1. En el dashboard de tu app
2. Click en "+ Agregar producto"
3. Busca "WhatsApp"
4. Click en "Configurar"
5. Selecciona "WhatsApp Business"

### 3. Obtener Phone Number ID y Token

1. En WhatsApp → Configuración
2. Ve a "Números de teléfono"
3. Copia el **Phone Number ID** (es un número largo)
4. Guárdalo → va en `WHATSAPP_PHONE_ID`

### 4. Generar Bearer Token

1. Ve a WhatsApp → Configuración
2. Click en "Nivel de acceso a API"
3. En "Tokens temporales":
   - Click en "Generar token"
   - Selecciona los permisos:
     - ✓ whatsapp_business_messaging
     - ✓ whatsapp_business_management
   - Copia el token → va en `WHATSAPP_TOKEN`

⚠️ **IMPORTANTE:** El token es de 1 hora. Para producción, genera un **token permanente** desde Configuración → Tokens de acceso.

### 5. Verificar tu Número de Teléfono

1. Ve a WhatsApp → Configuración
2. Click en "Verificar número"
3. Selecciona tu número de WhatsApp Business
4. Recibirás un código por WhatsApp
5. Verifica en Meta

### 6. Configurar Número Destinatario

1. El número destinatario es el que recibe las alertas
2. Formato: sin + y con código de país
   - México: `526361302743`
   - USA: `14155552671`
   - España: `34912345678`

### 7. (Opcional) Crear Plantilla de Mensaje

1. Ve a WhatsApp → Plantillas de mensaje
2. Click en "Crear plantilla"
3. Nombre: `firezense_alert`
4. Idioma: English (US) u otro
5. Tipo: Texto simple
6. Contenido:
   ```
   🔴 ALERTA DE INCENDIO
   
   Nodo: {{1}}
   Temperatura: {{2}}°C
   Humedad: {{3}}%
   ```
7. Click en "Enviar para revisión"

**Nota:** Por ahora usamos mensajes de texto directo. Las plantillas son para cuando quieras usar un formato pre-aprobado.

## 📝 Actualizar .env

Una vez tengas todo, edita `.env` en la raíz de fireZense:

```env
WHATSAPP_ENABLED=true
WHATSAPP_TOKEN=tu_token_aqui
WHATSAPP_PHONE_ID=tu_phone_id_aqui
WHATSAPP_TO_PHONE=numero_destinatario
WHATSAPP_API_VERSION=v25.0
```

## ✅ Verificar Configuración

1. Instala las dependencias:
   ```bash
   pip install -r backend/requirements.txt
   ```

2. Inicia el servidor:
   ```bash
   ./START.sh
   ```

3. Simula un incendio:
   ```bash
   curl -X POST http://localhost:8000/api/v1/simulate/uplink \
     -H "Content-Type: application/json" \
     -d '{
       "devEUI": "24E124126E174049",
       "object": {
         "temperature": 65,
         "moisture": 5,
         "electricity": 50
       },
       "timestamp": "2026-05-08T15:30:00Z"
     }'
   ```

4. Deberías recibir un mensaje en WhatsApp en segundos

## 🔧 Solución de Problemas

### "Error 401: Unauthorized"
- El token ha expirado
- Genera uno nuevo en Meta
- Verifica que esté en `.env` sin espacios extra

### "Error 400: Invalid recipient"
- El número destinatario está mal
- Debe tener código de país sin +
- No debe tener espacios o caracteres especiales
- Ej correcto: `526361302743`

### "Error 404: Not found"
- El Phone Number ID es incorrecto
- Cópialo de nuevo de Meta → WhatsApp → Configuración

### "El mensaje no llega"
- Verifica que tu número de teléfono esté registrado en Meta
- Asegúrate que WHATSAPP_ENABLED=true
- Revisa los logs del servidor

## 📚 Referencias

- [Meta WhatsApp API Docs](https://developers.facebook.com/docs/whatsapp)
- [Send Messages API](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/send-messages)
- [Message Templates](https://developers.facebook.com/docs/whatsapp/message-templates)
