"""Probe vector search with the real chat question embedding (same as /api/chat)."""
import os
import sys

import httpx
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

QUESTION = (
    "¿Qué tipo de termómetro es ideal para medir la temperatura de objetos "
    "en movimiento, muy calientes o inaccesibles, sin contacto físico?"
)


def main() -> None:
    model = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
    emb = GoogleGenAIEmbedding(model_name=model)
    vec = emb.get_query_embedding(QUESTION)

    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/rpc/match_ec0241_gemi_mantenimiento_industrial"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    payload = {
        "query_embedding": vec,
        "match_count": int(os.getenv("PROBE_MATCH_COUNT", "30")),
        "match_threshold": float(os.getenv("MATCH_THRESHOLD", "0.5")),
        "filter": {"has_topic_id": True},
    }
    r = httpx.post(
        url,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60.0,
    )
    r.raise_for_status()
    rows = r.json()
    print(f"Question: {QUESTION}\n")
    print(
        f"RPC returned {len(rows)} rows "
        f"(filter has_topic_id, k={payload['match_count']})\n"
    )
    for row in sorted(rows, key=lambda x: -x["similarity"])[:20]:
        md = row.get("metadata") or {}
        title = (md.get("title") or "")[:60]
        topic = md.get("topic_id", "")
        preview = (row.get("content") or "")[:80].replace("\n", " ")
        print(
            f"{row['id']:>6}  sim={row['similarity']:.4f}  topic={topic:<6}  {title}"
        )
        print(f"         {preview}...")

    pir = [
        row
        for row in rows
        if "pirómetro" in (row.get("content") or "").lower()
        or "pirometr" in (row.get("content") or "").lower()
        or "infrarrojo" in (row.get("content") or "").lower()
    ]
    if pir:
        best = max(pir, key=lambda x: x["similarity"])
        rank = 1 + sorted(rows, key=lambda x: -x["similarity"]).index(best)
        print(f"\nBest pirómetro/infrarrojo chunk: id={best['id']} sim={best['similarity']:.4f} rank={rank}/{len(rows)}")
    else:
        print("\nNo pirómetro/infrarrojo in returned set.", file=sys.stderr)


if __name__ == "__main__":
    main()
