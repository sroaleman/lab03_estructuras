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
  - varias repeticiones, promedio, desviacion estandar, IC 95 %, tratamiento de outliers (IQR)
  - graficas con titulo, ejes con unidades, leyenda
  - ficha tecnica con hardware/software/metodologia (para la sustentacion)

Todo corre en un solo proceso local, en RAM, sin I/O de disco durante las
mediciones. Usa time.perf_counter() (el reloj de mayor resolucion
de Python) para cronometrar; antes de cada medicion de busqueda hace un
calentamiento (sin medir) y desactiva el recolector de basura (gc).

MEJORAS DE PROTOCOLO (version 2):
  1. Ventana minima: cada medicion dura >= VENTANA segundos (1 s por defecto): se repite el
     lote de busquedas (o la construccion / el listado) hasta llenar la ventana.
  2. Semilla configurable. Por defecto 42 (reproduce el README). Con --semilla aleatoria
     cualquiera puede revisar el codigo con otros datos; la semilla usada queda registrada.
  3. Cada repeticion usa un dataset DISTINTO (semilla base + experimento + N + repeticion).
  4. El orden de N (y de las estructuras) se baraja en cada repeticion, para que la deriva del
     computador no se confunda con el efecto de N.
  5. IC 95 % (t de Student) ademas de la desviacion estandar; pendientes log-log con R^2 y
     pendientes teoricas de referencia (log N, N, N log N).
  6. Dos graficas nuevas: figH (dispersion entre repeticiones) y figI (estabilidad en el tiempo).

Uso:
    python laboratorio3_completo.py                        # corrida completa, semilla 42
    python laboratorio3_completo.py --semilla aleatoria    # datos distintos (queda registrada)
    python laboratorio3_completo.py --semilla 123          # otra semilla concreta
    python laboratorio3_completo.py --rapido               # prueba de ~1 min (no usar para el informe)
    python laboratorio3_completo.py --ventana 1.5          # ventana minima distinta
