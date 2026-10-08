# Laboratorio 3 — Sistema de búsqueda de estudiantes
### Lista vs Árbol Binario de Búsqueda (ABB) vs Árbol B+

## Uso de herramientas de IA

Se usó un asistente de IA para ayudar a diseñar la metodología estadística, depurar los experimentos y estructurar la redacción final de este documento. Sin embargo, todos los datos, gráficas y conclusiones fueron ejecutados y verificados en esta máquina local con el script principal del laboratorio.

---

## 1. Problema y objetivo

Se busca construir un sistema que permita buscar estudiantes por ID, insertar nuevos registros y listar todos los estudiantes en orden ascendente por ID, implementado con tres estrategias distintas:

- Lista
- Árbol Binario de Búsqueda (ABB)
- Árbol B+

El objetivo del laboratorio no es solo implementar las estructuras, sino comparar experimentalmente cómo cambia el tiempo de ejecución de cada operación a medida que crece el tamaño de entrada `N`, cómo influye el orden de inserción y cómo varía el volumen de búsquedas `M`.

Se prueba la diferencia entre la complejidad teórica y el comportamiento real del código, usando valores reproducibles y métricas estadísticas.

---

## 2. Estructuras implementadas

| Estructura | Buscar | Insertar | Listar (orden ascendente) |
|---|---|---|---|
| Lista | O(n) — recorrido lineal | O(1) — agrega al final | O(n log n) — ordena sobre la lista |
| ABB | O(log n) en promedio; O(n) si degenera | O(log n) en promedio; O(n) si degenera | O(n) — recorrido in-order |
| B+ | O(log n) con nodos internos y hojas enlazadas | O(log n) con splits | O(n) recorriendo hojas enlazadas |

### Observación clave

La implementación del ABB no incluye rebalanceo (`AVL`, `Red-Black`, etc.). Eso hace que el rendimiento dependa mucho del orden de inserción:

- si los datos llegan aleatorios, el árbol se comporta razonablemente bien;
- si llegan ya ordenados, la altura crece casi linealmente y el árbol se degenera.

En cambio, el B+ se auto-balancea y mantiene una altura mucho más estable, sin depender de cómo entren los IDs.

---

## 3. Código principal y archivos generados

### Archivos clave del repositorio

- `analisis_escalabilidad_completo.py`: script principal del laboratorio.
- `README.md`: documentación del proyecto.
- `resultados_lab3/`: carpeta con resultados experimentales y gráficos generados.

### Salidas reales generadas por el script

#### Gráficas

- `figA_busqueda_aleatorio.png`
- `figA2_busqueda_por_estructura.png`
- `figA3_zoom_abb_vs_bplus.png`
- `figB_busqueda_ordenado.png`
- `figC_construccion_gran_escala.png`
- `figD_variacion_M.png`
- `figE_altura_vs_busqueda.png`
- `figF_listar.png`
- `figG_busqueda_M_calibrado.png`

#### CSVs

- `A_busqueda_aleatorio_raw.csv`
- `A_busqueda_aleatorio_agg.csv`
- `A_altura_aleatorio.csv`
- `B_busqueda_ordenado_raw.csv`
- `B_busqueda_ordenado_agg.csv`
- `B_insercion_ordenado_agg.csv`
- `B_altura_ordenado.csv`
- `C_construccion_gran_escala_raw.csv`
- `C_construccion_gran_escala_agg.csv`
- `D_variacion_M_raw.csv`
- `D_variacion_M_agg.csv`
- `E_busqueda_M_calibrado_agg.csv`
- `E_busqueda_M_calibrado_raw.csv`
- `L_listar_raw.csv`
- `L_listar_agg.csv`
- `ficha_tecnica.txt`

### Ejecutar el análisis

Requisitos:

- Python 3.10+
- `numpy`
- `pandas`
- `matplotlib`

Comando:

```bash
python analisis_escalabilidad_completo.py
```

Esto genera automáticamente la carpeta `resultados_lab3/` con la salida experimental.

---

## 4. Metodología experimental

### 4.1 Hardware y software

El experimento se ejecuta localmente en RAM, sin usar disco durante la medición directa de tiempos. La ficha técnica del script reporta:

