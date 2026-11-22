
"""
EyeTrace - Analisis de la evaluacion con participantes
=====================================================

Lee los archivos que guarda el modo evaluacion en la carpeta datos/
y genera, en la carpeta resultados/:

  resultados.md                 tablas listas para pegar en el README
  resumen_participantes.csv     una fila por participante
  fig_exactitud_participantes.png
  fig_mapa_exactitud.png
  fig_precision_practica.png
  fig_deteccion.png
  fig_rendimiento.png
  fig_encuesta.png
  fig_galeria_obras.png

Uso (desde la carpeta del proyecto, con el entorno activo):

  python analisis/analizar_resultados.py
  python analisis/analizar_resultados.py --datos otra/carpeta --salida otra/salida

Las sesiones canceladas se ignoran salvo que se use --incluir-canceladas.
"""

import argparse
import csv
import glob
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.image as mpimg  # noqa: E402


# =====================================
# ESTILO DE LAS GRAFICAS
# =====================================
# Colores validados para daltonismo y contraste sobre fondo claro
# (versiones intensas de la paleta pastel de EyeTrace).

ROSA = "#d9668a"
AZUL = "#5b8fd6"
VERDE = "#3f9d6e"
TINTA = "#3d3553"
TINTA_SUAVE = "#6b6385"
REJILLA = "#e7e2ee"
FONDO = "#fcfcfb"

COLORES_FIGURA = {"corazon": ROSA, "flor": AZUL, "mariposa": VERDE}
NOMBRES_FIGURA = {"corazon": "Corazón", "flor": "Flor", "mariposa": "Mariposa"}

# Escala Likert divergente: desacuerdo (rosa) - neutro (gris) - acuerdo (azul)
COLORES_LIKERT = ["#c2476f", "#eba3b9", "#c9c6cf", "#9dbbe8", "#3f78c8"]

plt.rcParams.update({
    "figure.facecolor": FONDO,
    "axes.facecolor": FONDO,
    "axes.edgecolor": REJILLA,
    "axes.labelcolor": TINTA,
    "axes.titlecolor": TINTA,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "xtick.color": TINTA_SUAVE,
    "ytick.color": TINTA_SUAVE,
    "axes.grid": True,
    "grid.color": REJILLA,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
    "legend.frameon": False,
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
})


# =====================================
# LECTURA DE DATOS
# =====================================

def leer_csv(ruta):

    if not os.path.exists(ruta):
        return []

    with open(ruta, newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def numero(valor):

    try:
        return float(valor)
    except (TypeError, ValueError):
        return np.nan


def media_std(valores):

    v = np.array([x for x in valores if not np.isnan(x)], dtype=float)

    if len(v) == 0:
        return np.nan, np.nan

    return float(v.mean()), float(v.std(ddof=1)) if len(v) > 1 else 0.0


def fmt(valor, decimales=1, unidad=""):

    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"

    return f"{valor:.{decimales}f}{unidad}"


def fmt_ms(media, std, decimales=1, unidad=""):

    if np.isnan(media):
        return "—"

    return f"{media:.{decimales}f} ± {std:.{decimales}f}{unidad}"


def cargar(carpeta, incluir_canceladas):

    sesiones = leer_csv(os.path.join(carpeta, "sesiones.csv"))

    if not incluir_canceladas:
        sesiones = [s for s in sesiones if "[cancelada]" not in s.get("notas", "")]

    validas = {s["sesion"] for s in sesiones}

    def filtrar(filas):
        return [f for f in filas if f.get("sesion") in validas]

    datos = {
        "sesiones": sesiones,
        "exactitud": filtrar(leer_csv(os.path.join(carpeta, "exactitud.csv"))),
        "practica": filtrar(leer_csv(os.path.join(carpeta, "practica.csv"))),
        "encuesta": filtrar(leer_csv(os.path.join(carpeta, "encuesta.csv"))),
        "fotogramas": {},
        "obras": [],
    }

    for sesion in validas:

        ruta = os.path.join(carpeta, "fotogramas", f"{sesion}.csv")
        datos["fotogramas"][sesion] = leer_csv(ruta)

        obra = os.path.join(carpeta, "obras", f"{sesion}.png")
        if os.path.exists(obra):
            datos["obras"].append((sesion, obra))

    return datos


def participante_de(datos, sesion):

    for s in datos["sesiones"]:
        if s["sesion"] == sesion:
            return s["participante"]

    return sesion


# =====================================
# GRAFICAS
# =====================================

def barras_por_participante(ax, etiquetas, medias, desvios, color, unidad):

    x = np.arange(len(etiquetas))

    ax.bar(x, medias, width=0.6, color=color, edgecolor=FONDO, linewidth=2,
           yerr=desvios, capsize=4, error_kw={"ecolor": TINTA_SUAVE, "lw": 1.2})

    for xi, m in zip(x, medias):
        if not np.isnan(m):
            ax.text(xi, m, f" {m:.0f}{unidad}", ha="center", va="bottom",
                    color=TINTA, fontsize=9, rotation=0)

    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas)
    ax.grid(axis="x", visible=False)


