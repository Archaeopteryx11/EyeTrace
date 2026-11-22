// =====================================
// EyeTrace - interfaz web
// =====================================
// Python (main.py) procesa la camara con OpenCV y MediaPipe
// y envia la posicion de la mirada por /eventos. Esta pagina
// solo dibuja: el pincel vive dentro del #escenario, asi que
// la mirada nunca alcanza la barra lateral de controles.

const COLORES = [
  { nombre: "Rosa", valor: "#f4a7b9" },
  { nombre: "Durazno", valor: "#f9b58a" },
  { nombre: "Mantequilla", valor: "#f2d16b" },
  { nombre: "Menta", valor: "#8fd3a8" },
  { nombre: "Agua", valor: "#7fcbc4" },
  { nombre: "Cielo", valor: "#8eb8ee" },
  { nombre: "Lavanda", valor: "#b39ddb" },
  { nombre: "Lila", valor: "#e0a3d8" },
];

const FONDOS = [
  { nombre: "Papel", valor: "#fff8ef" },
  { nombre: "Nube", valor: "#eef3fb" },
  { nombre: "Noche", valor: "#2e2b45" },
];

// Mismos puntos que calibration.py (fraccion del escenario)
const PUNTOS = [
  [0.10, 0.12], [0.50, 0.12], [0.90, 0.12],
  [0.10, 0.50], [0.50, 0.50], [0.90, 0.50],
  [0.10, 0.88], [0.50, 0.88], [0.90, 0.88],
];

const ESPERA_MS = 1000;
const CAPTURA_MS = 1500;
const MUESTRAS_MINIMAS = 12;

const $ = (id) => document.getElementById(id);

const escenario = $("escenario");
const lienzo = $("lienzo");
const ctx = lienzo.getContext("2d");
const capaCursor = $("cursor");
const ctxCursor = capaCursor.getContext("2d");
const capaGuia = $("guia");
const ctxGuia = capaGuia.getContext("2d");

const estado = {
  pantalla: "inicio",       // inicio | calibrando | dibujando | eligiendo | practicando | revisando
  mirada: { ok: false },    // ultimo dato de Python
  pincelActivo: true,
  color: 0,
  arcoiris: false,
  tono: 0,
  grosor: 10,
  fondo: 0,
  posicion: null,           // posicion suavizada del pincel
  anterior: null,           // ultimo punto dibujado
  fueraDePosicion: false,   // la cabeza se salio de la posicion de calibracion
};

// =====================================
// 1. DATOS DE LA MIRADA DESDE PYTHON
// =====================================

let alRecibirMuestra = null; // usado durante la calibracion

function conectarEventos() {
  const fuente = new EventSource("/eventos");

  fuente.onmessage = (evento) => {
    estado.mirada = JSON.parse(evento.data);
    actualizarEstadoOjos();

    if (alRecibirMuestra && estado.mirada.ok) {
      alRecibirMuestra(estado.mirada.x, estado.mirada.y, estado.mirada.cabeza);
    }

    vigilarPosicion();
  };

  fuente.onerror = () => {
    estado.mirada = { ok: false, desconectado: true };
    actualizarEstadoOjos();
  };
}

function actualizarEstadoOjos() {
  const m = estado.mirada;
  let texto, bien = false;

  if (m.desconectado) {
    texto = "Sin conexión con Python";
  } else if (m.ok) {
    texto = estado.pantalla === "inicio"
      ? "Ojos detectados ✿"
      : "Ojos detectados ✿ mirando " + m.direccion.toLowerCase();
    bien = true;
  } else if (m.ojos === 1) {
    texto = "Solo veo un ojo";
  } else {
    texto = "No te veo: mira a la cámara";
  }

  $("estado-ojos").textContent = texto;
  $("estado-bienvenida").textContent = m.ok ? "Ojos detectados ✿" : texto;

  for (const id of ["estado-ojos", "estado-bienvenida"]) {
    $(id).classList.toggle("bien", bien);
  }
}

// =====================================
// 2. LIENZO
// =====================================

function ajustarTamano() {
  const ancho = escenario.clientWidth;
  const alto = escenario.clientHeight;
  const ppp = window.devicePixelRatio || 1;

  // Conservar el dibujo al cambiar el tamano
  const copia = document.createElement("canvas");
  copia.width = lienzo.width;
  copia.height = lienzo.height;
  if (lienzo.width) copia.getContext("2d").drawImage(lienzo, 0, 0);

  for (const c of [lienzo, capaCursor, capaGuia]) {
    c.width = Math.round(ancho * ppp);
    c.height = Math.round(alto * ppp);
  }

  ctx.setTransform(ppp, 0, 0, ppp, 0, 0);
  ctxCursor.setTransform(ppp, 0, 0, ppp, 0, 0);
  ctxGuia.setTransform(ppp, 0, 0, ppp, 0, 0);

  if (practica.figura) practica.ruta = construirRuta(practica.figura);

  pintarFondo();
  if (copia.width) ctx.drawImage(copia, 0, 0, ancho, alto);
}

function pintarFondo() {
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = FONDOS[estado.fondo].valor;
  ctx.fillRect(0, 0, lienzo.width, lienzo.height);
  ctx.restore();
}

function limpiar() {
  pintarFondo();
  estado.anterior = null;
  avisar("Lienzo limpio");
}

function colorActual() {
  if (estado.arcoiris) {
    return `hsl(${estado.tono % 360}, 75%, 76%)`;
  }
  return COLORES[estado.color].valor;
}

// =====================================
// 3. CICLO DE DIBUJO
// =====================================

function cuadro() {
  const m = estado.mirada;
  const ancho = escenario.clientWidth;
  const alto = escenario.clientHeight;

  ctxCursor.clearRect(0, 0, ancho, alto);

  if (estado.pantalla === "practicando") actualizarPractica();

  const pintando =
    !estado.fueraDePosicion &&
    (estado.pantalla === "dibujando" ||
      (estado.pantalla === "practicando" && practica.fase !== "listo"));

  if (pintando && m.ok) {
    const objetivo = { x: m.sx * ancho, y: m.sy * alto };

    // Suavizado extra del lado de la pagina
    if (!estado.posicion) {
      estado.posicion = objetivo;
    } else {
      estado.posicion = {
        x: estado.posicion.x + (objetivo.x - estado.posicion.x) * 0.35,
        y: estado.posicion.y + (objetivo.y - estado.posicion.y) * 0.35,
      };
    }

    const p = estado.posicion;

    // En la practica el pincel pinta solo mientras se sigue el punto
    const pincel =
      estado.pantalla === "practicando"
        ? practica.fase === "siguiendo"
        : estado.pincelActivo;

    if (pincel) {
      dibujarTrazo(p);
    } else {
      estado.anterior = null;
    }

    if (estado.pantalla === "practicando" && practica.fase === "siguiendo") {
      medirPrecision(p);
    }

    dibujarCursor(p, pincel);
  } else {
    // Se perdio la mirada: no unir trazos
    estado.posicion = null;
    estado.anterior = null;
  }

  requestAnimationFrame(cuadro);
}

