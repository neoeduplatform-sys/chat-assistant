# RAG Implementation: Data Loading and LLM Knowledge Limitation

This document explains how the educational chatbot handles data loading and, crucially, how it limits the Large Language Model's (LLM) knowledge to the provided course materials, preventing it from "hallucinating" or using general internet knowledge.

## Data Loading Mechanism (Exclusive Vector Database)

The chat assistant's data loading mechanism is exclusively from a Supabase vector database at query time; it does not read from files directly during a chat interaction. The system is designed with a clear separation between data ingestion and querying.

### Data Ingestion Flow:

1.  **Manual (Initial Setup):** The `ingest.py` script is used for a one-time population of the database. It reads local files from a `./data` directory, chunks them, generates embeddings using the Google AI API, and stores them in a Supabase table defined in the environment variables.
2.  **Asynchronous (Ongoing Updates):** The `app/main.py` exposes an `/api/v1/ingest` endpoint. When this endpoint receives new content, it does not process it directly. Instead, it creates a job in an `ingestion_jobs` table in Supabase. The `worker.py` script runs as a separate background process, continuously polling this table. When it finds a new job, it performs an "upsert": it first deletes any old content with the same ID and then processes and stores the new content's vector embeddings in the appropriate course-specific table.

### RAG Architecture & Query Flow (`/api/chat`):

1.  **Request:** A user sends a query including a `course_id` to the `chat_endpoint` in `app/main.py`.
2.  **Dynamic Configuration:** The application calls the `CourseConfigService` (`app/course_config.py`) to fetch the specific Supabase `table_name` and `rpc_function` associated with the given `course_id`.
3.  **Vector Store Instantiation:** A `SupabaseVectorStore` instance (`app/supabase_vector_store.py`) is created dynamically with the retrieved table and RPC function names.
4.  **Retrieval:** The user's query is converted into a vector embedding. The `SupabaseVectorStore.query` method is called, which in turn executes a Remote Procedure Call (RPC) in Supabase. This database function performs the vector similarity search efficiently on the server side and returns the most relevant document chunks.
5.  **Augmentation & Generation:** The retrieved chunks are inserted into a prompt template as context. This complete prompt (context + original query) is sent to the Google Gemini model, which generates the final, context-aware answer.

In summary, the system **only** loads data from the vector database during a chat interaction. The loading of data *into* the database is a separate, asynchronous process designed to keep the main application responsive and the knowledge base up-to-date.

## Code Limiting LLM Knowledge

The knowledge of the LLM is specifically limited by the prompt engineering within the `app/main.py` file. The `PromptTemplate` explicitly instructs the Gemini model to use *only* the provided context for generating responses. This is a critical component of the RAG architecture to ensure responses are grounded in the course materials.

Here's the relevant code snippet from `app/main.py` (within the `chat_endpoint` function):

```python
        from llama_index.core.prompts import PromptTemplate

        qa_prompt_template = PromptTemplate(
            f"Eres un asistente educativo experto en {course_config['course_name']}. "
            "Tu objetivo es ayudar a estudiantes a aprender sobre este tema.\n\n"
            "IMPORTANTE: Siempre responde en español, sin importar el idioma de la pregunta.\n\n"
            "Contexto de referencia:\n"
            "{context_str}\n\n"
            "Pregunta: {query_str}\n\n"
            "Instrucciones:\n"
            "1. Responde ÚNICAMENTE en español\n"
            "2. Usa el contexto proporcionado para dar respuestas precisas\n"
            "3. Si no encuentras la respuesta en el contexto, indícalo claramente\n"
            "4. Sé claro, educativo y profesional\n\n"
            "Respuesta en español:"
        )

        course_query_engine = index.as_query_engine(
            streaming=False,
            similarity_top_k=similarity_top_k,
            text_qa_template=qa_prompt_template,
        )
```

**Explanation of how this code limits the LLM's knowledge:**

*   **`Contexto de referencia:\n{context_str}\n\n`**: This line explicitly injects the retrieved document chunks into the prompt. The `{context_str}` placeholder is where the relevant information from the Supabase vector store is placed.
*   **`Instrucciones:\n1. Responde ÚNICAMENTE en español\n2. Usa el contexto proporcionado para dar respuestas precisas\n3. Si no encuentras la respuesta en el contexto, indícalo claramente\n4. Sé claro, educativo y profesional\n\nRespuesta en español:`**: These instructions are crucial. They directly command the LLM to:
    1.  **`Usa el contexto proporcionado para dar respuestas precisas`**: This is the core instruction that forces the LLM to rely solely on the retrieved information.
    2.  **`Si no encuentras la respuesta en el contexto, indícalo claramente`**: This instruction prevents the LLM from fabricating answers when the relevant information is not present in the provided context, further reinforcing the reliance on the retrieved data.

By embedding these clear instructions within the prompt, the system effectively guides the Gemini model to operate strictly within the bounds of the provided course material, thereby limiting its "knowledge" to what has been retrieved from the vector database.
