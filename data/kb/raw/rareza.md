# Qué considera raro este sistema

Documento propio del proyecto. Define el criterio que usa Odd Worlds para decir
que un exoplaneta es anómalo. Las fuentes están al final.

---

## La idea

Un exoplaneta es "raro" cuando sus características físicas lo ubican en una zona
poco poblada del catálogo. No es una opinión ni una selección editorial: se
calcula comparando cada planeta contra los más de 6.000 confirmados hasta hoy.

La NASA clasifica los exoplanetas en cuatro tipos: gigante gaseoso, neptuniano,
súper Tierra y terrestre, con subcategorías como los mini Neptunos dentro de esos
grupos. Lo raro es lo que se aleja del centro de esa distribución.

---

## Qué variables se miran

Seis, todas físicas y todas disponibles en la tabla PSCompPars del NASA Exoplanet
Archive:

- **`pl_orbper`** — período orbital en días: lo que tarda el planeta en dar una
  vuelta completa alrededor de su estrella.
- **`pl_rade`** — radio en radios terrestres.
- **`pl_bmasse`** — masa en masas terrestres. Es la mejor estimación disponible;
  según el método de detección puede ser la masa real o una cota inferior.
- **`pl_dens`** — densidad en g/cm³: cuánta masa hay por unidad de volumen. Dice
  de qué está hecho.
- **`pl_eqt`** — temperatura de equilibrio en Kelvin: la que tendría el planeta
  modelado como cuerpo negro calentado solamente por su estrella.
- **`pl_orbeccen`** — excentricidad: cuánto se desvía la órbita de un círculo
  perfecto. Cero es circular.

---

## Cómo se calcula

Un modelo de detección de anomalías, Isolation Forest, asigna a cada planeta un
puntaje de rareza. La intuición es simple: si un punto se puede separar del resto
con pocos cortes, es raro; si hacen falta muchos, es típico.

Además se calcula, variable por variable, cuántas desviaciones se aleja ese
planeta de lo habitual. Eso permite decir no solo cuán raro es, sino en qué.

---

## Una zona rara que la ciencia ya identificó

No hace falta creerle al modelo para saber que hay huecos en la distribución. Hay
uno documentado: el **valle de radios**, o *Fulton gap*, llamado así por Benjamin
Fulton, autor principal del trabajo que lo describió. Datos de Kepler mostraron
que los planetas de entre 1,5 y 2 veces el diámetro de la Tierra son raros.

Una explicación posible es que ese sea un tamaño crítico en la formación
planetaria: los que lo superan atraen rápidamente atmósferas espesas de hidrógeno
y helio y se inflan hasta volverse gaseosos, mientras que los más chicos no logran
retener esa atmósfera y quedan rocosos. Otra posibilidad es que los más chicos que
orbitan cerca de su estrella sean núcleos de mundos tipo Neptuno a los que la
estrella les arrancó la atmósfera. Explicarlo bien va a requerir entender mucho
mejor cómo se forman los sistemas planetarios.

Esto importa para el producto: **las zonas poco pobladas del espacio de parámetros
son objeto de estudio activo, no una curiosidad estadística.**

---

## Tipos de rareza que ya tienen nombre

Sirven como referencia de qué clase de cosas aparecen cuando uno busca lo atípico.

**Júpiter calientes.** Gigantes gaseosos que orbitan tan cerca de su estrella que
sus temperaturas trepan a miles de grados. Fueron de los primeros tipos hallados,
justamente porque son fáciles de detectar: su masa hace tambalear visiblemente a
la estrella. Algunos completan una órbita en apenas 18 horas. No hay nada
parecido en nuestro sistema solar, donde los planetas más cercanos al Sol son
rocosos y están mucho más lejos.

**El más caliente de todos.** KELT-9 b es el gigante gaseoso más caliente
encontrado hasta ahora, más caliente que la mayoría de las estrellas, y su calor
directamente desarma las moléculas del lado que da a su estrella.

**Planetas que se están muriendo.** WASP-12 b es un Júpiter caliente que orbita
tan cerca que su estrella lo está desgarrando. Tarda 1,1 días en dar una vuelta.

**Núcleos desnudos.** TOI-849 b podría ser el núcleo expuesto de un gigante
gaseoso al que su estrella le voló la atmósfera.

