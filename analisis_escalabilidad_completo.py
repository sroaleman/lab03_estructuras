# -*- coding: utf-8 -*-
"""
Laboratorio 3 - Sistema de busqueda de estudiantes
Lista vs ABB vs Arbol B+

Cubre lo que pide la guia:
  - las 3 operaciones: Buscar, Insertar, Listar (ascendente por ID)
  - verificacion de correctitud (las 3 estructuras deben dar el mismo resultado)
  - estudio de escalabilidad en N (busqueda, insercion/construccion, listar)
  - IDs aleatorios vs IDs ordenados
  - M (numero de busquedas) como parametro independiente
  - relacion entre altura del arbol y tiempo de busqueda
  - varias repeticiones, promedio, desviacion estandar, tratamiento de outliers (IQR)
  - graficas con titulo, ejes con unidades, leyenda
  - ficha tecnica con hardware/software/metodologia (para la sustentacion)

Todo corre en un solo proceso local, en RAM, sin I/O de disco durante las
mediciones. Usa time.perf_counter() (el reloj de mayor resolucion
de Python) para cronometrar.
"""
import random, time, bisect, platform, datetime
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

random.seed(42)  # reproducibilidad: misma semilla = mismos datos cada corrida

OUT = str(Path(__file__).resolve().parent / "resultados_lab3") + "/"
Path(OUT).mkdir(parents=True, exist_ok=True)

t_inicio_total = time.perf_counter()
tiempos_experimentos = {}

# =====================================================================
# 1. GENERACION DE DATOS
# =====================================================================
def gen_nombre():
    c, v = "bcdfghjlmnprstvz", "aeiou"
    return "".join(random.choice(c) + random.choice(v) for _ in range(random.randint(2, 3))).capitalize()

def gen_estudiantes(n):
    """IDs unicos muestreados sin reemplazo de un rango amplio (simula matriculas reales)."""
    ids = random.sample(range(1000, 5_000_000), n)
    return [{"id": i, "nombre": gen_nombre(), "edad": random.randint(17, 28),
              "promedio": round(random.uniform(5, 10), 1)} for i in ids]

# =====================================================================
# 2. ESTRUCTURAS DE DATOS -- con Buscar, Insertar, Listar y Altura
# =====================================================================
class Lista:
    def __init__(self): self.datos = []
    def insertar(self, x): self.datos.append(x)
    def buscar(self, target_id):
        for x in self.datos:
            if x["id"] == target_id: return x
        return None
    def listar(self):
        """Lista no mantiene orden; para listar ascendente hay que ordenar: O(n log n)."""
        return sorted(self.datos, key=lambda x: x["id"])

class NodoABB:
    def __init__(self, e): self.e, self.id, self.izq, self.der = e, e["id"], None, None

class ABB:
    def __init__(self): self.raiz = None
    def insertar(self, e):
        n = NodoABB(e)
        if not self.raiz: self.raiz = n; return
        act = self.raiz
        while True:
            if e["id"] < act.id:
                if not act.izq: act.izq = n; break
                act = act.izq
            else:
                if not act.der: act.der = n; break
                act = act.der
    def buscar(self, target_id):
        act = self.raiz
        while act:
            if act.id == target_id: return act.e
            act = act.izq if target_id < act.id else act.der
        return None
    def listar(self):
        """Recorrido in-order ITERATIVO (con pila propia, no recursion) para
        no reventar el limite de recursion de Python cuando el arbol esta
        degenerado (caso de insercion ordenada, altura = n)."""
        resultado, pila, act = [], [], self.raiz
        while act or pila:
            while act:
                pila.append(act); act = act.izq
            act = pila.pop()
            resultado.append(act.e)
            act = act.der
        return resultado
    def altura(self):
        """Altura = numero de niveles del arbol. Iterativo por la misma razon de arriba."""
        if not self.raiz: return 0
        maxh, pila = 0, [(self.raiz, 1)]
        while pila:
            nodo, prof = pila.pop()
            if prof > maxh: maxh = prof
            if nodo.izq: pila.append((nodo.izq, prof + 1))
            if nodo.der: pila.append((nodo.der, prof + 1))
        return maxh

class NodoBPlus:
    def __init__(self, h=False): self.hoja, self.k, self.v, self.sig = h, [], [], None

