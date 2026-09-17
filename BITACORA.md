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

### Por que 384 dimensiones

No lo elegimos nosotros: es un numero fijo del modelo. Cuando entrenaron `paraphrase-multilingual-MiniLM-L12-v2`, decidieron que cada texto se represente con 384 numeros. Otros modelos usan 768 o 1536 — mas dimensiones puede capturar mas matices pero pesa mas y es mas lento. Con ~300 fragmentos, 384 sobra. El modelo se eligio por tres criterios: multilingue (español-ingles), liviano (corre en CPU sin GPU), y probado (es uno de los mas usados en la libreria `sentence-transformers`).

### Por que busqueda hibrida (BM25 + semantica)

- **Solo semantica falla con terminos exactos:** `pl_orbeccen` no se "parece" a nada semanticamente, hay que encontrarlo por coincidencia literal de caracteres.
- **Solo palabras clave falla con lenguaje natural:** "planetas que se achicharran" no comparte una sola palabra con "Jupiter caliente".
- **Las dos juntas cubren los dos casos.** Se hacen las dos busquedas en paralelo y se fusionan con Reciprocal Rank Fusion (RRF, k=60).

### Por que RRF y no otra forma de fusionar

No se pueden sumar los puntajes directamente: BM25 da numeros tipo 14.7 y coseno da 0.62 — escalas incomparables. La alternativa seria normalizar los dos a [0,1] y sumar con un peso (Convex Combination), pero eso requiere calibrar ese peso y es fragil. RRF ignora los valores y usa solo la posicion en cada ranking: cada fragmento recibe `1/(60 + posicion)` en cada lista y se suman. El 60 es el valor estandar del paper original. No hay hiperparametro que ajustar.

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

### Paso 6: validacion de la busqueda

Tres consultas de prueba, cada una diseñada para estresar un aspecto distinto:

| Consulta | Que prueba | Resultado |
|---|---|---|
| `"que es un jupiter caliente"` | Semantica multilingue: pregunta en español, fuentes en ingles | Encontro fragmentos sobre hot Jupiters en ingles (coseno 0.44) y el parrafo de rareza.md en español (BM25 16.53). La fusion RRF combino las dos señales. |
| `"pl_orbeccen"` | Termino tecnico exacto, sin significado semantico | Primer resultado: la definicion exacta de esa columna (BM25 6.06). Un modelo semantico solo no lo hubiera encontrado porque el termino no "significa" nada en lenguaje natural. |
| `"planetas con densidad muy baja"` | Lenguaje natural sobre un concepto que no aparece literal | Coseno alto (0.63) en resultados sobre tipos de planetas y variables fisicas, a pesar de que ningun documento dice literalmente "densidad muy baja". |

Las tres juntas demuestran que la busqueda hibrida cubre casos que cada metodo por separado no puede.

---

## Catalogo y modelo de anomalias

### fetch_data.py — el catalogo

Se baja la tabla PSCompPars del NASA Exoplanet Archive via su API TAP (Table Access Protocol). Es un GET con una query SQL, no necesita API key. Se piden solo las columnas que el proyecto usa, no las ~200 de la tabla completa.

Resultado: 6.366 planetas. De esos, 5.118 tienen las 6 variables del modelo completas. La variable con peor cobertura es `pl_orbeccen` (excentricidad, 83%) — tiene sentido porque es la mas dificil de medir, necesitas observar muchas orbitas.

### anomaly.py — Isolation Forest y atribucion

**Por que log y no StandardScaler.** Isolation Forest NO usa distancias (no es como KNN ni k-means). Lo que hace es elegir una variable al azar y cortar en un valor al azar entre el minimo y el maximo. Una transformacion lineal como StandardScaler no cambia nada: los mismos puntos quedan del mismo lado del corte. Lo que si importa es la forma de la distribucion. Si el periodo orbital va de 0,1 a 100.000 dias, casi todo esta amontonado abajo y los cortes al azar caen en la zona vacia. Con log, el rango se reparte y los cortes son mas utiles. Se aplica log a periodo, radio, masa y densidad (las que tienen distribucion sesgada de varios ordenes de magnitud).

**Atribucion: z-score robusto.** El score y la explicacion son dos pasos distintos. El score viene del modelo mirando las 6 variables juntas (puede detectar rarezas de combinacion). La atribucion es posterior: por cada variable, se calcula cuantas dispersiones se aleja de la mediana (usando mediana y MAD, que son robustos a outliers).

**Anomalias por combinacion: el caso mas interesante.** Cuando el score es alto pero ningun z-score individual es extremo, significa que la rareza esta en la combinacion de parametros — un planeta con radio normal y masa normal pero cuya combinacion es imposible. Esos son justamente los casos que un humano filtrando por columnas nunca encontraria. El sistema los marca explicitamente como "anomalo por combinacion de parametros".

**Cantidad de arboles: validado empiricamente.** El default de scikit-learn es 100, pero "porque es el default" no es una respuesta. Se corrio con 50, 100, 300 y 500 arboles comparando cuantos planetas del top 20 se mantienen contra la corrida de 500:

| Arboles | Coinciden con 500 | Observacion |
|---|---|---|
| 50 | 16/20 | Inestable, cambian 4 |
| 100 | 18/20 | Casi, pero todavia se mueven 2 |
| 300 | 19/20 | Estable, solo cambia 1 en el borde |
| 500 | 20/20 | Referencia |

