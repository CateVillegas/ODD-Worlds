"""Construye la base de conocimiento. Se corre UNA vez (o cuando cambien los docs).

    pip install trafilatura requests sentence-transformers rank-bm25 pandas pyarrow lxml
    python kb_build.py

Deja tres cosas en data/kb/:
    raw/*.txt        el texto crudo de cada fuente (para que puedas leerlo vos)
    chunks.parquet   los fragmentos con sus metadatos
    embeddings.npy   la matriz de vectores, una fila por fragmento

Dos estrategias de corte distintas, porque hay dos formas de documento:
  - prosa   -> cortar por sección, con el título repetido arriba
  - columnas-> un fragmento por columna, sin cortar
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import trafilatura
from sentence_transformers import SentenceTransformer

KB = Path("data/kb")
RAW = KB / "raw"

# El modelo de embeddings. 384 dimensiones, ~100 MB, corre local y sin internet.
# Se baja solo la primera vez a ~/.cache/huggingface.
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Documentos de prosa. Poné acá las URLs que verificaste vos.
PROSE_SOURCES = {
    "nasa_exoplanets_overview": "https://science.nasa.gov/exoplanets/",
    "nasa_planet_types": "https://science.nasa.gov/exoplanets/planet-types/",
    "nasa_types_infographic": "https://science.nasa.gov/resource/exoplanet-types-infographic/",
    # "nasa_discovery_methods": "<-- pegá acá la URL de métodos de descubrimiento>",
}

# Documento de columnas: es una tabla HTML, se parsea distinto.
COLUMNS_SOURCE = "https://exoplanetarchive.ipac.caltech.edu/docs/API_exoplanet_columns.html"

MAX_WORDS = 400   # tamaño máximo de un fragmento de prosa
OVERLAP = 50      # palabras que se repiten entre fragmentos consecutivos


# ─────────────────────────────────────────────────────────────
# 1. Descarga
# ─────────────────────────────────────────────────────────────

def download(name: str, url: str) -> str:
    """Baja una página y extrae el texto principal en markdown.

    Se cachea en raw/. Si el archivo existe, no vuelve a pedir nada:
    así podés reconstruir la KB sin internet.
    """
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")

    html = requests.get(url, timeout=60, headers={"User-Agent": "odd-worlds/0.1"}).text
    # include_headings=True es clave: necesitamos los títulos para cortar por sección.
    text = trafilatura.extract(html, output_format="markdown", include_headings=True) or ""
    if not text.strip():
        raise RuntimeError(f"no se pudo extraer texto de {url}. Copialo a mano a {path}")

    path.write_text(text, encoding="utf-8")
    print(f"  bajado {name} ({len(text.split())} palabras)")
    return text


# ─────────────────────────────────────────────────────────────
# 2. Corte de prosa: por sección, no por caracteres
# ─────────────────────────────────────────────────────────────

def chunk_prose(text: str, source: str, url: str) -> list[dict]:
    """Corta por encabezado markdown. Si una sección es muy larga, la parte
    en pedazos con solapamiento. El título del documento y el de la sección
    se repiten arriba de cada fragmento.

    Por qué: un fragmento que dice "orbitan tan cerca que la temperatura llega
    a miles de grados" es inútil si no dice arriba "Tipos - Júpiter calientes".
    Eso ayuda a la búsqueda semántica Y a la de palabras clave.
    """
    doc_title = source.replace("_", " ")
    chunks: list[dict] = []
    section = "Introducción"
    buffer: list[str] = []

    def flush():
        """Cierra la sección actual y la parte si hace falta."""
        if not buffer:
            return
        words = " ".join(buffer).split()
        step = MAX_WORDS - OVERLAP
        for i in range(0, len(words), step):
            piece = " ".join(words[i:i + MAX_WORDS])
            if len(piece.split()) < 20:      # fragmentos muy cortos no aportan
                continue
            chunks.append({
                "text": f"{doc_title} — {section}\n\n{piece}",
                "source": source,
                "url": url,
                "section": section,
                "kind": "concepto",
            })
            if i + MAX_WORDS >= len(words):
                break
        buffer.clear()

    for line in text.splitlines():
        if re.match(r"^#{1,4}\s+", line):    # es un encabezado
            flush()
            section = re.sub(r"^#{1,4}\s+", "", line).strip()
        else:
            if line.strip():
                buffer.append(line.strip())
    flush()
    return chunks


# ─────────────────────────────────────────────────────────────
# 3. Corte de columnas: un fragmento por columna
# ─────────────────────────────────────────────────────────────

def chunk_columns(url: str) -> list[dict]:
    """Cada definición de columna ya es una unidad completa y corta.
    Cortarla por tamaño sería romperla. Un fragmento por fila de la tabla.
    """
    tables = pd.read_html(url)
    # Nos quedamos con la tabla más larga, que es la de definiciones.
    table = max(tables, key=len)
    table.columns = [str(c).strip().lower() for c in table.columns]

    name_col = next((c for c in table.columns if "column" in c or "name" in c), table.columns[0])
    desc_col = next((c for c in table.columns if "desc" in c), table.columns[-1])

    chunks = []
    for _, row in table.iterrows():
        col_name = str(row[name_col]).strip()
        desc = str(row[desc_col]).strip()
        if not col_name or col_name.lower() == "nan" or len(desc) < 10:
            continue
        chunks.append({
            "text": f"Columna del catálogo: {col_name}\n\n{desc}",
            "source": "nasa_archive_columns",
            "url": url,
            "section": col_name,
            "kind": "columna",
        })
    return chunks


# ─────────────────────────────────────────────────────────────
# 4. Nota propia
# ─────────────────────────────────────────────────────────────

def chunk_own_notes() -> list[dict]:
    """Tu documento: qué considera raro este sistema. Escribilo en
    data/kb/raw/rareza.md antes de correr esto.
    """
    path = RAW / "rareza.md"
    if not path.exists():
        print("  ojo: falta data/kb/raw/rareza.md (tu definición de 'raro')")
        return []
    return chunk_prose(path.read_text(encoding="utf-8"), "definicion_de_rareza", "local")


# ─────────────────────────────────────────────────────────────
# 5. Embeddings
# ─────────────────────────────────────────────────────────────

def build():
    KB.mkdir(parents=True, exist_ok=True)
    all_chunks: list[dict] = []

    print("prosa:")
    for name, url in PROSE_SOURCES.items():
        all_chunks += chunk_prose(download(name, url), name, url)

    print("columnas:")
    cols = chunk_columns(COLUMNS_SOURCE)
    print(f"  {len(cols)} definiciones")
    all_chunks += cols

    print("notas propias:")
    all_chunks += chunk_own_notes()

    df = pd.DataFrame(all_chunks)
    print(f"\ntotal: {len(df)} fragmentos")
    print(df.groupby(["kind"]).size())

    print("\ncalculando embeddings (la primera vez baja el modelo)…")
    model = SentenceTransformer(EMBED_MODEL)
    # normalize_embeddings=True hace que la similitud coseno sea un simple
    # producto punto, que es más rápido y evita normalizar después.
    vectors = model.encode(
        df["text"].tolist(),
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    df.to_parquet(KB / "chunks.parquet", index=False)
    np.save(KB / "embeddings.npy", vectors)
    print(f"\nlisto: {vectors.shape[0]} vectores de {vectors.shape[1]} dimensiones")


if __name__ == "__main__":
    build()