class ArbolBPlus:
    def __init__(self, M=16): self.r, self.M = NodoBPlus(True), M
    def buscar(self, k):
        n = self.r
        while not n.hoja: n = n.v[bisect.bisect_right(n.k, k)]
        i = bisect.bisect_left(n.k, k)
        return n.v[i] if i < len(n.k) and n.k[i] == k else None
    def insertar(self, e):
        k, v = e["id"], e
        if len(self.r.k) == self.M - 1:
            nr = NodoBPlus(False); nr.v.append(self.r); self._split(nr, 0); self.r = nr
        self._ins(self.r, k, v)
    def _split(self, p, i):
        h = p.v[i]; nn = NodoBPlus(h.hoja); m = len(h.k) // 2
        if h.hoja:
            nn.k, nn.v = h.k[m:], h.v[m:]
            h.k, h.v = h.k[:m], h.v[:m]
            nn.sig, h.sig = h.sig, nn
            p.k.insert(i, nn.k[0]); p.v.insert(i + 1, nn)
        else:
            p.k.insert(i, h.k[m])
            nn.k, nn.v = h.k[m + 1:], h.v[m + 1:]
            h.k, h.v = h.k[:m], h.v[:m + 1]
            p.v.insert(i + 1, nn)
    def _ins(self, n, k, v):
        if n.hoja:
            i = bisect.bisect_left(n.k, k); n.k.insert(i, k); n.v.insert(i, v)
        else:
            i = bisect.bisect_right(n.k, k)
            if len(n.v[i].k) == self.M - 1:
                self._split(n, i)
                if k > n.k[i]: i += 1
            self._ins(n.v[i], k, v)
    def listar(self):
        """Las hojas ya estan ordenadas y enlazadas (self.sig): basta con
        bajar hasta la hoja mas a la izquierda y recorrer la lista enlazada
        de hojas. O(n), sin necesidad de comparar ni ordenar nada."""
        n = self.r
        while not n.hoja: n = n.v[0]
        resultado = []
        while n:
            resultado.extend(n.v)
            n = n.sig
        return resultado
    def altura(self):
        """El B+ siempre esta balanceado: cualquier camino raiz->hoja sirve."""
        n, h = self.r, 1
        while not n.hoja:
            n = n.v[0]; h += 1
        return h

ESTRUCTURAS = [("Lista", Lista), ("ABB", ABB), ("B+", ArbolBPlus)]

def construir(cls, datos):
    est = cls()
    t0 = time.perf_counter()
    for d in datos:
        est.insertar(d)
    return est, time.perf_counter() - t0

def medir_busqueda(est, targets):
    t0 = time.perf_counter()
    for t in targets:
        est.buscar(t)
    return time.perf_counter() - t0

def medir_listar(est):
    t0 = time.perf_counter()
    r = est.listar()
    return r, time.perf_counter() - t0

