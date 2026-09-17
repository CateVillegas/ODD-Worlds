"""Búsqueda híbrida sobre la KB: palabras clave + significado, fusionados.

    python kb_search.py "que es un jupiter caliente"
    python kb_search.py "pl_orbeccen"

Por qué híbrida, que es lo que vas a defender:
  - Solo semántica falla con términos exactos y raros: `pl_orbeccen` no se
    "parece" a nada, hay que encontrarlo literal.
  - Solo palabras clave falla cuando la persona no sabe el término:
    "planetas que se achicharran" no comparte una sola palabra con
    "Júpiter caliente".
  - Las dos juntas cubren los dos casos.
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

KB = Path("data/kb")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def tokenize(text: str) -> list[str]:
    """Tokenizador simple para BM25. Minúsculas, y los guiones bajos se
    conservan para que `pl_orbeccen` quede como un token entero.
    """
    return re.findall(r"[a-zA-Z_áéíóúñ0-9]+", text.lower())


@lru_cache(maxsize=1)
def load():
    """Carga todo en memoria una vez. 300 fragmentos entran sin problema,
    por eso no hace falta ninguna base de datos vectorial.
    """
    chunks = pd.read_parquet(KB / "chunks.parquet")
    vectors = np.load(KB / "embeddings.npy")
    bm25 = BM25Okapi([tokenize(t) for t in chunks["text"]])
    model = SentenceTransformer(EMBED_MODEL)
    return chunks, vectors, bm25, model


def search(query: str, k: int = 5, kind: str | None = None) -> pd.DataFrame:
    """Devuelve los k fragmentos más relevantes.

    kind: si querés filtrar por tipo ('concepto' o 'columna'). Por ejemplo,
    si la pregunta menciona un nombre de columna, buscar solo entre columnas.
    """
    chunks, vectors, bm25, model = load()

    # ── señal 1: palabras clave ────────────────────────────────
    # BM25 da un puntaje por documento según qué tan raras y frecuentes son
    # las palabras compartidas. Es el mismo principio de rareza que usás en
    # el modelo de anomalías: lo poco frecuente pesa más.
    bm25_scores = bm25.get_scores(tokenize(query))

    # ── señal 2: significado ───────────────────────────────────
    # Convierte la pregunta en un vector y lo compara contra todos.
    # Como los vectores están normalizados, el producto punto ES el coseno.
    q_vec = model.encode([query], normalize_embeddings=True)[0]
    cosine_scores = vectors @ q_vec

    # ── fusión: Reciprocal Rank Fusion ─────────────────────────
    # No se pueden sumar los puntajes directamente: BM25 puede dar 14.7 y el
    # coseno 0.62, están en escalas distintas. RRF ignora el valor y usa la
    # POSICIÓN en cada ranking: cada documento suma 1/(60 + puesto).
    # El 60 es el valor estándar del paper original; amortigua las diferencias
    # entre los primeros puestos.
    def rrf(scores: np.ndarray, k_const: int = 60) -> np.ndarray:
        order = np.argsort(-scores)          # índices, del mejor al peor
        ranks = np.empty_like(order)
        ranks[order] = np.arange(len(scores))  # posición de cada documento
        return 1.0 / (k_const + ranks + 1)

    fused = rrf(bm25_scores) + rrf(cosine_scores)

    out = chunks.copy()
    out["score"] = fused
    out["bm25"] = bm25_scores
    out["cosine"] = cosine_scores

    if kind:
        out = out[out["kind"] == kind]

    return out.sort_values("score", ascending=False).head(k)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "que es un jupiter caliente"
    hits = search(q)
    print(f"\nconsulta: {q}\n")
    for _, row in hits.iterrows():
        print(f"[{row['kind']}] {row['source']} — {row['section']}")
        print(f"  rrf={row['score']:.4f}  bm25={row['bm25']:.2f}  cos={row['cosine']:.3f}")
        print(f"  {row['text'][:200].replace(chr(10), ' ')}…\n")
