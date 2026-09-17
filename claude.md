# CLAUDE.md — contexto del proyecto

Poné este archivo en la raíz del repo. Claude Code lo lee automáticamente al arrancar.

---

## Quién soy y por qué existe este proyecto

Soy Caterina, AI engineer. Construyo agentes en producción en una startup de educación: un sistema multiagente que acompaña a ingresantes universitarios durante la inscripción y detecta a los que están por abandonar.

Este proyecto es personal y tiene dos objetivos:
1. Aplicar lo que aprendí en un curso de AI engineering (hybrid search y chunking, orquestación, LangGraph con flujos cíclicos, evaluación y observabilidad, despliegue).
2. Tener algo propio y público para una entrevista técnica, donde me van a evaluar por qué tan a fondo entiendo lo que construí, no por el tamaño del proyecto.

**Implicancia directa para vos:** explicame las decisiones, no me des código que no pueda defender. Si hay una alternativa razonable, decime por qué elegimos una y no la otra. Yo tengo que poder contar cada línea.

---

## Qué es Odd Worlds

Una herramienta que responde, en lenguaje natural y en español, cuáles de los más de 6.000 exoplanetas confirmados son estadísticamente anómalos, en qué son anómalos, y cuáles de esos además se pueden observar.

**El usuario:** alguien que arma una propuesta de observación. El tiempo de telescopio es el recurso escaso. Hoy ese triage se hace bajando un CSV y abriendo un notebook.

**Lo que NO es:** un chatbot de astronomía. El modelo de lenguaje no aporta ni un dato. Interpreta la pregunta, elige el camino, y redacta con los números que devolvieron las herramientas.

---

## Las tres decisiones de producto

1. **"Raro" se calcula, no se opina.** Un planeta es anómalo si cae en una zona poco poblada del espacio de parámetros físicos. El score sale de un modelo.
2. **Se dice en qué es raro.** Cada resultado trae atribución por variable: qué característica lo empujó fuera de la distribución y cuánto.
3. **Raro no alcanza, tiene que ser observable.** Se cruza el score con la magnitud de la estrella y la profundidad del tránsito. Rareza sin factibilidad es curiosidad; con factibilidad es recomendación.

---

## Arquitectura

Un grafo de LangGraph. **El modelo interpreta y redacta; el grafo controla el flujo.** Todo el control de flujo es código testeable sin llamar a ningún modelo.

### Estado

`question`, `intent`, `filters`, `subset_size`, `attempts`, `relaxed`, `scored`, `kb_hits`, `answer`, `trace`.

### Nodos

- `route` — clasifica la intención con un LLM y salida estructurada: `knowledge`, `analysis`, `followup`, más un campo de confianza. Si la confianza es baja devuelve `ask_user` y repregunta. **Esto no es determinista y está bien que no lo sea**: clasificar lenguaje natural requiere un modelo. Lo determinista es qué pasa después.
- `kb_search` — búsqueda híbrida sobre la base de conocimiento.
- `explain` — redacta en lenguaje llano. Prompt propio: cálido, sin jerga, sin citas textuales, y termina proponiendo dos preguntas que el sistema sí puede analizar.
- `parse_filters` — traduce la pregunta a filtros estructurados.
- `query` — filtra el catálogo, guarda `subset_size`.
- `relax` — ensancha un filtro un escalón, suma a `attempts`, anota qué aflojó.
- `score` — Isolation Forest más atribución.
- `observability` — marca cuáles son observables de verdad.
- `report` — redacta con los números. Si hubo que aflojar filtros, lo dice.
- `followup` — responde sobre lo que ya está en `scored`, sin consultar nada nuevo.

### El ciclo

Después de `query`: si `subset_size < 50` y `attempts < 3`, va a `relax` y vuelve a `query`. Si se acabaron los intentos, va a `report` con la nota de datos insuficientes. **Nunca puntúa con datos insuficientes y nunca queda colgado.**