function dibujarTrazo(p) {
  const a = estado.anterior;

  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = estado.grosor;
  ctx.strokeStyle = colorActual();
  ctx.fillStyle = colorActual();

  if (a) {
    const distancia = Math.hypot(p.x - a.x, p.y - a.y);
    if (distancia < 0.5) return;

    // Curva suave: de punto medio a punto medio, usando el
    // punto anterior como control (evita trazos en zigzag)
    const medio = { x: (a.x + p.x) / 2, y: (a.y + p.y) / 2 };
    const desde = estado.medio || a;

    ctx.beginPath();
    ctx.moveTo(desde.x, desde.y);
    ctx.quadraticCurveTo(a.x, a.y, medio.x, medio.y);
    ctx.stroke();

    estado.medio = medio;
    estado.tono += distancia * 0.4;
  } else {
    ctx.beginPath();
    ctx.arc(p.x, p.y, estado.grosor / 2, 0, Math.PI * 2);
    ctx.fill();
    estado.medio = null;
  }

  estado.anterior = { ...p };
}

function dibujarCursor(p, pincel) {
  ctxCursor.lineWidth = 3;
  ctxCursor.strokeStyle = pincel ? colorActual() : "#9a93ad";
  ctxCursor.setLineDash(pincel ? [] : [6, 6]);

  ctxCursor.beginPath();
  ctxCursor.arc(p.x, p.y, estado.grosor / 2 + 10, 0, Math.PI * 2);
  ctxCursor.stroke();
  ctxCursor.setLineDash([]);
}

// =====================================
// 4. CALIBRACION
// =====================================

let calibracionCancelada = false;

async function calibrar() {
  cambiarPantalla("calibrando");
  calibracionCancelada = false;

  const punto = $("punto");
  const relleno = punto.querySelector(".relleno");
  const resultados = [];

  for (let i = 0; i < PUNTOS.length; i++) {
    const [px, py] = PUNTOS[i];

    punto.style.left = px * 100 + "%";
    punto.style.top = py * 100 + "%";
    $("progreso-calibracion").textContent = `${i + 1} de ${PUNTOS.length}`;

    let muestras = [];

    // Repetir el punto si no se vieron bien los ojos
    while (muestras.length < MUESTRAS_MINIMAS) {
      punto.classList.remove("capturando");
      relleno.style.width = relleno.style.height = "0px";

      await esperar(ESPERA_MS);
      if (calibracionCancelada) return false;

      punto.classList.add("capturando");
      muestras = [];
      alRecibirMuestra = (x, y, cabeza) => muestras.push(muestraConCabeza(x, y, cabeza));

      const inicio = performance.now();
      while (performance.now() - inicio < CAPTURA_MS) {
        const avance = (performance.now() - inicio) / CAPTURA_MS;
        relleno.style.width = relleno.style.height = 48 * avance + "px";
        await esperar(30);
        if (calibracionCancelada) {
          alRecibirMuestra = null;
          return false;
        }
      }

      alRecibirMuestra = null;

      if (muestras.length < MUESTRAS_MINIMAS) {
        avisar("No vi bien tus ojos, repitamos este punto");
      }
    }

    resultados.push({ px, py, muestras });
  }

  // Python calcula la calibracion (medianas + minimos cuadrados)
  const respuesta = await enviar("/calibrar", { puntos: resultados });

  // Dentro de la evaluacion, el recorrido decide que sigue
  if (evaluacion.activa) {
    if (respuesta.ok) $("btn-guardada").hidden = false;
    else avisar(respuesta.error || "No se pudo calibrar", 5000);
    return respuesta.ok;
  }

  if (respuesta.ok) {
    $("btn-guardada").hidden = false;
    empezarADibujar();
    avisar("¡Calibración lista! A dibujar con la mirada");
  } else {
    cambiarPantalla("inicio");
    avisar(respuesta.error || "No se pudo calibrar", 5000);
  }
}

function cancelarCalibracion() {
  calibracionCancelada = true;
  alRecibirMuestra = null;
  cambiarPantalla("inicio");
}

async function usarGuardada() {
  const respuesta = await enviar("/usar_guardada", {});

  if (respuesta.ok) {
    empezarADibujar();
    avisar("Usando la última calibración");
  } else {
    avisar(respuesta.error || "No hay calibración guardada");
  }
}

function empezarADibujar() {
  cambiarPantalla("dibujando");
  estado.pincelActivo = true;
  actualizarBotonPausa();
}

// =====================================
// 5. ACCIONES
// =====================================

function alternarPincel() {
  estado.pincelActivo = !estado.pincelActivo;
  estado.anterior = null;
  actualizarBotonPausa();
}

function actualizarBotonPausa() {
  const boton = $("btn-pausa");
  boton.classList.toggle("pincel-activo", estado.pincelActivo);
  boton.classList.toggle("pincel-pausa", !estado.pincelActivo);
  boton.querySelector(".texto").textContent =
    estado.pincelActivo ? "Pincel activo" : "Pincel en pausa";
}

function elegirColor(indice) {
  estado.color = indice;
  estado.arcoiris = false;
  actualizarControles();
}

function alternarArcoiris() {
  estado.arcoiris = !estado.arcoiris;
  actualizarControles();
}

function cambiarGrosor(delta) {
  estado.grosor = Math.min(40, Math.max(2, estado.grosor + delta));
  $("grosor").value = estado.grosor;
}

function cambiarFondo(indice) {
  // Cambiar el fondo empieza un lienzo nuevo
  estado.fondo = indice ?? (estado.fondo + 1) % FONDOS.length;
  pintarFondo();
  estado.anterior = null;
  actualizarControles();
}

async function guardar() {
  const imagen = lienzo.toDataURL("image/png");

  // Descarga en el navegador
  const enlace = document.createElement("a");
  enlace.href = imagen;
  enlace.download = "eyetrace_" + new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-") + ".png";
  enlace.click();

  // Copia en la carpeta obras/ del proyecto
  const respuesta = await enviar("/guardar", { imagen });
  avisar(respuesta.ok ? `Obra guardada en ${respuesta.archivo}` : "No se pudo guardar en obras/");

  if (respuesta.ok) {
    revision.guardada = true;
    pintarBotonesRevision();
  }
}

function pantallaCompleta() {
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    document.documentElement.requestFullscreen().catch(() => {});
  }
}

// =====================================
// 5b. PRACTICA: SEGUIR UN PUNTO
// =====================================
// Cada figura es una curva parametrica t -> (x, y), t de 0 a 2π.
// Se convierte a pixeles, se mide su largo y un punto la recorre
// a velocidad constante. El usuario lo sigue con la mirada.

const FIGURAS = {
  mariposa: {
    nombre: "Mariposa",
    tecla: "1",
    curva: (t) => {
      const r = (0.12 + Math.abs(Math.sin(2 * t))) * (1 + 0.35 * Math.cos(t));
      return [r * Math.sin(t), -r * Math.cos(t)];
    },
  },
  flor: {
    nombre: "Flor",
    tecla: "2",
    curva: (t) => {
      const r = 0.35 + 0.65 * Math.abs(Math.cos(2.5 * t));
      return [r * Math.cos(t - Math.PI / 2), r * Math.sin(t - Math.PI / 2)];
    },
  },
  corazon: {
    nombre: "Corazón",
    tecla: "3",
    curva: (t) => [
      16 * Math.sin(t) ** 3,
      -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)),
    ],
  },
};

