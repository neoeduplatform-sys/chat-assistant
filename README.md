# 🤖 Chatbot Educativo con Google Gemini

Un chatbot educativo completo basado en RAG (Retrieval-Augmented Generation) que utiliza la API de Google Gemini y ChromaDB para proporcionar respuestas precisas basadas en materiales de curso.

## 📋 Tabla de Contenidos

- [Características](#características)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalación Rápida](#instalación-rápida)
- [Configuración](#configuración)
- [Uso](#uso)
- [Despliegue en Producción](#despliegue-en-producción)
- [Personalización](#personalización)
- [Solución de Problemas](#solución-de-problemas)
- [API Documentation](#api-documentation)

## ✨ Características

- 🤖 **IA Avanzada**: Powered by Google Gemini (1.5 Pro / 2.5 Flash)
- 📚 **RAG Architecture**: Respuestas fundamentadas en tus documentos
- 🔍 **Búsqueda Semántica**: Encuentra información relevante automáticamente
- 💾 **ChromaDB**: Base de datos vectorial de código abierto
- ⚡ **FastAPI Backend**: API REST rápida y robusta
- 🎨 **Widget Personalizable**: Frontend ligero sin dependencias
- 🐳 **Docker Ready**: Despliegue simplificado con Docker Compose
- 🔒 **Seguro**: Variables de entorno para claves API

## 🏗️ Arquitectura

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Usuario   │─────>│ FastAPI      │─────>│ LlamaIndex  │
│   (HTML)    │<─────│ Backend      │<─────│ RAG Engine  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                      │
                            │                      ▼
                            │              ┌─────────────┐
                            │              │  ChromaDB   │
                            │              │  (Vectors)  │
                            │              └─────────────┘
                            ▼
                     ┌──────────────┐
                     │ Google Gemini│
                     │     API      │
                     └──────────────┘
```

### Flujo de Datos

1. **Usuario** hace una pregunta a través del widget HTML
2. **FastAPI** recibe la pregunta y la pasa a LlamaIndex
3. **LlamaIndex** convierte la pregunta en un vector (embedding)
4. **ChromaDB** busca los fragmentos más relevantes
5. **Google Gemini** genera una respuesta basada en el contexto
6. **Usuario** recibe la respuesta con fuentes citadas

## 📦 Requisitos

- Docker y Docker Compose
- API Key de Google AI Studio (gratuita)
- 4GB RAM mínimo
- Python 3.11+ (si ejecutas sin Docker)

## 🚀 Instalación Rápida

### 1. Clonar o Descargar el Proyecto

```bash
# Si usas git
git clone <tu-repositorio>
cd chatbot

# O simplemente descomprime el archivo ZIP
```

### 2. Obtener API Key de Google

Sigue la guía detallada en [`SETUP_API_KEY.md`](SETUP_API_KEY.md) para obtener tu clave API gratuita.

**Resumen rápido:**
1. Ve a [Google AI Studio](https://aistudio.google.com/)
2. Inicia sesión con tu cuenta de Google
3. Haz clic en "Get API key"
4. Copia tu API key

### 3. Configurar Variables de Entorno

```bash
# Copia el archivo de ejemplo
cp .env.example .env

# Edita el archivo .env y agrega tu API key
nano .env  # o usa tu editor favorito
```

Modifica esta línea en `.env`:
```env
GOOGLE_API_KEY="tu-api-key-aqui"
```

### 4. Agregar Documentos del Curso

Coloca tus documentos (PDF, TXT, MD, DOCX) en la carpeta `data/`:

```bash
cp /ruta/a/tus/documentos/*.pdf data/
```

### 5. Iniciar los Servicios

```bash
# Levantar ChromaDB
docker-compose up -d chromadb

# Esperar unos segundos para que ChromaDB esté listo
sleep 10

# Ejecutar el script de ingesta
docker-compose run --rm fastapi_app python ingest.py

# Iniciar la API
docker-compose up -d
```

### 6. ¡Listo! 🎉

- API: http://localhost:8080
- Docs: http://localhost:8080/docs
- Demo: Abre `frontend/index.html` en tu navegador

## ⚙️ Configuración

### Variables de Entorno

Todas las configuraciones se gestionan a través del archivo `.env`. Aquí están las principales opciones:

#### Configuración del Modelo

```env
# Modelo LLM de Gemini
# Opciones: models/gemini-1.5-pro-latest, models/gemini-2.5-flash
GEMINI_MODEL="models/gemini-1.5-pro-latest"

# Modelo de embeddings
EMBEDDING_MODEL="models/text-embedding-004"
```

#### Configuración RAG

```env
# Tamaño de los fragmentos de texto (512-1024 recomendado)
CHUNK_SIZE=512

# Superposición entre fragmentos
CHUNK_OVERLAP=20

# Número de fragmentos a recuperar por consulta
SIMILARITY_TOP_K=3
```

#### Configuración de ChromaDB

```env
CHROMADB_HOST="chromadb"
CHROMADB_PORT=8000
COLLECTION_NAME="course_content"
```

#### Configuración de la API

```env
API_PORT=8080
API_HOST="0.0.0.0"
LOG_LEVEL="INFO"
```

### Cambiar entre Modelos de Gemini

Para usar el modelo más rápido y económico:

```env
GEMINI_MODEL="models/gemini-2.5-flash"
```

Para máxima calidad:

```env
GEMINI_MODEL="models/gemini-1.5-pro-latest"
```

No necesitas reiniciar el contenedor, pero debes ejecutar:

```bash
docker-compose restart fastapi_app
```

## 💻 Uso

### Ejecutar el Script de Ingesta

Cada vez que agregues o modifiques documentos:

```bash
docker-compose run --rm fastapi_app python ingest.py
```

### Verificar el Estado de la API

```bash
curl http://localhost:8080/health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "message": "Todos los sistemas operativos.",
  "model": "models/gemini-1.5-pro-latest",
  "collection_count": 42
}
```

### Probar el Chatbot

#### Opción 1: Interfaz Web

Abre `frontend/index.html` en tu navegador y usa el widget de chat.

#### Opción 2: cURL

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cuáles son los temas principales del curso?"}'
```

#### Opción 3: Python

```python
import requests

response = requests.post(
    'http://localhost:8080/api/chat',
    json={'question': '¿Qué es RAG?'}
)

print(response.json()['answer'])
```

### Ver Logs

```bash
# Ver logs de la API
docker-compose logs -f fastapi_app

# Ver logs de ChromaDB
docker-compose logs -f chromadb
```

### Detener los Servicios

```bash
# Detener pero mantener los datos
docker-compose down

# Detener y eliminar volúmenes (¡perderás los datos!)
docker-compose down -v
```

## 🌐 Despliegue en Producción

### Opción 1: VPS o Servidor Cloud

1. **Requisitos del Servidor**:
   - Ubuntu 20.04+ / Debian 11+
   - 4GB RAM mínimo (8GB recomendado)
   - Docker y Docker Compose instalados

2. **Transferir el Proyecto**:
   ```bash
   scp -r ./* usuario@servidor:/ruta/al/proyecto
   ```

3. **Configurar el Servidor**:
   ```bash
   ssh usuario@servidor
   cd /ruta/al/proyecto

   # Configurar .env
   cp .env.example .env
   nano .env

   # Iniciar servicios
   docker-compose up -d
   ```

4. **Configurar Reverse Proxy (Nginx)**:
   ```nginx
   server {
       listen 80;
       server_name tu-dominio.com;

       location / {
           proxy_pass http://localhost:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

5. **Configurar SSL con Let's Encrypt**:
   ```bash
   sudo certbot --nginx -d tu-dominio.com
   ```

### Opción 2: Railway / Render / Fly.io

Estos servicios soportan Docker Compose. Consulta la documentación específica de cada plataforma.

### Opción 3: Google Cloud Run

1. **Construir la imagen**:
   ```bash
   docker build -t chatbot-api .
   ```

2. **Subir a Google Container Registry**:
   ```bash
   gcloud builds submit --tag gcr.io/tu-proyecto/chatbot-api
   ```

3. **Desplegar**:
   ```bash
   gcloud run deploy chatbot-api \
     --image gcr.io/tu-proyecto/chatbot-api \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars GOOGLE_API_KEY=tu-api-key
   ```

### Configuración de Producción

Actualiza tu `.env` para producción:

```env
# Deshabilitar reload en producción
# Modifica el CMD en docker-compose.yml:
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Configurar CORS para tu dominio
CORS_ORIGINS="https://tu-dominio.com,https://www.tu-dominio.com"

# Reducir nivel de log
LOG_LEVEL="WARNING"
```

## 🎨 Personalización

### Personalizar el Widget de Chat

Edita las variables en tu HTML antes de incluir el script:

```html
<script>
  // Configuración personalizada
  window.CHATBOT_API_URL = 'https://api.tu-dominio.com/api/chat';
  window.CHATBOT_TITLE = 'Mi Asistente';
  window.CHATBOT_SUBTITLE = '¿En qué puedo ayudarte?';
  window.CHATBOT_PLACEHOLDER = 'Escribe aquí...';
  window.CHATBOT_PRIMARY_COLOR = '#FF6B6B';
  window.CHATBOT_ACCENT_COLOR = '#4ECDC4';
  window.CHATBOT_POSITION = 'bottom-left'; // o 'bottom-right'
</script>
<script src="chat-widget.js"></script>
```

### Modificar el Prompt del Sistema

Edita `app/main.py` y agrega system prompt personalizado:

```python
query_engine = index.as_query_engine(
    streaming=False,
    similarity_top_k=similarity_top_k,
    system_prompt="""
    Eres un asistente educativo experto.
    Responde de manera clara y concisa.
    Si no conoces la respuesta, indícalo honestamente.
    """
)
```

## 🔧 Solución de Problemas

### Error: "GOOGLE_API_KEY no está configurada"

**Solución**: Verifica que el archivo `.env` existe y contiene la clave correcta.

```bash
cat .env | grep GOOGLE_API_KEY
```

### Error: "Cannot connect to ChromaDB"

**Solución**: Asegúrate de que ChromaDB está ejecutándose:

```bash
docker-compose ps
docker-compose logs chromadb
```

Si no está activo:

```bash
docker-compose up -d chromadb
```

### Error: "Collection is empty"

**Solución**: Ejecuta el script de ingesta:

```bash
docker-compose run --rm fastapi_app python ingest.py
```

### Error: "Quota exceeded" (API de Google)

**Solución**: Has alcanzado el límite de la cuota gratuita. Opciones:

1. Espera a que se reinicie la cuota (diaria/por minuto)
2. Cambia a un modelo más económico (Gemini 2.5 Flash)
3. Configura facturación en Google Cloud

### La API es muy lenta

**Soluciones**:

1. Cambia a Gemini 2.5 Flash (más rápido)
2. Reduce `SIMILARITY_TOP_K` (menos contexto = más rápido)
3. Aumenta `CHUNK_SIZE` (menos fragmentos)

### El chatbot da respuestas incorrectas

**Soluciones**:

1. Aumenta `SIMILARITY_TOP_K` (más contexto)
2. Reduce `CHUNK_SIZE` (fragmentos más pequeños y precisos)
3. Verifica que los documentos estén correctos
4. Ejecuta de nuevo el script de ingesta

## 📚 API Documentation

### Endpoints

#### GET `/`

Información básica de la API.

**Respuesta**:
```json
{
  "message": "API del Chatbot Educativo está en funcionamiento.",
  "version": "1.0.0",
  "endpoints": {
    "chat": "/api/chat",
    "health": "/health",
    "docs": "/docs"
  }
}
```

#### GET `/health`

Health check del sistema.

**Respuesta**:
```json
{
  "status": "healthy",
  "message": "Todos los sistemas operativos.",
  "model": "models/gemini-1.5-pro-latest",
  "collection_count": 42
}
```

#### POST `/api/chat`

Endpoint principal del chatbot.

**Request Body**:
```json
{
  "question": "¿Cuáles son los temas del módulo 1?"
}
```

**Response**:
```json
{
  "answer": "Los temas principales del módulo 1 son...",
  "sources": ["documento1.pdf", "documento2.pdf"]
}
```

### Documentación Interactiva

Una vez que la API esté ejecutándose, accede a:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## 📊 Monitoreo y Costos

### Monitorear el Uso de la API de Google

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto
3. Ve a "APIs & Services" → "Dashboard"
4. Busca "Generative Language API"

### Estimar Costos

**Cuota Gratuita de Gemini**:
- Gemini 1.5 Flash: 15 RPM, 1M tokens/día
- Gemini 1.5 Pro: 2 RPM, 50 tokens/día

**Precios (tras exceder cuota gratuita)**:
- Consulta los precios actualizados en [ai.google.dev/pricing](https://ai.google.dev/pricing)

**Consejos para Reducir Costos**:
1. Usa Gemini 2.5 Flash cuando sea posible
2. Reduce `CHUNK_SIZE` para enviar menos tokens
3. Reduce `SIMILARITY_TOP_K` para recuperar menos contexto
4. Implementa caché de respuestas frecuentes

## 🤝 Contribuir

¿Encontraste un bug o tienes una sugerencia? Abre un issue o envía un pull request.

## 📝 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## 🙏 Agradecimientos

- [Google Gemini](https://ai.google.dev/) - LLM
- [ChromaDB](https://www.trychroma.com/) - Base de datos vectorial
- [LlamaIndex](https://www.llamaindex.ai/) - Framework RAG
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web

---

**¿Necesitas ayuda?** Consulta la documentación completa o abre un issue en GitHub.

**¡Feliz aprendizaje! 🎓**