El umbral de 50 no es arbitrario: por debajo de unas decenas de objetos, Isolation Forest arma sus árboles sobre tan pocos puntos que todo parece anómalo. Hay que demostrarlo empíricamente con submuestras de 20, 50 y 200 y dejarlo en el README.

---

## La base de conocimiento

**Por qué existe:** sin conocimiento previo el usuario no sabe qué preguntar, y cualquier filtro que se le ocurra probablemente deje pocos planetas. La capa de conocimiento explica el dominio y sugiere qué preguntar.

**Fuentes:** páginas de la NASA sobre tipos de exoplanetas y panorama general, la documentación de columnas del NASA Exoplanet Archive, y un documento propio (`rareza.md`) que define qué considera raro este sistema.

**Dos estrategias de chunking, y esto es a propósito:**
- Prosa: corte por sección, con el título del documento y de la sección repetidos al principio de cada fragmento. Un fragmento que dice "orbitan tan cerca que la temperatura llega a miles de grados" es inútil si no dice arriba de qué habla.
- Definiciones de columnas: un fragmento por columna, sin cortar. Cada definición ya es una unidad completa.

**Búsqueda híbrida:** BM25 más similitud coseno sobre embeddings, fusionados con Reciprocal Rank Fusion (k=60). Semántica sola falla con términos exactos como `pl_orbeccen`; palabras clave solas fallan cuando alguien dice "planetas que se achicharran" y el documento dice "hot Jupiter".

**Embeddings multilingües y locales** (`paraphrase-multilingual-MiniLM-L12-v2`). Multilingüe porque la fuente está en inglés y el usuario pregunta en español, así que el espacio vectorial tiene que ser compartido; traducir agregaría un punto de falla entre la fuente y la respuesta. Locales porque no gastan API, funcionan sin internet y sacan una llamada externa del camino crítico.

**Sin vector store.** Con ~300 fragmentos, la búsqueda exhaustiva en numpy es exacta y más rápida que el overhead de una base. Va al README como decisión.

---

## Tono de las respuestas

**Dos prompts distintos, nunca uno solo.** Un prompt optimizado para dos objetivos promedia y no logra ninguno.

- `explain`: para alguien curioso sin formación técnica. Sin jerga, sin citar textual, con comparaciones cotidianas, y terminando siempre con dos preguntas concretas que el sistema pueda analizar. Las fuentes van abajo como referencia.
- `report`: preciso, con los números, sin adornos.

---

## Stack

Python 3.12. LangGraph para el grafo. Gemini para los LLM (hay API key con crédito limitado, no derrochar llamadas). sentence-transformers para embeddings locales. rank-bm25. scikit-learn para Isolation Forest. pandas. Datos en archivos (parquet, npy, csv), sin base de datos. Checkpointer de LangGraph con SQLite para persistir conversaciones.

---

## Estado actual

- [x] Diseño cerrado
- [ ] `kb_build.py` corriendo y KB construida
- [ ] `kb_search.py` validado con las tres consultas de prueba
- [ ] `fetch_data.py` y `anomaly.py`
- [ ] `graph.py`
- [ ] Evals
- [ ] Front
- [ ] README

**Orden innegociable:** cada pieza funciona sola antes de integrarse. Si armamos el grafo antes de que la KB y el modelo anden por separado, debuggeamos cinco cosas a la vez.

---

## Cómo quiero que trabajes conmigo

- Explicá antes de escribir. Si el cambio es grande, decime el plan primero.
- Comentá el código en español, y comentá el **porqué**, no el qué.
- No agregues dependencias sin decirme para qué.
- No agregues complejidad que no pedí: nada de vector store, deploy, autenticación, multiagente ni fine-tuning.
- Si algo que escribí está mal o hay una forma mejor, decímelo directamente.
- Si te falta un dato para decidir, preguntame en vez de asumir.
- Estoy en Windows con Git Bash. Las rutas van con barra normal.

---

## Fuera de alcance

Deploy automático, autenticación, base de datos relacional, streaming de respuestas, sistema multiagente, SHAP, reranker cross-encoder, MCP. Todo eso va al README como próximos pasos con su justificación.