const CUENTA_MS = 3000;

const practica = {
  figura: null,
  ruta: null,
  velocidad: 1,
  fase: "listo",        // cuenta | siguiendo | listo
  inicio: 0,
  sumaPrecision: 0,
  muestras: 0,
  recorrido: 0,         // pixeles recorridos por el punto
  ultimoCuadro: 0,
  respaldo: null,       // dibujo libre guardado mientras se practica
};

function puntosFigura(clave, cantidad = 700) {
  const puntos = [];
  for (let i = 0; i <= cantidad; i++) {
    puntos.push(FIGURAS[clave].curva((i / cantidad) * Math.PI * 2));
  }
  return puntos;
}

function ajustarPuntos(puntos, ancho, alto, margen) {
  // Escalar y centrar la figura dentro del area dada
  const xs = puntos.map((p) => p[0]);
  const ys = puntos.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const escala = Math.min(
    (ancho - 2 * margen) / (maxX - minX),
    (alto - 2 * margen) / (maxY - minY)
  );
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

  return {
    puntos: puntos.map(([x, y]) => ({
      x: ancho / 2 + (x - cx) * escala,
      y: alto / 2 + (y - cy) * escala,
    })),
    tamano: Math.max(maxX - minX, maxY - minY) * escala,
  };
}

function construirRuta(clave) {
  const ancho = escenario.clientWidth;
  const alto = escenario.clientHeight;
  const { puntos, tamano } = ajustarPuntos(
    puntosFigura(clave), ancho, alto, Math.min(ancho, alto) * 0.12
  );

  // Largo acumulado para moverse a velocidad constante
  const largos = [0];
  for (let i = 1; i < puntos.length; i++) {
    largos.push(
      largos[i - 1] +
      Math.hypot(puntos[i].x - puntos[i - 1].x, puntos[i].y - puntos[i - 1].y)
    );
  }

  return { puntos, largos, total: largos[largos.length - 1], tamano };
}

function puntoEnRuta(ruta, distancia) {
  const { puntos, largos } = ruta;
  let i = 1;
  while (i < largos.length - 1 && largos[i] < distancia) i++;
  const tramo = largos[i] - largos[i - 1] || 1;
  const f = Math.min(1, Math.max(0, (distancia - largos[i - 1]) / tramo));
  return {
    x: puntos[i - 1].x + (puntos[i].x - puntos[i - 1].x) * f,
    y: puntos[i - 1].y + (puntos[i].y - puntos[i - 1].y) * f,
  };
}

function abrirEleccion() {
  if (estado.pantalla === "dibujando") {
    // Guardar el dibujo libre para recuperarlo al terminar
    practica.respaldo = copiarLienzo();
  }
  cambiarPantalla("eligiendo");
}

function cerrarEleccion() {
  restaurarDibujoLibre();
  cambiarPantalla("dibujando");
}

function empezarPractica(clave) {
  practica.figura = clave;
  practica.ruta = construirRuta(clave);
  practica.fase = "cuenta";
  practica.inicio = performance.now();
  practica.inicioReal = performance.now();
  practica.ultimoCuadro = performance.now();
  practica.cuentaRestante = undefined;
  practica.recorrido = 0;
  practica.sumaPrecision = 0;
  practica.muestras = 0;

  pintarFondo();
  estado.anterior = null;
  estado.medio = null;

  $("practica-titulo").textContent = "Práctica: " + FIGURAS[clave].nombre.toLowerCase();
  $("practica-precision").textContent = "Precisión: —";
  $("practica-progreso").style.width = "0";
  cambiarPantalla("practicando");
}

function actualizarPractica() {
  const ruta = practica.ruta;
  const ahora = performance.now();
  const cuenta = $("cuenta");

  // Si la cabeza se sale de posicion, el tiempo se congela
  const dt = estado.fueraDePosicion ? 0 : ahora - practica.ultimoCuadro;
  practica.ultimoCuadro = ahora;

  // Velocidad: ~18% del tamano de la figura por segundo
  const pxPorSegundo = ruta.tamano * 0.18 * practica.velocidad;

  if (practica.fase === "cuenta") {
    practica.cuentaRestante = (practica.cuentaRestante ?? CUENTA_MS) - dt;

    if (practica.cuentaRestante <= 0) {
      practica.fase = "siguiendo";
      practica.cuentaRestante = undefined;
      cuenta.style.display = "none";
    } else {
      const inicio = ruta.puntos[0];
      cuenta.textContent = Math.ceil(practica.cuentaRestante / 1000);
      cuenta.style.display = "block";
      cuenta.style.left = inicio.x + "px";
      cuenta.style.top = inicio.y - 90 + "px";
    }
  }

  if (practica.fase === "siguiendo") {
    practica.recorrido += (dt / 1000) * pxPorSegundo;

    if (practica.recorrido >= ruta.total) {
      terminarPractica();
      return;
    }
  }

  const recorrido = practica.recorrido;
  practica.objetivo = puntoEnRuta(ruta, recorrido);
  $("practica-progreso").style.width = (recorrido / ruta.total) * 100 + "%";

  dibujarGuia(recorrido);
}

function dibujarGuia(recorrido) {
  const ruta = practica.ruta;
  const ancho = escenario.clientWidth;
  const alto = escenario.clientHeight;
  const oscuro = FONDOS[estado.fondo].nombre === "Noche";

  ctxGuia.clearRect(0, 0, ancho, alto);

  // Silueta punteada
  ctxGuia.save();
  ctxGuia.setLineDash([4, 10]);
  ctxGuia.lineCap = "round";
  ctxGuia.lineWidth = 3;
  ctxGuia.strokeStyle = oscuro ? "rgba(255,255,255,0.35)" : "rgba(61,53,83,0.25)";
  ctxGuia.beginPath();
  ruta.puntos.forEach((p, i) => (i ? ctxGuia.lineTo(p.x, p.y) : ctxGuia.moveTo(p.x, p.y)));
  ctxGuia.stroke();
  ctxGuia.restore();

  // Punto a seguir, con un halo que late
  const o = practica.objetivo;
  const pulso = 4 * Math.sin(performance.now() / 160);

  ctxGuia.fillStyle = "rgba(232,138,165,0.25)";
  ctxGuia.beginPath();
  ctxGuia.arc(o.x, o.y, 26 + pulso, 0, Math.PI * 2);
  ctxGuia.fill();

  ctxGuia.fillStyle = "#e88aa5";
  ctxGuia.strokeStyle = "#fff";
  ctxGuia.lineWidth = 3;
  ctxGuia.beginPath();
  ctxGuia.arc(o.x, o.y, 11, 0, Math.PI * 2);
  ctxGuia.fill();
  ctxGuia.stroke();
}

function medirPrecision(p) {
  // 100% si el pincel esta sobre el punto; 0% a 12% del tamano de la figura
  const o = practica.objetivo;
  if (!o) return;

  const distancia = Math.hypot(p.x - o.x, p.y - o.y);
  const tolerancia = practica.ruta.tamano * 0.12;

  practica.sumaPrecision += Math.max(0, 1 - distancia / tolerancia);
  practica.muestras += 1;

  $("practica-precision").textContent = `Precisión: ${precisionActual()}%`;
}