# =====================================================================
# 3. VERIFICACION DE CORRECTITUD (las 3 estructuras deben coincidir)
# =====================================================================
def verificar_correctitud(n=2000):
    datos = gen_estudiantes(n)
    estructuras = {nombre: cls() for nombre, cls in ESTRUCTURAS}
    for d in datos:
        for est in estructuras.values():
            est.insertar(d)

    ids_esperados = sorted(d["id"] for d in datos)

    for nombre, est in estructuras.items():
        ids_obtenidos = [x["id"] for x in est.listar()]
        assert ids_obtenidos == ids_esperados, f"ERROR: {nombre}.listar() no coincide con el orden esperado"

    id_existente = datos[len(datos) // 2]["id"]
    id_inexistente = max(ids_esperados) + 999_999

    for nombre, est in estructuras.items():
        assert est.buscar(id_existente) is not None, f"ERROR: {nombre}.buscar() no encontro un ID que si existe"
        assert est.buscar(id_inexistente) is None, f"ERROR: {nombre}.buscar() encontro un ID que NO existe"

    print(f"[OK] Verificacion de correctitud (n={n}): listar() y buscar() coinciden en Lista, ABB y B+.")

print("=== Verificacion de correctitud ===")
verificar_correctitud(2000)

# =====================================================================
# 4. TRATAMIENTO DE VALORES ATIPICOS (outliers) + agregacion estadistica
#    Metodo: regla del rango intercuartilico (IQR). Se descartan, dentro de
#    cada grupo (estructura, n, ...), las repeticiones fuera de
#    [Q1 - 1.5*IQR, Q3 + 1.5*IQR] antes de calcular media y desviacion
#    estandar. Se reporta tambien la mediana (estadistico robusto) y cuantos
#    outliers se removieron, para que quede documentado.
# =====================================================================
def agregar_robusto(df, group_cols, value_col):
    filas = []
    for key, sub in df.groupby(group_cols):
        key = key if isinstance(key, tuple) else (key,)
        s = sub[value_col].values.astype(float)
        if len(s) >= 4:
            q1, q3 = np.percentile(s, [25, 75])
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            limpio = s[(s >= lo) & (s <= hi)]
            if len(limpio) == 0:
                limpio = s
        else:
            limpio = s  # con pocas repeticiones no se puede estimar IQR de forma confiable
        fila = dict(zip(group_cols, key))
        fila[f"{value_col}_media"] = float(np.mean(limpio))
        fila[f"{value_col}_std"] = float(np.std(limpio, ddof=1)) if len(limpio) > 1 else 0.0
        fila[f"{value_col}_mediana"] = float(np.median(s))
        fila["repeticiones"] = len(s)
        fila["outliers_removidos"] = len(s) - len(limpio)
        filas.append(fila)
    return pd.DataFrame(filas)

# =====================================================================
# EXPERIMENTO A: BUSQUEDA vs N, orden ALEATORIO (rango amplio)
#   + se registra la ALTURA del arbol en cada corrida (ABB y B+)
# =====================================================================
print("\n=== A: busqueda vs N (aleatorio) ===")
t0_exp = time.perf_counter()
n_values_A = [10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]
REP_A, M_A = 5, 100   # M = numero de busquedas por repeticion
regA = []
for n in n_values_A:
    datos = gen_estudiantes(n)
    ids = [d["id"] for d in datos]
    for rep in range(REP_A):
        targets = random.sample(ids, min(M_A, n))
        for nombre, cls in ESTRUCTURAS:
            est, t_ins = construir(cls, datos)
            t_b = medir_busqueda(est, targets)
            altura = est.altura() if hasattr(est, "altura") else None
            regA.append({"estructura": nombre, "n": n, "rep": rep,
                         "t_insercion": t_ins, "t_busqueda": t_b, "altura": altura})
    print(f"  n={n:>7} OK")
dfA = pd.DataFrame(regA)
dfA.to_csv(OUT + "A_busqueda_aleatorio_raw.csv", index=False)
aggA_b = agregar_robusto(dfA, ["estructura", "n"], "t_busqueda")
aggA_altura = dfA.dropna(subset=["altura"]).groupby(["estructura", "n"])["altura"].mean().reset_index()
aggA_b.to_csv(OUT + "A_busqueda_aleatorio_agg.csv", index=False)
aggA_altura.to_csv(OUT + "A_altura_aleatorio.csv", index=False)
tiempos_experimentos["A"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['A']:.2f} s")

# =====================================================================
# EXPERIMENTO B: BUSQUEDA vs N, orden YA ORDENADO (rango acotado: el ABB
#   se degenera y su INSERCION es O(n^2)) + altura
# =====================================================================
print("\n=== B: busqueda vs N (ordenado) ===")
t0_exp = time.perf_counter()
n_values_B = [200, 500, 1000, 2000, 3000, 5000]
REP_B, M_B = 3, 100
regB = []
for n in n_values_B:
    datos_base = gen_estudiantes(n)
    datos = sorted(datos_base, key=lambda x: x["id"])
    ids = [d["id"] for d in datos_base]
    for rep in range(REP_B):
        targets = random.sample(ids, min(M_B, n))
        for nombre, cls in ESTRUCTURAS:
            est, t_ins = construir(cls, datos)
            t_b = medir_busqueda(est, targets)
            altura = est.altura() if hasattr(est, "altura") else None
            regB.append({"estructura": nombre, "n": n, "rep": rep,
                         "t_insercion": t_ins, "t_busqueda": t_b, "altura": altura})
    print(f"  n={n:>7} OK")
dfB = pd.DataFrame(regB)
dfB.to_csv(OUT + "B_busqueda_ordenado_raw.csv", index=False)
aggB_b = agregar_robusto(dfB, ["estructura", "n"], "t_busqueda")
aggB_i = agregar_robusto(dfB, ["estructura", "n"], "t_insercion")
aggB_altura = dfB.dropna(subset=["altura"]).groupby(["estructura", "n"])["altura"].mean().reset_index()
aggB_b.to_csv(OUT + "B_busqueda_ordenado_agg.csv", index=False)
aggB_i.to_csv(OUT + "B_insercion_ordenado_agg.csv", index=False)
aggB_altura.to_csv(OUT + "B_altura_ordenado.csv", index=False)
tiempos_experimentos["B"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['B']:.2f} s")

# =====================================================================
# EXPERIMENTO C: CONSTRUCCION a gran escala (orden aleatorio)
#   N = 10.000 / 100.000 / 1.000.000
# =====================================================================
print("\n=== C: construccion a gran escala (aleatorio) ===")
t0_exp = time.perf_counter()
n_values_C = [10000, 100000, 1000000]
REP_C = 3
regC = []
for n in n_values_C:
    datos = gen_estudiantes(n)
    for rep in range(REP_C):
        for nombre, cls in ESTRUCTURAS:
            _, t_ins = construir(cls, datos)
            regC.append({"estructura": nombre, "n": n, "rep": rep, "t_insercion": t_ins})
        print(f"  n={n:>8} rep={rep+1}/{REP_C} OK")
dfC = pd.DataFrame(regC)
dfC.to_csv(OUT + "C_construccion_gran_escala_raw.csv", index=False)
aggC = agregar_robusto(dfC, ["estructura", "n"], "t_insercion")
aggC.to_csv(OUT + "C_construccion_gran_escala_agg.csv", index=False)
tiempos_experimentos["C"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['C']:.2f} s")

# =====================================================================
# EXPERIMENTO D: variar M (numero de busquedas), N fijo = 10.000
# =====================================================================
print("\n=== D: variacion de M (N=10000 fijo, aleatorio) ===")
t0_exp = time.perf_counter()
n_fijo = 10000
m_values = [10, 100, 1000, 10000]
REP_D = 5
datos_fijo = gen_estudiantes(n_fijo)
ids_fijo = [d["id"] for d in datos_fijo]
regD = []
estructuras_fijas = {nombre: construir(cls, datos_fijo)[0] for nombre, cls in ESTRUCTURAS}
for m in m_values:
    for rep in range(REP_D):
        if m <= n_fijo:
            targets = random.sample(ids_fijo, m)
        else:
            targets = [random.choice(ids_fijo) for _ in range(m)]
        for nombre, est in estructuras_fijas.items():
            t_b = medir_busqueda(est, targets)
            regD.append({"estructura": nombre, "m": m, "rep": rep, "t_busqueda": t_b})
    print(f"  M={m:>6} OK")
dfD = pd.DataFrame(regD)
dfD.to_csv(OUT + "D_variacion_M_raw.csv", index=False)
aggD = agregar_robusto(dfD, ["estructura", "m"], "t_busqueda")
aggD.to_csv(OUT + "D_variacion_M_agg.csv", index=False)
tiempos_experimentos["D"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['D']:.2f} s")

# =====================================================================
# EXPERIMENTO L: tiempo de LISTAR vs N (orden aleatorio)
#   Lista debe ordenar (O(n log n)); ABB recorre in-order (O(n));
#   B+ recorre hojas ya enlazadas (O(n), sin comparaciones)
# =====================================================================
print("\n=== L: listar vs N (aleatorio) ===")
t0_exp = time.perf_counter()
n_values_L = [100, 1000, 10000, 100000]
REP_L = 5
regL = []
for n in n_values_L:
    datos = gen_estudiantes(n)
    estructuras = {nombre: construir(cls, datos)[0] for nombre, cls in ESTRUCTURAS}
    for rep in range(REP_L):
        for nombre, est in estructuras.items():
            _, t_l = medir_listar(est)
            regL.append({"estructura": nombre, "n": n, "rep": rep, "t_listar": t_l})
    print(f"  n={n:>7} OK")
dfL = pd.DataFrame(regL)
dfL.to_csv(OUT + "L_listar_raw.csv", index=False)
aggL = agregar_robusto(dfL, ["estructura", "n"], "t_listar")
aggL.to_csv(OUT + "L_listar_agg.csv", index=False)
tiempos_experimentos["L"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['L']:.2f} s")

# =====================================================================
# 5. GRAFICAS
# =====================================================================
colores = {"Lista": "#e74c3c", "ABB": "#3498db", "B+": "#2ecc71"}
marcas = {"Lista": "o", "ABB": "s", "B+": "^"}

def plot_err(ax, df, xcol, ycol_media, ycol_std, xlabel, ylabel, titulo):
    for est in ["Lista", "ABB", "B+"]:
        sub = df[df.estructura == est].sort_values(xcol)
        ax.errorbar(sub[xcol], sub[ycol_media], yerr=sub[ycol_std], label=est,
                    color=colores[est], marker=marcas[est], capsize=3, linewidth=1.8)
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(titulo)
    ax.legend(); ax.grid(alpha=0.3, which="both")

# FigA: busqueda vs n (aleatorio) en lineal / semilog / log-log
fig, axes = plt.subplots(1, 3, figsize=(17, 5))
for ax, esc in zip(axes, ["lineal", "semilog", "loglog"]):
    plot_err(ax, aggA_b, "n", "t_busqueda_media", "t_busqueda_std",
             "N (número de estudiantes)", "Tiempo total de búsqueda (M=100) [s]",
             esc.upper())
    if esc in ("semilog", "loglog"): ax.set_yscale("log")
    if esc == "loglog": ax.set_xscale("log")
fig.suptitle("Tiempo de BÚSQUEDA vs N — orden ALEATORIO (N=10 a 100.000, M=100)")
fig.tight_layout(); fig.savefig(OUT + "figA_busqueda_aleatorio.png", dpi=140); plt.close(fig)

# FigB: busqueda vs n (ordenado)
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggB_b, "n", "t_busqueda_media", "t_busqueda_std",
         "N (número de estudiantes)", "Tiempo total de búsqueda (M=100) [s]",
         "Búsqueda vs N — orden YA ORDENADO (caso patológico del ABB)")
