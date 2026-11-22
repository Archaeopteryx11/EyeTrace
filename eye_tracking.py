
import cv2
import mediapipe as mp
import numpy as np
from collections import deque


class EyeTracker:

    def __init__(self, model_path="face_landmarker.task"):

        # ---------------------------------
        # 1. CONFIGURACION DE MEDIAPIPE
        # ---------------------------------

        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarker = mp.tasks.vision.FaceLandmarker
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode

        # Se carga el modelo en memoria en lugar de pasar la ruta:
        # asi funciona aunque la carpeta tenga tildes, ñ o espacios
        # (por ejemplo "Escritorio/Año 2026" o rutas de OneDrive).
        with open(model_path, "rb") as archivo:
            model_data = archivo.read()

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_buffer=model_data
            ),
            running_mode=RunningMode.VIDEO,
            num_faces=1
        )

        self.landmarker = FaceLandmarker.create_from_options(
            options
        )

        # ---------------------------------
        # 2. DEFINICION DE LOS OJOS
        # ---------------------------------

        self.eyes = [
            {
                "name": "Ojo izquierdo",
                "corners": (33, 133),
                "upper": 159,
                "lower": 145,
                "iris": range(468, 473)
            },
            {
                "name": "Ojo derecho",
                "corners": (362, 263),
                "upper": 386,
                "lower": 374,
                "iris": range(473, 478)
            }
        ]

        # ---------------------------------
        # 3. HISTORIAL DE MEDICIONES
        # ---------------------------------

        self.history_x = deque(maxlen=7)
        self.history_y = deque(maxlen=7)

        # Posicion de la cabeza en el ultimo fotograma (o None)
        self.head = None
        self.history_head = deque(maxlen=7)

    # ---------------------------------
    # 4. PROCESAMIENTO DE CADA FOTOGRAMA
    # ---------------------------------

    def process_frame(self, frame, timestamp):

        height, width, _ = frame.shape

        # Convertir BGR a RGB
        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        # Detectar landmarks
        results = self.landmarker.detect_for_video(
            mp_image,
            timestamp
        )

        annotated_frame = frame.copy()

        if not results.face_landmarks:

            self.history_x.clear()
            self.history_y.clear()
            self.history_head.clear()
            self.head = None

            return annotated_frame, None, None, 0

        landmarks = results.face_landmarks[0]

        self.head = self._head_pose(landmarks)

        valid_eyes = []

        # ---------------------------------
        # 5. ANALISIS DE AMBOS OJOS
        # ---------------------------------

        for eye in self.eyes:

            # Obtener puntos del iris
            iris_points = [
                landmarks[i]
                for i in eye["iris"]
            ]

            iris_x = np.mean([
                point.x for point in iris_points
            ])

            iris_y = np.mean([
                point.y for point in iris_points
            ])

            # Obtener esquinas del ojo
            corner_1 = landmarks[eye["corners"][0]]
            corner_2 = landmarks[eye["corners"][1]]

            eye_width = np.hypot(
                corner_2.x - corner_1.x,
                corner_2.y - corner_1.y
            )

            if eye_width < 0.0001:
                continue

            # ---------------------------------
            # 6. DETECCION DE APERTURA DEL OJO
            # ---------------------------------

            upper = landmarks[eye["upper"]]
            lower = landmarks[eye["lower"]]

            eye_height = abs(
                lower.y - upper.y
            )

            openness = eye_height / eye_width

            # Ignorar ojos cerrados o parpadeos
            if openness < 0.10:
                continue

            # ---------------------------------
            # 7. CALCULO HORIZONTAL
            # ---------------------------------

            dx = corner_2.x - corner_1.x
            dy = corner_2.y - corner_1.y

            ratio_x = (
                (iris_x - corner_1.x) * dx +
                (iris_y - corner_1.y) * dy
            ) / (eye_width ** 2)

            # ---------------------------------
            # 8. CALCULO VERTICAL
            # ---------------------------------

            # Linea de referencia entre las esquinas
            reference_y = (
                corner_1.y +
                (iris_x - corner_1.x) *
                dy / dx
                if abs(dx) > 0.0001
                else (corner_1.y + corner_2.y) / 2
            )

            # Distancia vertical respecto a la linea
            ratio_y = (
                (iris_y - reference_y) / eye_width
            )

            valid_eyes.append(
                (ratio_x, ratio_y)
            )

            # ---------------------------------
            # 9. DIBUJAR LANDMARKS
            # ---------------------------------

            cx = int(iris_x * width)
            cy = int(iris_y * height)

            # Centro del iris
            cv2.circle(
                annotated_frame,
                (cx, cy),
                5,
                (255, 0, 0),
                -1
            )

            # Esquinas del ojo
            for point in [corner_1, corner_2]:

                px = int(point.x * width)
                py = int(point.y * height)

                cv2.circle(
                    annotated_frame,
                    (px, py),
                    3,
                    (0, 255, 255),
                    -1
                )

        # ---------------------------------
        # 10. VALIDAR LOS DOS OJOS
        # ---------------------------------

        if len(valid_eyes) != 2:

            return (
                annotated_frame,
                None,
                None,
                len(valid_eyes)
            )

        # ---------------------------------
        # 11. PROMEDIAR LOS RESULTADOS
        # ---------------------------------

        current_x = np.mean([
            value[0] for value in valid_eyes
        ])

        current_y = np.mean([
            value[1] for value in valid_eyes
        ])

        # Guardar mediciones
        self.history_x.append(current_x)
        self.history_y.append(current_y)

        # Suavizar resultados
        smooth_x = float(
            np.mean(self.history_x)
        )

        smooth_y = float(
            np.mean(self.history_y)
        )

        # ---------------------------------
        # 12. DEVOLVER RESULTADOS
        # ---------------------------------

        return (
            annotated_frame,
            smooth_x,
            smooth_y,
            2
        )

    # ---------------------------------
    # 13. POSICION DE LA CABEZA
    # ---------------------------------
    # La medida de la mirada (iris dentro del ojo) cambia si la
    # cabeza se mueve. Por eso se mide tambien la cabeza: donde
    # esta en la imagen, que tan cerca esta de la camara y hacia
    # donde esta girada. Asi se puede avisar cuando el usuario
    # se sale de la posicion en la que calibro.

    def _head_pose(self, landmarks):

        outer_left = landmarks[33]     # esquina externa ojo izquierdo
        outer_right = landmarks[263]   # esquina externa ojo derecho
        nose = landmarks[1]            # punta de la nariz

        center_x = (outer_left.x + outer_right.x) / 2
        center_y = (outer_left.y + outer_right.y) / 2

        # Distancia entre ojos: crece al acercarse a la camara
        size = np.hypot(
            outer_right.x - outer_left.x,
            outer_right.y - outer_left.y
        )

        if size < 0.0001:
            return None

        # Giro (izquierda/derecha) e inclinacion (arriba/abajo):
        # posicion de la nariz respecto al centro de los ojos
        yaw = (nose.x - center_x) / size
        pitch = (nose.y - center_y) / size

        self.history_head.append(
            (center_x, center_y, size, yaw, pitch)
        )

        promedio = np.mean(self.history_head, axis=0)

        return {
            "cx": float(promedio[0]),
            "cy": float(promedio[1]),
            "tam": float(promedio[2]),
            "giro": float(promedio[3]),
            "incl": float(promedio[4]),
        }

    # ---------------------------------
    # 14. CERRAR MEDIAPIPE
    # ---------------------------------

    def close(self):

        self.landmarker.close()
