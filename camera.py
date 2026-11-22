
import cv2

# Iniciar la cámara web
cap = cv2.VideoCapture(0)

# Verificar que la cámara esté disponible
if not cap.isOpened():
    print("Error: No se pudo abrir la cámara.")
    exit()

print("EyeTrace: cámara activada correctamente.")

while True:
    # Capturar un fotograma
    ret, frame = cap.read()

    if not ret:
        print("Error al capturar la imagen.")
        break

    # Reflejar la imagen como un espejo
    frame = cv2.flip(frame, 1)

    # Mostrar el video
    cv2.imshow("EyeTrace - Camara Web", frame)

    # Presionar ESC para salir
    if cv2.waitKey(1) & 0xFF == 27:
        break

# Liberar los recursos
cap.release()
cv2.destroyAllWindows()
