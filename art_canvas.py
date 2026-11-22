
import math
import os
import time
from datetime import datetime

import pygame

from calibration import GazeMapper, PUNTOS
from rutas import ruta_datos


class ArtCanvas:

    def __init__(self, width=1000, height=700):

        pygame.init()

        self.width = width
        self.height = height

        # Ventana artistica
        self.screen = pygame.display.set_mode(
            (width, height)
        )

        pygame.display.set_caption(
            "EyeTrace - Lienzo Artistico"
        )

        # Paleta de colores
        self.background = (242, 232, 215)

        self.palette = [
            (105, 30, 48),
            (145, 55, 72),
            (190, 105, 115),
            (65, 35, 45),
            (205, 155, 105)
        ]

        self.color_index = 0

        # Superficie de dibujo
        self.canvas = pygame.Surface(
            (width, height)
        )

        self.canvas.fill(self.background)

        # Posicion anterior del pincel
        self.previous_position = None

        self.brush_size = 5

        # Transformacion mirada -> lienzo
        self.mapper = GazeMapper()

        # Fuentes
        self.title_font = pygame.font.SysFont(
            "Arial", 26, bold=True
        )

        self.big_font = pygame.font.SysFont(
            "Arial", 54, bold=True
        )

        self.info_font = pygame.font.SysFont(
            "Arial", 16
        )

        self.text_font = pygame.font.SysFont(
            "Arial", 20
        )

        # Mensaje temporal (ej. "Obra guardada")
        self.message = None
        self.message_until = 0

        # Reloj
        self.clock = pygame.time.Clock()

        self.running = True

    # --------------------------------
    # CONVERTIR MIRADA EN POSICION
    # --------------------------------

    def map_gaze(self, x, y):

        # La calibracion convierte las coordenadas oculares
        # en coordenadas de 0 a 1 dentro del lienzo
        sx, sy = self.mapper.map(x, y)

        screen_x = int(sx * (self.width - 1))
        screen_y = int(sy * (self.height - 1))

        return screen_x, screen_y

    # --------------------------------
    # DIBUJAR SEGUN LA MIRADA
    # --------------------------------

    def draw_gaze(self, x, y, direction):

        if x is None or y is None:
            self.previous_position = None
            return

        position = self.map_gaze(x, y)

        # Color actual
        color = self.palette[self.color_index]

        # Dibujar linea
        if self.previous_position is not None:

            pygame.draw.line(
                self.canvas,
                color,
                self.previous_position,
                position,
                self.brush_size
            )

        # Dibujar punto
        pygame.draw.circle(
            self.canvas,
            color,
            position,
            self.brush_size // 2 + 2
        )

        self.previous_position = position

    # --------------------------------
    # CAMBIAR COLOR
    # --------------------------------

    def change_color(self):

        self.color_index = (
            self.color_index + 1
        ) % len(self.palette)

    # --------------------------------
    # LIMPIAR LIENZO
    # --------------------------------

    def clear_canvas(self):

        self.canvas.fill(self.background)

        self.previous_position = None

    # --------------------------------
    # GUARDAR OBRA
    # --------------------------------

    def save_artwork(self):

        carpeta = ruta_datos("obras")
        os.makedirs(carpeta, exist_ok=True)

        nombre = datetime.now().strftime(
            "eyetrace_%Y-%m-%d_%H-%M-%S.png"
        )

        ruta = os.path.join(carpeta, nombre)

        pygame.image.save(self.canvas, ruta)

        self.show_message(f"Obra guardada en obras/{nombre}")

        return ruta

    def show_message(self, texto, segundos=3):

        self.message = texto
        self.message_until = time.time() + segundos

    # --------------------------------
    # EVENTOS
    # --------------------------------

    def process_events(self):

        # Devuelve la lista de teclas presionadas para que
        # main.py decida que hacer segun el estado actual
        keys = []

        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                self.running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:

                    self.running = False

                else:

                    keys.append(event.key)

        return keys

    # --------------------------------
    # TEXTO CENTRADO
    # --------------------------------

    def _center_text(self, texto, font, color, y):

        superficie = font.render(texto, True, color)

        self.screen.blit(
            superficie,
            superficie.get_rect(center=(self.width // 2, y))
        )

    def _draw_message(self):

        if self.message and time.time() < self.message_until:

            superficie = self.info_font.render(
                self.message, True, (242, 232, 215)
            )

            caja = superficie.get_rect(
                center=(self.width // 2, self.height - 80)
            ).inflate(30, 16)

            pygame.draw.rect(
                self.screen, (65, 35, 45), caja, border_radius=8
            )

            self.screen.blit(
                superficie,
                superficie.get_rect(center=caja.center)
            )

    # --------------------------------
    # PANTALLA DE INICIO
    # --------------------------------

    def render_intro(self, face_detected, has_saved_calibration):

        self.screen.fill(self.background)

        vino = (105, 30, 48)
        oscuro = (65, 35, 45)

        self._center_text(
            "EyeTrace", self.big_font, vino, self.height // 2 - 150
        )

        self._center_text(
            "La mirada como pincel digital",
            self.text_font, oscuro, self.height // 2 - 100
        )

        lineas = [
            "Primero vamos a calibrar: aparecerán 9 puntos.",
            "Mira cada punto sin mover la cabeza hasta que se llene.",
        ]

        for i, linea in enumerate(lineas):
            self._center_text(
                linea, self.text_font, oscuro,
                self.height // 2 - 20 + i * 30
            )

        if face_detected:
            estado = "Rostro detectado: listo para calibrar"
            color = (40, 120, 60)
        else:
            estado = "No te veo: ubícate frente a la cámara con buena luz"
            color = (170, 40, 40)

        self._center_text(
            estado, self.text_font, color, self.height // 2 + 70
        )

        self._center_text(
            "ENTER: calibrar",
            self.title_font, vino, self.height // 2 + 140
        )

        if has_saved_calibration:
            self._center_text(
                "D: dibujar con la última calibración guardada",
                self.text_font, oscuro, self.height // 2 + 180
            )

        self._center_text(
            "ESC: salir", self.info_font, oscuro, self.height - 35
        )

        self._draw_message()

        pygame.display.flip()
        self.clock.tick(60)

    # --------------------------------
    # PANTALLA DE CALIBRACION
    # --------------------------------

    def render_calibration(self, calibrator, face_detected):

        self.screen.fill(self.background)

        vino = (105, 30, 48)
        oscuro = (65, 35, 45)

        px, py = calibrator.punto_actual()

        cx = int(px * self.width)
        cy = int(py * self.height)

        progreso = calibrator.progreso()

        # Anillo exterior que late mientras el ojo llega al punto
        pulso = 4 * math.sin(time.time() * 6) if progreso == 0 else 0

        pygame.draw.circle(
            self.screen, (190, 105, 115), (cx, cy), int(26 + pulso), 3
        )

        # Relleno que crece mientras se toman muestras
        if progreso > 0:
            pygame.draw.circle(
                self.screen, vino, (cx, cy), int(4 + 20 * progreso)
            )

        # Centro fijo para enfocar la mirada
        pygame.draw.circle(self.screen, oscuro, (cx, cy), 4)

        # Texto en el centro (o abajo si el punto esta en el centro)
        texto_y = self.height // 2 + (90 if py == 0.50 else 0)

        self._center_text(
            f"Mira el punto  ·  {calibrator.indice + 1} de {len(PUNTOS)}",
            self.text_font, oscuro, texto_y
        )

        if not face_detected:
            self._center_text(
                "No veo tus dos ojos: acércate a la cámara",
                self.text_font, (170, 40, 40), texto_y + 35
            )

        self._center_text(
            "ESC: salir  ·  C: cancelar calibración",
            self.info_font, oscuro, self.height - 35
        )

        pygame.display.flip()
        self.clock.tick(60)

    # --------------------------------
    # MOSTRAR LIENZO
    # --------------------------------

    def render(self, direction="CENTRO"):

        self.screen.blit(
            self.canvas,
            (0, 0)
        )

        # Encabezado
        title = self.title_font.render(
            "EyeTrace",
            True,
            (105, 30, 48)
        )

        self.screen.blit(
            title,
            (25, 20)
        )

        # Direccion detectada
        info = self.info_font.render(
            f"Mirada: {direction}",
            True,
            (65, 35, 45)
        )

        self.screen.blit(
            info,
            (25, 60)
        )

        # Instrucciones
        controls = self.info_font.render(
            "C: Limpiar | ESPACIO: Color | S: Guardar obra | "
            "K: Recalibrar | ESC: Salir",
            True,
            (105, 30, 48)
        )

        self.screen.blit(
            controls,
            (25, self.height - 35)
        )

        self._draw_message()

        pygame.display.flip()

        self.clock.tick(60)

    # --------------------------------
    # CERRAR
    # --------------------------------

    def close(self):

        pygame.quit()
