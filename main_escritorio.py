
import argparse
import sys

import cv2
import pygame

from eye_tracking import EyeTracker
from gaze_detection import GazeDetector
from art_canvas import ArtCanvas
from calibration import Calibrator, GazeMapper
from rutas import recurso, ruta_datos


# =====================================
# 0. OPCIONES DE INICIO
# =====================================
# Ejemplo: python main.py --camara 1
# (util si el computador tiene mas de una camara)

parser = argparse.ArgumentParser(description="EyeTrace")

parser.add_argument(
    "--camara",
    type=int,
    default=0,
    help="Numero de la camara a usar (por defecto 0)"
)

args = parser.parse_args()

CALIBRATION_FILE = ruta_datos("calibracion.json")


# =====================================
# 1. INICIALIZAR COMPONENTES
# =====================================

print("Iniciando EyeTrace...")

if sys.platform.startswith("win"):
    # DirectShow abre la camara mas rapido en Windows
    camera = cv2.VideoCapture(args.camara, cv2.CAP_DSHOW)

    if not camera.isOpened():
        camera = cv2.VideoCapture(args.camara)
else:
    camera = cv2.VideoCapture(args.camara)

if not camera.isOpened():
    print(
        f"Error: No se pudo abrir la camara {args.camara}. "
        "Revisa que este conectada y que ningun otro programa "
        "(Zoom, Teams, Meet...) la este usando."
    )
    input("Presiona ENTER para cerrar...")
    sys.exit(1)

tracker = EyeTracker(
    model_path=recurso("face_landmarker.task")
)

detector = GazeDetector()

canvas = ArtCanvas(
    width=1000,
    height=700
)

calibrator = Calibrator()

saved_mapper = GazeMapper.load(CALIBRATION_FILE)

print("EyeTrace iniciado correctamente.")


# =====================================
# 2. CICLO PRINCIPAL
# =====================================
# Estados:
#   INICIO     -> pantalla de bienvenida
#   CALIBRANDO -> 9 puntos para ajustar la mirada
#   DIBUJANDO  -> la mirada pinta en el lienzo

state = "INICIO"

# Teclas presionadas en la ventana de la camara (OpenCV),
# para que los controles funcionen en cualquiera de las dos ventanas
cv_keys = []

frame_number = 0
direction = "CENTRO"

try:

    while canvas.running:

        # ---------------------------------
        # CAPTURA DE CAMARA
        # ---------------------------------

        ret, frame = camera.read()

        if not ret:
            print("Error al capturar imagen.")
            break

        # Efecto espejo
        frame = cv2.flip(frame, 1)

        frame_number += 1
        timestamp = frame_number * 33

        # ---------------------------------
        # SEGUIMIENTO OCULAR
        # ---------------------------------

        processed_frame, x, y, valid_eyes = (
            tracker.process_frame(frame, timestamp)
        )

        eyes_ok = (
            valid_eyes == 2 and x is not None and y is not None
        )

        # ---------------------------------
        # TECLADO
        # ---------------------------------

        keys = canvas.process_events() + cv_keys
        cv_keys = []

        if not canvas.running:
            break

        if state == "INICIO":

            if pygame.K_RETURN in keys or pygame.K_KP_ENTER in keys:
                calibrator.start()
                state = "CALIBRANDO"

            elif pygame.K_d in keys and saved_mapper is not None:
                canvas.mapper = saved_mapper
                canvas.clear_canvas()
                state = "DIBUJANDO"

        elif state == "CALIBRANDO":

            if pygame.K_c in keys:
                calibrator.cancel()
                state = "INICIO"

        elif state == "DIBUJANDO":

            if pygame.K_c in keys:
                canvas.clear_canvas()

            if pygame.K_SPACE in keys:
                canvas.change_color()

            if pygame.K_s in keys:
                ruta = canvas.save_artwork()
                print(f"Obra guardada: {ruta}")

            if pygame.K_k in keys:
                calibrator.start()
                state = "CALIBRANDO"

        # ---------------------------------
        # CALIBRACION
        # ---------------------------------

        if state == "CALIBRANDO":

            calibrator.update(
                x if eyes_ok else None,
                y if eyes_ok else None
            )

            if calibrator.terminado:

                if calibrator.mapper is not None:

                    canvas.mapper = calibrator.mapper
                    calibrator.mapper.save(CALIBRATION_FILE)
                    saved_mapper = calibrator.mapper

                    canvas.clear_canvas()
                    canvas.show_message(
                        "Calibración lista. ¡A dibujar con la mirada!"
                    )
                    state = "DIBUJANDO"

                else:

                    canvas.show_message(calibrator.error, 5)
                    state = "INICIO"

        # ---------------------------------
        # DETECCION DE DIRECCION Y DIBUJO
        # ---------------------------------

        if state == "DIBUJANDO":

            if eyes_ok:

                sx, sy = canvas.mapper.map(x, y)
                direction = detector.detectar_direccion_pantalla(sx, sy)

                canvas.draw_gaze(x, y, direction)

            else:

                direction = "NO DETECTADO"

                # Evitar unir trazos tras perder la deteccion
                canvas.draw_gaze(None, None, direction)

        # ---------------------------------
        # TEXTO SOBRE LA CAMARA
        # ---------------------------------

        if eyes_ok:

            cv2.putText(
                processed_frame,
                f"Posicion X: {x:.2f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                processed_frame,
                f"Posicion Y: {y:.2f}",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            if state == "DIBUJANDO":
                cv2.putText(
                    processed_frame,
                    f"Direccion: {direction}",
                    (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 0, 255),
                    2
                )

            cv2.putText(
                processed_frame,
                "OJOS DETECTADOS: 2/2",
                (20, 145),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )

        else:

            cv2.putText(
                processed_frame,
                "MIRADA NO DETECTADA",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        # ---------------------------------
        # MOSTRAR CAMARA
        # ---------------------------------

        cv2.imshow(
            "EyeTrace - Seguimiento Ocular",
            processed_frame
        )

        # ---------------------------------
        # ACTUALIZAR LIENZO
        # ---------------------------------

        if state == "INICIO":
            canvas.render_intro(eyes_ok, saved_mapper is not None)

        elif state == "CALIBRANDO":
            canvas.render_calibration(calibrator, eyes_ok)

        else:
            canvas.render(direction)

        # ESC tambien permite salir desde la ventana OpenCV
        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            break

        if key != 255:
            # Las letras, ENTER y ESPACIO tienen el mismo codigo
            # en OpenCV y en Pygame
            cv_keys.append(key)


# =====================================
# 3. LIBERAR RECURSOS
# =====================================

finally:

    camera.release()

    tracker.close()

    canvas.close()

    cv2.destroyAllWindows()

    print("EyeTrace finalizado.")
