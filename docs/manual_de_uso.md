# Manual de uso de EyeTrace

EyeTrace convierte el movimiento de los ojos en trazos sobre un lienzo digital, dentro de una página web.

- **Python + OpenCV** capturan la cámara y dibujan los landmarks sobre el video.
- **MediaPipe Face Landmarker** ubica el iris y las esquinas de cada ojo.
- **NumPy** calcula la calibración por mínimos cuadrados.
- **La página** (carpeta `web/`) muestra el lienzo, la barra de herramientas y el video procesado. Python le envía la posición de la mirada en tiempo real.

## Cómo abrirlo

> **Primero descomprime el .zip** (clic derecho → "Extraer todo…"). No ejecutes los archivos desde dentro del zip.

### Windows
1. Instala **Python 3.12, 3.13 o 3.14** desde https://www.python.org/downloads/ y marca **"Add Python to PATH"** durante la instalación.
2. Haz doble clic en **`INICIAR_WINDOWS.bat`**.

La primera vez instala las librerías (necesita internet y tarda unos minutos). Luego **se abre la página sola en el navegador** (http://localhost:8000). La ventana negra es Python trabajando: déjala abierta mientras dibujas y ciérrala para salir.

### macOS / Linux
```bash
./iniciar_mac_linux.sh
```
En macOS, acepta el permiso de cámara para la Terminal la primera vez.

### Windows sin instalar Python (ejecutable)
En un computador donde EyeTrace ya funciona:
1. Ejecuta `INICIAR_WINDOWS.bat` al menos una vez.
2. Haz doble clic en **`CREAR_EXE_WINDOWS.bat`**.
3. Copia la carpeta **`dist\EyeTrace`** completa a cualquier PC con Windows y abre **`EyeTrace.exe`**.

## Cómo se usa

1. **Inicio:** ubícate frente a la cámara, a un brazo de distancia, con la cara bien iluminada. Cuando diga "Ojos detectados", presiona **Calibrar y empezar** (o Enter).
2. **Calibración:** aparecen 9 puntos. Mira el centro de cada uno **sin mover la cabeza** hasta que se llene de color.
3. **Dibujo:** tu mirada pinta en el lienzo. Los controles están en la barra lateral, a la que el pincel nunca llega, así que siempre se ven.
4. **Si te mueves** (por ejemplo, para mirar el teclado), el pincel se pausa solo y aparece **"Vuelve a tu posición"**, con una pista y una guía: el círculo verde es tu posición de calibración y la carita eres tú. Cuando vuelves a entrar, sigue pintando.
5. **Si el pincel quedó corrido**, presiona **R (Recentrar)**: miras el punto del centro un segundo y se corrige el desfase. Tu postura actual pasa a ser la nueva referencia. Es mucho más rápido que recalibrar.
6. **Terminar (T):** se abre la vista previa de la obra. Ahí decides si **guardarla**, **seguir dibujando** o empezar una **nueva obra**.

### Modo práctica (P)

Sirve para calentar antes de dibujar libre. Eliges una figura (**mariposa**, **flor** o **corazón**) y una velocidad (lenta, normal o rápida). Aparece la silueta punteada y, después de una cuenta regresiva de 3 segundos, un punto la recorre. Síguelo con la mirada: el pincel pinta solo. Al final ves el dibujo con tu **precisión**: 100% significa que el pincel estuvo siempre sobre el punto. Desde ahí puedes guardar, repetir, elegir otra figura o volver al dibujo libre, que se recupera tal como lo dejaste.

| Tecla | Acción |
|---|---|
| Espacio | Pausar o activar el pincel (para mirar sin dibujar) |
| 1 – 8 | Elegir color pastel |
| A | Modo arcoíris |
| + / − | Grosor del pincel |
| N | Cambiar fondo (papel, nube, noche) |
| C | Limpiar el lienzo |
| T | Terminar y ver la obra antes de guardarla |
| P | Modo práctica (1 mariposa, 2 flor, 3 corazón) |
| R | Recentrar: corregir el desfase mirando el centro |
| K | Volver a calibrar (los 9 puntos) |
| F | Pantalla completa |
| Enter / D / E | En el inicio: calibrar / usar la última calibración / modo evaluación |
| Esc | Cancelar la calibración o la práctica, o volver al dibujo |

En la vista previa: **S** guarda (se descarga y queda una copia en `obras/`), **Esc** vuelve a dibujar, **C** empieza una obra nueva y, en la práctica, **R** repite y **P** cambia de figura.

Todos los controles también funcionan con el mouse.

Opciones al iniciar: `--camara 1` usa otra cámara y `--puerto 8080` cambia el puerto. Ejemplo: `INICIAR_WINDOWS.bat --camara 1`.

## Modo evaluación (pruebas con participantes)

En la pantalla de inicio, **E** abre un recorrido guiado de unos 4 minutos por persona:

| Paso | Qué se hace | Qué se mide |
|---|---|---|
| 1. Datos | Código del participante (P01, P02… nunca el nombre), si usa lentes e iluminación | Condiciones de la prueba |
| 2. Calibración | Los 9 puntos de siempre | — |
| 3. Exactitud | 9 puntos **nuevos**, distintos a los de calibración | **Error de exactitud** (distancia entre la mediana de la mirada y el punto, en px y en % de la diagonal) y **dispersión** (RMS de las muestras alrededor de su centro) |
| 4. Práctica | Corazón, flor y mariposa a velocidad normal | **Precisión de seguimiento** y duración |
| 5. Dibujo libre | 1 minuto creando libremente | Detección de ojos durante el uso real y la obra resultante |
| 6. Encuesta | 7 afirmaciones en escala de 1 a 5 y un comentario | Experiencia de usuario |
| 7. Resumen | Métricas de la sesión en pantalla | — |

Durante toda la sesión, cada fotograma de la cámara queda registrado: si se detectaron los ojos, la posición de la mirada y de la cabeza, y el tiempo de procesamiento. Con eso se calculan la **tasa de detección**, los **FPS** y el **tiempo de procesamiento por fotograma**.

### Dónde quedan los datos

```
datos/
├── sesiones.csv            una fila por participante con el resumen de su sesión
├── exactitud.csv           una fila por punto de la prueba de exactitud
├── practica.csv            una fila por figura practicada
├── encuesta.csv            respuestas de la encuesta
├── fotogramas/<sesión>.csv cada fotograma de la cámara (≈30 por segundo)
└── obras/<sesión>.png      la obra del minuto de dibujo libre
```

Si una sesión se cancela, queda marcada como `[cancelada]` en `sesiones.csv` y el análisis la ignora.

### Analizar los resultados

Con el entorno activo, después de hacer las pruebas:

```bash
# Windows
.venv\Scripts\python analisis\analizar_resultados.py
# macOS / Linux
.venv/bin/python analisis/analizar_resultados.py
```

Se crea la carpeta `resultados/` con `resultados.md` (todas las tablas, listas para el README), `resumen_participantes.csv` y las gráficas: exactitud por participante, mapa de exactitud en el lienzo, precisión por figura, detección por participante y por condición, tiempo de procesamiento, encuesta y galería de obras.

### Recomendaciones para las pruebas

- **Entre 8 y 10 participantes** como mínimo, cada uno en su propia sesión.
- Varíen las condiciones a propósito, para poder compararlas: personas **con y sin lentes**, y **luz buena, regular y baja**.
- Usen siempre el **mismo computador y la misma pantalla**, en pantalla completa (**F**) y a la misma distancia (un brazo).
- Pidan permiso a cada persona antes de la prueba. No se guardan imágenes de la cámara, solo números y el dibujo.
- Suban la carpeta `datos/` completa a Google Drive o OneDrive y pongan el enlace en el README.

## Consejos para una buena calibración

- **Calibra en la misma postura en la que vas a dibujar.** Lo que más daña la calibración es mover la cabeza, porque el programa mide dónde está el iris *dentro del ojo*.
- **Apoya la cabeza o los codos** (silla con espaldar, o la barbilla en las manos) y **mueve solo los ojos**.
- **Luz de frente** que ilumine la cara, sin ventanas ni bombillos detrás de ti.
- **Cámara arriba y al centro** de la pantalla, a la altura de los ojos, a unos **50–70 cm**.
- **Pantalla completa (F)**, para que el lienzo sea más grande.
- **Si te moviste y el pincel quedó corrido:** primero prueba **R (Recentrar)**. Si sigue mal, recalibra con **K**.

## Problemas comunes

- **"No se pudo abrir la cámara":** cierra Zoom, Teams, Meet u otro programa que la esté usando, o prueba con `--camara 1`.
- **La página dice "Sin conexión con Python":** la ventana negra se cerró. Vuelve a abrir `INICIAR_WINDOWS.bat`.
- **El trazo no llega a los bordes:** recalibra con **K**, mantén la cabeza quieta y mejora la luz frontal (evita tener una ventana detrás).
- **El aviso "Vuelve a tu posición" sale muy seguido (o nunca):** ajusta `TOLERANCIA_CABEZA` en `calibration.py`. Valores más altos permiten moverse más.
- **Calibraste con una versión anterior:** recalibra una vez con **K** para que se guarde tu posición de referencia. Sin eso, el aviso de posición no aparece.
- **"Los ojos casi no se movieron":** en la calibración mueve solo los ojos y sigue cada punto.
- **Lentes con reflejo:** inclina un poco la pantalla o cambia la luz.

## Archivos

| Archivo | Qué hace |
|---|---|
| `main.py` | Servidor: hilo de la cámara (OpenCV + MediaPipe), video MJPEG, mirada en tiempo real (SSE), calibración y guardado |
| `eye_tracking.py` | Detección del iris y de las esquinas del ojo, filtro de parpadeos, suavizado y posición de la cabeza |
| `calibration.py` | Calibración de 9 puntos (medianas y mínimos cuadrados), referencia de la cabeza y recentrado |
| `gaze_detection.py` | Dirección de la mirada (izquierda, derecha, arriba, abajo, centro) |
| `evaluacion.py` | Registro del modo evaluación: métricas de exactitud y dispersión, y archivos CSV |
| `analisis/analizar_resultados.py` | Lee `datos/` y genera las tablas y gráficas de `resultados/` |
| `rutas.py` | Ubica los archivos tanto en modo script como en el .exe |
| `web/` | Página: `index.html`, `estilos.css`, `app.js` y las fuentes |
| `main_escritorio.py`, `art_canvas.py` | Versión anterior de escritorio con Pygame (opcional) |
| `camera.py` | Prueba sencilla de la cámara |
| `test_gaze.py` | Pruebas de dirección y calibración: `python test_gaze.py` |
| `face_landmarker.task` | Modelo de MediaPipe (478 puntos del rostro, incluido el iris) |

## Cómo funciona

```
Cámara ──► OpenCV (captura, espejo) ──► MediaPipe (landmarks del iris)
       ──► razón del iris dentro del ojo, promedio de ambos ojos, suavizado
       ──► calibración (transformación afín) ──► posición en el lienzo (0 a 1)
       ──► página web: trazo suavizado con curvas
```

**Posición de la cabeza.** Además del iris, se mide la cabeza en cada fotograma: el centro entre los ojos (x, y), la distancia entre las esquinas externas de los ojos (crece al acercarse) y la posición de la punta de la nariz respecto a los ojos (giro e inclinación). Al calibrar se guarda la mediana de esas medidas como referencia. Luego, cada diferencia se divide por su tolerancia; si alguna pasa de 1, la cabeza salió de posición. Para volver, debe bajar de 0,8 (histéresis), así el aviso no parpadea.

**Recentrado.** Mirando el centro del lienzo (0,5; 0,5), se calcula dónde predice la calibración que estás mirando. La diferencia se suma a los términos independientes (c1, c2) de la transformación afín: así se corrige el desfase sin repetir los 9 puntos.

**Figuras de práctica.** Cada figura es una curva paramétrica, con t entre 0 y 2π. El corazón usa la curva clásica x = 16·sen³t; la flor, una curva polar r = 0,35 + 0,65·|cos 2,5t|; y la mariposa, r = (0,12 + |sen 2t|)·(1 + 0,35·cos t). La curva se escala al lienzo y el punto la recorre a velocidad constante según su largo. La precisión es el promedio, cuadro a cuadro, de 1 − distancia / tolerancia, donde la tolerancia es el 12% del tamaño de la figura.

**Calibración.** Se muestran 9 puntos de posición conocida. Para cada uno se toman muestras durante 1,5 s, después de 1 s de espera para que el ojo llegue al punto. Python calcula la **mediana** de esas muestras, que es robusta a parpadeos y saltos. Con los 9 pares (mirada, punto) ajusta por **mínimos cuadrados** una transformación afín:

```
pantalla_x = a1·ojo_x + b1·ojo_y + c1
pantalla_y = a2·ojo_x + b2·ojo_y + c2
```

## Créditos de fuentes

Shrikhand (Jonny Pinhorn), Patrick Hand (Patrick Wagesreiter) y Caveat (Impallari Type), bajo la licencia SIL Open Font License. Las licencias están en `web/fuentes/`. Las fuentes vienen incluidas, así que la página funciona sin internet.