def fig_exactitud_participantes(datos, salida):

    filas = datos["exactitud"]

    if not filas:
        return None

    participantes = sorted({f["participante"] for f in filas})
    medias, desvios = [], []

    for p in participantes:
        m, s = media_std([numero(f["error_px"]) for f in filas if f["participante"] == p])
        medias.append(m)
        desvios.append(s)

    general, _ = media_std([numero(f["error_px"]) for f in filas])

    fig, ax = plt.subplots(figsize=(max(6, 0.7 * len(participantes) + 3), 4))
    barras_por_participante(ax, participantes, medias, desvios, AZUL, "")

    ax.axhline(general, color=ROSA, lw=2, ls="--")
    ax.text(len(participantes) - 0.5, general, f"promedio {general:.0f} px",
            ha="right", va="bottom", color=TINTA, fontsize=9)

    ax.set_title("Error de exactitud por participante")
    ax.set_ylabel("Error (px)  ·  media ± desviación")
    ax.set_xlabel("Participante")

    ruta = os.path.join(salida, "fig_exactitud_participantes.png")
    fig.savefig(ruta)
    plt.close(fig)

    return ruta


def fig_mapa_exactitud(datos, salida):

    filas = datos["exactitud"]

    if not filas:
        return None

    ancho = np.nanmedian([numero(s["ancho_lienzo_px"]) for s in datos["sesiones"]]) or 1000
    alto = np.nanmedian([numero(s["alto_lienzo_px"]) for s in datos["sesiones"]]) or 700

    fig, ax = plt.subplots(figsize=(8, 8 * alto / ancho + 0.6))

    # Cada mirada, normalizada al tamano de su propio lienzo
    tamanos = {s["sesion"]: (numero(s["ancho_lienzo_px"]), numero(s["alto_lienzo_px"]))
               for s in datos["sesiones"]}

    por_punto = {}

    for f in filas:

        w, h = tamanos.get(f["sesion"], (ancho, alto))
        ox, oy = numero(f["objetivo_x"]) / w, numero(f["objetivo_y"]) / h
        mx, my = numero(f["mirada_x"]) / w, numero(f["mirada_y"]) / h

        ax.plot([ox * ancho, mx * ancho], [oy * alto, my * alto],
                color=AZUL, alpha=0.25, lw=1)
        ax.scatter(mx * ancho, my * alto, s=22, color=AZUL, alpha=0.55,
                   edgecolor=FONDO, linewidth=0.8, zorder=3)

        por_punto.setdefault((round(ox, 3), round(oy, 3)), []).append((mx, my))

    # Objetivo y mirada promedio de todos los participantes
    for (ox, oy), miradas in por_punto.items():

        mx, my = np.mean(miradas, axis=0)

        ax.annotate("", xy=(mx * ancho, my * alto), xytext=(ox * ancho, oy * alto),
                    arrowprops={"arrowstyle": "->", "color": ROSA, "lw": 2})
        ax.scatter(ox * ancho, oy * alto, s=90, color=TINTA, edgecolor=FONDO,
                   linewidth=2, zorder=4)

    ax.set_xlim(0, ancho)
    ax.set_ylim(alto, 0)
    ax.set_aspect("equal")
    ax.set_title("Mapa de exactitud en el lienzo")
    ax.set_xlabel("x (px)")
    ax.set_ylabel("y (px)")

    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", color=TINTA, markersize=9, label="Punto objetivo"),
        Line2D([], [], marker="o", ls="", color=AZUL, alpha=0.6, markersize=6, label="Mirada de cada participante"),
        Line2D([], [], color=ROSA, lw=2, label="Desfase promedio"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3)

    ruta = os.path.join(salida, "fig_mapa_exactitud.png")
    fig.savefig(ruta)
    plt.close(fig)

    return ruta