fig.tight_layout(); fig.savefig(OUT + "figB_busqueda_ordenado.png", dpi=140); plt.close(fig)

# FigC: construccion gran escala
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggC, "n", "t_insercion_media", "t_insercion_std",
         "N (escala log)", "Tiempo total de construcción [s] (escala log)",
         "Construcción vs N — 10.000 / 100.000 / 1.000.000 (aleatorio)")
ax.set_xscale("log"); ax.set_yscale("log")
fig.tight_layout(); fig.savefig(OUT + "figC_construccion_gran_escala.png", dpi=140); plt.close(fig)

# FigD: variacion de M
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggD, "m", "t_busqueda_media", "t_busqueda_std",
         "M = número de búsquedas (escala log)", "Tiempo total de búsqueda [s] (escala log)",
         "Tiempo de búsqueda vs M — N=10.000 fijo, aleatorio")
ax.set_xscale("log"); ax.set_yscale("log")
fig.tight_layout(); fig.savefig(OUT + "figD_variacion_M.png", dpi=140); plt.close(fig)

# FigE: altura del arbol vs n (aleatorio vs ordenado) -- respuesta directa
# a la pregunta "que relacion existe entre la altura del arbol y el tiempo
# de busqueda?"
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for est in ["ABB", "B+"]:
    sub = aggA_altura[aggA_altura.estructura == est].sort_values("n")
    axes[0].plot(sub.n, sub.altura, marker=marcas[est], color=colores[est], label=f"{est} (aleatorio)", linewidth=1.8)
    subo = aggB_altura[aggB_altura.estructura == est].sort_values("n")
    axes[0].plot(subo.n, subo.altura, marker=marcas[est], color=colores[est], linestyle="--",
                 label=f"{est} (ordenado)", linewidth=1.8, alpha=0.6)