function precisionActual() {
  if (!practica.muestras) return 0;
  return Math.round((practica.sumaPrecision / practica.muestras) * 100);
}

function terminarPractica() {
  practica.fase = "listo";
  $("cuenta").style.display = "none";
  ctxGuia.clearRect(0, 0, escenario.clientWidth, escenario.clientHeight);

  // En la evaluacion se entrega el resultado al recorrido
  if (practica.alTerminar) {
    const fin = practica.alTerminar;
    practica.alTerminar = null;
    fin({
      precision: precisionActual(),
      muestras: practica.muestras,
      duracion: (performance.now() - practica.inicioReal) / 1000,
    });
    return;
  }

  abrirRevision("practica");
}

function cancelarPractica() {
  practica.fase = "listo";
  $("cuenta").style.display = "none";
  ctxGuia.clearRect(0, 0, escenario.clientWidth, escenario.clientHeight);

  if (practica.alTerminar) {
    const fin = practica.alTerminar;
    practica.alTerminar = null;
    fin(null);
    return;
  }

  restaurarDibujoLibre();
  cambiarPantalla("dibujando");
}

function copiarLienzo() {
  const copia = document.createElement("canvas");
  copia.width = lienzo.width;
  copia.height = lienzo.height;
  copia.getContext("2d").drawImage(lienzo, 0, 0);
  return copia;
}

function restaurarDibujoLibre() {
  if (!practica.respaldo) return;
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(practica.respaldo, 0, 0, lienzo.width, lienzo.height);
  ctx.restore();
  practica.respaldo = null;
  estado.anterior = null;
}

function construirFiguras() {
  for (const [clave, figura] of Object.entries(FIGURAS)) {
    const boton = document.createElement("button");
    boton.className = "figura";

    // Miniatura de la figura
    const mini = document.createElement("canvas");
    mini.width = 320;
    mini.height = 280;
    const c = mini.getContext("2d");
    const { puntos } = ajustarPuntos(puntosFigura(clave), 320, 280, 26);
    const gradiente = c.createLinearGradient(0, 0, 320, 280);
    gradiente.addColorStop(0, "#f4a7b9");
    gradiente.addColorStop(0.5, "#c9b6f2");
    gradiente.addColorStop(1, "#8eb8ee");
    c.strokeStyle = gradiente;
    c.lineWidth = 9;
    c.lineCap = c.lineJoin = "round";
    c.beginPath();
    puntos.forEach((p, i) => (i ? c.lineTo(p.x, p.y) : c.moveTo(p.x, p.y)));
    c.stroke();

    const nombre = document.createElement("div");
    nombre.className = "nombre";
    nombre.innerHTML = `<span>${figura.nombre}</span><kbd>${figura.tecla}</kbd>`;

    boton.append(mini, nombre);
    boton.onclick = () => empezarPractica(clave);
    $("figuras").appendChild(boton);
  }

  document.querySelectorAll("[data-velocidad]").forEach((b) => {
    b.onclick = () => {
      practica.velocidad = Number(b.dataset.velocidad);
      marcarVelocidad();
    };
  });
  marcarVelocidad();
}

function marcarVelocidad() {
  document.querySelectorAll("[data-velocidad]").forEach((b) =>
    b.classList.toggle("activo", Number(b.dataset.velocidad) === practica.velocidad)
  );
}

// =====================================
// 5c. TERMINAR: REVISAR ANTES DE GUARDAR
// =====================================

const revision = { modo: "libre", guardada: false };

function abrirRevision(modo) {
  revision.modo = modo;
  revision.guardada = false;

  $("revision-imagen").src = lienzo.toDataURL("image/png");

  if (modo === "practica") {
    const p = precisionActual();
    const frase =
      p >= 80 ? "¡Excelente puntería!" :
      p >= 60 ? "¡Muy bien!" :
      p >= 40 ? "¡Vas mejorando!" : "Sigue practicando, ¡tú puedes!";
    $("revision-titulo").textContent = `¡${FIGURAS[practica.figura].nombre} lista!`;
    $("revision-nota").textContent = `Precisión: ${p}% · ${frase}`;
  } else {
    $("revision-titulo").textContent = "¡Tu obra!";
    $("revision-nota").textContent = "¿Te gusta? Puedes guardarla o seguir dibujando";
  }

  pintarBotonesRevision();
  cambiarPantalla("revisando");
}

function opcionesRevision() {
  const guardarTexto = revision.guardada ? "Guardada ✓" : "Guardar";

  if (revision.modo === "practica") {
    return [
      { texto: guardarTexto, tecla: "S", accion: guardar, principal: true },
      { texto: "Repetir", tecla: "R", accion: () => empezarPractica(practica.figura) },
      { texto: "Otra figura", tecla: "P", accion: () => cambiarPantalla("eligiendo") },
      { texto: "Volver al dibujo libre", tecla: "Esc", accion: cancelarPractica },
    ];
  }

  return [
    { texto: guardarTexto, tecla: "S", accion: guardar, principal: true },
    { texto: "Seguir dibujando", tecla: "Esc", accion: () => cambiarPantalla("dibujando") },
    {
      texto: "Nueva obra", tecla: "C",
      accion: () => { pintarFondo(); estado.anterior = null; cambiarPantalla("dibujando"); },
    },
  ];
}

function pintarBotonesRevision() {
  const contenedor = $("revision-botones");
  contenedor.innerHTML = "";

  for (const opcion of opcionesRevision()) {
    const boton = document.createElement("button");
    boton.className = "boton" + (opcion.principal ? " principal" : "");
    boton.innerHTML = `<span>${opcion.texto}</span><kbd>${opcion.tecla}</kbd>`;
    boton.onclick = () => { boton.blur(); opcion.accion(); };
    contenedor.appendChild(boton);
  }
}

function teclaRevision(tecla) {
  const mapa = { s: "S", r: "R", p: "P", c: "C", escape: "Esc", t: "Esc" };
  const opcion = opcionesRevision().find((o) => o.tecla === mapa[tecla]);
  if (opcion) opcion.accion();
}

// =====================================
// 5d. POSICION DE LA CABEZA
// =====================================
// Python compara la cabeza actual con la de la calibracion y
// envia "desvio" (menor que 1 = bien). Si te sales (por ejemplo
// al mirar el teclado), el pincel se pausa y aparece una guia.
// Se usa histeresis para que el aviso no parpadee.

const SALIR_MS = 350;     // tiempo fuera antes de avisar
const VOLVER_MS = 450;    // tiempo dentro antes de seguir

const posicion = { desde: 0, candidato: false };

function vigilarPosicion() {
  const m = estado.mirada;
  const vigilando = ["dibujando", "practicando"].includes(estado.pantalla);

  if (!vigilando) {
    ponerFueraDePosicion(false);
    return;
  }

  let fuera;

  if (!m.cabeza) {
    fuera = true;                              // no se ve la cara
  } else if (m.desvio == null) {
    fuera = false;                             // calibracion sin referencia
  } else {
    // Histeresis: para volver hay que estar bien adentro
    fuera = estado.fueraDePosicion ? m.desvio > 0.8 : m.desvio > 1;
  }

  const ahora = performance.now();

  if (fuera !== posicion.candidato) {
    posicion.candidato = fuera;
    posicion.desde = ahora;
  }

  const espera = fuera ? SALIR_MS : VOLVER_MS;

  if (fuera !== estado.fueraDePosicion && ahora - posicion.desde > espera) {
    ponerFueraDePosicion(fuera);
  }

  if (estado.fueraDePosicion) actualizarGuiaPosicion();
}