def fig_precision_practica(datos, salida):

    filas = datos["practica"]

    if not filas:
        return None

    figuras = [f for f in ["corazon", "flor", "mariposa"]
               if any(r["figura"] == f for r in filas)]

    fig, ax = plt.subplots(figsize=(6.5, 4))

    for i, figura in enumerate(figuras):

        valores = [numero(r["precision_pct"]) for r in filas if r["figura"] == figura]
        valores = [v for v in valores if not np.isnan(v)]

        if not valores:
            continue

        # Caja + cada participante como punto
        caja = ax.boxplot([valores], positions=[i], widths=0.45, patch_artist=True,
                          showfliers=False)
        for elemento in caja["boxes"]:
            elemento.set(facecolor=COLORES_FIGURA[figura], alpha=0.35,
                         edgecolor=COLORES_FIGURA[figura], linewidth=1.5)
        for clave in ("whiskers", "caps", "medians"):
            for elemento in caja[clave]:
                elemento.set(color=COLORES_FIGURA[figura], linewidth=1.5)

        jitter = np.random.default_rng(i).uniform(-0.12, 0.12, len(valores))
        ax.scatter(i + jitter, valores, s=30, color=COLORES_FIGURA[figura],
                   edgecolor=FONDO, linewidth=1, zorder=3)

        ax.text(i, 103, f"media {np.mean(valores):.0f}%", ha="center",
                color=TINTA, fontsize=9)

    ax.set_xticks(range(len(figuras)))
    ax.set_xticklabels([NOMBRES_FIGURA[f] for f in figuras])
    ax.set_ylim(0, 110)
    ax.set_ylabel("Precisión de seguimiento (%)")
    ax.set_title("Precisión en el modo práctica por figura")
    ax.grid(axis="x", visible=False)

    ruta = os.path.join(salida, "fig_precision_practica.png")
    fig.savefig(ruta)
    plt.close(fig)

    return ruta


def tasas_por_etapa(datos):

    # Tasa de deteccion (ambos ojos) por sesion y por etapa
    resultado = {}

    for sesion, filas in datos["fotogramas"].items():

        etapas = {}

        for f in filas:
            if f["etapa"] in ("inicio", "encuesta", "resumen"):
                continue
            etapa = f["etapa"].split("_")[0]
            total, ok = etapas.get(etapa, (0, 0))
            etapas[etapa] = (total + 1, ok + int(f["ok"] == "1"))

        resultado[sesion] = {e: 100 * ok / total for e, (total, ok) in etapas.items() if total}

    return resultado


