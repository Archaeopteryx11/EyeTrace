
import argparse
import base64
import json
import mimetypes
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

from eye_tracking import EyeTracker
from gaze_detection import GazeDetector
from calibration import (
    CLAVES_CABEZA,
    GazeMapper,
    ajustar_calibracion,
    mediana_de_cabeza,
    mediana_de_muestras,
)
from evaluacion import Evaluacion, PREGUNTAS_ENCUESTA
from rutas import recurso, ruta_datos


# =====================================
# EyeTrace - VERSION WEB
# =====================================
# Python hace todo el procesamiento de imagen:
#   OpenCV    -> captura de la camara y video con landmarks
#   MediaPipe -> landmarks del rostro y del iris
#   NumPy     -> calibracion por minimos cuadrados
#
# La pagina (carpeta web/) solo muestra el lienzo y la
# interfaz. Se comunica con Python por HTTP:
#   /video    -> video de la camara procesado (MJPEG)
#   /eventos  -> coordenadas de la mirada en tiempo real (SSE)
#   /calibrar -> envia las muestras de calibracion a Python
#   /recentrar -> corrige el desfase mirando el centro
#   /guardar  -> guarda la obra en la carpeta obras/
#   /evaluacion/... -> registro de la evaluacion con participantes


CALIBRATION_FILE = ruta_datos("calibracion.json")
WEB_DIR = recurso("web")


# =====================================
# 1. MOTOR DE SEGUIMIENTO OCULAR
# =====================================
# Corre en un hilo aparte: lee la camara, procesa cada
# fotograma y deja disponible el ultimo resultado.

class MotorMirada(threading.Thread):

    def __init__(self, camera):

        super().__init__(daemon=True)

        self.camera = camera

        self.tracker = EyeTracker(
            model_path=recurso("face_landmarker.task")
        )

        self.detector = GazeDetector()

        self.mapper = GazeMapper.load(CALIBRATION_FILE) or GazeMapper()
        self.calibracion_guardada = os.path.exists(CALIBRATION_FILE)

        self.lock = threading.Lock()
        self.nuevo_dato = threading.Condition(self.lock)

        self.evaluacion = Evaluacion()

        self.jpeg = None
        self.dato = {"ok": False, "ojos": 0}
        self.contador = 0

        self.activo = True

    def run(self):

        inicio = time.time()

        while self.activo:

            ret, frame = self.camera.read()

            if not ret:
                time.sleep(0.05)
                continue

            # Tiempo de procesamiento de este fotograma
            t_proceso = time.perf_counter()

            # Efecto espejo
            frame = cv2.flip(frame, 1)

            # MediaPipe necesita marcas de tiempo crecientes (ms)
            timestamp = int((time.time() - inicio) * 1000)

            processed, x, y, valid_eyes = self.tracker.process_frame(
                frame, timestamp
            )

            ok = valid_eyes == 2 and x is not None and y is not None

            dato = {"ok": ok, "ojos": valid_eyes}

            cabeza = self.tracker.head

            if cabeza is not None:

                dato["cabeza"] = {
                    clave: round(valor, 5) for clave, valor in cabeza.items()
                }

                # Que tan lejos esta la cabeza de la posicion
                # en la que se calibro
                desvio, pista, relativos = self.mapper.desvio_cabeza(cabeza)

                if desvio is not None:
                    dato["desvio"] = round(desvio, 3)
                    dato["pista"] = pista
                    dato["relativo"] = relativos

            if ok:

                sx, sy = self.mapper.map(x, y)

                dato.update({
                    "x": round(x, 5),
                    "y": round(y, 5),
                    "sx": round(sx, 4),
                    "sy": round(sy, 4),
                    "direccion": self.detector.detectar_direccion_pantalla(sx, sy),
                })

            procesamiento_ms = (time.perf_counter() - t_proceso) * 1000

            self.evaluacion.registrar_fotograma(dato, cabeza, procesamiento_ms)

            # Video pequeno para la pagina
            alto, ancho = processed.shape[:2]
            escala = 360 / ancho
            pequeno = cv2.resize(
                processed, (360, int(alto * escala))
            )

            ok_jpg, jpg = cv2.imencode(
                ".jpg", pequeno, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )

            with self.nuevo_dato:

                self.dato = dato
                self.contador += 1

                if ok_jpg:
                    self.jpeg = jpg.tobytes()

                self.nuevo_dato.notify_all()

        self.tracker.close()

    def esperar_dato(self, ultimo, timeout=1.0):

        with self.nuevo_dato:

            self.nuevo_dato.wait_for(
                lambda: self.contador != ultimo, timeout
            )

            return self.contador, self.dato, self.jpeg

    def set_mapper(self, mapper):

        with self.lock:
            self.mapper = mapper


# =====================================
# 2. SERVIDOR WEB
# =====================================