function ponerFueraDePosicion(fuera) {
  if (estado.fueraDePosicion === fuera) return;

  estado.fueraDePosicion = fuera;
  estado.anterior = null;
  estado.posicion = null;
  document.body.classList.toggle("fuera-de-posicion", fuera);
}

function actualizarGuiaPosicion() {
  const m = estado.mirada;
  const lienzoBurbuja = $("burbuja");
  const c = lienzoBurbuja.getContext("2d");
  const centro = 160;
  const radio = 70;   // el circulo = la tolerancia permitida

  $("posicion-pista").textContent = m.cabeza
    ? (m.pista || "Mueve la cabeza hasta que el punto entre al círculo")
    : "No veo tu cara: mira hacia la pantalla";

  c.clearRect(0, 0, 320, 320);

  // Zona correcta
  c.fillStyle = "#e3f6ea";
  c.strokeStyle = "#8fd3a8";
  c.lineWidth = 6;
  c.setLineDash([14, 10]);
  c.beginPath();
  c.arc(centro, centro, radio, 0, Math.PI * 2);
  c.fill();
  c.stroke();
  c.setLineDash([]);

  if (!m.relativo) return;

  // Tu cabeza: posicion segun cx/cy, tamano segun cercania
  const limitar = (v) => Math.max(-1.7, Math.min(1.7, v));
  const x = centro + limitar(m.relativo.cx) * radio;
  const y = centro + limitar(m.relativo.cy) * radio;
  const r = 26 * (1 + limitar(m.relativo.tam) * 0.25);

  c.fillStyle = m.desvio > 1 ? "#f4a7b9" : "#8fd3a8";
  c.strokeStyle = "#3d3553";
  c.lineWidth = 4;
  c.beginPath();
  c.arc(x, y, r, 0, Math.PI * 2);
  c.fill();
  c.stroke();

  // Ojitos que indican hacia donde esta girada la cara
  const gx = limitar(m.relativo.giro) * 6;
  const gy = limitar(m.relativo.incl) * 6;
  c.fillStyle = "#3d3553";
  for (const lado of [-1, 1]) {
    c.beginPath();
    c.arc(x + lado * r * 0.38 + gx, y - r * 0.12 + gy, 4, 0, Math.PI * 2);
    c.fill();
  }
}

// =====================================
// 5e. RECENTRADO RAPIDO
// =====================================
// Mirar el centro 1,5 s: Python corrige el desfase y toma la
// postura actual como nueva referencia. Mucho mas rapido que
// recalibrar los 9 puntos.

function muestraConCabeza(x, y, cabeza) {
  return cabeza
    ? [x, y, cabeza.cx, cabeza.cy, cabeza.tam, cabeza.giro, cabeza.incl]
    : [x, y];
}

let recentrando = false;

async function recentrar() {
  if (recentrando) return;
  recentrando = true;

  ponerFueraDePosicion(false);
  cambiarPantalla("recentrando");

  const punto = $("punto");
  const relleno = punto.querySelector(".relleno");
  punto.style.left = "50%";
  punto.style.top = "50%";

  let muestras = [];

  for (let intento = 0; intento < 3 && muestras.length < MUESTRAS_MINIMAS; intento++) {
    punto.classList.remove("capturando");
    relleno.style.width = relleno.style.height = "0px";
    await esperar(700);

    punto.classList.add("capturando");
    muestras = [];
    alRecibirMuestra = (x, y, cabeza) => muestras.push(muestraConCabeza(x, y, cabeza));

    const inicio = performance.now();
    while (performance.now() - inicio < CAPTURA_MS) {
      const avance = (performance.now() - inicio) / CAPTURA_MS;
      relleno.style.width = relleno.style.height = 48 * avance + "px";
      await esperar(30);
    }
    alRecibirMuestra = null;
  }

  const respuesta = muestras.length >= MUESTRAS_MINIMAS
    ? await enviar("/recentrar", { muestras })
    : { ok: false, error: "No vi bien tus ojos. Intenta otra vez o recalibra con K" };

  recentrando = false;
  cambiarPantalla("dibujando");
  avisar(respuesta.ok ? "¡Recentrado! Esta postura es tu nueva posición" : respuesta.error, 3500);
}

// =====================================
// 5f. MODO EVALUACION
// =====================================
// Recorrido guiado para evaluar el sistema con participantes.
// Python guarda todo en la carpeta datos/ (ver evaluacion.py):
//   1. Datos del participante
//   2. Calibracion (9 puntos)
//   3. Prueba de exactitud: 9 puntos NUEVOS, distintos a los de
//      calibracion -> error (exactitud) y dispersion (precision)
//   4. Practica: corazon, flor y mariposa a velocidad normal
//   5. Un minuto de dibujo libre
//   6. Encuesta de experiencia (escala 1 a 5)
//   7. Resumen de la sesion

const PUNTOS_PRUEBA = [
  [0.30, 0.25], [0.70, 0.25], [0.50, 0.35],
  [0.20, 0.55], [0.50, 0.62], [0.80, 0.55],
  [0.35, 0.80], [0.65, 0.80], [0.92, 0.88],
];

const FIGURAS_EVALUACION = ["corazon", "flor", "mariposa"];
const DIBUJO_LIBRE_S = 60;

const PASOS_EVALUACION = [
  "Datos", "Calibración", "Exactitud", "Práctica",
  "Dibujo libre", "Encuesta", "Resumen",
];

const evaluacion = {
  activa: false,
  cancelada: false,
  paso: 0,
  preguntas: [],
  respuestaPantalla: null,   // resuelve la promesa de cada pantalla
};

class EvaluacionCancelada extends Error {}

function revisarCancelacion() {
  if (evaluacion.cancelada) throw new EvaluacionCancelada();
}

function marcarPaso(indice, detalle = "") {
  evaluacion.paso = indice;
  $("evaluacion-pasos").innerHTML = PASOS_EVALUACION.map((nombre, i) =>
    `<li class="${i < indice ? "hecho" : i === indice ? "actual" : ""}">${nombre}</li>`
  ).join("");
  $("evaluacion-detalle").textContent = detalle;
}

function etapa(nombre) {
  return enviar("/evaluacion/etapa", { etapa: nombre });
}

// Muestra una pantalla dentro de #evaluacion y espera un boton
function pantallaEvaluacion(html) {
  $("evaluacion-contenido").innerHTML = html;
  cambiarPantalla("evaluando");

  return new Promise((resolver) => {
    evaluacion.respuestaPantalla = resolver;

    $("evaluacion-contenido").querySelectorAll("[data-accion]").forEach((b) => {
      b.onclick = () => resolver(b.dataset.accion);
    });
  });
}