**Densidades imposibles.** TOI-3757 b es un gigante gaseoso con la densidad de un
malvavisco, el planeta de menor densidad detectado alrededor de una enana roja.
Y en el catálogo hay planetas con la densidad del telgopor, mundos de lava
cubiertos de mares fundidos, y núcleos de planetas que siguen orbitando sus
estrellas.

---

## La advertencia más importante: raro en el catálogo no es raro en el universo

El catálogo está sesgado por cómo detectamos planetas, y eso hay que decirlo.

Los planetas grandes son mucho más fáciles de detectar que los chicos, con los dos
métodos principales. Con el método de tránsito, un planeta rocoso del tamaño de la
Tierra se nota mucho mejor contra una estrella chica como una enana roja, porque
tapa una fracción proporcionalmente mayor de su luz. Una estrella del tamaño del
Sol se oscurece mucho menos cuando pasa un planeta como la Tierra, y eso hace su
tránsito mucho más difícil de detectar.

Además está el problema del tiempo: un planeta que orbite a la distancia de la
Tierra tarda unos 365 días en dar una vuelta, y para confirmarlo hay que observar
esa estrella durante todo ese tiempo y ver dos o tres tránsitos. El resultado es
que encontramos muchos planetas rocosos chicos, pero casi todos alrededor de
enanas rojas.

Como dice Jessie Christiansen, investigadora del Exoplanet Science Institute de la
NASA, los sistemas planetarios que estamos encontrando no se parecen al nuestro, y
todavía no sabemos si eso es importante.

**Conclusión operativa para este sistema:** cuando Odd Worlds dice que un planeta
es raro, quiere decir raro *respecto de lo que hemos podido observar hasta hoy*.
No es lo mismo que raro en la naturaleza. De hecho, la Tierra misma podría ser el
verdadero bicho raro de la galaxia, o no, y por ahora no hay datos suficientes
para saberlo.

---

## Raro tampoco significa importante

Que un planeta sea raro no lo hace más habitable ni mejor candidato para buscar
vida. Y a veces la rareza es un error de medición y no una propiedad del planeta.

Por eso el sistema mira dos cosas más:

**Si sus parámetros están en discusión.** La tabla trae `pl_controv_flag`, que
marca los planetas cuya confirmación fue cuestionada en la literatura publicada,
y columnas de incertidumbre para cada parámetro. Un planeta anómalo cuya masa
tiene una incertidumbre enorme es sospechoso, no interesante.

**Si vale la pena observarlo.** Un planeta rarísimo alrededor de una estrella muy
tenue no sirve para pedir tiempo de telescopio. La tabla trae `pl_tsm` y `pl_esm`,
las métricas de espectroscopía de transmisión y de emisión de Kempton y otros
(2018), que es el estándar que usa la comunidad para priorizar objetivos de
seguimiento. Y trae `pl_nobs_jwst_tran`, `pl_nobs_jwst_e` y `pl_nobs_jwst_pc`, la
cantidad de observaciones ya aprobadas del JWST para ese planeta.

Con eso, la recomendación de Odd Worlds no es "este planeta es raro", sino
**"este planeta es raro, se puede observar, y todavía nadie pidió mirarlo"**.

---

## Fuentes

- NASA, *Exoplanets*: https://science.nasa.gov/exoplanets/
- NASA, *What is an Exoplanet?* (tipos, Fulton gap): https://science.nasa.gov/exoplanets/facts/
- NASA, *Exoplanet Types*: https://science.nasa.gov/exoplanets/planet-types/
- NASA, *What is a Gas Giant?* (Júpiter calientes): https://science.nasa.gov/exoplanets/gas-giant/
- NASA, *What is a Super-Earth?*: https://science.nasa.gov/exoplanets/super-earth/
- NASA, *Strange New Worlds* (KELT-9 b, WASP-12 b, TOI-849 b, TOI-3757 b): https://science.nasa.gov/exoplanets/immersive/strange-new-worlds/
- NASA, *Is Earth an Oddball?* (sesgos de detección): https://science.nasa.gov/universe/exoplanets/is-earth-an-oddball/
- NASA Exoplanet Archive, *PS and PSCompPars Table Definitions*: https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html