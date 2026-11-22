
class GazeDetector:

    def __init__(self):

        # Umbrales horizontales
        self.umbral_izquierda = 0.38
        self.umbral_derecha = 0.60

        # Umbrales verticales calibrados
        self.umbral_arriba = -0.105
        self.umbral_abajo = -0.045

    def detectar_direccion(self, x, y):

        if x is None or y is None:
            return "NO DETECTADO"

        # Direcciones horizontales
        if x < self.umbral_izquierda:
            return "IZQUIERDA"

        elif x > self.umbral_derecha:
            return "DERECHA"

        # Direcciones verticales
        elif y < self.umbral_arriba:
            return "ARRIBA"

        elif y > self.umbral_abajo:
            return "ABAJO"

        else:
            return "CENTRO"

    def detectar_direccion_pantalla(self, sx, sy):

        # Direccion a partir de la posicion calibrada en el
        # lienzo (0 a 1). No depende de la persona ni de la
        # camara, porque la calibracion ya hizo ese ajuste.

        if sx is None or sy is None:
            return "NO DETECTADO"

        if sx < 1 / 3:
            return "IZQUIERDA"

        elif sx > 2 / 3:
            return "DERECHA"

        elif sy < 1 / 3:
            return "ARRIBA"

        elif sy > 2 / 3:
            return "ABAJO"

        else:
            return "CENTRO"