def fig_deteccion(datos, salida):

    sesiones = datos["sesiones"]

    if not sesiones:
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4),
                                   gridspec_kw={"width_ratios": [max(len(sesiones), 3), 3]})

    # Por participante
    etiquetas = [s["participante"] for s in sesiones]
    tasas = [numero(s["tasa_deteccion_pct"]) for s in sesiones]
    barras_por_participante(ax1, etiquetas, tasas, [0] * len(tasas), AZUL, "%")
    ax1.set_ylim(0, 110)
    ax1.set_title("Detección de ambos ojos por participante")
    ax1.set_ylabel("Fotogramas con ambos ojos (%)")
    ax1.set_xlabel("Participante")

    # Por condicion
    grupos = []
    for campo, nombre in (("lentes", "Lentes"), ("iluminacion", "Luz")):
        for valor in sorted({s[campo] for s in sesiones if s[campo]}):
            m, sd = media_std([numero(s["tasa_deteccion_pct"]) for s in sesiones if s[campo] == valor])
            n = sum(1 for s in sesiones if s[campo] == valor)
            grupos.append((f"{nombre}: {valor}\n(n={n})", m, sd,
                           ROSA if campo == "lentes" else VERDE))

    if grupos:
        x = np.arange(len(grupos))
        ax2.bar(x, [g[1] for g in grupos], yerr=[g[2] for g in grupos], width=0.6,
                color=[g[3] for g in grupos], edgecolor=FONDO, linewidth=2, capsize=4,
                error_kw={"ecolor": TINTA_SUAVE})
        ax2.set_xticks(x)
        ax2.set_xticklabels([g[0] for g in grupos], fontsize=9)
        for xi, g in zip(x, grupos):
            ax2.text(xi, g[1], f" {g[1]:.0f}%", ha="center", va="bottom", color=TINTA, fontsize=9)
    ax2.set_ylim(0, 110)
    ax2.set_title("Detección según condición")
    ax2.grid(axis="x", visible=False)

    ruta = os.path.join(salida, "fig_deteccion.png")
    fig.savefig(ruta)
    plt.close(fig)

    return ruta


def fig_rendimiento(datos, salida):

    tiempos = []
    fps_sesion = []

    for sesion, filas in datos["fotogramas"].items():

        t = [numero(f["t_s"]) for f in filas]
        tiempos += [numero(f["procesamiento_ms"]) for f in filas]

        if len(t) > 1:
            dt = np.diff(t)
            dt = dt[dt > 0]
            if len(dt):
                fps_sesion.append(1 / np.median(dt))

    tiempos = np.array([v for v in tiempos if not np.isnan(v)])

    if len(tiempos) == 0:
        return None

    fig, ax = plt.subplots(figsize=(7, 3.8))

    limite = np.percentile(tiempos, 99.5)
    ax.hist(tiempos[tiempos <= limite], bins=40, color=AZUL, edgecolor=FONDO, linewidth=1)

    mediana = np.median(tiempos)
    p95 = np.percentile(tiempos, 95)
    ax.axvline(mediana, color=ROSA, lw=2)
    ax.axvline(p95, color=ROSA, lw=2, ls="--")
    ax.text(mediana, ax.get_ylim()[1] * 0.92, f" mediana {mediana:.1f} ms", color=TINTA, fontsize=9)
    ax.text(p95, ax.get_ylim()[1] * 0.80, f" p95 {p95:.1f} ms", color=TINTA, fontsize=9)

    titulo = "Tiempo de procesamiento por fotograma"
    if fps_sesion:
        titulo += f"  ·  {np.mean(fps_sesion):.1f} FPS en promedio"
    ax.set_title(titulo)
    ax.set_xlabel("Procesamiento (ms): espejo + MediaPipe + cálculo de la mirada")
    ax.set_ylabel("Fotogramas")
    ax.grid(axis="x", visible=False)

    ruta = os.path.join(salida, "fig_rendimiento.png")
    fig.savefig(ruta)
    plt.close(fig)

    return ruta


