# Odd Worlds — Bitacora tecnica

Registro de decisiones, pasos y explicaciones del proyecto.
Tecnico pero explicado simple — para estudiar antes de la entrevista y como base para un paper.

Ultima actualizacion: 2026-09-17

---

## Que es Odd Worlds

**El problema.** Hay mas de 6.000 exoplanetas confirmados. Alguien que quiere armar una propuesta de observacion (pedir tiempo de telescopio) necesita encontrar los que son estadisticamente raros *y* que ademas se pueden observar. Hoy eso se hace bajando un CSV y abriendo un notebook a mano.

**La solucion.** Una herramienta que responde en lenguaje natural y en espanol: cuales planetas son anomalos, en que son anomalos, y cuales de esos vale la pena observar.

**Lo que NO es.** Un chatbot de astronomia. El modelo de lenguaje (Gemini) no aporta ni un dato: interpreta la pregunta del usuario, elige el camino en el grafo, y redacta la respuesta con los numeros que devolvieron las herramientas. Todos los datos salen del catalogo publico de la NASA.

**Las cuatro reglas de producto:**

1. **"Raro" se calcula, no se opina.** El score sale de Isolation Forest, un modelo de deteccion de anomalias.
2. **Se dice en que es raro.** Cada resultado trae atribucion por variable: que caracteristica lo empujo fuera de la distribucion.
3. **Raro no alcanza: tiene que ser observable y no estar ya observado.** Se usan las metricas estandar de la comunidad (TSM/ESM de Kempton+2018) y se cruza con observaciones JWST ya aprobadas.
4. **Se distingue anomalia real de mala medicion.** Planetas con parametros en discusion o incertidumbre enorme se marcan, no se descartan en silencio.

---

## Decisiones de arquitectura

### Por que un grafo y no una cadena lineal

El flujo tiene un ciclo: si la consulta del usuario devuelve muy pocos planetas (<50), el sistema afloja los filtros y vuelve a consultar, hasta 3 veces. Una cadena lineal no puede hacer eso. LangGraph permite definir ese ciclo como codigo testeable.

### Por que cada pieza se construye por separado

Orden innegociable: KB primero, despues catalogo + modelo de anomalias, recien ahi el grafo. Si armas el grafo antes, estas debuggeando cinco piezas a la vez sin saber cual falla.


### Por que sin vector store

Con ~300 fragmentos, la busqueda exhaustiva en numpy es exacta y mas rapida que el overhead de levantar una base vectorial. 

### Por que embeddings locales y no via API

Tres razones: no gastan credito de API, funcionan sin internet, y sacan una llamada externa del camino critico. El modelo pesa ~450 MB pero se baja una sola vez.

### Por que el modelo de embeddings es multilingue

`paraphrase-multilingual-MiniLM-L12-v2` en vez de `all-MiniLM-L6-v2`. Las fuentes estan en ingles y el usuario pregunta en espanol. Si usas un modelo solo en ingles, "planetas que se achicharran" y "hot Jupiter" caen en zonas distintas del espacio vectorial. El modelo multilingue fue entrenado con pares de textos en 50+ idiomas, asi que los dos caen cerca.

### Por que busqueda hibrida (BM25 + semantica)

- **Solo semantica falla con terminos exactos:** `pl_orbeccen` no se "parece" a nada semanticamente, hay que encontrarlo por coincidencia literal de caracteres.
- **Solo palabras clave falla con lenguaje natural:** "planetas que se achicharran" no comparte una sola palabra con "Jupiter caliente".
- **Las dos juntas cubren los dos casos.** Se fusionan con Reciprocal Rank Fusion (RRF, k=60), que usa la posicion en cada ranking en vez del puntaje crudo (porque BM25 da numeros tipo 14.7 y coseno da 0.62 — escalas incomparables).

### Por que dos estrategias de chunking

Hay dos tipos de documento, y cortarlos igual seria un error:

- **Prosa** (paginas de la NASA): se corta por seccion markdown. Cada fragmento lleva arriba el titulo del documento y de la seccion, porque un fragmento que dice "orbitan tan cerca que la temperatura llega a miles de grados" es inutil si no dice de que habla. Si una seccion es muy larga, se parte con solapamiento de 50 palabras.
- **Definiciones de columnas** (tabla del archivo de la NASA): un fragmento por columna, sin cortar. Cada definicion ya es una unidad completa y corta — cortarla por tamano seria romperla.

### Por que dos prompts distintos para las respuestas

Un prompt optimizado para dos objetivos promedia y no logra ninguno:
- `explain`: para alguien curioso sin formacion tecnica. Sin jerga, con comparaciones cotidianas, termina con dos preguntas que el sistema si puede analizar.
- `report`: preciso, con los numeros, sin adornos.

---

## Base de conocimiento — lo que hicimos

### Paso 1: estructura de archivos

```
data/kb/
  raw/          <- texto crudo de cada fuente, legible por humanos
  chunks.parquet <- fragmentos con metadatos
  embeddings.npy <- matriz de vectores
```

### Paso 2: fuentes

7 paginas de prosa de la NASA + la tabla de definiciones de columnas del Exoplanet Archive + `rareza.md` (documento propio que define que es "raro" para el sistema).

Las fuentes estan en una whitelist explicita en el codigo (`PROSE_SOURCES` y `COLUMNS_SOURCE`). No se sigue ningun link encontrado dentro de las paginas — nada de crawling.

### Paso 3: descarga con cache

`trafilatura` extrae el texto limpio de cada pagina HTML (saca menus, banners, scripts, publicidad y deja solo el contenido). Se guarda en `data/kb/raw/` como markdown. Si el archivo ya existe, no vuelve a pedir nada — asi se puede reconstruir la KB sin internet.

### Paso 4: chunking

Se generaron **130 fragmentos**: 71 de concepto (prosa) y 59 de columna (definiciones).

### Paso 5: embeddings

Modelo `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones, normalizado (asi el producto punto es equivalente a similitud coseno, mas rapido). Se guarda como `.npy`.

El modelo se descarga a `.venv/huggingface/` (configurado con `HF_HOME` para que quede dentro del proyecto y no en la carpeta global del usuario).

---

## Que sigue

- [ ] Validar `kb_search.py` con consultas de prueba (termino tecnico, lenguaje natural, nombre de columna)
- [ ] `fetch_data.py` — bajar el catalogo de exoplanetas del NASA Exoplanet Archive
- [ ] `anomaly.py` — Isolation Forest + atribucion por variable
- [ ] `graph.py` — el grafo de LangGraph que une todo
- [ ] `prompts.py` — los prompts de explain y report
- [ ] `app.py` — interfaz web
- [ ] Evals — 20 preguntas con resultado esperado
- [ ] README — con todas las decisiones documentadas