- Python: 3.12.10
- SO: Windows 11
- Procesador: Intel64 Family 6 Model 186 Stepping 3, GenuineIntel
- Semilla fija: `random.seed(42)`

Esto hace que los datos y la altura de los árboles sean reproducibles desde la misma máquina y con el mismo código.

### 4.2 Generación de datos

Los IDs se generan aleatoriamente con `random.sample()` sobre un rango amplio, simulando matrículas reales. Cada estudiante incluye:

- `id`
- `nombre`
- `edad`
- `promedio`

El ID es la clave principal usada para búsquedas y ordenamiento. Nombre, edad y promedio no afectan las métricas medibles de rendimiento, solo el ID se usa para comparar estructuras.

### 4.3 Medición de tiempos

Se usa `time.perf_counter()` para cronometrar con alta precisión.

- Inserción: se mide el tiempo para construir la estructura completa con N elementos.
- Búsqueda: se mide el tiempo total de M búsquedas sobre IDs existentes.
- Listado: se mide una llamada completa a `listar()`.

Antes de la medición real, el script realiza calentamiento y desactiva el recolector de basura (`gc`) durante la medición para reducir ruido.

### 4.4 Tratamiento de outliers

Dentro de cada grupo `(estructura, N)` se aplica la regla del rango intercuartílico (IQR):

- se descartan valores fuera de `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`;
- se reporta la media y la desviación estándar con outliers removidos;
- se reporta también la mediana como referencia robusta.

Esto queda documentado en los CSV agregados con columnas como:

- `t_busqueda_media`
- `t_busqueda_std`
- `t_busqueda_mediana`
- `outliers_removidos`

### 4.5 Experimentos realizados

| Experimento | Descripción | Parámetros |
|---|---|---|
| A | Búsqueda vs N, orden aleatorio | N = 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000; M=10000; 7 repeticiones |
| B | Búsqueda vs N, orden ya ordenado | N = 200, 500, 1000, 2000, 3000, 5000, 7500, 10000; M=10000; 3 repeticiones |
| C | Construcción a gran escala | N = 10000, 100000, 1000000; 3 repeticiones |
| D | Variación de M | N = 10000 fijo; M = 10, 100, 1000, 10000; 5 repeticiones |
| L | Listar vs N | N = 100, 1000, 10000, 100000; 5 repeticiones |

### 4.6 Verificación de correctitud

Antes de ejecutar los experimentos, el script compone las tres estructuras con `n=2000` y verifica que:

1. `listar()` produce el mismo orden en todas las estructuras.
2. `buscar()` encuentra un ID existente y rechaza uno inexistente.

La salida esperada es:

```text
[OK] Verificacion de correctitud (n=2000): listar() y buscar() coinciden en Lista, ABB y B+.
```

---

## 5. Resultados reales

### 5.1 Altura del árbol vs N

#### Orden aleatorio

| N | Altura ABB | Altura B+ |
|---|---:|---:|
| 10 | 6 | 1 |
| 50 | 10 | 2 |
| 100 | 13 | 2 |
| 200 | 19 | 3 |
| 500 | 17 | 3 |
| 1000 | 22 | 3 |
| 2000 | 23 | 4 |
| 5000 | 28 | 4 |
| 10000 | 30 | 4 |
| 20000 | 37 | 5 |
| 50000 | 36 | 5 |
| 100000 | 44 | 5 |

#### Orden ya ordenado

| N | Altura ABB | Altura B+ |
|---|---:|---:|
| 200 | 200 | 3 |
| 500 | 500 | 3 |
| 1000 | 1000 | 4 |
| 2000 | 2000 | 4 |
| 3000 | 3000 | 4 |
| 5000 | 5000 | 4 |

#### Interpretación

- Con inserción ordenada, el ABB se degenera casi completamente: su altura llega a `N`.
- El B+ se mantiene casi inalterado: pasa de 3 a 4 niveles sin prácticamente perder estabilidad.

La gráfica correspondiente es:

![Altura vs tiempo de búsqueda](resultados_lab3/figE_altura_vs_busqueda.png)

