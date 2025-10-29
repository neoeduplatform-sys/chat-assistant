# Como reiniciar docker

```sh
docker compose down -v
```

Reinicar Chromadb

```sh
docker compose up -d chromadb
docker compose logs chromadb | tail -20
docker compose run --rm fastapi_app python ingest.py
``` 


Restart app:
```
docker compose build fastapi_app
docker up -d
```

Ejecuta estos comandos:

  # Reiniciar el servicio de FastAPI
  docker compose restart fastapi_app

  # Ver los logs para confirmar que el frontend se montó correctamente
  docker compose logs fastapi_app | grep -i frontend

  Deberías ver algo como:
  ✅ Frontend montado en /static desde /app/frontend

  ✅ Ahora Puedes Acceder de 3 Formas

  1. Interfaz Principal (Recomendado)

  http://localhost:8080/
  Esto mostrará directamente el index.html con el widget de chat.

  2. Archivos Estáticos

  http://localhost:8080/static/index.html
  http://localhost:8080/static/chat-widget.js
