
from gaze_detection import GazeDetector
from calibration import GazeMapper, Calibrator, PUNTOS


detector = GazeDetector()

fallos = 0


def revisar(nombre, esperado, obtenido):

    global fallos

    estado = "OK" if esperado == obtenido else "FALLO"

    if estado == "FALLO":
        fallos += 1

    print(
        f"[{estado}] {nombre} | "
        f"Esperado: {esperado} | Detectado: {obtenido}"
    )


# =====================================
# 1. DIRECCION CON LOS UMBRALES ORIGINALES
# =====================================
# Valores dentro de los rangos actuales:
# x entre 0.20 y 0.80, y entre -0.16 y 0.02

print("--- Umbrales de la mirada ---")

pruebas = [
    ("Centro", 0.50, -0.07, "CENTRO"),
    ("Izquierda", 0.30, -0.07, "IZQUIERDA"),
    ("Derecha", 0.70, -0.07, "DERECHA"),
    ("Arriba", 0.50, -0.13, "ARRIBA"),
    ("Abajo", 0.50, -0.01, "ABAJO"),
]

for nombre, x, y, esperado in pruebas:

    revisar(
        nombre,
        esperado,
        detector.detectar_direccion(x, y)
    )


# =====================================
# 2. DIRECCION EN EL LIENZO CALIBRADO
# =====================================

print("--- Direccion en el lienzo ---")

pruebas_pantalla = [
    ("Centro", 0.5, 0.5, "CENTRO"),
    ("Izquierda", 0.1, 0.5, "IZQUIERDA"),
    ("Derecha", 0.9, 0.5, "DERECHA"),
    ("Arriba", 0.5, 0.1, "ARRIBA"),
    ("Abajo", 0.5, 0.9, "ABAJO"),
]

for nombre, sx, sy, esperado in pruebas_pantalla:

    revisar(
        nombre,
        esperado,
        detector.detectar_direccion_pantalla(sx, sy)
    )


# =====================================
# 3. CALIBRACION CON DATOS SIMULADOS
# =====================================
# Se simula una persona cuyos ojos se mueven en un rango
# distinto al original, se calibra y se verifica que cada
# punto quede donde corresponde en el lienzo.

print("--- Calibracion simulada ---")

calibrador = Calibrator()
calibrador.start()


def ojo_simulado(px, py):

    # Rango propio de esta "persona"
    return 0.35 + 0.25 * px, -0.12 + 0.08 * py


for px, py in PUNTOS:
    calibrador.resultados.append((*ojo_simulado(px, py), px, py))

calibrador._finish()

mapper = calibrador.mapper

for px, py in PUNTOS:

    sx, sy = mapper.map(*ojo_simulado(px, py))

    revisar(
        f"Punto ({px:.2f}, {py:.2f})",
        True,
        abs(sx - px) < 0.01 and abs(sy - py) < 0.01
    )




# =====================================
# 4. POSICION DE LA CABEZA Y RECENTRADO
# =====================================

print("--- Cabeza y recentrado ---")

referencia = {"cx": 0.5, "cy": 0.45, "tam": 0.15, "giro": 0.0, "incl": 0.3}
mapper.cabeza = dict(referencia)

desvio, pista, _ = mapper.desvio_cabeza(dict(referencia))
revisar("Misma posicion", True, desvio < 1)

abajo = dict(referencia, cy=0.55)
desvio, pista, _ = mapper.desvio_cabeza(abajo)
revisar("Cabeza mas abajo", "Sube un poco la cabeza", pista)

cerca = dict(referencia, tam=0.19)
desvio, pista, _ = mapper.desvio_cabeza(cerca)
revisar("Muy cerca", "Aléjate un poco de la pantalla", pista)

# Desfase: el usuario mira el centro pero el mapper da otra cosa
ojo_centro = ojo_simulado(0.5, 0.5)
ojo_corrido = (ojo_centro[0] + 0.02, ojo_centro[1])
mapper.recentrar(*ojo_corrido)
sx, sy = mapper.map(*ojo_corrido)
revisar("Recentrar lleva al centro", True, abs(sx - 0.5) < 0.001 and abs(sy - 0.5) < 0.001)

print()
print("Todas las pruebas pasaron." if fallos == 0 else f"{fallos} pruebas fallaron.")