---

### 5.2 Búsqueda vs N (orden aleatorio)

Los valores reales están en `A_busqueda_aleatorio_agg.csv` y muestran cómo el tiempo total aumenta con `N`.

| Estructura | N | Tiempo medio [s] | Desv. std [s] |
|---|---:|---:|---:|
| Lista | 10 | 2.80e-03 | 6.38e-04 |
| ABB | 10 | 2.55e-03 | 5.67e-04 |
| B+ | 10 | 2.46e-03 | 2.71e-04 |
| Lista | 100 | 1.21e-02 | 7.03e-04 |
| ABB | 100 | 3.51e-03 | 1.02e-03 |
| B+ | 100 | 2.13e-03 | 1.83e-04 |
| Lista | 1000 | 1.36e-03 | 1.20e-04 |
| ABB | 1000 | 4.97e-03 | 1.95e-05 |
| B+ | 1000 | 2.90e-03 | 1.97e-05 |
| Lista | 10000 | 1.09 | 2.50e-02 |
| ABB | 10000 | 7.37e-03 | 9.31e-05 |
| B+ | 10000 | 4.35e-03 | 2.10e-04 |
| Lista | 100000 | 1.50e+00 | 1.64e-02 |
| ABB | 100000 | 1.27e-02 | 2.52e-04 |
| B+ | 100000 | 9.21e-03 | 8.61e-04 |

Observación importante: para `N` pequeños, la diferencia es menor porque el overhead constante de Python domina; a medida que `N` crece, la diferencia de complejidad se vuelve evidente.

La gráfica generada fue:

![Búsqueda aleatoria vs N](resultados_lab3/figA_busqueda_aleatorio.png)

---

### 5.3 Búsqueda vs N (orden ya ordenado)

Este caso es el más crítico para el ABB, ya que al insertarse ordenado, el árbol se degenera en una lista enlazada.

| Estructura | N | Tiempo medio [s] |
|---|---:|---:|
| Lista | 200 | 2.59e-02 |
| ABB | 200 | 3.10e-02 |
| B+ | 200 | 2.93e-03 |
| Lista | 1000 | 1.10e-01 |
| ABB | 1000 | 1.70e-01 |
| B+ | 1000 | 3.44e-03 |
| Lista | 5000 | 5.84e-01 |
| ABB | 5000 | 7.89e-01 |
| B+ | 5000 | 3.87e-03 |
| Lista | 10000 | 1.47 |  
| ABB | 10000 | 1.59 |  
| B+ | 10000 | 4.80e-03 |

Resultado clave:

- La Lista y el ABB ordenado tienen crecimiento casi lineal con `N`.
- El B+ mantiene prácticamente el mismo comportamiento en todos los tamaños.

![Búsqueda con orden ya ordenado](resultados_lab3/figB_busqueda_ordenado.png)

---

### 5.4 Construcción a gran escala

La construcción es más costosa en los árboles que en la Lista, porque ellos deben mantener el orden y el balanceo.

| Estructura | N | Tiempo medio de construcción [s] |
|---|---:|---:|
| Lista | 10000 | 4.21e-04 |
| ABB | 10000 | 9.33e-03 |
| B+ | 10000 | 7.56e-03 |
| Lista | 100000 | 4.75e-03 |
| ABB | 100000 | 1.93e-01 |
| B+ | 100000 | 1.48e-01 |
| Lista | 1000000 | 5.20e-02 |
| ABB | 1000000 | 2.90 |
| B+ | 1000000 | 2.80 |

Conclusión:

- La Lista es mucho más barata de construir.
- El costo extra de ABB y B+ se compensa en búsquedas repetidas a gran escala.

![Construcción a gran escala](resultados_lab3/figC_construccion_gran_escala.png)

---

### 5.5 Variación del número de búsquedas M

Este experimento fija `N=10000` y cambia `M`.