async function modoEvaluacion() {
  if (evaluacion.activa) return;

  evaluacion.activa = true;
  evaluacion.cancelada = false;
  ponerClaseEvaluacion(true);

  try {
    // ---------- 1. Datos ----------
    marcarPaso(0);
    const datos = await formularioParticipante();
    if (!datos) throw new EvaluacionCancelada();

    const inicio = await enviar("/evaluacion/iniciar", {
      ...datos,
      ancho: escenario.clientWidth,
      alto: escenario.clientHeight,
    });
    if (!inicio.ok) throw new Error(inicio.error);
    $("evaluacion-participante").textContent = datos.participante;

    // ---------- 2. Calibracion ----------
    let calibrado = false;
    for (let intento = 1; !calibrado; intento++) {
      marcarPaso(1, intento > 1 ? `Intento ${intento}` : "");
      await etapa("calibracion");
      calibrado = await calibrar();
      revisarCancelacion();

      if (!calibrado) {
        const opcion = await pantallaEvaluacion(`
          <h1>Repitamos la calibración</h1>
          <p class="lema">No quedó bien. Revisa la luz y que la cabeza esté quieta.</p>
          <div class="fila-botones">
            <button class="boton principal" data-accion="repetir"><span>Repetir</span><kbd>Enter</kbd></button>
          </div>`);
        if (opcion !== "repetir") throw new EvaluacionCancelada();
      }
    }

    // ---------- 3. Exactitud ----------
    marcarPaso(2);
    await pantallaEvaluacion(`
      <h1>Prueba de exactitud</h1>
      <p class="lema">Aparecerán 9 puntos nuevos. Míralos igual que en la calibración:
      quieto/a, solo con los ojos, hasta que se llenen.</p>
      <div class="fila-botones">
        <button class="boton principal" data-accion="seguir"><span>Empezar</span><kbd>Enter</kbd></button>
      </div>`);
    revisarCancelacion();
    await etapa("exactitud");
    const exactitud = await pruebaExactitud();
    revisarCancelacion();
    await mostrarResultadoExactitud(exactitud);
    revisarCancelacion();

    // ---------- 4. Practica ----------
    for (let i = 0; i < FIGURAS_EVALUACION.length; i++) {
      const clave = FIGURAS_EVALUACION[i];
      marcarPaso(3, `${FIGURAS[clave].nombre} (${i + 1} de ${FIGURAS_EVALUACION.length})`);

      await pantallaEvaluacion(`
        <h1>Práctica: ${FIGURAS[clave].nombre.toLowerCase()}</h1>
        <p class="lema">Sigue el punto con la mirada hasta completar la figura.</p>
        <div class="fila-botones">
          <button class="boton principal" data-accion="seguir"><span>Empezar</span><kbd>Enter</kbd></button>
        </div>`);
      revisarCancelacion();

      await etapa("practica_" + clave);
      const resultado = await practicarEnEvaluacion(clave);
      revisarCancelacion();

      await enviar("/evaluacion/practica", {
        figura: clave,
        velocidad: practica.velocidad,
        ...resultado,
      });
    }

    // ---------- 5. Dibujo libre ----------
    marcarPaso(4);
    await pantallaEvaluacion(`
      <h1>Dibujo libre</h1>
      <p class="lema">Tienes ${DIBUJO_LIBRE_S} segundos para crear lo que quieras con la mirada.
      Puedes cambiar colores y pausar el pincel con Espacio.</p>
      <div class="fila-botones">
        <button class="boton principal" data-accion="seguir"><span>Empezar</span><kbd>Enter</kbd></button>
      </div>`);
    revisarCancelacion();
    await etapa("dibujo_libre");
    await dibujoLibreEvaluacion();
    revisarCancelacion();

    // ---------- 6. Encuesta ----------
    marcarPaso(5);
    await etapa("encuesta");
    const encuesta = await formularioEncuesta();
    if (!encuesta) throw new EvaluacionCancelada();
    await enviar("/evaluacion/encuesta", encuesta);

    // ---------- 7. Resumen ----------
    marcarPaso(6);
    await etapa("resumen");
    const resumen = await enviar("/evaluacion/terminar", {});
    evaluacion.activa = false;
    await mostrarResumen(resumen);

  } catch (error) {
    if (!(error instanceof EvaluacionCancelada)) {
      console.error(error);
      avisar("Hubo un problema en la evaluación: " + error.message, 5000);
    }
    if (evaluacion.activa) await enviar("/evaluacion/terminar", { cancelada: true });
  }

  evaluacion.activa = false;
  evaluacion.cancelada = false;
  ponerClaseEvaluacion(false);
  pintarFondo();
  cambiarPantalla("inicio");
}

function cancelarEvaluacion() {
  if (!evaluacion.activa) return;
  evaluacion.cancelada = true;

  // Detener lo que este corriendo en ese momento
  if (estado.pantalla === "calibrando") cancelarCalibracion();
  if (estado.pantalla === "practicando") cancelarPractica();
  if (evaluacion.respuestaPantalla) evaluacion.respuestaPantalla(null);
  if (evaluacion.finDibujo) evaluacion.finDibujo();
  avisar("Evaluación cancelada");
}

function ponerClaseEvaluacion(activa) {
  document.body.classList.toggle("en-evaluacion", activa);
}

// ---------- Formularios ----------

function formularioParticipante() {
  const html = `
    <h1>Modo evaluación</h1>
    <p class="lema">Antes de empezar: pantalla completa (F), buena luz de frente
    y el participante sentado cómodo, a un brazo de la pantalla.</p>
    <form id="form-participante" class="formulario">
      <label>Código del participante
        <input name="participante" required maxlength="20" placeholder="P01" autocomplete="off">
      </label>
      <fieldset>
        <legend>¿Usa lentes?</legend>
        <label class="opcion"><input type="radio" name="lentes" value="si" required> Sí</label>
        <label class="opcion"><input type="radio" name="lentes" value="no"> No</label>
      </fieldset>
      <fieldset>
        <legend>Iluminación</legend>
        <label class="opcion"><input type="radio" name="iluminacion" value="buena" required> Buena</label>
        <label class="opcion"><input type="radio" name="iluminacion" value="regular"> Regular</label>
        <label class="opcion"><input type="radio" name="iluminacion" value="baja"> Baja</label>
      </fieldset>
      <label>Notas (opcional)
        <input name="notas" maxlength="300" placeholder="Ej.: luz de ventana a la izquierda" autocomplete="off">
      </label>
      <div class="fila-botones">
        <button type="submit" class="boton principal"><span>Empezar evaluación</span></button>
        <button type="button" class="boton" data-accion="cancelar"><span>Cancelar</span></button>
      </div>
    </form>
    <p class="nota-pausa">Usen solo un código (P01, P02…), no el nombre, para proteger la privacidad.</p>`;

  const promesa = pantallaEvaluacion(html);

  const form = $("form-participante");
  form.onsubmit = (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(form));
    evaluacion.respuestaPantalla(d);
  };
  setTimeout(() => form.participante.focus(), 50);

  return promesa.then((r) => (r && typeof r === "object" ? r : null));
}

