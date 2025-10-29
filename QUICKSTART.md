# 🚀 Guía de Inicio Rápido

¿Primera vez usando el chatbot? ¡Empieza aquí! Esta guía te llevará de cero a un chatbot funcionando en menos de 10 minutos.

## ⚡ Inicio Rápido (5 comandos)

```bash
# 1. Configurar variables de entorno
cp .env.example .env

# 2. Editar .env y agregar tu API key de Google
nano .env  # o tu editor favorito

# 3. Agregar documentos del curso
cp /ruta/a/tus/documentos/*.pdf data/

# 4. Iniciar servicios e ingerir datos
docker compose up -d chromadb
sleep 10
docker compose run --rm fastapi_app python ingest.py

# 5. Iniciar la API
docker compose up -d
```

¡Listo! Abre `frontend/index.html` en tu navegador.

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener:

- ✅ Docker instalado ([descargar](https://www.docker.com/get-started))
- ✅ Docker Compose instalado (incluido con Docker Desktop)
- ✅ API Key de Google AI Studio ([obtener gratis](https://aistudio.google.com/))

## 🎯 Paso a Paso Detallado

### Paso 1: Obtener tu API Key de Google

1. Ve a [Google AI Studio](https://aistudio.google.com/)
2. Inicia sesión con tu cuenta de Google
3. Haz clic en **"Get API key"**
4. Copia tu API key

📚 **¿Necesitas ayuda?** Lee [`SETUP_API_KEY.md`](SETUP_API_KEY.md) para instrucciones detalladas.

### Paso 2: Configurar el Proyecto

```bash
# Opción A: Usando el script automático (recomendado)
./scripts/setup.sh

# Opción B: Configuración manual
cp .env.example .env
nano .env  # Pega tu API key aquí
```

En el archivo `.env`, busca esta línea y reemplaza con tu API key:

```env
GOOGLE_API_KEY="tu-api-key-aqui"
```

### Paso 3: Agregar Documentos del Curso

Coloca tus documentos en el directorio `data/`:

```bash
# Ejemplo con PDFs
cp ~/Descargas/curso_modulo_1.pdf data/
cp ~/Descargas/curso_modulo_2.pdf data/

# Soporta: PDF, TXT, MD, DOCX
```

**💡 Tip:** Ya hay un archivo de ejemplo (`data/ejemplo_curso.md`) que puedes usar para testing.

### Paso 4: Iniciar ChromaDB

```bash
# Iniciar la base de datos vectorial
docker up -d chromadb

# Esperar a que esté lista (importante)
sleep 10

# Verificar que está corriendo
docker ps
```

Deberías ver:

```
NAME                IMAGE              STATUS
chromadb_service    chromadb/chroma    Up
```

### Paso 5: Procesar los Documentos

```bash
# Ejecutar el script de ingesta
docker run --rm fastapi_app python ingest.py
```

**⏳ Esto puede tardar varios minutos** dependiendo del tamaño de tus documentos.

Verás algo como:

```
✅ Se cargaron 3 documentos exitosamente.
✅ Conexión a ChromaDB exitosa.
✅ Índice vectorial creado y almacenado en ChromaDB exitosamente.
📊 Total de fragmentos almacenados: 42
```

### Paso 6: Iniciar la API

```bash
# Iniciar el servidor FastAPI
docker up -d

# Ver logs (opcional)
dockerlogs -f fastapi_app
```

La API estará disponible en: http://localhost:8080

### Paso 7: Probar el Chatbot

**Opción 1: Interfaz Web (Recomendado)**

1. Abre el archivo `frontend/index.html` en tu navegador
2. Haz clic en el ícono de chat en la esquina inferior derecha
3. ¡Haz tu primera pregunta!

**Opción 2: Curl (Prueba rápida)**

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Qué es RAG?"}'
```

**Opción 3: API Docs (Interactivo)**

Visita: http://localhost:8080/docs

## ✅ Verificación del Sistema

Ejecuta el script de pruebas:

```bash
./scripts/quick-test.sh
```

O verifica manualmente:

```bash
# Health check
curl http://localhost:8080/health

# Debería retornar:
# {
#   "status": "healthy",
#   "model": "models/gemini-1.5-pro-latest",
#   "collection_count": 42
# }
```

## 🎨 Personalización Rápida

### Cambiar el Modelo de IA

Edita `.env`:

```env
# Para máxima calidad (más lento)
GEMINI_MODEL="models/gemini-1.5-pro-latest"

# Para velocidad (recomendado)
GEMINI_MODEL="models/gemini-2.5-flash"
```

Reinicia:

```bash
dockerrestart fastapi_app
```

### Personalizar el Widget de Chat

Edita `frontend/index.html`, busca la sección de configuración:

```html
<script>
  window.CHATBOT_TITLE = 'Mi Asistente Personal';
  window.CHATBOT_PRIMARY_COLOR = '#FF6B6B';
</script>
```

## 🛠️ Comandos Útiles

```bash
# Ver logs en tiempo real
dockerlogs -f fastapi_app

# Reiniciar servicios
docker restart

# Detener todo
docker down

# Detener y eliminar datos (¡cuidado!)
docker down -v

# Ver estado de los servicios
docker ps

# Ejecutar pruebas
python tests/test_api.py
```

## 🐛 Solución Rápida de Problemas

### "GOOGLE_API_KEY no está configurada"

```bash
# Verificar que existe el archivo .env
cat .env | grep GOOGLE_API_KEY

# Si está vacío, edítalo
nano .env
```

### "Cannot connect to ChromaDB"

```bash
# Asegúrate de que ChromaDB está ejecutándose
docker up -d chromadb
sleep 10

# Verifica que está arriba
docker ps
```

### "Collection is empty"

```bash
# Ejecuta el script de ingesta
docker run --rm fastapi_app python ingest.py
```

### "Port 8080 already in use"

Cambia el puerto en `.env`:

```env
API_PORT=8081
```

Y reinicia:

```bash
docker down
docker up -d
```

### La API no responde

```bash
# Ver logs para diagnóstico
docker logs fastapi_app

# Verificar que el contenedor está corriendo
docker ps

# Reiniciar el servicio
docker restart fastapi_app
```

## 📚 Siguientes Pasos

Una vez que tu chatbot esté funcionando:

1. **Agrega más documentos**: Simplemente copia archivos a `data/` y ejecuta el script de ingesta
2. **Lee la documentación completa**: [`README.md`](README.md)
3. **Personaliza el widget**: Cambia colores, textos, posición
4. **Optimiza el rendimiento**: Ajusta `CHUNK_SIZE`, `SIMILARITY_TOP_K` en `.env`
5. **Despliega en producción**: Consulta la sección de despliegue en el README

## 🆘 ¿Necesitas Ayuda?

- 📖 Lee el [README completo](README.md)
- 🔍 Consulta la [guía de API Key](SETUP_API_KEY.md)
- 🐛 Revisa la sección de [Troubleshooting](README.md#solución-de-problemas)
- 📝 Abre un issue en el repositorio

## 🎉 ¡Felicidades!

Si llegaste hasta aquí, ¡tu chatbot educativo está listo!

**Prueba haciendo estas preguntas:**
- "¿Qué es RAG?"
- "Explícame la arquitectura del sistema"
- "¿Qué componentes usa este chatbot?"

---

**💡 Tip Pro:** Marca esta página para referencia rápida. ¡La necesitarás!