| Estructura | M | Tiempo medio [s] |
|---|---:|---:|
| Lista | 10 | 1.53e-03 |
| ABB | 10 | 2.87e-05 |
| B+ | 10 | 2.71e-05 |
| Lista | 100 | 1.17e-02 |
| ABB | 100 | 1.56e-04 |
| B+ | 100 | 1.18e-04 |
| Lista | 1000 | 1.08e-01 |
| ABB | 1000 | 1.09e-03 |
| B+ | 1000 | 7.42e-04 |
| Lista | 10000 | 1.09 |
| ABB | 10000 | 9.13e-03 |
| B+ | 10000 | 5.14e-03 |

La tendencia es aproximadamente lineal en `M`, como se esperaba. La Lista crece más rápido porque cada búsqueda es verdadera búsqueda lineal.

![Variación de M](resultados_lab3/figD_variacion_M.png)

---

### 5.6 Listar vs N

| Estructura | N | Tiempo medio [s] |
|---|---:|---:|
| Lista | 100 | 2.59e-05 |
| ABB | 100 | 3.04e-05 |
| B+ | 100 | 2.12e-06 |
| Lista | 1000 | 1.56e-04 |
| ABB | 1000 | 1.28e-04 |
| B+ | 1000 | 2.71e-05 |
| Lista | 10000 | 2.24e-03 |
| ABB | 10000 | 1.32e-03 |
| B+ | 10000 | 2.28e-04 |
| Lista | 100000 | 3.64e-02 |
| ABB | 100000 | 3.37e-02 |
| B+ | 100000 | 6.55e-03 |

El B+ vuelve a ganar con claridad: sus hojas ya están enlazadas y ordenadas, por lo que recorrerlas es muy eficiente.

![Listar vs N](resultados_lab3/figF_listar.png)

---

## 6. Interpretación de los resultados

### 6.1 Lista

La Lista tiene una búsqueda lineal y un costo que crece con `N`.

- Muy simple de implementar.
- Muy barata de construir.
- Muy poco eficiente en búsqueda a gran escala.
- No le afecta el orden de inserción, porque la operación de ordenado es independiente del patrón de entrada.

### 6.2 ABB

El ABB es muy eficiente en promedio cuando los datos son aleatorios, pero no es robusto ante entradas ordenadas:

- con datos aleatorios, su altura crece de forma aproximadamente logarítmica;
- con datos ya ordenados, su altura llega a `N` y la complejidad se vuelve prácticamente lineal.

Eso confirma que el ABB sin rebalanceo no es seguro para caso de peor caso.

### 6.3 B+

El B+ es la estructura más estable y eficiente para este experimento:

- mantiene baja altura incluso cuando los datos vienen ordenados;
- soporta búsquedas rápidas;
- ofrece listado muy eficiente por recorrer hojas enlazadas;
- presenta mejor desempeño en la mayor parte de las pruebas.

---

## 7. Hallazgos principales

1. El ABB sin rebalanceo sufre una degeneración severa si la inserción es ordenada.
2. El B+ es casi insensible al orden de llegada de los datos y mantiene un árbol balanceado.
3. La Lista es la más barata de construir, pero la más costosa de buscar cuando `N` crece.
4. El B+ es la mejor opción para búsquedas y listado en orden ascendente por ID.
5. La diferencia entre estructuras se vuelve claramente visible a partir de `N` relativamente pequeños, y se amplifica fuertemente en el caso grande.

---

## 8. Conclusión

Este laboratorio demuestra que la complejidad teórica se refleja en el comportamiento práctico y que, además, la estructura de datos importa tanto como el algoritmo.

- La Lista es útil para tamaños pequeños o cuando la carga de trabajo no es intensa.
- El ABB funciona bien solo si el orden de inserción es razonablemente aleatorio.
- El B+ es la opción más robusta y eficiente para este tipo de operación de búsqueda y listado ordenado.

La implementación queda verificada no solo en términos de correctitud sino también en términos de escalabilidad, y los resultados generados en `resultados_lab3/` muestran de forma tangible la diferencia entre las tres estructuras.

---

## 9. Nota final

Todo este análisis fue generado con el script `analisis_escalabilidad_completo.py`. La carpeta `resultados_lab3/` contiene los CSVs, las gráficas y la ficha técnica de la ejecución real de este laboratorio, por lo que el README queda sincronizado con el código y la evidencia producida por la corrida local.