function formularioEncuesta() {
  const filas = evaluacion.preguntas.map((p) => `
    <div class="pregunta">
      <p>${p.texto}</p>
      <div class="escala">
        ${[1, 2, 3, 4, 5].map((v) => `
          <label><input type="radio" name="${p.clave}" value="${v}" required><span>${v}</span></label>`).join("")}
      </div>
    </div>`).join("");

  const html = `
    <h1>¿Cómo te fue?</h1>
    <p class="lema">1 = totalmente en desacuerdo · 5 = totalmente de acuerdo</p>
    <form id="form-encuesta" class="formulario encuesta">
      ${filas}
      <label>¿Algún comentario?
        <textarea name="comentario" rows="2" maxlength="500"></textarea>
      </label>
      <div class="fila-botones">
        <button type="submit" class="boton principal"><span>Enviar respuestas</span></button>
      </div>
    </form>`;

  const promesa = pantallaEvaluacion(html);
  const form = $("form-encuesta");
  form.onsubmit = (e) => {
    e.preventDefault();
    evaluacion.respuestaPantalla(Object.fromEntries(new FormData(form)));
  };

  return promesa.then((r) => (r && typeof r === "object" ? r : null));
}

// ---------- Prueba de exactitud ----------

async function pruebaExactitud() {
  cambiarPantalla("calibrando");
  $("progreso-calibracion").textContent = "";
  document.body.classList.add("midiendo");

  const punto = $("punto");
  const relleno = punto.querySelector(".relleno");
  const resultados = [];

  for (let i = 0; i < PUNTOS_PRUEBA.length; i++) {
    const [px, py] = PUNTOS_PRUEBA[i];
    punto.style.left = px * 100 + "%";
    punto.style.top = py * 100 + "%";
    $("progreso-calibracion").textContent = `Prueba ${i + 1} de ${PUNTOS_PRUEBA.length}`;

    let muestras = [];

    for (let intento = 0; intento < 3 && muestras.length < MUESTRAS_MINIMAS; intento++) {
      punto.classList.remove("capturando");
      relleno.style.width = relleno.style.height = "0px";
      await esperar(ESPERA_MS);
      revisarCancelacion();

      punto.classList.add("capturando");
      muestras = [];
      // Se guarda la posicion en el lienzo (0..1) ya calibrada
      alRecibirMuestra = () => muestras.push([estado.mirada.sx, estado.mirada.sy]);

      const inicio = performance.now();
      while (performance.now() - inicio < CAPTURA_MS) {
        relleno.style.width = relleno.style.height =
          48 * ((performance.now() - inicio) / CAPTURA_MS) + "px";
        await esperar(30);
        if (evaluacion.cancelada) { alRecibirMuestra = null; revisarCancelacion(); }
      }
      alRecibirMuestra = null;
    }

    const respuesta = await enviar("/evaluacion/punto", {
      punto: i + 1,
      objetivo: [px, py],
      muestras,
      ancho: escenario.clientWidth,
      alto: escenario.clientHeight,
    });

    resultados.push({
      objetivo: [px, py],
      mirada: muestras.length ? medianaXY(muestras) : null,
      error_px: respuesta.ok ? respuesta.error_px : null,
      error_pct: respuesta.ok ? respuesta.error_pct : null,
    });
  }

  document.body.classList.remove("midiendo");
  return resultados;
}

function medianaXY(muestras) {
  const mediana = (v) => {
    const o = [...v].sort((a, b) => a - b);
    const m = Math.floor(o.length / 2);
    return o.length % 2 ? o[m] : (o[m - 1] + o[m]) / 2;
  };
  return [mediana(muestras.map((m) => m[0])), mediana(muestras.map((m) => m[1]))];
}

async function mostrarResultadoExactitud(resultados) {
  const validos = resultados.filter((r) => r.error_px != null);
  const promedio = (v) => v.reduce((a, b) => a + b, 0) / (v.length || 1);
  const errorPx = promedio(validos.map((r) => r.error_px));
  const errorPct = promedio(validos.map((r) => r.error_pct));

  const promesa = pantallaEvaluacion(`
    <h1>Resultado de exactitud</h1>
    <p class="lema">Error promedio: <b>${errorPx.toFixed(0)} px</b> (${errorPct.toFixed(1)}% de la pantalla)
    · ${validos.length} de ${resultados.length} puntos medidos</p>
    <canvas id="grafica-exactitud" width="720" height="440"></canvas>
    <p class="nota-pausa">● objetivo &nbsp; ✚ donde miró el participante</p>
    <div class="fila-botones">
      <button class="boton principal" data-accion="seguir"><span>Continuar</span><kbd>Enter</kbd></button>
    </div>`);

  // Dibujo: objetivos y miradas, unidos por una linea
  const c = $("grafica-exactitud").getContext("2d");
  const W = 720, H = 440;
  c.fillStyle = "#fff8ef"; c.fillRect(0, 0, W, H);
  c.strokeStyle = "#d9cdf5"; c.strokeRect(0.5, 0.5, W - 1, H - 1);

  for (const r of resultados) {
    const ox = r.objetivo[0] * W, oy = r.objetivo[1] * H;
    if (r.mirada) {
      const mx = r.mirada[0] * W, my = r.mirada[1] * H;
      c.strokeStyle = "#b39ddb"; c.lineWidth = 2;
      c.beginPath(); c.moveTo(ox, oy); c.lineTo(mx, my); c.stroke();
      c.strokeStyle = "#e88aa5"; c.lineWidth = 3;
      c.beginPath(); c.moveTo(mx - 8, my); c.lineTo(mx + 8, my); c.moveTo(mx, my - 8); c.lineTo(mx, my + 8); c.stroke();
    }
    c.fillStyle = "#3d3553";
    c.beginPath(); c.arc(ox, oy, 6, 0, Math.PI * 2); c.fill();
  }

  return promesa;
}

// ---------- Practica y dibujo libre ----------

function practicarEnEvaluacion(clave) {
  return new Promise((resolver) => {
    practica.velocidad = 1;
    marcarVelocidad();
    practica.alTerminar = (resultado) => resolver(resultado);
    empezarPractica(clave);
  });
}

function dibujoLibreEvaluacion() {
  return new Promise((resolver) => {
    pintarFondo();
    estado.anterior = null;
    empezarADibujar();

    let restanteMs = DIBUJO_LIBRE_S * 1000;

    const terminar = async () => {
      clearInterval(reloj);
      evaluacion.finDibujo = null;
      if (!evaluacion.cancelada) {
        await enviar("/evaluacion/obra", { imagen: lienzo.toDataURL("image/png") });
      }
      resolver();
    };

    const reloj = setInterval(() => {
      // El tiempo no corre mientras la cabeza esta fuera de posicion
      if (!estado.fueraDePosicion) restanteMs -= 250;
      const restante = Math.max(0, Math.ceil(restanteMs / 1000));
      $("evaluacion-detalle").textContent = `Quedan ${restante} s`;
      if (restanteMs <= 0) terminar();
    }, 250);

    evaluacion.finDibujo = terminar;
  });
}

// ---------- Resumen ----------

