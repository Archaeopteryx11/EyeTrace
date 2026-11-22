
import json
import time

import numpy as np


# =====================================
# CALIBRACION DE LA MIRADA
# =====================================
# Cada persona y cada camara producen valores distintos
# de la mirada. La calibracion muestra 9 puntos en el
# lienzo; mientras el usuario mira cada uno, se guardan
# las coordenadas oculares. Con esos datos se ajusta,
# por minimos cuadrados, una transformacion afin:
#
#   pantalla_x = a1 * ojo_x + b1 * ojo_y + c1
#   pantalla_y = a2 * ojo_x + b2 * ojo_y + c2
#
# Las coordenadas de pantalla van de 0 a 1.


# Puntos de calibracion (fraccion del ancho / alto)
PUNTOS = [
    (0.10, 0.12), (0.50, 0.12), (0.90, 0.12),
    (0.10, 0.50), (0.50, 0.50), (0.90, 0.50),
    (0.10, 0.88), (0.50, 0.88), (0.90, 0.88),
]

TIEMPO_ESPERA = 1.0      # segundos para que el ojo llegue al punto
TIEMPO_CAPTURA = 1.5     # segundos tomando muestras
MUESTRAS_MINIMAS = 12    # si hay menos, se repite el punto


# Calibracion original del proyecto (la que estaba fija en
# art_canvas.py). Se usa solo si no hay una calibracion guardada.
COEF_POR_DEFECTO = {
    "x": [1 / 0.60, 0.0, -0.20 / 0.60],
    "y": [0.0, 1 / 0.18, 0.16 / 0.18],
}


# Cuanto puede moverse la cabeza antes de avisar.
# Si el aviso salta demasiado, sube estos valores;
# si el pincel se corre sin aviso, bajalos.
TOLERANCIA_CABEZA = {
    "cx": 0.06,    # desplazamiento horizontal (fraccion de la imagen)
    "cy": 0.06,    # desplazamiento vertical (fraccion de la imagen)
    "tam": 0.12,   # acercarse o alejarse (12% de cambio de tamano)
    "giro": 0.10,  # girar la cara a los lados
    "incl": 0.10,  # inclinar la cara arriba o abajo
}

CLAVES_CABEZA = ["cx", "cy", "tam", "giro", "incl"]


class GazeMapper:

    # Convierte coordenadas oculares en coordenadas 0..1

    def __init__(self, coeficientes=None, cabeza=None):

        coef = coeficientes or COEF_POR_DEFECTO

        self.coef_x = np.array(coef["x"], dtype=float)
        self.coef_y = np.array(coef["y"], dtype=float)

        self.calibrado = coeficientes is not None

        # Posicion de la cabeza durante la calibracion
        self.cabeza = cabeza

    # ---------------------------------
    # DESVIO DE LA CABEZA
    # ---------------------------------

    def desvio_cabeza(self, actual):

        # Devuelve (desvio, pista, relativos). desvio < 1 significa que la
        # cabeza esta dentro de la tolerancia; la pista dice que
        # hacer para volver a la posicion de calibracion.

        if self.cabeza is None or actual is None:
            return None, None, None

        diferencias = {
            "cx": actual["cx"] - self.cabeza["cx"],
            "cy": actual["cy"] - self.cabeza["cy"],
            "tam": actual["tam"] / self.cabeza["tam"] - 1,
            "giro": actual["giro"] - self.cabeza["giro"],
            "incl": actual["incl"] - self.cabeza["incl"],
        }

        relativos = {
            clave: abs(valor) / TOLERANCIA_CABEZA[clave]
            for clave, valor in diferencias.items()
        }

        peor = max(relativos, key=relativos.get)
        valor = diferencias[peor]

        # La imagen esta en espejo: moverse a la derecha en la
        # imagen es moverse a la derecha propia
        pistas = {
            "cx": "Muévete un poco a tu izquierda" if valor > 0 else "Muévete un poco a tu derecha",
            "cy": "Sube un poco la cabeza" if valor > 0 else "Baja un poco la cabeza",
            "tam": "Aléjate un poco de la pantalla" if valor > 0 else "Acércate un poco a la pantalla",
            "giro": "Gira la cara hacia la pantalla",
            "incl": "Levanta un poco la cara" if valor > 0 else "Baja un poco la cara",
        }

        # Diferencias con signo, en unidades de tolerancia
        # (para dibujar la guia de posicion en la pagina)
        con_signo = {
            clave: round(valor / TOLERANCIA_CABEZA[clave], 3)
            for clave, valor in diferencias.items()
        }

        return relativos[peor], pistas[peor], con_signo

    # ---------------------------------
    # RECENTRAR
    # ---------------------------------

    def recentrar(self, ojo_x, ojo_y, cabeza=None):

        # El usuario mira el centro del lienzo (0.5, 0.5):
        # se corrige el desfase moviendo solo el termino
        # independiente de la transformacion
        sx = np.array([ojo_x, ojo_y, 1.0]) @ self.coef_x
        sy = np.array([ojo_x, ojo_y, 1.0]) @ self.coef_y

        self.coef_x[2] += 0.5 - sx
        self.coef_y[2] += 0.5 - sy

        # La postura actual pasa a ser la nueva referencia
        if cabeza is not None:
            self.cabeza = cabeza

        return float(0.5 - sx), float(0.5 - sy)

    def map(self, x, y):

        vector = np.array([x, y, 1.0])

        sx = float(np.clip(vector @ self.coef_x, 0.0, 1.0))
        sy = float(np.clip(vector @ self.coef_y, 0.0, 1.0))

        return sx, sy

    # ---------------------------------
    # GUARDAR / CARGAR
    # ---------------------------------

    def save(self, path):

        with open(path, "w", encoding="utf-8") as archivo:
            json.dump(
                {
                    "x": self.coef_x.tolist(),
                    "y": self.coef_y.tolist(),
                    "cabeza": self.cabeza,
                },
                archivo,
                indent=2
            )

    @staticmethod
    def load(path):

        try:
            with open(path, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)

            return GazeMapper(
                {"x": datos["x"], "y": datos["y"]},
                datos.get("cabeza")
            )

        except (OSError, ValueError, KeyError):
            return None