def fig_encuesta(datos, salida, preguntas):

    filas = datos["encuesta"]

    if not filas:
        return None

    claves = [c for c, _ in preguntas if any(f.get(c) for f in filas)]

    fig, ax = plt.subplots(figsize=(10, 0.6 * len(claves) + 1.6))

    for i, clave in enumerate(claves):

        valores = [int(f[clave]) for f in filas if f.get(clave, "").isdigit()]
        n = len(valores)

        if not n:
            continue

        conteo = [valores.count(v) / n * 100 for v in range(1, 6)]

        # Barra divergente centrada en el punto neutro (3)
        inicio = -(conteo[0] + conteo[1] + conteo[2] / 2)

        for v in range(5):
            ax.barh(i, conteo[v], left=inicio, color=COLORES_LIKERT[v],
                    edgecolor=FONDO, linewidth=2, height=0.62)
            if conteo[v] >= 8:
                ax.text(inicio + conteo[v] / 2, i, f"{conteo[v]:.0f}%", ha="center",
                        va="center", fontsize=8, color=TINTA)
            inicio += conteo[v]

        ax.text(102, i, f"media {np.mean(valores):.1f}", va="center", color=TINTA, fontsize=9)

    textos = dict(preguntas)
    ax.set_yticks(range(len(claves)))
    ax.set_yticklabels([textos[c] for c in claves])
    ax.invert_yaxis()
    ax.axvline(0, color=TINTA_SUAVE, lw=1)
    ax.set_xlim(-100, 120)
    ax.set_xticks([-100, -50, 0, 50, 100])
    ax.set_xticklabels(["100%", "50%", "0", "50%", "100%"])
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Encuesta de experiencia (n = {len(filas)})")

    from matplotlib.patches import Patch
    nombres = ["1 Totalmente en desacuerdo", "2", "3 Neutral", "4", "5 Totalmente de acuerdo"]
    ax.legend(handles=[Patch(color=c, label=t) for c, t in zip(COLORES_LIKERT, nombres)],
              loc="upper center", bbox_to_anchor=(0.45, -0.12), ncol=5, fontsize=8)

    ruta = os.path.join(salida, "fig_encuesta.png")
    fig.savefig(ruta)
    plt.close(fig)

    return ruta


def fig_galeria(datos, salida):

    obras = sorted(datos["obras"])

    if not obras:
        return None

    columnas = min(4, len(obras))
    filas = int(np.ceil(len(obras) / columnas))

    fig, ejes = plt.subplots(filas, columnas, figsize=(3.4 * columnas, 2.6 * filas + 0.4),
                             squeeze=False)

    for eje in ejes.flat:
        eje.axis("off")

    for eje, (sesion, ruta) in zip(ejes.flat, obras):
        eje.imshow(mpimg.imread(ruta))
        eje.set_title(participante_de(datos, sesion), fontsize=10, color=TINTA)

    fig.suptitle("Obras del minuto de dibujo libre", color=TINTA, fontweight="bold")

    ruta = os.path.join(salida, "fig_galeria_obras.png")
    fig.savefig(ruta)
    plt.close(fig)

    return ruta


# =====================================
# TABLAS
# =====================================

