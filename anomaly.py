"""Detección de anomalías sobre el catálogo de exoplanetas.

    python anomaly.py

Lee data/cache/pscomppars.csv (generado por fetch_data.py),
descarta planetas con variables incompletas, aplica Isolation Forest
y guarda los resultados con score y atribución por variable.

Dos decisiones clave que hay que poder defender:

1. Se aplica log a período, radio, masa y densidad, NO StandardScaler.
   Isolation Forest corta al azar dentro del rango de cada variable.
   Una transformación lineal (restar media, dividir por desvío) no
   cambia el resultado: los mismos puntos quedan del mismo lado del
   corte. Lo que sí importa es la forma de la distribución: si el
   período va de 0,1 a 100.000 días, casi todo está amontonado abajo
   y los cortes al azar caen en la zona vacía. Con log, el rango se
   reparte y los cortes son más útiles.

2. El score y la atribución son dos pasos distintos. El score viene
   del modelo mirando las 6 variables juntas (puede detectar rarezas
   de combinación). La atribución es posterior: z-score robusto por
   variable. Cuando el score es alto pero ningún z-score individual
   es extremo, la rareza está en la combinación — y esos son los
   casos más interesantes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

CACHE = Path("data/cache")
CATALOG = CACHE / "pscomppars.csv"

# Las 6 variables del modelo, en el mismo orden que en rareza.md.
FEATURES = ["pl_orbper", "pl_rade", "pl_bmasse", "pl_dens", "pl_eqt", "pl_orbeccen"]

# Variables a las que se les aplica log: las que tienen distribución
# muy sesgada (rango de varios órdenes de magnitud).
LOG_COLS = ["pl_orbper", "pl_rade", "pl_bmasse", "pl_dens"]

# Umbral de z-score para considerar una variable "extrema".
Z_THRESHOLD = 3.0

# Validado con test de estabilidad: con 300 el top 20 coincide 19/20
# con 500. Con 100 todavía se mueven 2 planetas.
N_ESTIMATORS = 300


def load_and_clean() -> pd.DataFrame:
    """Carga el catálogo y descarta planetas sin las 6 variables completas."""
    df = pd.read_csv(CATALOG)
    before = len(df)
    df = df.dropna(subset=FEATURES).copy()
    print(f"catálogo: {before} planetas, {len(df)} con las 6 variables completas")
    return df


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica log donde la distribución lo necesita.

    No se usa StandardScaler: Isolation Forest corta al azar dentro
    del rango de cada variable, así que una transformación lineal
    no cambia el ranking. Lo que importa es la forma.
    """
    X = df[FEATURES].copy()
    for col in LOG_COLS:
        # clip en un mínimo pequeño para evitar log(0)
        X[col] = np.log10(X[col].clip(lower=1e-6))
    return X


def score_anomalies(X: pd.DataFrame, n_estimators: int = N_ESTIMATORS) -> np.ndarray:
    """Corre Isolation Forest y devuelve un score entre 0 y 1.

    sklearn devuelve decision_function donde más negativo = más anómalo.
    Lo invertimos y normalizamos a [0, 1] para que sea más intuitivo:
    1 = máxima rareza, 0 = completamente típico.
    """
    # contamination=0.02: solo desplaza el umbral de la etiqueta binaria,
    # el ranking por score no cambia. El producto usa el ranking.
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=0.02,
        random_state=42,
    )
    model.fit(X)
    raw = model.decision_function(X)
    # Invertir (más negativo → más raro → score más alto) y normalizar a [0, 1]
    score = (raw.max() - raw) / (raw.max() - raw.min())
    return score


