# Guía: Cómo Obtener tu API Key de Google AI Studio

Esta guía te mostrará paso a paso cómo obtener una clave API de Google AI Studio para usar con los modelos Gemini.

## Requisitos Previos

- Una cuenta de Google (Gmail)
- Acceso a internet

## Pasos para Obtener la API Key

### 1. Accede a Google AI Studio

Ve a la página oficial de Google AI Studio:
```
https://aistudio.google.com/
```

### 2. Inicia Sesión

- Haz clic en el botón **"Get API key"** o **"Sign in"** en la esquina superior derecha
- Inicia sesión con tu cuenta de Google

### 3. Acepta los Términos de Servicio

- La primera vez que accedas, se te pedirá que aceptes los términos de servicio
- Lee y acepta los términos para continuar

### 4. Crea tu API Key

Hay dos formas de crear una API key:

#### Opción A: Desde la página principal
1. En la página principal de Google AI Studio, busca el botón **"Get API key"** en la barra superior
2. Haz clic en **"Create API key"**

#### Opción B: Desde el menú lateral
1. En el menú lateral izquierdo, busca la opción **"Get API key"**
2. Haz clic en **"Create API key in new project"** o selecciona un proyecto existente de Google Cloud

### 5. Selecciona o Crea un Proyecto

- **Opción recomendada**: Selecciona **"Create API key in new project"** para crear un proyecto dedicado
- Si ya tienes un proyecto de Google Cloud, puedes seleccionarlo de la lista

### 6. Copia tu API Key

- Una vez creada, Google mostrará tu API key
- **IMPORTANTE**: Copia esta clave inmediatamente y guárdala en un lugar seguro
- Haz clic en el icono de **copiar** para copiar la clave al portapapeles

### 7. Configura la API Key en tu Proyecto

1. En la raíz de tu proyecto, crea un archivo llamado `.env`:
   ```bash
   touch .env
   ```

2. Abre el archivo `.env` y añade tu API key:
   ```env
   GOOGLE_API_KEY="tu-api-key-aqui"
   ```

3. Reemplaza `tu-api-key-aqui` con la clave que copiaste

**Ejemplo**:
```env
GOOGLE_API_KEY="AIzaSyD1234567890abcdefghijklmnopqrstuvw"
```

## Seguridad de la API Key

### ⚠️ Importante: Protege tu API Key

- **NUNCA** compartas tu API key públicamente
- **NUNCA** subas el archivo `.env` a repositorios públicos (GitHub, GitLab, etc.)
- El archivo `.gitignore` ya está configurado para excluir `.env`

### Mejores Prácticas

1. **Usa variables de entorno**: Mantén la clave en el archivo `.env`
2. **Rotación de claves**: Cambia tu API key periódicamente
3. **Restricciones de API**: En Google Cloud Console, puedes restringir el uso de tu API key:
   - Por dirección IP
   - Por aplicación
   - Por servicios específicos

### Dónde Restringir tu API Key (Recomendado)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto
3. En el menú lateral, ve a **"APIs & Services"** → **"Credentials"**
4. Encuentra tu API key y haz clic en el icono de editar
5. En **"API restrictions"**, selecciona **"Restrict key"**
6. Marca solo: **"Generative Language API"**
7. Guarda los cambios

## Límites y Costos

### Cuota Gratuita

Google ofrece una cuota gratuita generosa:
- **Gemini 1.5 Flash**: 15 solicitudes por minuto (RPM), 1 millón de tokens por día
- **Gemini 1.5 Pro**: 2 RPM, 50 tokens por día (límites pueden variar)

### Monitoreo de Uso

Puedes monitorear tu uso en:
```
https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/
```

### Actualizar a Pago (Opcional)

Si necesitas más cuota:
1. Ve a Google Cloud Console
2. Configura una cuenta de facturación
3. Los límites aumentarán automáticamente

## Verificación de la API Key

Para verificar que tu API key funciona correctamente, puedes usar el siguiente comando curl:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models?key=TU_API_KEY"
```

Si funciona, deberías ver una lista de modelos disponibles.

## Solución de Problemas

### Error: "API key not valid"
- Verifica que copiaste la clave completa
- Asegúrate de que no hay espacios al principio o al final
- Verifica que la clave no haya sido revocada

### Error: "Quota exceeded"
- Has alcanzado el límite de solicitudes gratuitas
- Espera a que se reinicie la cuota (diariamente o por minuto)
- Considera actualizar a un plan de pago

### Error: "Permission denied"
- Asegúrate de que la API de Generative Language está habilitada en tu proyecto
- Ve a Google Cloud Console → APIs & Services → Enable APIs and Services
- Busca "Generative Language API" y habilítala

## Referencias

- [Google AI Studio](https://aistudio.google.com/)
- [Documentación de Gemini API](https://ai.google.dev/docs)
- [Google Cloud Console](https://console.cloud.google.com/)

---

Una vez que tengas tu API key configurada, ¡estás listo para continuar con la instalación del chatbot!
