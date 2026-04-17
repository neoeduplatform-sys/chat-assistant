## GEMINI.md

This document provides a comprehensive overview of the **Educational Chatbot with Google Gemini** project, serving as instructional context for future interactions.

### Project Overview

This project implements a robust educational chatbot powered by Google Gemini and a Retrieval-Augmented Generation (RAG) architecture. It is designed to provide accurate, context-aware responses based on provided course materials. The system features a FastAPI backend, LlamaIndex for RAG orchestration, and Supabase (leveraging `pgvector`) for efficient vector storage and multi-course management. A lightweight HTML/JavaScript frontend widget allows for easy integration and user interaction.

The core functionality revolves around:
*   **Advanced AI:** Utilizing Google Gemini (1.5 Pro / 2.5 Flash) for powerful language models.
*   **RAG Architecture:** Grounding responses in specific course documents.
*   **Semantic Search:** Automatically finding relevant information.
*   **Vector Database:** Employing Supabase (leveraging `pgvector`) as the primary **external** vector database for efficient vector storage and multi-course management. Connection details are configured via environment variables. (Note: While `README.md` and other documentation might contain references to ChromaDB, these are either outdated or refer to an alternative configuration not actively used by the Python implementation.)
*   **FastAPI Backend:** A fast and robust REST API.
*   **Customizable Widget:** A dependency-free frontend chat widget.
*   **Docker Ready:** Simplified deployment with Docker Compose.
*   **Multi-Course Support:** Dynamic configuration and knowledge base management for multiple courses.

### Architecture

The system follows a typical RAG architecture:

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Usuario   │─────>│ FastAPI      │─────>│ LlamaIndex  │
│   (HTML)    │<─────│ Backend      │<─────│ RAG Engine  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                      │
                            │                      ▼
                            │              ┌─────────────┐
                            │              ┌─────────────┐
                            │              │  Supabase   │
                            │              │ (External)  │
                            │              └─────────────┘
                            ▼
                     ┌──────────────┐
                     │ Google Gemini│
                     │     API      │
                     └──────────────┘
```

**Data Flow:**
1.  A user submits a question via the HTML chat widget.
2.  The FastAPI backend receives the question and passes it to LlamaIndex.
3.  LlamaIndex converts the question into a vector embedding using Google's embedding model.
4.  Supabase searches for the most relevant document chunks based on semantic similarity.
5.  Google Gemini generates a response, using the retrieved context.
6.  The user receives the answer, optionally with cited sources.

### Building and Running

This project uses Docker Compose for easy setup and deployment.

**Prerequisites:**
*   Docker and Docker Compose installed.
*   A Google AI Studio API Key (refer to `SETUP_API_KEY.md`).

**Quick Start Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository>
    cd chatbot
    ```

2.  **Obtain Google API Key:**
    Follow the detailed guide in `SETUP_API_KEY.md` or:
    *   Go to [Google AI Studio](https://aistudio.google.com/).
    *   Log in with your Google account.
    *   Click "Get API key" and copy it.

3.  **Configure Environment Variables:**
    Copy the example file and edit `.env` with your API key and other settings.
    ```bash
    cp .env.example .env
    # Edit .env, e.g., with nano .env
    # GOOGLE_API_KEY="your-api-key-here"
    # SUPABASE_URL="your-supabase-url"
    # SUPABASE_SERVICE_ROLE_KEY="your-supabase-key"
    ```

4.  **Add Course Documents:**
    Place your documents (PDF, TXT, MD, DOCX) into the `data/` directory.
    ```bash
    cp /path/to/your/documents/*.pdf data/
    ```

5.  **Start Services & Ingest Data:**
    *   Start the application services, which include the FastAPI backend and an ingestion worker.
    *   Run the ingestion script to process your documents and store them in Supabase.

    ```bash
    # (Optional: If you have a separate Supabase docker service, start it first.
    # The current docker-compose.yml only defines fastapi_app and ingestion_worker,
    # assuming Supabase is an external service.)

    # Start FastAPI app and ingestion worker
    docker-compose up -d

    # Run the ingestion script (after services are up and Supabase is accessible)
    docker-compose run --rm fastapi_app python ingest.py
    ```

6.  **Access the Chatbot:**
    *   **API:** `http://localhost:8080`
    *   **API Docs (Swagger UI):** `http://localhost:8080/docs`
    *   **Demo Frontend:** Open `frontend/index.html` in your web browser.

### Development Conventions

*   **Environment Variables:** All major configurations are managed via `.env` files (e.g., `GOOGLE_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL`, `CHUNK_SIZE`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_TABLE_NAME`, `SUPABASE_RPC_FUNCTION`).
*   **Logging:** The application uses Python's standard `logging` module, configurable via the `LOG_LEVEL` environment variable (default: `INFO`).
*   **CORS:** Cross-Origin Resource Sharing is managed through the `CORS_ORIGINS` environment variable, allowing flexible frontend integration.
*   **Multi-Course Support:** The `app/main.py` demonstrates a flexible design for handling multiple courses, dynamically configuring the RAG engine based on a `course_id` provided in chat requests. Course configurations are managed via dedicated API endpoints (`/api/v1/courses`).
*   **Asynchronous Ingestion:** Content ingestion is designed as an asynchronous process. New content is submitted via an API endpoint (`/api/v1/ingest`), queued in a Supabase table (`ingestion_jobs`), and processed by a background worker (`worker.py`).
*   **Error Handling:** The FastAPI application utilizes `HTTPException` for standardized API error responses.
*   **Code Structure:** The project is organized into logical modules:
    *   `app/`: Contains the main FastAPI application, models, and Supabase integration.
    *   `data/`: Directory for raw course documents to be ingested.
    *   `frontend/`: Static files for the chat widget demo.
    *   `migrations/`: SQL migration scripts.
    *   `scripts/`: Utility shell scripts.
    *   `tests/`: Unit and integration tests.

### Key Files

*   `README.md`: Project overview, setup, usage, and deployment.
*   `requirements.txt`: Python dependencies.
*   `docker-compose.yml`: Docker Compose configuration for `fastapi_app` and `ingestion_worker`.
*   `app/main.py`: Main FastAPI application, API endpoints, RAG engine initialization, and course management logic.
*   `ingest.py`: Script for ingesting documents from `./data` into Supabase.
*   `app/supabase_vector_store.py`: Custom LlamaIndex vector store integration for Supabase.
*   `app/course_config.py`: Service for managing course configurations in Supabase.
*   `app/models.py`: Pydantic models for API request/response validation and database interaction.
*   `frontend/index.html`: Demo HTML file for the chat widget.
*   `frontend/chat-widget.js`: JavaScript logic for the interactive chat widget.

This `GEMINI.md` file will serve as an essential reference for understanding the project's structure, functionality, and operational procedures in future interactions.
