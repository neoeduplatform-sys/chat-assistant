# Production management

1.  Navigate into your project directory:

    ```bash
    cd /path/to/your/project
    ```

2.  Build the images and start all services in the background:

    ```bash
    docker compose up -d --build
    ```

      * `-d` runs the containers in detached mode.
      * `--build` forces Docker to build your images from your `Dockerfile`.

-----
Recargar las Variables de Entorno en Docker (IMPORTANTE)

  Docker NO recarga el .env automáticamente. Debes hacer:

  # En tu servidor de producción:

  # Detener los contenedores
  docker compose down

  # Reconstruir las imágenes (para asegurar que tomen el nuevo .env)
  docker compose build --no-cache

  # Levantar los servicios
  docker compose up -d

  # Verificar que levantaron correctamente
  docker compose ps

  3. Verificar que se Cargó Correctamente

  # Ver los logs del servicio FastAPI
  docker compose logs fastapi_app | grep "RPC Function"

  # Deberías ver algo como:
  # INFO:     - RPC Function: match_ec0241_gemi_test

  Si ves match_ec1121_gemi_mantenimiento_mecanico_automotriz, significa que NO se recargó
  el .env.

-----

### 4\. How to Check Logs and Update

Now, your setup is complete and your familiar commands will work.

  * **To see the status of all services:**

    ```bash
    docker compose ps
    ```

  * **To monitor your ingestion worker (as you wanted):**

    ```bash
    docker compose logs -f ingestion_worker
    ```

  * **To monitor your web app:**

    ```bash
    docker compose logs -f fastapi_app
    ```

### How to Update Your App in the Future

Because you are using **volumes** (e.g., `- ./app:/app/app`), your code is mounted directly from the host. This makes updates very easy.

1.  Pull your new code:
    ```bash
    git pull
    ```
2.  Restart the relevant service (it will pick up the new code):
    ```bash
    docker compose restart fastapi_app
    ```

You **only** need to run `docker compose up -d --build` again if you make changes to your `Dockerfile` or your `requirements.txt` file.
