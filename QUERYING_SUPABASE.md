# Querying Supabase for Specific Topics After Ingestion

This document outlines the steps to query your Supabase database for information related to a specific topic, leveraging the vector embeddings generated during the ingestion process.

## Prerequisites

*   **Ingested Data:** Ensure your course documents have been successfully ingested into your Supabase database.
*   **Supabase Connection Details:** You'll need your `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from your `.env` file to connect to your Supabase instance.
*   **Topic Embedding:** You must be able to generate a vector embedding for your specific topic using the **same Google embedding model** used during the ingestion process.

## Steps

### 1. Identify Supabase Configuration

First, determine the name of your Supabase table and the relevant column names.

*   **Supabase Table Name:** This is typically found in your `.env` file under `SUPABASE_TABLE_NAME`. (Based on previous interaction, it's likely `ec0241_gemi_test`).
*   **Vector Column:** The column storing the vector embeddings. Common name: `embedding`.
*   **Content Column:** The column storing the original text content of the document chunks. Common name: `content`.

### 2. Generate a Vector Embedding for Your Topic

To perform a semantic search, your topic needs to be converted into a vector embedding. This is a critical step, as the embedding **must be generated using the exact same model** used for ingesting your documents.

**How to generate the embedding (conceptual):**

*   **Programmatic Approach:** Use a Python script with the `google.generativeai` library or LlamaIndex's `GoogleEmbedding` class, configured with your `GOOGLE_API_KEY`. You would feed your specific topic (e.g., "quantum physics concepts") into this model to receive a list of floating-point numbers representing its embedding.

    ```python
    # Conceptual Python snippet (requires setup with API key and model)
    from llama_index.embeddings.google import GoogleEmbedding
    import os

    # Assuming GOOGLE_API_KEY is in environment variables
    embed_model = GoogleEmbedding(model="models/embedding-001") # Or your specific embedding model

    topic_text = "Your specific topic here, e.g., History of ancient Rome"
    topic_embedding = embed_model.get_query_embedding(topic_text)

    # topic_embedding will be a list of floats, e.g., [0.1, 0.2, -0.05, ...]
    ```
*   **Google AI Studio:** If available and suitable for short text, you might use Google AI Studio's embedding capabilities.

**Result:** You will obtain a vector (a list of floating-point numbers) for your topic. For example: `[0.123, 0.456, -0.789, ..., 0.999]`.

### 3. Query Supabase using SQL

Once you have the vector embedding for your topic, you can construct a SQL query to find the most semantically similar document chunks in your Supabase database using the `pgvector` extension.

Replace the placeholders with your actual values:

*   `your_supabase_table`: The actual table name (e.g., `ec0241_gemi_test`).
*   `embedding_column`: The column containing the vector embeddings (e.g., `embedding`).
*   `content_column`: The column containing the text content (e.g., `content`).
*   `[YOUR_TOPIC_EMBEDDING_VECTOR]`: The comma-separated string representation of the vector you generated in Step 2 (e.g., `[0.123, 0.456, -0.789, ..., 0.999]`).

```sql
SELECT
    id,
    content_column, -- Or any other relevant metadata columns
    1 - (embedding_column <-> '[YOUR_TOPIC_EMBEDDING_VECTOR]') AS similarity_score
FROM
    your_supabase_table
ORDER BY
    similarity_score DESC
LIMIT 5; -- Adjust the limit to retrieve more or fewer results
```

**Explanation of the SQL Query:**

*   **`[YOUR_TOPIC_EMBEDDING_VECTOR]`**: This is the vector embedding of your search topic.
*   **`<->`**: This is the `pgvector` operator for calculating the **Euclidean distance** between two vectors. A smaller distance means higher similarity.
*   **`1 - (embedding_column <-> '[YOUR_TOPIC_EMBEDDING_VECTOR]') AS similarity_score`**: We subtract the Euclidean distance from 1 to convert it into a similarity score, where 1 indicates perfect similarity and 0 indicates maximum dissimilarity (based on the range of Euclidean distance). If you are using cosine similarity, the formula might be different.
*   **`ORDER BY similarity_score DESC`**: Sorts the results to show the most similar document chunks first.
*   **`LIMIT 5`**: Retrieves the top 5 most relevant document chunks. You can modify this number as needed.

### 4. Execute the SQL Query

You can execute this SQL query using one of the following methods:

*   **Supabase Dashboard SQL Editor:**
    1.  Log in to your Supabase project dashboard.
    2.  Navigate to the **SQL Editor** section.
    3.  Paste your constructed SQL query into the editor.
    4.  Click "Run" to execute the query and see the results.

*   **`psql` Command-Line Client:**
    1.  Ensure you have the `psql` client installed on your system.
    2.  Connect to your Supabase database from your terminal using your connection string. You'll need to extract the host from your `SUPABASE_URL`.
        ```bash
        psql "postgresql://postgres:[YOUR_SUPABASE_SERVICE_ROLE_KEY]@[YOUR_SUPABASE_URL_HOST]:5432/postgres"
        ```
        (Example: If `SUPABASE_URL="https://abc.supabase.co"`, the host might be `db.abc.supabase.co`. Refer to your Supabase project settings for the exact host and connection string details.)
    3.  Once connected, paste your SQL query and press Enter to execute.

By following these steps, you can directly interact with your Supabase database to retrieve semantically similar content based on any specific topic you wish to query.