class Calibrator:

    def __init__(self):

        self.activo = False
        self.terminado = False
        self.error = None

    # ---------------------------------
    # INICIAR
    # ---------------------------------

    def start(self):

        self.activo = True
        self.terminado = False
        self.error = None

        self.indice = 0
        self.muestras = []          # muestras del punto actual
        self.resultados = []        # (ojo_x, ojo_y, punto_x, punto_y)
        self.inicio_punto = time.time()

    # ---------------------------------
    # ESTADO PARA DIBUJAR
    # ---------------------------------

    def punto_actual(self):

        return PUNTOS[self.indice]

    def progreso(self):

        # 0 = esperando, 0..1 = capturando
        transcurrido = time.time() - self.inicio_punto

        if transcurrido < TIEMPO_ESPERA:
            return 0.0

        return min(
            (transcurrido - TIEMPO_ESPERA) / TIEMPO_CAPTURA,
            1.0
        )

    # ---------------------------------
    # ACTUALIZAR CON CADA FOTOGRAMA
    # ---------------------------------

    def update(self, x, y):

        if not self.activo:
            return

        transcurrido = time.time() - self.inicio_punto

        if transcurrido < TIEMPO_ESPERA:
            return

        if x is not None and y is not None:
            self.muestras.append((x, y))

        if transcurrido < TIEMPO_ESPERA + TIEMPO_CAPTURA:
            return

        # Termino el tiempo del punto
        if len(self.muestras) < MUESTRAS_MINIMAS:

            # No se vio bien la mirada: repetir el punto
            self.muestras = []
            self.inicio_punto = time.time()
            return

        ojo_x, ojo_y = mediana_de_muestras(self.muestras)

        punto_x, punto_y = PUNTOS[self.indice]

        self.resultados.append(
            (ojo_x, ojo_y, punto_x, punto_y)
        )

        self.muestras = []
        self.indice += 1
        self.inicio_punto = time.time()

        if self.indice >= len(PUNTOS):
            self._finish()

    # ---------------------------------
    # AJUSTE POR MINIMOS CUADRADOS
    # ---------------------------------

    def _finish(self):

        self.activo = False
        self.terminado = True

        self.mapper, self.error = ajustar_calibracion(
            self.resultados
        )

    def cancel(self):

        self.activo = False
        self.terminado = False


# =====================================
# FUNCIONES DE AJUSTE (usadas por la version web y la de escritorio)
# =====================================

def mediana_de_muestras(muestras):

    # La mediana es robusta a parpadeos y saltos de la mirada
    ojo_x = float(np.median([m[0] for m in muestras]))
    ojo_y = float(np.median([m[1] for m in muestras]))

    return ojo_x, ojo_y


def mediana_de_cabeza(cabezas):

    # cabezas: lista de diccionarios {cx, cy, tam, giro, incl}
    cabezas = [c for c in cabezas if c]

    if not cabezas:
        return None

    return {
        clave: float(np.median([c[clave] for c in cabezas]))
        for clave in CLAVES_CABEZA
    }


def ajustar_calibracion(resultados, cabeza=None):

    # resultados: lista de (ojo_x, ojo_y, punto_x, punto_y)
    # cabeza: posicion de la cabeza durante la calibracion
    # Devuelve (GazeMapper, None) o (None, mensaje de error)

    if len(resultados) < 3:
        return None, "Faltan puntos de calibracion."

    datos = np.array(resultados, dtype=float)

    # Verificar que la mirada realmente se movio
    rango_x = np.ptp(datos[:, 0])
    rango_y = np.ptp(datos[:, 1])

    if rango_x < 0.02 or rango_y < 0.005:

        return None, (
            "Los ojos casi no se movieron. "
            "Mira cada punto sin mover la cabeza."
        )

    # Minimos cuadrados: [ojo_x, ojo_y, 1] -> punto
    ojos = np.column_stack([
        datos[:, 0],
        datos[:, 1],
        np.ones(len(datos))
    ])

    coef_x, *_ = np.linalg.lstsq(ojos, datos[:, 2], rcond=None)
    coef_y, *_ = np.linalg.lstsq(ojos, datos[:, 3], rcond=None)

    mapper = GazeMapper(
        {
            "x": coef_x.tolist(),
            "y": coef_y.tolist(),
        },
        cabeza
    )

    return mapper, None