"""
import argparse, math, random, time, bisect, platform, datetime, gc
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# =====================================================================
# 0. PARAMETROS DE EJECUCION (semilla, ventana, modo rapido)
# =====================================================================
_ap = argparse.ArgumentParser(description="Laboratorio 3: Lista vs ABB vs B+")
_ap.add_argument("--semilla", default="42", help="entero, o 'aleatoria' para usar datos distintos (defecto 42)")
_ap.add_argument("--ventana", type=float, default=1.0, help="segundos minimos por medicion (defecto 1.0)")
_ap.add_argument("--rapido", action="store_true", help="prueba corta para verificar que todo corre")
_args = _ap.parse_args()

RAPIDO = _args.rapido
VENTANA = 0.05 if RAPIDO else _args.ventana
if str(_args.semilla).lower() in ("aleatoria", "random", "azar"):
    SEMILLA = random.SystemRandom().randrange(1, 10**9)
    SEMILLA_MODO = "aleatoria (elegida al azar al iniciar)"
else:
    SEMILLA = int(_args.semilla)
    SEMILLA_MODO = "fija (reproducible)"
random.seed(SEMILLA)  # reproducibilidad: misma semilla = mismos datos cada corrida

_base = Path(__file__).resolve().parent
if RAPIDO:
    _nombre_salida = "resultados_lab3_rapido"
elif SEMILLA == 42:
    _nombre_salida = "resultados_lab3"
else:
    _nombre_salida = f"resultados_lab3_semilla_{SEMILLA}"   # no pisa los resultados de la semilla 42
OUT = str(_base / _nombre_salida) + "/"
Path(OUT).mkdir(parents=True, exist_ok=True)
print(f"Semilla: {SEMILLA} [{SEMILLA_MODO}] | ventana minima: {VENTANA} s | salida: {OUT}"
      + ("  | MODO RAPIDO" if RAPIDO else ""))

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

def sembrar(exp, n, rep):
    """Semilla propia de cada (experimento, N, repeticion): cada repeticion usa datos DISTINTOS
    y todo sigue siendo reproducible a partir de la semilla base."""
    random.seed(f"{SEMILLA}-{exp}-{n}-{rep}")

def barajar(lista, exp, rep):
    """Devuelve una copia en orden aleatorio (reproducible) para cada repeticion."""
    r = random.Random(f"{SEMILLA}-orden-{exp}-{rep}")
    l = list(lista)
    r.shuffle(l)
    return l

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

def construir_ventana(cls, datos, ventana=None):
    """Construye desde cero repetidamente hasta acumular >= ventana de tiempo medido.
    Cada construccion se cronometra por separado (liberar la anterior queda fuera del reloj).
    Devuelve (ultima estructura, segundos por construccion, construcciones)."""
    ventana = VENTANA if ventana is None else ventana
    acum, k, est = 0.0, 0, None
    gc.collect(); gc.disable()
    try:
        while True:
            est = None
            e = cls()
            t0 = time.perf_counter()
            for d in datos:
                e.insertar(d)
            acum += time.perf_counter() - t0
            est = e; k += 1
            if acum >= ventana:
                break
    finally:
        gc.enable()
    return est, acum / k, k

def hacer_lotes(ids, m, nlotes=10):
    """Varios lotes de M IDs existentes (con reemplazo). Se recorren ciclicamente cuando la ventana
    exige repetir, para no medir siempre las mismas rutas (que quedarian calientes en cache)."""
    return [random.choices(ids, k=m) for _ in range(nlotes)]

def medir_busqueda(est, lotes, ventana=None):
    """Tiempo de UN lote de M busquedas, promediado sobre una ventana de >= `ventana` segundos.
    Devuelve (segundos por lote de M, lotes ejecutados, tiempo total medido)."""
    ventana = VENTANA if ventana is None else ventana
    buscar = est.buscar
    # Calentamiento (NO cronometrado): evita medir efectos de primera llamada / cache frio.
    for t in lotes[0][:min(200, len(lotes[0]))]:
        if buscar(t) is None:
            raise AssertionError("buscar() no encontro un ID que existe")
    gc.collect()
    gc.disable()   # el recolector de basura no debe interrumpir la medicion
    try:
        t0 = time.perf_counter()
        for t in lotes[0]:
            buscar(t)
        t_lote = time.perf_counter() - t0
        if t_lote >= ventana:
            return t_lote, 1, t_lote
        k, total, nl = 0, 0.0, len(lotes)
        while total < ventana:            # rondas hasta que el tiempo MEDIDO llene la ventana
            faltan = max(1, math.ceil((ventana - total) / t_lote))
            t0 = time.perf_counter()
            for i in range(k, k + faltan):
                for t in lotes[i % nl]:
                    buscar(t)
            total += time.perf_counter() - t0
            k += faltan
        return total / k, k, total
    finally:
        gc.enable()

def medir_listar(est, ventana=None):
    """Tiempo de UNA llamada a listar(), promediado sobre una ventana de >= `ventana` segundos.
    Devuelve (resultado de la primera llamada, segundos por llamada, llamadas)."""
    ventana = VENTANA if ventana is None else ventana
    r = est.listar()                       # calentamiento + resultado para verificar
    acum, k = 0.0, 0
    gc.collect(); gc.disable()
    try:
        while True:
            t0 = time.perf_counter()
            x = est.listar()
            acum += time.perf_counter() - t0
            x = None
            k += 1
            if acum >= ventana:
                break
    finally:
        gc.enable()
    return r, acum / k, k

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
# 4. ESTADISTICA: atipicos (IQR), media, desviacion estandar, IC 95 %, pendientes log-log
#    Metodo de atipicos: regla del rango intercuartilico (IQR). Se descartan, dentro de
#    cada grupo (estructura, n, ...), las repeticiones fuera de
#    [Q1 - 1.5*IQR, Q3 + 1.5*IQR] antes de calcular media y desviacion
#    estandar. Se reporta tambien la mediana (estadistico robusto) y cuantos
#    outliers se removieron, para que quede documentado.
#    IC 95 %: media +- t(0.975, n-1) * s / sqrt(n)  (t de Student, pocas repeticiones).
# =====================================================================
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
         10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110,
         18: 2.101, 19: 2.093, 20: 2.086, 25: 2.060, 30: 2.042}

def t_student(gl):
    """Valor critico t (dos colas, 95 %) para gl grados de libertad (tabla; conservador entre entradas)."""
    if gl < 1:
        return 0.0
    if gl > 30:
        return 1.96
    return _T975[max(k for k in _T975 if k <= gl)]

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
        fila[f"{value_col}_ic95"] = (t_student(len(limpio) - 1) * fila[f"{value_col}_std"] / math.sqrt(len(limpio))
                                     if len(limpio) > 1 else 0.0)
        fila[f"{value_col}_mediana"] = float(np.median(s))
        fila["cv_pct"] = (fila[f"{value_col}_std"] / fila[f"{value_col}_media"] * 100) if fila[f"{value_col}_media"] else 0.0   # ruido relativo
        fila["repeticiones"] = len(s)
        fila["outliers_removidos"] = len(s) - len(limpio)
        filas.append(fila)
    return pd.DataFrame(filas)

def pendientes_loglog(agg, xcol, ycol, experimento):
    """Pendiente de ln(tiempo) vs ln(x) por estructura, con R^2, junto a las pendientes que
    tendrian log2(N+1), N y N*log2(N+1) en ESA MISMA rejilla de N (referencia teorica)."""
    filas = []
    for est, sub in agg.groupby("estructura"):
        sub = sub.sort_values(xcol)
        if len(sub) < 3:
            continue
        xs = sub[xcol].astype(float).values
        x, y = np.log(xs), np.log(sub[ycol].values)
        p, b = np.polyfit(x, y, 1)
        ss_res = float(((y - (p * x + b)) ** 2).sum()); ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
        if xcol == "n":
            ref = lambda f: float(np.polyfit(x, np.log(f(xs)), 1)[0])
            r_log, r_n, r_nlog = ref(lambda v: np.log2(v + 1)), 1.0, ref(lambda v: v * np.log2(v + 1))
        else:   # x = M: cada busqueda es independiente, lo esperado es lineal en M
            r_log, r_n, r_nlog = float("nan"), 1.0, float("nan")
        filas.append({"experimento": experimento, "estructura": est, "puntos": len(sub),
                      "x_min": xs.min(), "x_max": xs.max(), "pendiente": p, "R2": r2,
                      "ref_log2N": r_log, "ref_N": r_n, "ref_NlogN": r_nlog})
    return pd.DataFrame(filas)

# =====================================================================
# EXPERIMENTO A: BUSQUEDA vs N, orden ALEATORIO (rango amplio)
#   + se registra la ALTURA del arbol en cada corrida (ABB y B+)
#   Repeticion = dataset distinto; el orden de N se baraja en cada repeticion.
# =====================================================================
print("\n=== A: busqueda vs N (aleatorio) ===")
t0_exp = time.perf_counter()
n_values_A = [10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000]
REP_A, M_A = 7, 10000   # M = numero de busquedas por lote; 7 repeticiones para promediar el ruido
if RAPIDO:
    n_values_A, REP_A, M_A = [10, 100, 1000, 10000], 2, 1000
regA = []
for rep in range(REP_A):
    for n in barajar(n_values_A, "A", rep):
        sembrar("A", n, rep)
        datos = gen_estudiantes(n)
        ids = [d["id"] for d in datos]
        lotes = hacer_lotes(ids, M_A)
        for nombre, cls in barajar(ESTRUCTURAS, f"A{n}", rep):
            est, t_ins = construir(cls, datos)
            t_b, k_l, w = medir_busqueda(est, lotes)
            altura = est.altura() if hasattr(est, "altura") else None
            regA.append({"estructura": nombre, "n": n, "rep": rep, "t_insercion": t_ins, "t_busqueda": t_b,
                         "altura": altura, "lotes": k_l, "ventana_s": w, "t_epoch": time.time()})
            del est
    print(f"  repeticion {rep + 1}/{REP_A} OK ({time.perf_counter() - t0_exp:.0f} s acumulados)")
dfA = pd.DataFrame(regA)
dfA.to_csv(OUT + "A_busqueda_aleatorio_raw.csv", index=False)
aggA_b = agregar_robusto(dfA, ["estructura", "n"], "t_busqueda")
aggA_altura = dfA.dropna(subset=["altura"]).groupby(["estructura", "n"])["altura"].mean().reset_index()
aggA_b.to_csv(OUT + "A_busqueda_aleatorio_agg.csv", index=False)
aggA_altura.to_csv(OUT + "A_altura_aleatorio.csv", index=False)
tiempos_experimentos["A"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['A']:.2f} s")

# =====================================================================
# EXPERIMENTO B: BUSQUEDA vs N, orden YA ORDENADO (el ABB se degenera y su
#   INSERCION es O(n^2): por eso el ABB se mide solo hasta N_ABB_ORD_MAX;
#   Lista y B+ llegan hasta 100.000) + altura
# =====================================================================
print("\n=== B: busqueda vs N (ordenado) ===")
t0_exp = time.perf_counter()
n_values_B = [200, 500, 1000, 2000, 3000, 5000, 7500, 10000, 30000, 100000]
N_ABB_ORD_MAX = 30000
REP_B, M_B = 3, 10000
if RAPIDO:
    n_values_B, REP_B, M_B = [200, 1000, 3000], 2, 1000
regB = []
for rep in range(REP_B):
    for n in barajar(n_values_B, "B", rep):
        sembrar("B", n, rep)
        datos_base = gen_estudiantes(n)
        datos = sorted(datos_base, key=lambda x: x["id"])
        ids = [d["id"] for d in datos_base]
        lotes = hacer_lotes(ids, M_B)
        for nombre, cls in barajar(ESTRUCTURAS, f"B{n}", rep):
            if nombre == "ABB" and n > N_ABB_ORD_MAX:
                continue          # ABB degenerado: insercion O(n^2), demasiado lento
            est, t_ins = construir(cls, datos)
            t_b, k_l, w = medir_busqueda(est, lotes)
            altura = est.altura() if hasattr(est, "altura") else None
            regB.append({"estructura": nombre, "n": n, "rep": rep, "t_insercion": t_ins, "t_busqueda": t_b,
                         "altura": altura, "lotes": k_l, "ventana_s": w, "t_epoch": time.time()})
            del est
    print(f"  repeticion {rep + 1}/{REP_B} OK ({time.perf_counter() - t0_exp:.0f} s acumulados)")
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
#   N = 10.000 / 100.000 / 1.000.000. Se repite la construccion hasta llenar la ventana
#   (con N grande una sola construccion ya la supera).
# =====================================================================
print("\n=== C: construccion a gran escala (aleatorio) ===")
t0_exp = time.perf_counter()
n_values_C = [10000, 100000, 1000000]
REP_C = 3
if RAPIDO:
    n_values_C, REP_C = [1000, 10000], 2
regC = []
for rep in range(REP_C):
    for n in barajar(n_values_C, "C", rep):
        sembrar("C", n, rep)
        datos = gen_estudiantes(n)
        for nombre, cls in barajar(ESTRUCTURAS, f"C{n}", rep):
            est, t_ins, k_c = construir_ventana(cls, datos)
            regC.append({"estructura": nombre, "n": n, "rep": rep, "t_insercion": t_ins,
                         "construcciones": k_c, "t_epoch": time.time()})
            del est
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
if RAPIDO:
    n_fijo, m_values, REP_D = 1000, [10, 100, 1000], 2
regD = []
for rep in range(REP_D):
    sembrar("D", n_fijo, rep)
    datos_fijo = gen_estudiantes(n_fijo)
    ids_fijo = [d["id"] for d in datos_fijo]
    estructuras_fijas = {nombre: construir(cls, datos_fijo)[0] for nombre, cls in ESTRUCTURAS}
    for m in barajar(m_values, "D", rep):
        lotes = hacer_lotes(ids_fijo, m)
        for nombre in barajar([n for n, _ in ESTRUCTURAS], f"D{m}", rep):
            t_b, k_l, w = medir_busqueda(estructuras_fijas[nombre], lotes)
            regD.append({"estructura": nombre, "m": m, "rep": rep, "t_busqueda": t_b,
                         "lotes": k_l, "ventana_s": w, "t_epoch": time.time()})
    print(f"  repeticion {rep + 1}/{REP_D} OK")
dfD = pd.DataFrame(regD)
dfD.to_csv(OUT + "D_variacion_M_raw.csv", index=False)
aggD = agregar_robusto(dfD, ["estructura", "m"], "t_busqueda")
aggD.to_csv(OUT + "D_variacion_M_agg.csv", index=False)
tiempos_experimentos["D"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['D']:.2f} s")

# =====================================================================
# EXPERIMENTO E: busqueda con M CALIBRADO POR ESTRUCTURA (para que los
#   tiempos caigan en el rango 1-5 s recomendado). Como ABB y B+ son hasta
#   ~1000 veces mas rapidos que la Lista, necesitan un M mucho mayor.
#   OJO: M distinto por estructura => estas curvas NO se comparan entre si
#   (para comparar estructuras con el mismo M usar el Experimento A).
#   La Lista se toma del Experimento A (M=10000), que ya cae en el rango
#   desde N=10.000.
# =====================================================================
print("\n=== E: busqueda con M calibrado por estructura (ABB y B+) ===")
t0_exp = time.perf_counter()
n_values_E = [10000, 50000, 100000, 200000]
M_E = {"ABB": 2_000_000, "B+": 4_000_000}
REP_E = 3
if RAPIDO:
    n_values_E, M_E, REP_E = [1000, 10000], {"ABB": 20_000, "B+": 40_000}, 2
regE = []
for rep in range(REP_E):
    for n in barajar(n_values_E, "E", rep):
        sembrar("E", n, rep)
        datos = gen_estudiantes(n)
        ids = [d["id"] for d in datos]
        for nombre, cls in barajar(ESTRUCTURAS, f"E{n}", rep):
            if nombre not in M_E:
                continue
            est, _ = construir(cls, datos)
            lotes = [random.choices(ids, k=M_E[nombre])]      # un solo lote: ya supera la ventana
            t_b, k_l, w = medir_busqueda(est, lotes)
            regE.append({"estructura": nombre, "n": n, "m": M_E[nombre], "rep": rep, "t_busqueda": t_b,
                         "lotes": k_l, "ventana_s": w, "t_epoch": time.time()})
            del est
    print(f"  repeticion {rep + 1}/{REP_E} OK")
dfE = pd.DataFrame(regE)
dfE.to_csv(OUT + "E_busqueda_M_calibrado_raw.csv", index=False)
aggE = agregar_robusto(dfE, ["estructura", "n", "m"], "t_busqueda")
aggE.to_csv(OUT + "E_busqueda_M_calibrado_agg.csv", index=False)
tiempos_experimentos["E"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['E']:.2f} s")

# =====================================================================
# EXPERIMENTO L: tiempo de LISTAR vs N (orden aleatorio)
#   Lista debe ordenar (O(n log n)); ABB recorre in-order (O(n));
#   B+ recorre hojas ya enlazadas (O(n), sin comparaciones).
#   Cada medicion repite listar() hasta llenar la ventana.
# =====================================================================
print("\n=== L: listar vs N (aleatorio) ===")
t0_exp = time.perf_counter()
n_values_L = [100, 1000, 10000, 100000]
REP_L = 5
if RAPIDO:
    n_values_L, REP_L = [100, 1000, 10000], 2
regL = []
for rep in range(REP_L):
    for n in barajar(n_values_L, "L", rep):
        sembrar("L", n, rep)
        datos = gen_estudiantes(n)
        ids_ord = sorted(d["id"] for d in datos)
        for nombre, cls in barajar(ESTRUCTURAS, f"L{n}", rep):
            est, _ = construir(cls, datos)
            r, t_l, k_l = medir_listar(est)
            assert [x["id"] for x in r] == ids_ord, f"{nombre}.listar() no devuelve los IDs ordenados"
            regL.append({"estructura": nombre, "n": n, "rep": rep, "t_listar": t_l, "llamadas": k_l,
                         "t_epoch": time.time()})
            del est, r
    print(f"  repeticion {rep + 1}/{REP_L} OK")
dfL = pd.DataFrame(regL)
dfL.to_csv(OUT + "L_listar_raw.csv", index=False)
aggL = agregar_robusto(dfL, ["estructura", "n"], "t_listar")
aggL.to_csv(OUT + "L_listar_agg.csv", index=False)
tiempos_experimentos["L"] = time.perf_counter() - t0_exp
print(f"  >> tardo {tiempos_experimentos['L']:.2f} s")

# =====================================================================
# 4b. PENDIENTES LOG-LOG (con R^2) frente a la teoria  -> pendientes_loglog.csv
# =====================================================================
pend = pd.concat([pendientes_loglog(aggA_b, "n", "t_busqueda_media", "A busqueda aleatorio"),
                  pendientes_loglog(aggB_b, "n", "t_busqueda_media", "B busqueda ordenado"),
                  pendientes_loglog(aggB_i, "n", "t_insercion_media", "B construccion ordenado"),
                  pendientes_loglog(aggC, "n", "t_insercion_media", "C construccion aleatorio"),
                  pendientes_loglog(aggL, "n", "t_listar_media", "L listar aleatorio"),
                  pendientes_loglog(aggD, "m", "t_busqueda_media", "D busqueda vs M")], ignore_index=True)
pend.to_csv(OUT + "pendientes_loglog.csv", index=False)
print("\n=== Pendientes log-log (tiempo vs N; ref: log2N, N, NlogN en la misma rejilla) ===")
print(pend.round(3).to_string(index=False))

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

PIE = (f"Cada punto = media de las repeticiones (cada medicion dura >= {VENTANA:g} s); "
       f"barras = desviacion estandar. Semilla {SEMILLA}.")

def guardar(fig, nombre, dpi=140, pie=None):
    fig.text(0.01, 0.005, pie or PIE, fontsize=7.5, color="#666666", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(OUT + nombre, dpi=dpi); plt.close(fig)

# FigA: busqueda vs n (aleatorio) en lineal / semilog / log-log
fig, axes = plt.subplots(1, 3, figsize=(17, 5))
for ax, esc in zip(axes, ["lineal", "semilog", "loglog"]):
    plot_err(ax, aggA_b, "n", "t_busqueda_media", "t_busqueda_std",
             "N (número de estudiantes)", f"Tiempo total de búsqueda (M={M_A}) [s]",
             esc.upper())
    if esc in ("semilog", "loglog"): ax.set_yscale("log")
    if esc == "loglog": ax.set_xscale("log")
fig.suptitle(f"Tiempo de BÚSQUEDA vs N — orden ALEATORIO (N={min(n_values_A):,} a {max(n_values_A):,}, M={M_A:,})".replace(",", "."))
guardar(fig, "figA_busqueda_aleatorio.png")

# FigA2: una grafica POR estructura, cada una con su propia escala vertical
# (sirve para ver el detalle de ABB y B+; OJO: las escalas Y son distintas
# entre paneles, para comparar estructuras usar figA o figA3)
fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
for ax, est in zip(axes, ["Lista", "ABB", "B+"]):
    sub = aggA_b[aggA_b.estructura == est].sort_values("n")
    ax.errorbar(sub.n, sub.t_busqueda_media, yerr=sub.t_busqueda_std, color=colores[est],
                marker=marcas[est], capsize=3, linewidth=1.8, label=est)
    ax.set_xlabel("N (número de estudiantes)")
    ax.set_ylabel(f"Tiempo total de búsqueda (M={M_A}) [s]")
    ax.set_title(f"{est} (escala vertical propia)")
    ax.legend(); ax.grid(alpha=0.3)
fig.suptitle(f"Búsqueda vs N por estructura — orden ALEATORIO (M={M_A})")
guardar(fig, "figA2_busqueda_por_estructura.png")

# FigA3: zoom ABB vs B+ (comparables entre si, sin la Lista que los aplasta)
fig, ax = plt.subplots(figsize=(7.5, 5))
plot_err(ax, aggA_b[aggA_b.estructura.isin(["ABB", "B+"])], "n", "t_busqueda_media", "t_busqueda_std",
         "N (número de estudiantes)", f"Tiempo total de búsqueda (M={M_A}) [s]",
         "Zoom: ABB vs B+ — búsqueda vs N, orden ALEATORIO")
guardar(fig, "figA3_zoom_abb_vs_bplus.png")

# FigB: busqueda vs n (ordenado)
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggB_b, "n", "t_busqueda_media", "t_busqueda_std",
         f"N (número de estudiantes)", f"Tiempo total de búsqueda (M={M_B}) [s]",
         "Búsqueda vs N — orden YA ORDENADO (caso patológico del ABB)")
guardar(fig, "figB_busqueda_ordenado.png")

# FigC: construccion gran escala
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggC, "n", "t_insercion_media", "t_insercion_std",
         "N (escala log)", "Tiempo total de construcción [s] (escala log)",
         f"Construcción vs N — {' / '.join(f'{v:,}'.replace(',', '.') for v in n_values_C)} (aleatorio)")
ax.set_xscale("log"); ax.set_yscale("log")
guardar(fig, "figC_construccion_gran_escala.png")

# FigD: variacion de M
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggD, "m", "t_busqueda_media", "t_busqueda_std",
         "M = número de búsquedas (escala log)", "Tiempo total de búsqueda [s] (escala log)",
         f"Tiempo de búsqueda vs M — N={n_fijo:,} fijo, aleatorio".replace(",", "."))
ax.set_xscale("log"); ax.set_yscale("log")
guardar(fig, "figD_variacion_M.png")

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
axes[1].set_ylabel(f"Tiempo total de búsqueda (M={M_A}) [s]")
axes[1].set_title("Relación altura <-> tiempo de búsqueda (cada punto = una corrida)")
axes[1].legend(); axes[1].grid(alpha=0.3)
guardar(fig, "figE_altura_vs_busqueda.png")

# FigF: tiempo de listar vs n
fig, ax = plt.subplots(figsize=(7, 5))
plot_err(ax, aggL, "n", "t_listar_media", "t_listar_std",
         "N (escala log)", "Tiempo de listar() [s] (escala log)",
         "Tiempo de LISTAR (orden ascendente por ID) vs N")
ax.set_xscale("log"); ax.set_yscale("log")
guardar(fig, "figF_listar.png")

# FigG: busqueda con M calibrado por estructura (una grafica por estructura,
# cada una con su propio M y su propia escala; NO comparar entre paneles)
fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
sub_l = aggA_b[(aggA_b.estructura == "Lista") & (aggA_b.n >= min(n_values_E))].sort_values("n")
paneles = [("Lista", sub_l.n, sub_l.t_busqueda_media, sub_l.t_busqueda_std, M_A)]
for est in ["ABB", "B+"]:
    se = aggE[aggE.estructura == est].sort_values("n")
    paneles.append((est, se.n, se.t_busqueda_media, se.t_busqueda_std, M_E[est]))
for ax, (est, x, y, e, m) in zip(axes, paneles):
    ax.errorbar(x, y, yerr=e, color=colores[est], marker=marcas[est], capsize=3, linewidth=1.8, label=est)
    ax.axhspan(1, 5, color="gold", alpha=0.25, label="Rango 1-5 s")
    ax.set_xlabel("N (número de estudiantes)")
    ax.set_ylabel("Tiempo total de búsqueda [s]")
    ax.set_title(f"{est}: M = {m:,}".replace(",", "."))
    ax.legend(); ax.grid(alpha=0.3)
fig.suptitle("Búsqueda vs N con M calibrado por estructura (cada panel usa su propio M y su propia escala)")
guardar(fig, "figG_busqueda_M_calibrado.png")

# FigH (NUEVA): DISPERSION entre repeticiones. Boxplot de las repeticiones del experimento A en
# dos N (uno pequeno y uno grande): caja = Q1-Q3, linea = mediana, circulos = atipicos (regla IQR).
n_disp = [n for n in (10000, 200000) if n in n_values_A] or [max(n_values_A)]
fig, axes = plt.subplots(1, len(n_disp), figsize=(6.2 * len(n_disp), 5), squeeze=False)
for ax, n in zip(axes[0], n_disp):
    datos_box = [dfA[(dfA.estructura == e) & (dfA.n == n)].t_busqueda.values for e in ["Lista", "ABB", "B+"]]
    bp = ax.boxplot(datos_box, patch_artist=True)
    ax.set_xticks([1, 2, 3]); ax.set_xticklabels(["Lista", "ABB", "B+"])
    for patch, e in zip(bp["boxes"], ["Lista", "ABB", "B+"]):
        patch.set_facecolor(colores[e]); patch.set_alpha(0.5)
    for i, e in enumerate(["Lista", "ABB", "B+"], start=1):   # cada repeticion como punto
        v = dfA[(dfA.estructura == e) & (dfA.n == n)].t_busqueda.values
        ax.scatter(np.full(len(v), i) + np.linspace(-0.12, 0.12, len(v)), v, s=14, color="k", alpha=0.6, zorder=3)
    ax.set_yscale("log"); ax.grid(alpha=0.3, which="both")
    ax.set_ylabel(f"Tiempo total de búsqueda (M={M_A}) [s] (escala log)")
    ax.set_title(f"N = {n:,}".replace(",", "."))
fig.suptitle("DISPERSIÓN entre repeticiones (punto negro = 1 repetición)")
guardar(fig, "figH_dispersion_repeticiones.png",
        pie=f"Caja = Q1-Q3, línea = mediana, círculos = atípicos (regla IQR). Cada repetición usa datos distintos. Semilla {SEMILLA}.")

# FigI (NUEVA): ESTABILIDAD del computador en el tiempo. Cada medicion de busqueda (A y B) se divide
# entre la mediana de su grupo (estructura, N, experimento); si el computador se ralentiza o acelera
# durante la corrida, la linea se aleja de 1.0.
frames = []
for nom_exp, d in (("A", dfA), ("B", dfB)):
    d = d.copy(); d["exp"] = nom_exp; frames.append(d[["exp", "estructura", "n", "t_busqueda", "t_epoch"]])
dfT = pd.concat(frames, ignore_index=True)
dfT["rel"] = dfT.t_busqueda / dfT.groupby(["exp", "estructura", "n"]).t_busqueda.transform("median")
dfT["min"] = (dfT.t_epoch - dfT.t_epoch.min()) / 60
fig, ax = plt.subplots(figsize=(11, 5))
for est in ["Lista", "ABB", "B+"]:
    s = dfT[dfT.estructura == est].sort_values("min")
    ax.scatter(s["min"], s.rel, s=9, alpha=0.3, color=colores[est])
    ax.plot(s["min"], s.rel.rolling(25, min_periods=5, center=True).median(), color=colores[est], linewidth=2,
            label=f"{est} (mediana móvil)")
ax.axhline(1.0, color="k", linewidth=0.8)
ax.set_xlabel("Minutos desde el inicio de las mediciones de búsqueda")
ax.set_ylabel("Tiempo de la medición / mediana de su grupo (1.0 = sin deriva)")
ax.set_title("ESTABILIDAD del computador durante la corrida (búsqueda, experimentos A y B)")
ax.legend(); ax.grid(alpha=0.3)
guardar(fig, "figI_estabilidad_tiempo.png",
        pie=f"Cada punto = una medición de búsqueda dividida entre la mediana de su grupo; línea = mediana móvil. Semilla {SEMILLA}.")

print("\nGraficas guardadas: figA, figA2, figA3, figB..figG, figH (dispersion), figI (estabilidad)")

# =====================================================================
# 6. FICHA TECNICA (para la sustentacion: hardware, software, metodologia)
# =====================================================================
tiempo_total = time.perf_counter() - t_inicio_total

ruido_lineas = []
for _est in ["Lista", "ABB", "B+"]:
    _sub = aggA_b[(aggA_b.estructura == _est) & (aggA_b.n >= 10000)]
    if _sub.empty:
        continue
    _imin, _imax = _sub.cv_pct.idxmin(), _sub.cv_pct.idxmax()
    ruido_lineas.append(
        f"   {_est:<6}: minimo {_sub.cv_pct.loc[_imin]:.2f}% (N={int(_sub.n.loc[_imin]):,}) | "
        f"maximo {_sub.cv_pct.loc[_imax]:.2f}% (N={int(_sub.n.loc[_imax]):,})".replace(",", "."))
ruido_txt = "\n".join(ruido_lineas)

_vent = pd.concat([dfA[["ventana_s"]], dfB[["ventana_s"]], dfD[["ventana_s"]], dfE[["ventana_s"]]])
cumple_txt = (f"{(_vent.ventana_s >= VENTANA * 0.999).mean() * 100:.1f} % de las {len(_vent)} mediciones de busqueda "
              f"(A, B, D, E) duraron >= {VENTANA:g} s (minimo {_vent.ventana_s.min():.3f} s)")
ficha = f"""FICHA TECNICA DEL EXPERIMENTO - Laboratorio 3
================================================
Fecha y hora de la corrida : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'*** MODO RAPIDO: solo para probar el script, NO usar estos numeros en el informe ***' if RAPIDO else ''}