def attribute(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score robusto por variable: cuántas dispersiones se aleja de la mediana.

    Usa mediana y MAD (median absolute deviation) en vez de media y desvío
    porque son robustos a outliers — justamente lo que estamos buscando.
    """
    X = df[FEATURES].copy()
    zscores = pd.DataFrame(index=df.index)
    for col in FEATURES:
        median = X[col].median()
        mad = (X[col] - median).abs().median()
        if mad == 0:
            mad = X[col].std()
        zscores[f"z_{col}"] = ((X[col] - median) / mad).abs()

    return zscores


def top_two_drivers(row: pd.Series, z_cols: list[str]) -> str:
    """Las dos variables con mayor desvío absoluto.

    Si ninguna supera el umbral, la rareza está en la combinación
    de parámetros — el caso más interesante.
    """
    sorted_z = sorted(z_cols, key=lambda c: row[c], reverse=True)
    max_z = row[sorted_z[0]]
    if max_z < Z_THRESHOLD:
        return "combinación"
    top = [c.replace("z_", "") for c in sorted_z[:2]]
    return ", ".join(top)


def flag_quality(df: pd.DataFrame) -> pd.Series:
    """Marca planetas con datos sospechosos. No los descarta — los etiqueta.

    Tres señales de sospecha:
    - pl_controv_flag == 1: la comunidad cuestionó la confirmación
    - densidad fuera de rango físico (> 30 g/cm³ o < 0.01): no existe
      material conocido con esas densidades a escala planetaria
    - incertidumbre relativa > 50% en alguna de las 6 variables: la
      medición es tan imprecisa que el valor podría ser cualquier cosa
    """
    flags: list[str] = []
    for _, row in df.iterrows():
        warnings = []

        if row.get("pl_controv_flag") == 1:
            warnings.append("controvertido")

        if row["pl_dens"] > 30 or row["pl_dens"] < 0.01:
            warnings.append(f"densidad fuera de rango ({row['pl_dens']:.2f})")

        # Incertidumbre relativa alta en alguna variable del modelo
        for col in FEATURES:
            err1 = f"{col}err1"
            err2 = f"{col}err2"
            if err1 in df.columns and err2 in df.columns:
                e1 = abs(row.get(err1, 0) or 0)
                e2 = abs(row.get(err2, 0) or 0)
                val = abs(row[col]) if row[col] != 0 else 1e-10
                err_rel = max(e1, e2) / val
                if err_rel > 0.5:
                    warnings.append(f"{col} incertidumbre >{50}%")
                    break  # una basta para marcar

        flags.append("; ".join(warnings) if warnings else "")
    return pd.Series(flags, index=df.index, name="quality_flag")


def run(n_estimators: int = N_ESTIMATORS, top_n: int = 20):
    df = load_and_clean()
    X = prepare_features(df)

    print(f"\ncorriendo Isolation Forest ({n_estimators} árboles)…")
    df["anomaly_score"] = score_anomalies(X, n_estimators)

    print("calculando atribución por variable…")
    zscores = attribute(df)
    z_cols = zscores.columns.tolist()
    df = pd.concat([df, zscores], axis=1)

    df["anomaly_type"] = df.apply(lambda row: top_two_drivers(row, z_cols), axis=1)

    print("marcando datos sospechosos…")
    df["quality_flag"] = flag_quality(df)

    ranked = df.sort_values("anomaly_score", ascending=False)

    print(f"\n── top {top_n} más anómalos ──\n")
    for i, (_, row) in enumerate(ranked.head(top_n).iterrows(), 1):
        flag = f"  ⚠ {row['quality_flag']}" if row["quality_flag"] else ""
        print(f"{i:2d}. {row['pl_name']}{flag}")
        print(f"    score={row['anomaly_score']:.3f}  tipo={row['anomaly_type']}")
        print(f"    P={row['pl_orbper']:.1f}d  R={row['pl_rade']:.1f}Re  "
              f"M={row['pl_bmasse']:.1f}Me  ρ={row['pl_dens']:.2f}  "
              f"Teq={row['pl_eqt']:.0f}K  e={row['pl_orbeccen']:.2f}")
        print()

    top = ranked.head(top_n)
    n_flagged = (top["quality_flag"] != "").sum()
    n_combo = (top["anomaly_type"] == "combinación").sum()
    print(f"de los top {top_n}: {n_flagged} con datos sospechosos, "
          f"{n_combo} por combinación, {top_n - n_combo} por variable individual")

    return ranked


def stability_test(top_n: int = 20):
    """Compara el top N con distintas cantidades de árboles.

    Si el top se mantiene estable entre 100 y 300, no hace falta más.
    Corre rápido: Isolation Forest sobre 5.000 filas tarda milisegundos.
    """
    df = load_and_clean()
    X = prepare_features(df)

    tree_counts = [50, 100, 300, 500]
    tops: dict[int, set[str]] = {}

    for n in tree_counts:
        scores = score_anomalies(X, n_estimators=n)
        df_tmp = df.copy()
        df_tmp["anomaly_score"] = scores
        top_names = set(df_tmp.nlargest(top_n, "anomaly_score")["pl_name"])
        tops[n] = top_names

    print(f"\n── estabilidad del top {top_n} ──\n")
    print(f"{'árboles':>10s}  {'coinciden con 500':>20s}  {'planetas que cambian'}")
    for n in tree_counts:
        shared = len(tops[n] & tops[500])
        diff = tops[n] - tops[500]
        diff_str = ", ".join(sorted(diff)[:3])
        if len(diff) > 3:
            diff_str += f" (+{len(diff)-3} más)"
        print(f"{n:>10d}  {shared:>20d}/{top_n}  {diff_str if diff else '—'}")


if __name__ == "__main__":
    import sys
    if "--stability" in sys.argv:
        stability_test()
    else:
        run()