**Decision: 300 arboles.** De 300 a 500 no se gana nada. El que cambia con 300 (TOI-201 c) esta en la posicion 20, al borde del corte.

**Datos faltantes: descartar, no imputar.** De los 6.366 planetas, 5.118 tienen las 6 variables completas. Se descartan los incompletos. Imputar inventa datos donde no los hay, y un planeta con excentricidad imputada que despues sale "anomalo en excentricidad" es un falso positivo generado por nosotros. Es mas honesto decir "se analizaron 5.118 de 6.366".

**Contamination = 0.02.** Este parametro solo define que proporcion se etiqueta como anomala. Pero el ranking por score no cambia — y el producto usa el ranking, no la etiqueta. La eleccion no es critica, y saber decir eso demuestra que se entendio el parametro.

### Filtro de calidad

La primera corrida mostro que 11 de los top 20 tenian datos sospechosos. Sin este filtro, alguien miraria el ranking y pensaria que Kepler-80 f con densidad 703 g/cm³ es un hallazgo, cuando en realidad es un dato roto (el hierro tiene densidad ~8).

Se marcan (no se descartan) planetas con tres criterios:
- `pl_controv_flag == 1`: la comunidad cuestiono la confirmacion
- Densidad fuera de rango fisico (> 30 g/cm³ o < 0.01)
- Incertidumbre relativa > 50% en alguna de las 6 variables

Resultado del top 20 con flags: 11 sospechosos, 9 limpios. Los limpios (HD 128717 b, HD 110537 b, KIC 3526061 b, TOI-1994 b, etc.) son los raros de verdad.

**0 anomalias por combinacion en el top 20** — esperable. Los mas extremos del catalogo completo tienen alguna variable gritando. Las anomalias por combinacion apareceran cuando el grafo corra sobre subconjuntos filtrados, donde los extremos obvios ya quedaron afuera.

### Por que anomaly.py se corre ahora si la rareza depende de la consulta

Se corre ahora sobre el catalogo completo para verificar que la herramienta funciona: que los scores tienen sentido, que el filtro de calidad atrapa los datos rotos, que 300 arboles son estables. Es testing.

En produccion, el grafo corre Isolation Forest sobre el subconjunto filtrado de cada consulta. Si alguien pregunta "planetas terrestres alrededor de estrellas frias", la rareza se calcula dentro de ese grupo, no del catalogo entero. Un planeta puede ser normal entre todos pero rarisimo entre los terrestres.

Lo que esta hardcodeado es la herramienta (las 6 variables, el log, la atribucion). El resultado se recalcula cada vez.

### Por que 300 arboles funciona tambien con subconjuntos chicos

El numero de arboles es para promediar la aleatoriedad de los cortes, no depende del tamano de los datos. Con menos datos cada arbol es mas simple, pero seguis necesitando promediar muchos para estabilizar. El piso es otro: si el subconjunto tiene menos de 50 planetas, Isolation Forest no sirve (todo parece raro). Por eso el grafo chequea `subset_size < 50` y afloja filtros o avisa.

### Por que los datos malos son un problema real

Los exoplanetas no se ven directamente. Se detectan por efectos indirectos:
- **Transito**: el brillo de la estrella baja cuando el planeta pasa por delante. De cuanto baja, se calcula el radio. Pero si la estrella es variable o hay dos estrellas pegadas en la imagen, podes confundir cosas.
- **Velocidad radial**: la estrella "bambolea" por la gravedad del planeta. De ahi se saca la masa. Pero manchas estelares tambien causan bamboleo.

El resultado: algunos "planetas" del catalogo pueden no ser planetas, y otros tienen mediciones muy imprecisas. Una densidad de 703 g/cm³ es fisicamente imposible (el osmio, el material mas denso en condiciones normales, tiene ~22.6). Por eso marcamos tres cosas: confirmacion cuestionada, densidad imposible, e incertidumbre enorme.

### Por que no metemos mas papers y datos a la KB

La KB tiene un proposito acotado: que el usuario entienda que tipos de planetas existen, que significan las columnas, y que puede preguntar. No es una enciclopedia. Con 130 fragmentos bien curados la busqueda es precisa; con 500 papers, los fragmentos relevantes se pierden entre cientos irrelevantes.

Los papers de controversia son academicos, muchos detras de paywall, y el sistema no necesita explicar por que un planeta fue cuestionado — solo marcarlo. Agregar mas fuentes (como el paper de Kempton+2018 sobre metricas de observabilidad) es una mejora futura que va al README.

### KB y catalogo son dos capas distintas a proposito

- **KB** (kb_build.py) = texto, conocimiento → "que es un Jupiter caliente", "que significa pl_orbeccen"
- **Catalogo** (fetch_data.py) = numeros, datos → "el planeta X tiene masa 140, radio 2.6"

El agente usa las dos pero para cosas distintas: la KB para entender y explicar, el catalogo para calcular y filtrar.

---

## Que sigue

- [x] Validar `kb_search.py` con consultas de prueba (termino tecnico, lenguaje natural, nombre de columna)
- [x] `fetch_data.py` — bajar el catalogo de exoplanetas del NASA Exoplanet Archive
- [x] `anomaly.py` — Isolation Forest con 300 arboles, atribucion, filtro de calidad
- [ ] `graph.py` — el grafo de LangGraph que une todo
- [ ] `prompts.py` — los prompts de explain y report
- [ ] `app.py` — interfaz web
- [ ] Evals — 20 preguntas con resultado esperado
- [ ] README — con todas las decisiones documentadas