HARDWARE / SOFTWARE
--------------------
Python       : {platform.python_version()}
SO           : {platform.system()} {platform.release()}
Procesador   : {platform.processor() or 'no identificado'}
Reloj        : time.perf_counter, resolucion {time.get_clock_info('perf_counter').resolution:.1e} s
(Nota: correr localmente, NO en Colab, para evitar variabilidad de recursos
 compartidos. Todo el experimento corre en un solo proceso, en RAM.)

SEMILLA Y GENERACION DE DATOS
-------------------------------
Semilla base: {SEMILLA}  [{SEMILLA_MODO}]
Para repetir exactamente esta corrida: python laboratorio3_completo.py --semilla {SEMILLA}
IDs unicos por muestreo sin reemplazo (random.sample) sobre un rango amplio,
simulando numeros de matricula reales. Nombre/edad/promedio son sinteticos,
no afectan el rendimiento medido (solo el ID se usa para buscar/ordenar).
Cada repeticion usa un dataset DISTINTO: semilla = "<base>-<experimento>-<N>-<repeticion>".
Asi la desviacion estandar incluye la variabilidad entre conjuntos de datos y no solo el ruido
del reloj. Con otra semilla base (--semilla aleatoria) se obtienen datos distintos.

GENERACION DE BUSQUEDAS
------------------------
Para cada N se generan lotes de M IDs objetivo, elegidos aleatoriamente
ENTRE LOS IDs QUE SI EXISTEN en el conjunto (random.choices, con reemplazo, para que M sea
constante aunque N < M), para medir el caso de busqueda exitosa. Se preparan 10 lotes
distintos que se recorren ciclicamente si la ventana exige repetir. M es un parametro
independiente, explorado en el Experimento D (M = 10, 100, 1000, 10000) con N fijo.

