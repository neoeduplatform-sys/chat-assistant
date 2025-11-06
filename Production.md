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
