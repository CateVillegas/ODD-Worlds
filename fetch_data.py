"""Baja el catálogo de exoplanetas del NASA Exoplanet Archive.

    python fetch_data.py

Deja un CSV en data/cache/pscomppars.csv con una fila por planeta.
Se usa la tabla PSCompPars, que trae el mejor valor disponible de cada
parámetro por planeta (compilado de todas las publicaciones).

Si el archivo ya existe, no vuelve a bajar nada. Para forzar una
actualización, borralo a mano y corré de nuevo.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

CACHE = Path("data/cache")
OUT = CACHE / "pscomppars.csv"

TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

# Las columnas que necesitamos, agrupadas por para qué las usamos.
COLUMNS = [
    # ── identificación ──
    "pl_name",
    "hostname",
    "discoverymethod",
    "disc_year",

    # ── las 6 variables del modelo de anomalías ──
    "pl_orbper",
    "pl_rade",
    "pl_bmasse",
    "pl_dens",
    "pl_eqt",
    "pl_orbeccen",

    # ── incertidumbres de esas 6 (para marcar mediciones dudosas) ──
    "pl_orbpererr1", "pl_orbpererr2",
    "pl_radeerr1", "pl_radeerr2",
    "pl_bmasseerr1", "pl_bmasseerr2",
    "pl_denserr1", "pl_denserr2",
    "pl_eqterr1", "pl_eqterr2",
    "pl_orbeccenerr1", "pl_orbeccenerr2",

    # ── observabilidad (métricas estándar de Kempton+2018) ──
    "pl_tsm",
    "pl_esm",

    # ── controversia ──
    "pl_controv_flag",

    # ── datos de la estrella (para contexto en el reporte) ──
    "st_teff",
    "st_rad",
    "st_mass",
    "sy_vmag",
    "sy_kmag",
]

QUERY = f"SELECT {','.join(COLUMNS)} FROM pscomppars"


def fetch():
    CACHE.mkdir(parents=True, exist_ok=True)

    if OUT.exists():
        df = pd.read_csv(OUT)
        print(f"cache encontrado: {len(df)} planetas en {OUT}")
        return df

    print("bajando catálogo del NASA Exoplanet Archive…")
    resp = requests.get(
        TAP_URL,
        params={"query": QUERY, "format": "csv"},
        timeout=120,
        headers={"User-Agent": "odd-worlds/0.1"},
    )
    resp.raise_for_status()

    OUT.write_text(resp.text, encoding="utf-8")
    df = pd.read_csv(OUT)

    print(f"descargado: {len(df)} planetas")
    print(f"\ncobertura de las 6 variables del modelo:")
    for col in ["pl_orbper", "pl_rade", "pl_bmasse", "pl_dens", "pl_eqt", "pl_orbeccen"]:
        n = df[col].notna().sum()
        print(f"  {col:20s} {n:>5d} / {len(df)}  ({100*n/len(df):.0f}%)")

    completas = df[["pl_orbper", "pl_rade", "pl_bmasse", "pl_dens", "pl_eqt", "pl_orbeccen"]].dropna()
    print(f"\nplanetas con las 6 variables completas: {len(completas)}")

    return df


if __name__ == "__main__":
    fetch()