def tablas(datos, salida, figuras, preguntas):

    sesiones = datos["sesiones"]
    exactitud = datos["exactitud"]
    practica = datos["practica"]
    encuesta = datos["encuesta"]
    etapas = tasas_por_etapa(datos)

    lineas = ["# Resultados de la evaluación de EyeTrace", ""]
    lineas.append(f"Participantes: **{len(sesiones)}**  ")
    lineas.append(f"Puntos de exactitud medidos: **{len(exactitud)}**  ")
    lineas.append(f"Figuras practicadas: **{len(practica)}**  ")
    lineas.append(f"Encuestas: **{len(encuesta)}**")
    lineas.append("")

    # ---------- Resumen general ----------
    def fila_general(nombre, valores, decimales=1, unidad=""):
        m, s = media_std(valores)
        v = [x for x in valores if not np.isnan(x)]
        rango = f"{min(v):.{decimales}f} – {max(v):.{decimales}f}{unidad}" if v else "—"
        return f"| {nombre} | {fmt_ms(m, s, decimales, unidad)} | {rango} |"

    lineas += [
        "## Resumen general (media ± desviación estándar entre participantes)", "",
        "| Métrica | Media ± DE | Rango |",
        "|---|---|---|",
        fila_general("Detección de ambos ojos", [numero(s["tasa_deteccion_pct"]) for s in sesiones], 1, "%"),
        fila_general("Fotogramas por segundo", [numero(s["fps_promedio"]) for s in sesiones], 1),
        fila_general("Procesamiento por fotograma", [numero(s["procesamiento_ms_promedio"]) for s in sesiones], 1, " ms"),
        fila_general("Error de exactitud", [numero(s["error_medio_px"]) for s in sesiones], 0, " px"),
        fila_general("Error de exactitud (% diagonal)", [numero(s["error_medio_pct"]) for s in sesiones], 1, "%"),
        fila_general("Dispersión de la mirada (RMS)", [numero(s["dispersion_media_px"]) for s in sesiones], 0, " px"),
        fila_general("Precisión en la práctica", [numero(s["precision_practica_pct"]) for s in sesiones], 1, "%"),
        "",
    ]

    # ---------- Por participante ----------
    lineas += [
        "## Por participante", "",
        "| Participante | Lentes | Luz | Detección | FPS | Error (px) | Error (%) | Dispersión (px) | Práctica |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    filas_csv = []

    for s in sesiones:
        lineas.append(
            f"| {s['participante']} | {s['lentes']} | {s['iluminacion']} | "
            f"{fmt(numero(s['tasa_deteccion_pct']), 1, '%')} | {fmt(numero(s['fps_promedio']))} | "
            f"{fmt(numero(s['error_medio_px']), 0)} | {fmt(numero(s['error_medio_pct']), 1, '%')} | "
            f"{fmt(numero(s['dispersion_media_px']), 0)} | {fmt(numero(s['precision_practica_pct']), 1, '%')} |"
        )
        filas_csv.append(s)

    lineas.append("")

    # ---------- Exactitud por condicion ----------
    if exactitud:
        lineas += [
            "## Exactitud según condición", "",
            "| Condición | n participantes | Error medio (px) | Error medio (%) |",
            "|---|---|---|---|",
        ]
        for campo, nombre in (("lentes", "Lentes"), ("iluminacion", "Iluminación")):
            for valor in sorted({f[campo] for f in exactitud if f[campo]}):
                grupo = [f for f in exactitud if f[campo] == valor]
                n = len({f["participante"] for f in grupo})
                m_px, s_px = media_std([numero(f["error_px"]) for f in grupo])
                m_pc, s_pc = media_std([numero(f["error_pct"]) for f in grupo])
                lineas.append(f"| {nombre}: {valor} | {n} | {fmt_ms(m_px, s_px, 0)} | {fmt_ms(m_pc, s_pc, 1, '%')} |")
        lineas.append("")

        # Error por zona de la pantalla (cada punto de prueba)
        lineas += [
            "## Error por punto de prueba", "",
            "| Punto | Objetivo (fracción del lienzo) | Error medio (px) | Desfase medio x / y (px) |",
            "|---|---|---|---|",
        ]
        for punto in sorted({int(numero(f["punto"])) for f in exactitud}):
            grupo = [f for f in exactitud if int(numero(f["punto"])) == punto]
            tam = {s["sesion"]: (numero(s["ancho_lienzo_px"]), numero(s["alto_lienzo_px"])) for s in sesiones}
            g0 = grupo[0]
            w, h = tam.get(g0["sesion"], (1, 1))
            m, s = media_std([numero(f["error_px"]) for f in grupo])
            ex = np.nanmean([numero(f["error_x_px"]) for f in grupo])
            ey = np.nanmean([numero(f["error_y_px"]) for f in grupo])
            lineas.append(
                f"| {punto} | ({numero(g0['objetivo_x']) / w:.2f}, {numero(g0['objetivo_y']) / h:.2f}) | "
                f"{fmt_ms(m, s, 0)} | {ex:+.0f} / {ey:+.0f} |"
            )
        lineas.append("")

    # ---------- Practica ----------
    if practica:
        lineas += [
            "## Modo práctica por figura", "",
            "| Figura | n | Precisión (%) | Duración (s) |",
            "|---|---|---|---|",
        ]
        for figura in ["corazon", "flor", "mariposa"]:
            grupo = [r for r in practica if r["figura"] == figura]
            if grupo:
                m, s = media_std([numero(r["precision_pct"]) for r in grupo])
                md, sd = media_std([numero(r["duracion_s"]) for r in grupo])
                lineas.append(f"| {NOMBRES_FIGURA[figura]} | {len(grupo)} | {fmt_ms(m, s, 1)} | {fmt_ms(md, sd, 1)} |")
        lineas.append("")

    # ---------- Deteccion por etapa ----------
    if etapas:
        nombres_etapa = {"calibracion": "Calibración", "exactitud": "Prueba de exactitud",
                         "practica": "Práctica", "dibujo": "Dibujo libre"}
        lineas += [
            "## Detección de ambos ojos por etapa", "",
            "| Etapa | Detección media |",
            "|---|---|",
        ]
        for clave, nombre in nombres_etapa.items():
            valores = [e[clave] for e in etapas.values() if clave in e]
            if valores:
                m, s = media_std(valores)
                lineas.append(f"| {nombre} | {fmt_ms(m, s, 1, '%')} |")
        lineas.append("")

    # ---------- Encuesta ----------
    if encuesta:
        lineas += [
            "## Encuesta (escala 1 a 5)", "",
            "| Afirmación | Media ± DE | % de acuerdo (4–5) |",
            "|---|---|---|",
        ]
        for clave, texto in preguntas:
            valores = [int(f[clave]) for f in encuesta if f.get(clave, "").isdigit()]
            if valores:
                m, s = media_std(valores)
                acuerdo = 100 * sum(v >= 4 for v in valores) / len(valores)
                lineas.append(f"| {texto} | {fmt_ms(m, s, 2)} | {acuerdo:.0f}% |")
        lineas.append("")

        comentarios = [f["comentario"] for f in encuesta if f.get("comentario")]
        if comentarios:
            lineas += ["### Comentarios", ""] + [f"- {c}" for c in comentarios] + [""]

    # ---------- Figuras ----------
    lineas += ["## Gráficas", ""]
    for ruta in figuras:
        if ruta:
            nombre = os.path.basename(ruta)
            lineas.append(f"![{nombre}]({nombre})")
            lineas.append("")

    with open(os.path.join(salida, "resultados.md"), "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas))

    if filas_csv:
        with open(os.path.join(salida, "resumen_participantes.csv"), "w", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=list(filas_csv[0].keys()))
            escritor.writeheader()
            escritor.writerows(filas_csv)


# =====================================
# PRINCIPAL
# =====================================

def main():

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, raiz)

    parser = argparse.ArgumentParser(description="Analiza la evaluacion de EyeTrace")
    parser.add_argument("--datos", default=os.path.join(raiz, "datos"))
    parser.add_argument("--salida", default=os.path.join(raiz, "resultados"))
    parser.add_argument("--incluir-canceladas", action="store_true")
    args = parser.parse_args()

    try:
        from evaluacion import PREGUNTAS_ENCUESTA as preguntas
    except ImportError:
        preguntas = []

    datos = cargar(args.datos, args.incluir_canceladas)

    if not datos["sesiones"]:
        print(f"No hay sesiones completas en {args.datos}. Haz al menos una evaluación primero.")
        return

    os.makedirs(args.salida, exist_ok=True)

    figuras = [
        fig_exactitud_participantes(datos, args.salida),
        fig_mapa_exactitud(datos, args.salida),
        fig_precision_practica(datos, args.salida),
        fig_deteccion(datos, args.salida),
        fig_rendimiento(datos, args.salida),
        fig_encuesta(datos, args.salida, preguntas),
        fig_galeria(datos, args.salida),
    ]

    tablas(datos, args.salida, figuras, preguntas)

    print(f"Listo: {len(datos['sesiones'])} sesiones analizadas.")
    print(f"Resultados en: {args.salida}")
    for ruta in figuras:
        if ruta:
            print("  -", os.path.basename(ruta))
    print("  - resultados.md")
    print("  - resumen_participantes.csv")


if __name__ == "__main__":
    main()
