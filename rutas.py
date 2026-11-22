
import os
import sys


# =====================================
# RUTAS DEL PROYECTO
# =====================================
# Permite que EyeTrace encuentre sus archivos sin importar
# desde que carpeta se ejecute, y tambien cuando se
# empaqueta como .exe con PyInstaller.


def _empaquetado():

    return getattr(sys, "frozen", False)


def recurso(nombre):

    # Archivos que vienen con el programa (ej. el modelo)
    if _empaquetado():
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base, nombre)


def carpeta_datos():

    # Carpeta donde se guardan la calibracion y las obras
    if _empaquetado():
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.abspath(__file__))


def ruta_datos(*partes):

    return os.path.join(carpeta_datos(), *partes)