METODO DE MEDICION DE TIEMPOS
-------------------------------
time.perf_counter() (reloj monotonico de mayor resolucion en Python).
VENTANA MINIMA: cada medicion dura >= {VENTANA:g} s. Se mide un lote; si dura menos que la
ventana, se repite (lotes distintos) hasta acumular la ventana y se reporta el tiempo medio por
lote. Lo mismo para listar() (repite llamadas) y para la construccion del Experimento C
(repite construcciones). Cumplimiento: {cumple_txt}.
Insercion: se cronometra construir la estructura completa (N inserciones).
Busqueda:  se cronometra el total de las M busquedas (no una individual).
           Antes de cronometrar se hace un calentamiento de hasta 200 busquedas
           (sin medir) y se desactiva el recolector de basura (gc) durante la medicion.
Listar:    se cronometra una llamada a listar() sobre la estructura ya construida.
ORDEN ALEATORIO DE EJECUCION: en cada repeticion se baraja el orden de los N y de las
estructuras (reproducible por semilla), para que la deriva del computador (calentamiento,
procesos de fondo) no se confunda con el efecto de N. La figura figI muestra esa deriva.

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
Media y desviacion estandar (tras remover outliers), IC 95 % de la media (t de Student,
columna *_ic95), mediana (sin remover outliers, como referencia robusta), coeficiente de
variacion (cv_pct) y ajuste de pendiente log-log con R^2 (regresion sobre ln(tiempo) vs ln(N),
archivo pendientes_loglog.csv) junto a las pendientes que tendrian log2(N+1), N y N*log2(N+1)
en la misma rejilla de N, para comparar el crecimiento empirico con la complejidad teorica.

