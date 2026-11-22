
import csv
import os
import threading
import time
from datetime import datetime

import numpy as np

from rutas import ruta_datos


# =====================================
# REGISTRO DE LA EVALUACION
# =====================================
# Guarda en la carpeta datos/ todo lo que se mide durante una
# sesion de evaluacion con un participante:
#
#   datos/sesiones.csv          -> una fila por sesion (resumen)
#   datos/fotogramas/<id>.csv   -> una fila por fotograma de camara
#   datos/exactitud.csv         -> una fila por punto de la prueba de exactitud
#   datos/practica.csv          -> una fila por figura practicada
#   datos/encuesta.csv          -> respuestas de la encuesta
#   datos/obras/<id>.png        -> obra del minuto de dibujo libre
#
# Luego analisis/analizar_resultados.py lee estos archivos y
# genera tablas y graficas.


CARPETA = ruta_datos("datos")

COLUMNAS_SESION = [
    "sesion", "participante", "fecha", "lentes", "iluminacion", "notas",
    "ancho_lienzo_px", "alto_lienzo_px",
    "fotogramas", "tasa_deteccion_pct", "fps_promedio", "procesamiento_ms_promedio",
    "error_medio_px", "error_medio_pct", "dispersion_media_px",
    "precision_practica_pct", "duracion_s",
]

COLUMNAS_FOTOGRAMA = [
    "t_s", "etapa", "rostro", "ojos_validos", "ok",
    "ojo_x", "ojo_y", "pantalla_x", "pantalla_y",
    "cabeza_cx", "cabeza_cy", "cabeza_tam", "cabeza_giro", "cabeza_incl",
    "desvio_cabeza", "procesamiento_ms",
]

COLUMNAS_EXACTITUD = [
    "sesion", "participante", "lentes", "iluminacion", "punto",
    "objetivo_x", "objetivo_y", "mirada_x", "mirada_y",
    "error_px", "error_pct", "error_x_px", "error_y_px",
    "dispersion_px", "muestras",
]

COLUMNAS_PRACTICA = [
    "sesion", "participante", "lentes", "iluminacion",
    "figura", "velocidad", "precision_pct", "duracion_s", "muestras",
]

PREGUNTAS_ENCUESTA = [
    ("facilidad", "Fue fácil controlar el pincel con la mirada"),
    ("exactitud", "El pincel siguió mi mirada a donde yo quería"),
    ("respuesta", "El sistema respondió rápido, sin retraso molesto"),
    ("calibracion", "La calibración fue sencilla"),
    ("comodidad", "Me sentí cómodo/a, sin cansancio en los ojos"),
    ("obra", "Me gustó la obra que creé"),
    ("recomendaria", "Recomendaría esta experiencia a otras personas"),
]

COLUMNAS_ENCUESTA = (
    ["sesion", "participante", "lentes", "iluminacion"]
    + [clave for clave, _ in PREGUNTAS_ENCUESTA]
    + ["comentario"]
)