axes[0].set_xscale("log")
axes[0].set_xlabel("N (escala log)"); axes[0].set_ylabel("Altura del árbol (niveles)")
axes[0].set_title("Altura vs N — aleatorio (línea sólida) vs ordenado (punteada)")
axes[0].legend(); axes[0].grid(alpha=0.3)

# Dispersión altura vs tiempo de busqueda (todas las corridas de A, ABB y B+)
dfA_abb_bplus = dfA[dfA.estructura.isin(["ABB", "B+"])].dropna(subset=["altura"])
for est in ["ABB", "B+"]:
    sub = dfA_abb_bplus[dfA_abb_bplus.estructura == est]
    axes[1].scatter(sub.altura, sub.t_busqueda, s=12, alpha=0.4, color=colores[est], label=est)
axes[1].set_xlabel("Altura del árbol (niveles)")
axes[1].set_ylabel("Tiempo total de búsqueda (M=100) [s]")
axes[1].set_title("Relación altura <-> tiempo de búsqueda (cada punto = una corrida)")
axes[1].legend(); axes[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT + "figE_altura_vs_busqueda.png", dpi=140); plt.close(fig)

# FigF: tiempo de listar vs n
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggL, "n", "t_listar_media", "t_listar_std",
         "N (escala log)", "Tiempo de listar() [s] (escala log)",
         "Tiempo de LISTAR (orden ascendente por ID) vs N")