function mostrarResumen(r) {
  const fila = (nombre, valor, unidad = "") =>
    `<tr><td>${nombre}</td><td><b>${valor === "" || valor == null ? "—" : valor + unidad}</b></td></tr>`;

  return pantallaEvaluacion(`
    <h1>¡Evaluación completa!</h1>
    <p class="lema">Participante ${r.participante ?? ""} · datos guardados en la carpeta <b>datos/</b></p>
    <table class="tabla-resumen">
      ${fila("Detección de ambos ojos", r.tasa_deteccion_pct, "%")}
      ${fila("Fotogramas por segundo", r.fps_promedio)}
      ${fila("Procesamiento por fotograma", r.procesamiento_ms_promedio, " ms")}
      ${fila("Error de exactitud promedio", r.error_medio_px, " px")}
      ${fila("Error de exactitud (% pantalla)", r.error_medio_pct, "%")}
      ${fila("Dispersión de la mirada", r.dispersion_media_px, " px")}
      ${fila("Precisión en la práctica", r.precision_practica_pct, "%")}
      ${fila("Duración de la sesión", r.duracion_s, " s")}
    </table>
    <div class="fila-botones">
      <button class="boton principal" data-accion="nueva"><span>Terminar</span><kbd>Enter</kbd></button>
    </div>`);
}

// =====================================
// 6. INTERFAZ
// =====================================

function construirControles() {
  COLORES.forEach((color, i) => {
    const boton = document.createElement("button");
    boton.className = "color";
    boton.style.background = color.valor;
    boton.title = `${color.nombre} (${i + 1})`;
    boton.onclick = () => elegirColor(i);
    $("paleta").appendChild(boton);
  });

  FONDOS.forEach((fondo, i) => {
    const boton = document.createElement("button");
    boton.className = "fondo";
    boton.style.background = fondo.valor;
    boton.title = fondo.nombre;
    boton.onclick = () => cambiarFondo(i);
    $("fondos").appendChild(boton);
  });

  $("btn-pausa").onclick = alternarPincel;
  $("btn-arcoiris").onclick = alternarArcoiris;
  $("btn-limpiar").onclick = limpiar;
  $("btn-terminar").onclick = () => abrirRevision("libre");
  $("btn-practica").onclick = abrirEleccion;
  $("btn-recentrar").onclick = recentrar;
  $("btn-evaluacion").onclick = modoEvaluacion;
  $("btn-cancelar-evaluacion").onclick = cancelarEvaluacion;
  $("btn-cerrar-elegir").onclick = cerrarEleccion;
  $("btn-terminar-practica").onclick = terminarPractica;
  $("btn-cancelar-practica").onclick = cancelarPractica;
  $("btn-recalibrar").onclick = calibrar;
  $("btn-pantalla").onclick = pantallaCompleta;
  $("btn-calibrar").onclick = calibrar;
  $("btn-guardada").onclick = usarGuardada;
  $("btn-cancelar").onclick = cancelarCalibracion;
  $("grosor").oninput = (e) => (estado.grosor = Number(e.target.value));

  construirFiguras();

  // Que los botones no se queden con el foco (Espacio los activaria)
  document.querySelectorAll("button").forEach((b) =>
    b.addEventListener("mouseup", () => b.blur())
  );

  actualizarControles();
}

function actualizarControles() {
  document.querySelectorAll(".color").forEach((b, i) =>
    b.classList.toggle("activo", !estado.arcoiris && i === estado.color)
  );
  document.querySelectorAll(".fondo").forEach((b, i) =>
    b.classList.toggle("activo", i === estado.fondo)
  );
  $("btn-arcoiris").classList.toggle("activo", estado.arcoiris);
}

function cambiarPantalla(nombre) {
  estado.pantalla = nombre;
  document.body.className =
    nombre +
    (estado.fueraDePosicion ? " fuera-de-posicion" : "") +
    (evaluacion.activa ? " en-evaluacion" : "");
  estado.anterior = null;
}

let temporizadorAviso = null;

function avisar(texto, duracion = 2800) {
  const aviso = $("aviso");
  aviso.textContent = texto;
  aviso.classList.add("visible");
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => aviso.classList.remove("visible"), duracion);
}

// =====================================
// 7. TECLADO
// =====================================

document.addEventListener("keydown", (e) => {
  if (e.repeat && !["+", "-", "="].includes(e.key)) return;

  const tecla = e.key.toLowerCase();

  // Escribiendo en un formulario: no usar atajos
  if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;

  if (estado.pantalla === "evaluando") {
    // Enter = boton principal de la pantalla
    if (tecla === "enter") {
      const principal = document.querySelector("#evaluacion-contenido .principal[data-accion]");
      if (principal) { e.preventDefault(); principal.click(); }
    }
    return;
  }

  // Durante la evaluacion no se abren otras pantallas
  if (evaluacion.activa && ["t", "s", "p", "k", "c"].includes(tecla) && estado.pantalla === "dibujando") return;

  if (estado.pantalla === "inicio") {
    if (tecla === "e") modoEvaluacion();
    if (tecla === "enter") calibrar();
    if (tecla === "d" && !$("btn-guardada").hidden) usarGuardada();
    return;
  }

  if (estado.pantalla === "calibrando") {
    if (tecla === "escape") evaluacion.activa ? cancelarEvaluacion() : cancelarCalibracion();
    return;
  }

  if (estado.pantalla === "eligiendo") {
    const clave = Object.keys(FIGURAS).find((k) => FIGURAS[k].tecla === tecla);
    if (clave) empezarPractica(clave);
    if (tecla === "escape") cerrarEleccion();
    return;
  }

  if (estado.pantalla === "recentrando") return;

  if (estado.pantalla === "practicando") {
    if (evaluacion.activa) {
      if (tecla === "escape") cancelarEvaluacion();
      return;
    }
    if (tecla === "escape") cancelarPractica();
    if (tecla === "t") terminarPractica();
    return;
  }

  if (estado.pantalla === "revisando") {
    e.preventDefault();
    teclaRevision(tecla);
    return;
  }

  // Dibujando
  if (tecla === " ") { e.preventDefault(); alternarPincel(); }
  else if (tecla >= "1" && tecla <= "8") elegirColor(Number(tecla) - 1);
  else if (tecla === "a") alternarArcoiris();
  else if (tecla === "+" || tecla === "=") cambiarGrosor(2);
  else if (tecla === "-") cambiarGrosor(-2);
  else if (tecla === "c") limpiar();
  else if (tecla === "t" || tecla === "s") { e.preventDefault(); abrirRevision("libre"); }
  else if (tecla === "p") abrirEleccion();
  else if (tecla === "r") recentrar();
  else if (tecla === "k") calibrar();
  else if (tecla === "f") pantallaCompleta();
  else if (tecla === "n") cambiarFondo();
});

// =====================================
// 8. UTILIDADES E INICIO
// =====================================

function esperar(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function enviar(url, datos) {
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });
    return await r.json();
  } catch {
    return { ok: false, error: "Sin conexión con Python" };
  }
}

async function iniciar() {
  construirControles();
  ajustarTamano();
  window.addEventListener("resize", ajustarTamano);

  try {
    const r = await fetch("/estado");
    const info = await r.json();
    $("btn-guardada").hidden = !info.calibracion_guardada;
    evaluacion.preguntas = info.encuesta || [];
  } catch {}

  conectarEventos();
  requestAnimationFrame(cuadro);
}

iniciar();