class Handler(BaseHTTPRequestHandler):

    motor = None

    # Silenciar el registro de cada peticion en la consola
    def log_message(self, format, *args):
        pass

    # ---------------------------------
    # RESPUESTAS
    # ---------------------------------

    def _json(self, datos, codigo=200):

        cuerpo = json.dumps(datos).encode("utf-8")

        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _leer_json(self):

        largo = int(self.headers.get("Content-Length", 0))

        return json.loads(self.rfile.read(largo) or b"{}")

    def _archivo(self, ruta_relativa):

        ruta = os.path.normpath(os.path.join(WEB_DIR, ruta_relativa))

        # No permitir salir de la carpeta web/
        if not ruta.startswith(os.path.normpath(WEB_DIR)) or not os.path.isfile(ruta):
            self.send_error(404)
            return

        tipo = mimetypes.guess_type(ruta)[0] or "application/octet-stream"

        if ruta.endswith(".ttf"):
            tipo = "font/ttf"

        with open(ruta, "rb") as archivo:
            cuerpo = archivo.read()

        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(cuerpo)

    # ---------------------------------
    # GET
    # ---------------------------------

    def do_GET(self):

        ruta = self.path.split("?")[0]

        if ruta == "/":
            self._archivo("index.html")

        elif ruta == "/video":
            self._video()

        elif ruta == "/eventos":
            self._eventos()

        elif ruta == "/estado":
            self._json({
                "calibracion_guardada": self.motor.calibracion_guardada,
                "encuesta": [
                    {"clave": clave, "texto": texto}
                    for clave, texto in PREGUNTAS_ENCUESTA
                ],
            })

        else:
            self._archivo(ruta.lstrip("/"))

    def _video(self):

        # Video MJPEG: una imagen JPEG tras otra
        self.send_response(200)
        self.send_header(
            "Content-Type", "multipart/x-mixed-replace; boundary=frame"
        )
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        ultimo = -1
        siguiente_envio = 0

        try:
            while self.motor.activo:

                ultimo, _, jpeg = self.motor.esperar_dato(ultimo)

                # Limitar a ~15 imagenes por segundo
                if jpeg is None or time.time() < siguiente_envio:
                    continue

                siguiente_envio = time.time() + 1 / 15

                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                    + jpeg
                    + b"\r\n"
                )

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _eventos(self):

        # Server-Sent Events: un mensaje por fotograma procesado
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        ultimo = -1

        try:
            while self.motor.activo:

                nuevo, dato, _ = self.motor.esperar_dato(ultimo)

                if nuevo == ultimo:
                    # Mantener viva la conexion
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue

                ultimo = nuevo

                self.wfile.write(
                    f"data: {json.dumps(dato)}\n\n".encode()
                )
                self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    # ---------------------------------
    # POST
    # ---------------------------------

    def do_POST(self):

        ruta = self.path.split("?")[0]

        try:
            datos = self._leer_json()
        except ValueError:
            self._json({"ok": False, "error": "Datos invalidos"}, 400)
            return

        if ruta == "/calibrar":
            self._calibrar(datos)

        elif ruta == "/recentrar":
            self._recentrar(datos)

        elif ruta == "/usar_guardada":
            mapper = GazeMapper.load(CALIBRATION_FILE)

            if mapper is None:
                self._json({"ok": False, "error": "No hay calibracion guardada"})
            else:
                self.motor.set_mapper(mapper)
                self._json({"ok": True})

        elif ruta == "/guardar":
            self._guardar(datos)

        elif ruta.startswith("/evaluacion/"):
            self._evaluacion(ruta.split("/")[-1], datos)

        else:
            self.send_error(404)

    @staticmethod
    def _cabezas(muestras):

        # Cada muestra es [x, y, cx, cy, tam, giro, incl]
        # (las 5 ultimas solo si se detecto la cabeza)
        return [
            dict(zip(CLAVES_CABEZA, m[2:7]))
            for m in muestras
            if len(m) >= 7
        ]

    def _calibrar(self, datos):

        # datos["puntos"] = [{px, py, muestras: [[x, y, ...], ...]}, ...]
        resultados = []
        cabezas = []

        for punto in datos.get("puntos", []):

            muestras = punto.get("muestras", [])

            if len(muestras) < 5:
                continue

            ojo_x, ojo_y = mediana_de_muestras(muestras)

            resultados.append(
                (ojo_x, ojo_y, float(punto["px"]), float(punto["py"]))
            )

            cabezas += self._cabezas(muestras)

        mapper, error = ajustar_calibracion(
            resultados, mediana_de_cabeza(cabezas)
        )

        if mapper is None:
            self._json({"ok": False, "error": error})
            return

        mapper.save(CALIBRATION_FILE)

        self.motor.set_mapper(mapper)
        self.motor.calibracion_guardada = True

        print("Calibracion lista y guardada.")

        self._json({"ok": True})

    def _recentrar(self, datos):

        muestras = datos.get("muestras", [])

        if len(muestras) < 5:
            self._json({"ok": False, "error": "No vi bien tus ojos, intenta otra vez"})
            return

        ojo_x, ojo_y = mediana_de_muestras(muestras)

        with self.motor.lock:
            mapper = self.motor.mapper

            if not mapper.calibrado:
                self._json({"ok": False, "error": "Primero calibra con K"})
                return

            dx, dy = mapper.recentrar(
                ojo_x, ojo_y, mediana_de_cabeza(self._cabezas(muestras))
            )

        mapper.save(CALIBRATION_FILE)

        print(f"Recentrado: desfase corregido ({dx:+.3f}, {dy:+.3f})")

        self._json({"ok": True})

    def _evaluacion(self, accion, datos):

        evaluacion = self.motor.evaluacion

        if accion == "iniciar":
            sesion = evaluacion.iniciar(datos)
            print(f"Evaluacion iniciada: {sesion}")
            self._json({"ok": True, "sesion": sesion})
            return

        if not evaluacion.activa:
            self._json({"ok": False, "error": "No hay evaluacion activa"})
            return

        if accion == "etapa":
            evaluacion.cambiar_etapa(datos.get("etapa", ""))
            self._json({"ok": True})

        elif accion == "punto":
            self._json(evaluacion.registrar_punto(datos))

        elif accion == "practica":
            self._json(evaluacion.registrar_practica(datos))

        elif accion == "encuesta":
            self._json(evaluacion.registrar_encuesta(datos))

        elif accion == "obra":
            imagen = datos.get("imagen", "")
            if "," not in imagen:
                self._json({"ok": False, "error": "Imagen vacia"})
                return
            archivo = evaluacion.guardar_obra(base64.b64decode(imagen.split(",", 1)[1]))
            self._json({"ok": True, "archivo": archivo})

        elif accion == "terminar":
            resumen = evaluacion.terminar(bool(datos.get("cancelada")))
            print(f"Evaluacion terminada: {resumen.get('sesion')}")
            self._json(resumen)

        else:
            self.send_error(404)

    def _guardar(self, datos):

        imagen = datos.get("imagen", "")

        if "," not in imagen:
            self._json({"ok": False, "error": "Imagen vacia"}, 400)
            return

        carpeta = ruta_datos("obras")
        os.makedirs(carpeta, exist_ok=True)

        nombre = datetime.now().strftime(
            "eyetrace_%Y-%m-%d_%H-%M-%S.png"
        )

        with open(os.path.join(carpeta, nombre), "wb") as archivo:
            archivo.write(base64.b64decode(imagen.split(",", 1)[1]))

        print(f"Obra guardada: obras/{nombre}")

        self._json({"ok": True, "archivo": f"obras/{nombre}"})