def _agregar_fila(nombre, columnas, fila):

    # Agrega una fila a un CSV, creando el archivo con encabezado
    os.makedirs(CARPETA, exist_ok=True)

    ruta = os.path.join(CARPETA, nombre)
    nuevo = not os.path.exists(ruta)

    with open(ruta, "a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)

        if nuevo:
            escritor.writeheader()

        escritor.writerow({c: fila.get(c, "") for c in columnas})


def _redondear(valor, decimales=4):

    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return ""

    return round(float(valor), decimales)


class Evaluacion:

    def __init__(self):

        self.lock = threading.Lock()
        self.activa = False

    # ---------------------------------
    # INICIO
    # ---------------------------------

    def iniciar(self, datos):

        with self.lock:

            ahora = datetime.now()

            participante = str(datos.get("participante", "")).strip() or "P??"
            participante = "".join(
                c for c in participante if c.isalnum() or c in "-_"
            )[:20] or "P"

            self.sesion = f"{participante}_{ahora.strftime('%Y%m%d_%H%M%S')}"
            self.participante = participante
            self.lentes = datos.get("lentes", "")
            self.iluminacion = datos.get("iluminacion", "")
            self.notas = str(datos.get("notas", ""))[:300]
            self.fecha = ahora.strftime("%Y-%m-%d %H:%M")
            self.inicio = time.time()
            self.etapa = "inicio"
            self.lienzo = (datos.get("ancho"), datos.get("alto"))

            self.errores = []
            self.dispersiones = []
            self.errores_pct = []
            self.precisiones = []

            # Contadores para la tasa de deteccion y el rendimiento
            self.fotogramas = 0
            self.fotogramas_ok = 0
            self.procesamientos = []
            self.tiempos = []

            carpeta = os.path.join(CARPETA, "fotogramas")
            os.makedirs(carpeta, exist_ok=True)

            self.archivo_fotogramas = open(
                os.path.join(carpeta, f"{self.sesion}.csv"),
                "w", newline="", encoding="utf-8"
            )
            self.escritor = csv.DictWriter(
                self.archivo_fotogramas, fieldnames=COLUMNAS_FOTOGRAMA
            )
            self.escritor.writeheader()

            self.activa = True

            return self.sesion

    def cambiar_etapa(self, etapa):

        with self.lock:
            self.etapa = str(etapa)[:40]

    def _base(self):

        return {
            "sesion": self.sesion,
            "participante": self.participante,
            "lentes": self.lentes,
            "iluminacion": self.iluminacion,
        }

    # ---------------------------------
    # CADA FOTOGRAMA
    # ---------------------------------

    def registrar_fotograma(self, dato, cabeza, procesamiento_ms):

        if not self.activa:
            return

        with self.lock:

            if not self.activa:
                return

            ahora = time.time()
            cabeza = cabeza or {}

            self.escritor.writerow({
                "t_s": round(ahora - self.inicio, 3),
                "etapa": self.etapa,
                "rostro": int(bool(cabeza)),
                "ojos_validos": dato.get("ojos", 0),
                "ok": int(dato.get("ok", False)),
                "ojo_x": dato.get("x", ""),
                "ojo_y": dato.get("y", ""),
                "pantalla_x": dato.get("sx", ""),
                "pantalla_y": dato.get("sy", ""),
                "cabeza_cx": _redondear(cabeza.get("cx")),
                "cabeza_cy": _redondear(cabeza.get("cy")),
                "cabeza_tam": _redondear(cabeza.get("tam")),
                "cabeza_giro": _redondear(cabeza.get("giro")),
                "cabeza_incl": _redondear(cabeza.get("incl")),
                "desvio_cabeza": dato.get("desvio", ""),
                "procesamiento_ms": round(procesamiento_ms, 2),
            })

            # La encuesta y el formulario no cuentan para la deteccion
            if self.etapa not in ("inicio", "encuesta", "resumen"):
                self.fotogramas += 1
                self.fotogramas_ok += int(dato.get("ok", False))
                self.procesamientos.append(procesamiento_ms)
                self.tiempos.append(ahora)

    # ---------------------------------
    # PRUEBA DE EXACTITUD
    # ---------------------------------

    def registrar_punto(self, datos):

        # datos: {punto, objetivo: [x, y] (0..1), muestras: [[sx, sy], ...],
        #         ancho, alto}
        muestras = np.array(datos.get("muestras", []), dtype=float)

        if len(muestras) < 5:
            return {"ok": False, "error": "Pocas muestras"}

        ancho = float(datos.get("ancho", 1000))
        alto = float(datos.get("alto", 700))
        diagonal = np.hypot(ancho, alto)

        objetivo = np.array(datos["objetivo"], dtype=float) * [ancho, alto]
        puntos = muestras * [ancho, alto]

        # Exactitud (accuracy): distancia entre la mediana de la
        # mirada y el punto objetivo
        mirada = np.median(puntos, axis=0)
        error_xy = mirada - objetivo
        error = float(np.hypot(*error_xy))

        # Precision (dispersion): RMS de las muestras alrededor
        # de su propio centro. Mide que tanto tiembla la mirada.
        centro = puntos.mean(axis=0)
        dispersion = float(np.sqrt(np.mean(np.sum((puntos - centro) ** 2, axis=1))))

        fila = dict(self._base(), **{
            "punto": datos.get("punto"),
            "objetivo_x": _redondear(objetivo[0], 1),
            "objetivo_y": _redondear(objetivo[1], 1),
            "mirada_x": _redondear(mirada[0], 1),
            "mirada_y": _redondear(mirada[1], 1),
            "error_px": _redondear(error, 1),
            "error_pct": _redondear(100 * error / diagonal, 2),
            "error_x_px": _redondear(error_xy[0], 1),
            "error_y_px": _redondear(error_xy[1], 1),
            "dispersion_px": _redondear(dispersion, 1),
            "muestras": len(muestras),
        })

        _agregar_fila("exactitud.csv", COLUMNAS_EXACTITUD, fila)

        self.errores.append(error)
        self.errores_pct.append(100 * error / diagonal)
        self.dispersiones.append(dispersion)

        return {"ok": True, "error_px": round(error, 1), "error_pct": round(100 * error / diagonal, 2)}

    # ---------------------------------
    # PRACTICA, ENCUESTA Y OBRA
    # ---------------------------------

    def registrar_practica(self, datos):

        fila = dict(self._base(), **{
            "figura": datos.get("figura"),
            "velocidad": datos.get("velocidad"),
            "precision_pct": datos.get("precision"),
            "duracion_s": _redondear(datos.get("duracion"), 1),
            "muestras": datos.get("muestras"),
        })

        _agregar_fila("practica.csv", COLUMNAS_PRACTICA, fila)

        if datos.get("precision") is not None:
            self.precisiones.append(float(datos["precision"]))

        return {"ok": True}

    def registrar_encuesta(self, datos):

        fila = dict(self._base())

        for clave, _ in PREGUNTAS_ENCUESTA:
            valor = datos.get(clave)
            fila[clave] = int(valor) if str(valor).isdigit() else ""

        fila["comentario"] = str(datos.get("comentario", ""))[:500].replace("\n", " ")

        _agregar_fila("encuesta.csv", COLUMNAS_ENCUESTA, fila)

        return {"ok": True}

    def guardar_obra(self, png_bytes):

        carpeta = os.path.join(CARPETA, "obras")
        os.makedirs(carpeta, exist_ok=True)

        nombre = f"{self.sesion}.png"

        with open(os.path.join(carpeta, nombre), "wb") as archivo:
            archivo.write(png_bytes)

        return f"datos/obras/{nombre}"

    # ---------------------------------
    # CIERRE Y RESUMEN
    # ---------------------------------

    def terminar(self, cancelada=False):

        with self.lock:

            if not self.activa:
                return {"ok": False, "error": "No hay evaluacion activa"}

            self.activa = False

            if cancelada:
                self.notas = (self.notas + " [cancelada]").strip()
            self.archivo_fotogramas.close()

            tasa = 100 * self.fotogramas_ok / self.fotogramas if self.fotogramas else 0

            if len(self.tiempos) > 1:
                fps = (len(self.tiempos) - 1) / (self.tiempos[-1] - self.tiempos[0])
            else:
                fps = 0

            resumen = {
                "sesion": self.sesion,
                "participante": self.participante,
                "fecha": self.fecha,
                "lentes": self.lentes,
                "iluminacion": self.iluminacion,
                "notas": self.notas,
                "ancho_lienzo_px": self.lienzo[0],
                "alto_lienzo_px": self.lienzo[1],
                "fotogramas": self.fotogramas,
                "tasa_deteccion_pct": _redondear(tasa, 1),
                "fps_promedio": _redondear(fps, 1),
                "procesamiento_ms_promedio": _redondear(np.mean(self.procesamientos) if self.procesamientos else None, 1),
                "error_medio_px": _redondear(np.mean(self.errores) if self.errores else None, 1),
                "error_medio_pct": _redondear(np.mean(self.errores_pct) if self.errores_pct else None, 2),
                "dispersion_media_px": _redondear(np.mean(self.dispersiones) if self.dispersiones else None, 1),
                "precision_practica_pct": _redondear(np.mean(self.precisiones) if self.precisiones else None, 1),
                "duracion_s": _redondear(time.time() - self.inicio, 0),
            }

            _agregar_fila("sesiones.csv", COLUMNAS_SESION, resumen)

            return dict(resumen, ok=True)