ax.set_xscale("log"); ax.set_yscale("log")
fig.tight_layout(); fig.savefig(OUT + "figF_listar.png", dpi=140); plt.close(fig)

print("\nGraficas guardadas: figA..figF")

# =====================================================================
# 6. FICHA TECNICA (para la sustentacion: hardware, software, metodologia)
# =====================================================================
tiempo_total = time.perf_counter() - t_inicio_total
ficha = f"""FICHA TECNICA DEL EXPERIMENTO - Laboratorio 3
================================================
Fecha y hora de la corrida : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

HARDWARE / SOFTWARE
--------------------
Python       : {platform.python_version()}
SO           : {platform.system()} {platform.release()}
Procesador   : {platform.processor() or 'no identificado'}
(Nota: correr localmente, NO en Colab, para evitar variabilidad de recursos
 compartidos. Todo el experimento corre en un solo proceso, en RAM.)

GENERACION DE DATOS
--------------------
IDs unicos por muestreo sin reemplazo (random.sample) sobre un rango amplio,
simulando numeros de matricula reales. Nombre/edad/promedio son sinteticos,
no afectan el rendimiento medido (solo el ID se usa para buscar/ordenar).
Semilla fija (seed=42): la corrida es reproducible.

GENERACION DE BUSQUEDAS
------------------------
Para cada N se genera un conjunto de M IDs objetivo, elegidos aleatoriamente
ENTRE LOS IDs QUE SI EXISTEN en el conjunto (random.sample sin reemplazo),
para medir el caso de busqueda exitosa. M es un parametro independiente,
explorado en el Experimento D (M = 10, 100, 1000, 10000) con N fijo.

METODO DE MEDICION DE TIEMPOS
-------------------------------
time.perf_counter() (reloj monotonico de mayor resolucion en Python).
Insercion: se cronometra construir la estructura completa (N inserciones).
Busqueda:  se cronometra el total de las M busquedas (no una individual).
Listar:    se cronometra una llamada a listar() sobre la estructura ya construida.

TRATAMIENTO DE VALORES ATIPICOS
---------------------------------
Regla del rango intercuartilico (IQR) por cada grupo (estructura, N):
se descartan las repeticiones fuera de [Q1 - 1.5*IQR, Q3 + 1.5*IQR] antes
de calcular media y desviacion estandar. Se reporta tambien la mediana
(estadistico robusto) y cuantos valores se removieron por grupo (columna
'outliers_removidos' en los _agg.csv). Con menos de 4 repeticiones no se
aplica el filtro (IQR no es confiable con tan pocos datos).

ESTADISTICAS UTILIZADAS
-------------------------
Media y desviacion estandar (tras remover outliers), mediana (sin remover
outliers, como referencia robusta), y ajuste de pendiente log-log
(regresion sobre ln(tiempo) vs ln(N)) para estimar el orden de crecimiento
empirico y compararlo con la complejidad teorica.

PARAMETROS DE CADA EXPERIMENTO
--------------------------------
A) Busqueda vs N, aleatorio : N={n_values_A}
   repeticiones={REP_A}, M={M_A}  -> tardo {tiempos_experimentos['A']:.2f} s
B) Busqueda vs N, ordenado  : N={n_values_B}  (acotado: ABB insercion O(n^2))
   repeticiones={REP_B}, M={M_B}  -> tardo {tiempos_experimentos['B']:.2f} s
C) Construccion gran escala : N={n_values_C}
   repeticiones={REP_C}  -> tardo {tiempos_experimentos['C']:.2f} s
D) Variacion de M, N={n_fijo} fijo : M={m_values}
   repeticiones={REP_D}  -> tardo {tiempos_experimentos['D']:.2f} s
L) Listar vs N, aleatorio   : N={n_values_L}
   repeticiones={REP_L}  -> tardo {tiempos_experimentos['L']:.2f} s

TIEMPO TOTAL DEL SCRIPT: {tiempo_total:.2f} s (~{tiempo_total/60:.1f} min)

VERIFICACION DE CORRECTITUD: realizada al inicio (n=2000) -- las 3
estructuras producen el mismo resultado en listar() y en buscar()
(ver mensaje "[OK] Verificacion de correctitud" en la salida de consola).
"""
with open(OUT + "ficha_tecnica.txt", "w", encoding="utf-8") as f:
    f.write(ficha)
print("\n" + ficha)
print(f"Todo listo. Resultados en: {OUT}")