PARAMETROS DE CADA EXPERIMENTO
--------------------------------
A) Busqueda vs N, aleatorio : N={n_values_A}
   repeticiones={REP_A}, M={M_A}  -> tardo {tiempos_experimentos['A']:.2f} s
B) Busqueda vs N, ordenado  : N={n_values_B}  (ABB solo hasta N={N_ABB_ORD_MAX}: insercion O(n^2))
   repeticiones={REP_B}, M={M_B}  -> tardo {tiempos_experimentos['B']:.2f} s
C) Construccion gran escala : N={n_values_C}
   repeticiones={REP_C}  -> tardo {tiempos_experimentos['C']:.2f} s
D) Variacion de M, N={n_fijo} fijo : M={m_values}
   repeticiones={REP_D}  -> tardo {tiempos_experimentos['D']:.2f} s
E) Busqueda con M calibrado (ABB y B+; Lista = Experimento A): N={n_values_E}
   M por estructura={M_E}, repeticiones={REP_E}  -> tardo {tiempos_experimentos['E']:.2f} s
L) Listar vs N, aleatorio   : N={n_values_L}
   repeticiones={REP_L}  -> tardo {tiempos_experimentos['L']:.2f} s

TIEMPO TOTAL DEL SCRIPT: {tiempo_total:.2f} s (~{tiempo_total/60:.1f} min)

RUIDO EN EL EXPERIMENTO A (desviacion estandar / media, N >= 10.000)
{ruido_txt}

VERIFICACION DE CORRECTITUD: realizada al inicio (n=2000) -- las 3
estructuras producen el mismo resultado en listar() y en buscar()
(ver mensaje "[OK] Verificacion de correctitud" en la salida de consola).
Ademas, en cada medicion de listar() se comprueba que los IDs salgan ordenados y en cada
calentamiento de busqueda que el ID buscado exista.
"""
with open(OUT + "ficha_tecnica.txt", "w", encoding="utf-8") as f:
    f.write(ficha)
print("\n" + ficha)
print(f"Todo listo. Resultados en: {OUT}")