# =====================================
# 3. INICIO
# =====================================

def abrir_camara(indice):

    if sys.platform.startswith("win"):
        # DirectShow abre la camara mas rapido en Windows
        camera = cv2.VideoCapture(indice, cv2.CAP_DSHOW)

        if camera.isOpened():
            return camera

    return cv2.VideoCapture(indice)


def iniciar_servidor(puerto_inicial):

    # Si el puerto esta ocupado, probar los siguientes
    for puerto in range(puerto_inicial, puerto_inicial + 20):

        try:
            return ThreadingHTTPServer(("127.0.0.1", puerto), Handler), puerto
        except OSError:
            continue

    raise OSError("No se encontro un puerto libre.")


def main():

    parser = argparse.ArgumentParser(description="EyeTrace")

    parser.add_argument(
        "--camara", type=int, default=0,
        help="Numero de la camara a usar (por defecto 0)"
    )

    parser.add_argument(
        "--puerto", type=int, default=8000,
        help="Puerto de la pagina (por defecto 8000)"
    )

    parser.add_argument(
        "--sin-navegador", action="store_true",
        help="No abrir el navegador automaticamente"
    )

    args = parser.parse_args()

    print("Iniciando EyeTrace...")

    camera = abrir_camara(args.camara)

    if not camera.isOpened():
        print(
            f"Error: No se pudo abrir la camara {args.camara}. "
            "Revisa que este conectada y que ningun otro programa "
            "(Zoom, Teams, Meet...) la este usando."
        )
        input("Presiona ENTER para cerrar...")
        sys.exit(1)

    motor = MotorMirada(camera)
    motor.start()

    Handler.motor = motor

    servidor, puerto = iniciar_servidor(args.puerto)
    servidor.daemon_threads = True

    url = f"http://localhost:{puerto}"

    print()
    print("==========================================")
    print(f"  EyeTrace esta listo en {url}")
    print("  Para salir, cierra esta ventana (o Ctrl+C)")
    print("==========================================")

    if not args.sin_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        servidor.serve_forever()

    except KeyboardInterrupt:
        pass

    finally:
        if motor.evaluacion.activa:
            motor.evaluacion.terminar(cancelada=True)
        motor.activo = False
        motor.join(timeout=2)
        servidor.server_close()
        camera.release()
        print("EyeTrace finalizado.")


if __name__ == "__main__":
    main()
