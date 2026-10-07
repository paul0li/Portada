// El lienzo: el preview de cada paso, con las figuras que se arrastran y se
// escalan con el dedo (WEB-43, template v11).
//
// Este archivo APILA; no compone. No sabe dónde va una figura, ni cómo se
// escala, ni hasta dónde puede llegar: todo eso viene en `lienzo.json`, que
// sale del mismo armado que el PNG que se descarga (COMPOSITION-42). Lo único
// que hace por su cuenta es seguir al dedo mientras arrastra — sin pedirle nada
// al servidor — y, al soltar, pedir el ajuste nuevo y quedarse con lo que
// vuelve, ya acotado. Por eso lo que se ve al soltar es lo que se descarga.
//
// El borrador sigue viviendo en la URL: cada soltar es una entrada del
// historial, así que «atrás» deshace un arrastre igual que deshacía un toque.
//
// Sin JS, o si el lienzo no carga, queda el `<img id="preview">` de siempre y
// los pads con flechas: la misma miniatura, con otro mando.
(() => {
  const host = document.querySelector("[data-lienzo]");
  const previa = document.getElementById("preview");
  if (!host || !previa) return;

  const formulario = document.querySelector('form[action="/nueva"]');
  const campo = (id) => document.getElementById(id);
  const titulo = {
    texto: campo("titulo"),
    ancho: campo("titulo-ancho"),
    tamano: campo("titulo-tamano"),
    alto: campo("titulo-alto"),
    apilado: campo("titulo-apilado"),
    x: campo("titulo-x"),
    y: campo("titulo-y"),
  };

  // Lo que no es un ajuste viene de `data-lienzo` y no cambia en esta página:
  // las fotos elegidas y el fondo por defecto. Los ajustes sí cambian.
  const fijo = new URLSearchParams(host.dataset.lienzo.split("?")[1] || "");
  let ajustes = fijo.getAll("ajuste");
  fijo.delete("ajuste");

  let estado = null; // el último lienzo.json
  let elegida = null; // el nombre de la capa seleccionada
  let pedido = 0; // para quedarse solo con la respuesta más nueva
  const capas = new Map(); // nombre -> <img>

  // --- pedir -------------------------------------------------------------

  const camposDelTitulo = () => {
    if (!titulo.texto) return [];
    return [
      ["title", titulo.texto.value],
      ["titulo_ancho", titulo.ancho ? titulo.ancho.value : 0],
      ["titulo_tamano", titulo.tamano ? titulo.tamano.value : 0],
      ["titulo_alto", titulo.alto ? titulo.alto.value : 0],
      ["titulo_apilado", titulo.apilado && titulo.apilado.checked ? 1 : 0],
      ["titulo_x", titulo.x ? titulo.x.value : 0],
      ["titulo_y", titulo.y ? titulo.y.value : 0],
    ];
  };

  const consulta = (lista) => {
    const params = new URLSearchParams(fijo);
    for (const a of lista) params.append("ajuste", a);
    for (const [k, v] of camposDelTitulo()) params.set(k, v);
    return params;
  };

  const pedir = async (lista, { historial = false } = {}) => {
    const mio = ++pedido;
    let respuesta;
    try {
      respuesta = await fetch("/nueva/lienzo.json?" + consulta(lista), {
        credentials: "same-origin",
      });
    } catch {
      return false;
    }
    if (mio !== pedido) return true; // llegó otra más nueva: esta ya no manda
    if (!respuesta.ok || respuesta.status === 204) return false;
    estado = await respuesta.json();
    ajustes = estado.ajustes;
    if (titulo.x) titulo.x.value = estado.titulo.x;
    if (titulo.y) titulo.y.value = estado.titulo.y;
    sincronizar(historial);
    pintar();
    return true;
  };

  // El borrador a la barra de direcciones, a los enlaces del paso y al
  // formulario del título. Lo hecho en el lienzo no se puede perder al tocar
  // «Siguiente»: los enlaces los dibujó el servidor ANTES de este arrastre.
  const sincronizar = (historial) => {
    if (historial && new URLSearchParams(location.search).has("paso")) {
      const aqui = new URLSearchParams(location.search);
      aqui.delete("ajuste");
      for (const a of ajustes) aqui.append("ajuste", a);
      history.pushState(null, "", "?" + aqui);
    }
    if (formulario) {
      for (const viejo of formulario.querySelectorAll('input[name="ajuste"]')) viejo.remove();
      for (const a of ajustes) {
        const nuevo = document.createElement("input");
        nuevo.type = "hidden";
        nuevo.name = "ajuste";
        nuevo.value = a;
        formulario.appendChild(nuevo);
      }
    }
  };

  document.addEventListener("click", (evento) => {
    const enlace = evento.target.closest && evento.target.closest('a[href^="/nueva?"]');
    if (!enlace || !estado) return;
    const url = new URL(enlace.href, location.origin);
    url.searchParams.delete("ajuste");
    for (const a of ajustes) url.searchParams.append("ajuste", a);
    enlace.href = url.pathname + url.search;
  });

  window.addEventListener("popstate", () => {
    ajustes = new URLSearchParams(location.search).getAll("ajuste");
    pedir(ajustes);
  });

  // --- pintar ------------------------------------------------------------

  const escenario = document.createElement("div");
  escenario.className = "lienzo";
  escenario.setAttribute("role", "application");
  escenario.setAttribute("aria-label", "Miniatura: toca una figura para moverla");
  escenario.tabIndex = 0;
  const caja = document.createElement("div");
  caja.className = "seleccion";
  // Las asas. La esquina escala (una figura, o el título entero); los bordes
  // solo los tiene el título: el derecho es su ancho y el de arriba su alto.
  const nuevaAsa = (tipo) => {
    const el = document.createElement("span");
    el.className = "asa asa-" + tipo;
    el.dataset.asa = tipo;
    el.setAttribute("aria-hidden", "true");
    caja.appendChild(el);
    return el;
  };
  const asa = nuevaAsa("esquina");
  const asaAncho = nuevaAsa("ancho");
  const asaAlto = nuevaAsa("alto");
  // Las capas se insertan DELANTE de la caja: tiene que estar dentro desde el
  // principio, o el primer `insertBefore` no tiene dónde.
  escenario.appendChild(caja);
  const barra = document.createElement("div");
  barra.className = "herramientas";

  const pct = (valor, total) => (valor / total) * 100 + "%";

  const colocar = (el, x, y, ancho, alto) => {
    const [W, H] = estado.lienzo;
    el.style.left = pct(x, W);
    el.style.top = pct(y, H);
    el.style.width = pct(ancho, W);
    el.style.height = pct(alto, H);
  };

  const pintar = () => {
    const vistas = new Set();
    for (const capa of estado.capas) {
      vistas.add(capa.nombre);
      let img = capas.get(capa.nombre);
      if (!img) {
        img = document.createElement("img");
        img.className = "capa";
        img.alt = "";
        img.draggable = false;
        img.decoding = "async";
        capas.set(capa.nombre, img);
      }
      // El orden del DOM es el orden de dibujo: appendChild mueve, no copia.
      escenario.insertBefore(img, caja);
      colocar(img, capa.x, capa.y, capa.ancho, capa.alto);
      if (img.dataset.src !== capa.src) {
        img.dataset.src = capa.src;
        // Se precarga antes de cambiarla: sin esto, cada soltar parpadea.
        const nueva = new Image();
        nueva.src = capa.src;
        const poner = () => {
          if (img.dataset.src !== capa.src) return;
          img.src = capa.src;
          img.style.transform = "";
          delete alfas[capa.src];
        };
        nueva.decode().then(poner, poner);
      }
    }
    for (const [nombre, img] of capas) {
      if (!vistas.has(nombre)) {
        img.remove();
        capas.delete(nombre);
      }
    }
    if (elegida && !capaDe(elegida)) elegida = null;
    pintarSeleccion();
  };

  const capaDe = (nombre) => estado && estado.capas.find((c) => c.nombre === nombre);

  const pintarSeleccion = (caja_ = null) => {
    const capa = elegida && capaDe(elegida);
    if (!capa) {
      caja.hidden = true;
      barra.hidden = true;
      return;
    }
    // El título se enmarca por su BLOQUE, no por su tinta: es lo que las asas
    // estiran, y lo que deja ver cuánto sitio queda para repartir palabras.
    const b = caja_ || capa.bloque || capa;
    caja.hidden = false;
    colocar(caja, b.x, b.y, b.ancho, b.alto);
    const esTitulo = capa.nombre === "titulo";
    asa.hidden = !((capa.mueve && capa.ancla) || esTitulo);
    asaAncho.hidden = asaAlto.hidden = !esTitulo;
    if (!caja_) pintarBarra(capa);
  };

  // --- la barra de la figura elegida ---------------------------------------

  // Los íconos de siempre, en SVG en línea y en el color del texto. Cada botón
  // dice además con palabras qué hace (`aria-label` y `title`): un ícono solo
  // se adivina, y «Atrás» y «Adelante» se parecen mucho entre sí.
  const trazo = (cuerpo) =>
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    cuerpo +
    "</svg>";
  const ICONOS = {
    // Dos triángulos a cada lado de un eje: el de la izquierda lleno, su
    // reflejo vacío. Vertical para el espejo, horizontal para boca abajo.
    espejo: trazo(
      '<path d="M12 3v18" stroke-dasharray="2 2.5"/>' +
        '<path d="M9 6v13H3z" fill="currentColor"/><path d="M15 6v13h6z"/>',
    ),
    bocaAbajo: trazo(
      '<path d="M3 12h18" stroke-dasharray="2 2.5"/>' +
        '<path d="M6 9h13V3z" fill="currentColor"/><path d="M6 15h13v6z"/>',
    ),
    // Dos cuadrados solapados; el que va a moverse es el lleno.
    atras: trazo(
      '<rect x="9" y="3" width="12" height="12" rx="2" fill="currentColor"/>' +
        '<rect x="3" y="9" width="12" height="12" rx="2" style="fill: var(--tarjeta)"/>',
    ),
    adelante: trazo(
      '<rect x="9" y="3" width="12" height="12" rx="2"/>' +
        '<rect x="3" y="9" width="12" height="12" rx="2" fill="currentColor"/>',
    ),
    restablecer: trazo('<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v5h5"/>'),
    // Una persona con un destello: «sacarle el fondo» sin escribirlo.
    quitarFondo: trazo(
      '<circle cx="10" cy="8" r="3.5"/><path d="M3.5 21a6.5 6.5 0 0 1 13 0"/>' +
        '<path d="M19 2.5v5M16.5 5h5"/>',
    ),
    espera: trazo('<path d="M12 3a9 9 0 1 0 9 9"><animateTransform attributeName="transform" ' +
      'type="rotate" from="0 12 12" to="360 12 12" dur="0.9s" repeatCount="indefinite"/></path>'),
  };

  const boton = (icono, nombre, accion, { puesto = null, apagado = false } = {}) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "opcion icono";
    b.innerHTML = ICONOS[icono];
    b.setAttribute("aria-label", nombre);
    b.title = nombre;
    if (puesto !== null) b.setAttribute("aria-pressed", puesto ? "true" : "false");
    b.disabled = apagado;
    b.addEventListener("click", () => accion(b));
    return b;
  };

  const pintarBarra = (capa) => {
    barra.hidden = false;
    barra.replaceChildren();
    const rotulo = document.createElement("p");
    rotulo.className = "rotulo";
    const fila = document.createElement("div");
    fila.className = "fila";

    if (capa.nombre === "titulo") {
      rotulo.textContent = `Título · ${capa.tamano} px` + (capa.mandos.tamano ? "" : " (auto)");
      // «Restablecer» repone todo lo del lienzo: el sitio y los tres mandos.
      const m = capa.mandos;
      const tocado = estado.titulo.x || estado.titulo.y || m.ancho || m.tamano || m.alto;
      const reponerTitulo = () => {
        for (const el of Object.values(deslizadores)) if (el) el.value = 0;
        moverTitulo(0, 0);
      };
      fila.append(boton("restablecer", "Restablecer", reponerTitulo, { apagado: !tocado }));
    } else if (capa.ancla) {
      const a = capa.ajuste;
      rotulo.textContent = `${capa.etiqueta} · ${a.escala}%`;
      // Quitar el fondo solo donde hace algo (WEB-46): si el rol no admite
      // recorte o el proveedor no quita fondos, el botón no está.
      if (capa.recorte && capa.recorte.admite) {
        const puesto = capa.recorte.puesto;
        fila.append(
          boton(
            "quitarFondo",
            puesto ? "Devolverle el fondo" : "Quitarle el fondo",
            (b) => recortar(capa, b),
            { puesto },
          ),
        );
      }
      if (capa.voltea) {
        fila.append(
          boton(
            "espejo",
            "Espejo horizontal",
            () => cambiar(capa, { voltear_x: !a.voltear_x }, "scaleX(-1)"),
            { puesto: a.voltear_x },
          ),
          boton(
            "bocaAbajo",
            "Espejo vertical",
            () => cambiar(capa, { voltear_y: !a.voltear_y }, "scaleY(-1)"),
            { puesto: a.voltear_y },
          ),
        );
      }
      if (capa.mueve) {
        fila.append(
          boton("atras", "Enviar atrás", () => cambiar(capa, { capa: a.capa - 1 }), {
            apagado: a.capa <= capa.capas[0],
          }),
          boton("adelante", "Traer adelante", () => cambiar(capa, { capa: a.capa + 1 }), {
            apagado: a.capa >= capa.capas[1],
          }),
        );
      }
      const tocada =
        a.dx || a.dy || a.capa || a.voltear_x || a.voltear_y || a.escala !== 100;
      fila.append(boton("restablecer", "Restablecer", () => reponer(capa), { apagado: !tocada }));
    } else if (capa.nombre === "fondo") {
      const a = capa.ajuste || { voltear_x: false, voltear_y: false };
      rotulo.textContent = "Fondo";
      fila.append(
        boton("espejo", "Espejo horizontal", () => voltearFondo({ ...a, voltear_x: !a.voltear_x }), {
          puesto: a.voltear_x,
        }),
        boton("bocaAbajo", "Espejo vertical", () => voltearFondo({ ...a, voltear_y: !a.voltear_y }), {
          puesto: a.voltear_y,
        }),
      );
    }
    barra.append(rotulo, fila);
  };

  // Quitar o devolver el fondo: los mismos endpoints que el modal de la foto.
  // Recortar tarda ~0,5 s (el primero del proceso, ~3 s), así que el botón
  // dice que está trabajando en vez de parecer que no hizo nada.
  const recortar = async (capa, b) => {
    const ruta = `/libreria/fotos/${capa.foto}/fondo` + (capa.recorte.puesto ? "/deshacer" : "");
    b.disabled = true;
    b.setAttribute("aria-busy", "true");
    b.innerHTML = ICONOS.espera;
    const datos = new FormData();
    datos.append("volver", location.pathname + location.search);
    try {
      // `manual`: el endpoint contesta con una redirección para el formulario
      // del modal; aquí no hace falta seguirla, solo saber que salió bien.
      await fetch(ruta, {
        method: "POST",
        body: datos,
        credentials: "same-origin",
        redirect: "manual",
      });
    } catch {
      // Si falló, el lienzo que vuelve lo dice: el botón sigue como estaba.
    }
    pedir(ajustes);
  };

  // --- pedir un ajuste -----------------------------------------------------

  // El formato de `_texto_del_ajuste` en el router. Se escribe solo para PEDIR:
  // lo que se guarda es lo que vuelve, ya acotado.
  const texto = (nombre, a) =>
    `${nombre}:${a.dx},${a.dy},${a.capa},${a.voltear_x ? 1 : 0},${a.voltear_y ? 1 : 0},${a.escala}`;

  const con = (nombre, nuevo) => [
    ...ajustes.filter((a) => !a.startsWith(nombre + ":")),
    ...(nuevo ? [texto(nombre, nuevo)] : []),
  ];

  const cambiar = (capa, cambios, adelanto = "") => {
    // El volteo se adelanta con CSS mientras llega la imagen volteada de verdad.
    if (adelanto) {
      const img = capas.get(capa.nombre);
      if (img) img.style.transform = img.style.transform ? "" : adelanto;
    }
    return pedir(con(capa.nombre, { ...capa.ajuste, ...cambios }), { historial: true });
  };

  const reponer = (capa) => pedir(con(capa.nombre, null), { historial: true });

  const voltearFondo = (a) =>
    pedir(con("fondo.0", { dx: 0, dy: 0, capa: 0, escala: 100, ...a }), { historial: true });

  const moverTitulo = (x, y) => {
    if (!titulo.x || !titulo.y) return;
    titulo.x.value = x;
    titulo.y.value = y;
    pedir(ajustes);
  };

  // --- tocar, arrastrar, escalar ------------------------------------------

  const punto = (evento) => {
    const r = escenario.getBoundingClientRect();
    const [W, H] = estado.lienzo;
    return [((evento.clientX - r.left) / r.width) * W, ((evento.clientY - r.top) / r.height) * H];
  };

  // El alfa de cada capa, para tocar la FIGURA y no su rectángulo: dos bustos
  // se solapan de hombros, y el rectángulo del de delante taparía la cara del
  // de atrás.
  const alfas = {};
  const opaco = (capa, x, y) => {
    const img = capas.get(capa.nombre);
    if (!img || !img.complete || !img.naturalWidth) return true;
    let datos = alfas[capa.src];
    if (!datos) {
      const c = document.createElement("canvas");
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      try {
        datos = alfas[capa.src] = ctx.getImageData(0, 0, c.width, c.height);
      } catch {
        return true;
      }
    }
    const u = Math.floor(((x - capa.x) / capa.ancho) * datos.width);
    const v = Math.floor(((y - capa.y) / capa.alto) * datos.height);
    if (u < 0 || v < 0 || u >= datos.width || v >= datos.height) return false;
    return datos.data[(v * datos.width + u) * 4 + 3] > 24;
  };

  const dentro = (capa, x, y) =>
    x >= capa.x && y >= capa.y && x <= capa.x + capa.ancho && y <= capa.y + capa.alto;

  // De arriba abajo, solo lo que se puede tocar: el logo y el marco son marca
  // y no se agarran, aunque estén encima de todo.
  const tocada = (x, y) => {
    for (const capa of [...estado.capas].reverse()) {
      if (capa.nombre === "titulo" && dentro(capa, x, y)) return capa;
      if (capa.ancla && dentro(capa, x, y) && opaco(capa, x, y)) return capa;
    }
    const fondo = estado.capas[0];
    return fondo && fondo.voltea ? fondo : null;
  };

  let gesto = null;
  const dedos = new Map();

  const cajaEn = (capa, dx, dy, factor = 1) => {
    const ancho = capa.ancho * factor;
    const alto = capa.alto * factor;
    if (!capa.ancla) return { x: capa.x + dx, y: capa.y + dy, ancho, alto };
    const ax = capa.ancla[0] + dx;
    const ay = capa.ancla[1] + dy;
    const y = capa.apoyo === "bottom-center" ? ay - alto : ay - alto / 2;
    return { x: ax - ancho / 2, y, ancho, alto };
  };

  // Lo mismo que acota el servidor, para que el dedo no se lleve la figura a
  // un sitio del que después rebota: su centro no sale del lienzo.
  const acotarCentro = (capa, dx, dy, factor) => {
    const [W, H] = estado.lienzo;
    const b = cajaEn(capa, dx, dy, factor);
    const cx = b.x + b.ancho / 2;
    const cy = b.y + b.alto / 2;
    return [dx - Math.min(0, cx) - Math.max(0, cx - W), dy - Math.min(0, cy) - Math.max(0, cy - H)];
  };

  const acotarTitulo = (dx, dy) => {
    const l = estado.limites.titulo;
    const x = Math.max(-l.izquierda, Math.min(l.derecha, estado.titulo.x + dx));
    const y = Math.max(-l.arriba, Math.min(l.abajo, estado.titulo.y + dy));
    return [x - estado.titulo.x, y - estado.titulo.y];
  };

  const factorPermitido = (capa, factor) => {
    const [min, max] = estado.limites.escala;
    const escala = Math.max(min, Math.min(max, Math.round(capa.ajuste.escala * factor)));
    return escala / capa.ajuste.escala;
  };

  // --- las asas del título -------------------------------------------------
  //
  // Mueven los TRES MANDOS de siempre, los de los sliders del paso, y con sus
  // mismos pasos: un valor fuera de paso, el slider lo corregiría por su cuenta.
  // El texto no se reparte aquí: se reparte en el servidor, que se pide
  // mientras se arrastra -- de a uno, quedándose con el último.

  const aPaso = (valor, [min, max, paso]) =>
    Math.max(min, Math.min(max, min + Math.round((valor - min) / paso) * paso));

  const deslizadores = { ancho: titulo.ancho, tamano: titulo.tamano, alto: titulo.alto };

  let enVuelo = false;
  let otraVez = false;
  const refrescarTitulo = async () => {
    if (enVuelo) {
      otraVez = true;
      return;
    }
    enVuelo = true;
    await pedir(ajustes);
    enVuelo = false;
    if (otraVez) {
      otraVez = false;
      refrescarTitulo();
    }
  };

  const ponerMandos = (mandos) => {
    let cambio = false;
    for (const [nombre, valor] of Object.entries(mandos)) {
      const el = deslizadores[nombre];
      if (el && Number(el.value) !== valor) {
        el.value = valor;
        cambio = true;
      }
    }
    if (cambio) refrescarTitulo();
  };

  // Con el tamaño en automático, estirar el bloque no repartiría las palabras:
  // el auto-ajuste se comería el sitio subiendo la letra (la trampa de v10).
  // Así que la primera asa que se toca fija el tamaño en el que tenía.
  //
  // Ojo con el cero: en el mando del tamaño, 0 no es «104 px», es AUTOMÁTICO.
  // Un 100 redondeado al paso de 8 caía en 0 y el tamaño no quedaba fijado. Si
  // la letra no está justo en la del template, se fija en el paso más cercano
  // que no sea cero; si está justo ahí, el automático ya no puede crecer más
  // y ensanchar reparte igual.
  const tamanoFijado = (capa) => {
    if (capa.mandos.tamano) return capa.mandos.tamano;
    const diferencia = capa.tamano - capa.tamano_base;
    const fijado = aPaso(diferencia, capa.rangos.tamano);
    if (fijado || !diferencia) return fijado;
    return Math.sign(diferencia) * capa.rangos.tamano[2];
  };

  const gestoDelTitulo = (x, y) => {
    const { capa, tipo, desde } = gesto;
    const b0 = capa.bloque;
    const m0 = capa.mandos;
    const abajo = b0.y + b0.alto;
    let m = { ...m0, tamano: gesto.tamano };
    if (tipo === "ancho") {
      m.ancho = aPaso(m0.ancho + (x - desde[0]), capa.rangos.ancho);
    } else if (tipo === "alto") {
      m.alto = aPaso(m0.alto - (y - desde[1]), capa.rangos.alto);
    } else {
      // La esquina agranda todo en proporción, desde la esquina de abajo a la
      // izquierda: la letra, el ancho y el alto. Así el corte de líneas se
      // mantiene y el título crece entero, como en Canva.
      const r = Math.hypot(x - b0.x, y - abajo) / gesto.radio;
      m = {
        tamano: aPaso(capa.tamano * r - capa.tamano_base, capa.rangos.tamano),
        ancho: aPaso(m0.ancho + b0.ancho * (r - 1), capa.rangos.ancho),
        alto: aPaso(m0.alto + b0.alto * (r - 1), capa.rangos.alto),
      };
    }
    const ancho = b0.ancho + (m.ancho - m0.ancho);
    const alto = b0.alto + (m.alto - m0.alto);
    pintarSeleccion({ x: b0.x, y: abajo - alto, ancho, alto });
    ponerMandos(m);
  };

  const seguir = () => {
    const { capa, dx, dy, factor } = gesto;
    const b = cajaEn(capa, dx, dy, factor);
    colocar(capas.get(capa.nombre), b.x, b.y, b.ancho, b.alto);
    pintarSeleccion(b);
  };

  escenario.addEventListener("pointerdown", (evento) => {
    if (!estado) return;
    escenario.setPointerCapture(evento.pointerId);
    const [x, y] = punto(evento);
    dedos.set(evento.pointerId, [x, y]);

    // El segundo dedo sobre una figura elegida: pellizcar para escalar.
    if (dedos.size === 2 && gesto && gesto.capa.ancla && gesto.capa.mueve) {
      const [p, q] = [...dedos.values()];
      gesto = { ...gesto, tipo: "pellizco", distancia: Math.hypot(p[0] - q[0], p[1] - q[1]) };
      return;
    }
    if (dedos.size > 1) return;

    const deAsa = evento.target.dataset && evento.target.dataset.asa;
    const capa = deAsa ? capaDe(elegida) : tocada(x, y);
    elegida = capa ? capa.nombre : null;
    pintarSeleccion();
    if (!capa || !(capa.mueve || capa.nombre === "titulo")) return;
    evento.preventDefault();

    if (deAsa && capa.nombre === "titulo") {
      const b = capa.bloque;
      gesto = {
        capa,
        tipo: deAsa,
        desde: [x, y],
        tamano: tamanoFijado(capa),
        radio: Math.max(1, Math.hypot(x - b.x, y - (b.y + b.alto))),
        titulo: true,
      };
      return;
    }
    const tipo = deAsa ? "escala" : "arrastre";
    gesto = { capa, tipo, desde: [x, y], dx: 0, dy: 0, factor: 1, movio: false };
    if (tipo === "escala") {
      gesto.radio = Math.max(1, Math.hypot(x - capa.ancla[0], y - capa.ancla[1]));
    }
  });

  escenario.addEventListener("pointermove", (evento) => {
    if (!gesto || !dedos.has(evento.pointerId)) return;
    const [x, y] = punto(evento);
    dedos.set(evento.pointerId, [x, y]);
    if (gesto.titulo) {
      gestoDelTitulo(x, y);
      return;
    }
    const { capa } = gesto;

    if (gesto.tipo === "pellizco" && dedos.size === 2) {
      const [p, q] = [...dedos.values()];
      const d = Math.hypot(p[0] - q[0], p[1] - q[1]);
      gesto.factor = factorPermitido(capa, d / gesto.distancia);
    } else if (gesto.tipo === "escala") {
      const r = Math.hypot(x - capa.ancla[0], y - capa.ancla[1]);
      gesto.factor = factorPermitido(capa, r / gesto.radio);
    } else if (gesto.tipo === "arrastre") {
      const crudo = [x - gesto.desde[0], y - gesto.desde[1]];
      [gesto.dx, gesto.dy] =
        capa.nombre === "titulo"
          ? acotarTitulo(...crudo)
          : acotarCentro(capa, crudo[0], crudo[1], gesto.factor);
    }
    gesto.movio = gesto.movio || gesto.factor !== 1 || Math.abs(gesto.dx) + Math.abs(gesto.dy) > 2;
    seguir();
  });

  const soltar = (evento) => {
    dedos.delete(evento.pointerId);
    if (!gesto || dedos.size > 0) return;
    const { capa, dx, dy, factor, movio, titulo: deTitulo } = gesto;
    gesto = null;
    // Las asas del título ya pidieron lo suyo mientras se arrastraba; al soltar
    // solo queda volver a enmarcar el bloque como lo describe el servidor.
    if (deTitulo) {
      refrescarTitulo();
      return;
    }
    if (!movio) return;
    if (capa.nombre === "titulo") {
      moverTitulo(estado.titulo.x + Math.round(dx), estado.titulo.y + Math.round(dy));
      return;
    }
    const a = capa.ajuste;
    pedir(
      con(capa.nombre, {
        ...a,
        dx: a.dx + Math.round(dx),
        dy: a.dy + Math.round(dy),
        escala: Math.round(a.escala * factor),
      }),
      { historial: true },
    );
  };
  escenario.addEventListener("pointerup", soltar);
  escenario.addEventListener("pointercancel", soltar);

  // Con teclado: flechas mueven 4 px, con mayúsculas 20 (el paso de los pads).
  escenario.addEventListener("keydown", (evento) => {
    const capa = elegida && capaDe(elegida);
    const flechas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (!capa || !flechas[evento.key]) return;
    evento.preventDefault();
    const salto = evento.shiftKey ? 20 : 4;
    const [mx, my] = flechas[evento.key];
    if (capa.nombre === "titulo") {
      moverTitulo(estado.titulo.x + mx * salto, estado.titulo.y + my * salto);
    } else if (capa.mueve) {
      cambiar(capa, { dx: capa.ajuste.dx + mx * salto, dy: capa.ajuste.dy + my * salto });
    }
  });

  // --- el título se repinta mientras se teclea ------------------------------

  // Es lo que hacía la isla de JS de este paso, y cuesta lo mismo: el título es
  // overlay, así que solo se vuelve a pedir su capa. Si el lienzo no cargó, se
  // repinta el `<img>` de siempre.
  let pendiente;
  const alTeclear = () => {
    clearTimeout(pendiente);
    pendiente = setTimeout(() => {
      if (estado) {
        pedir(ajustes);
        return;
      }
      const base = previa.src.split("&titulo_ancho=")[0];
      const resto = camposDelTitulo().filter(([k]) => k !== "title");
      previa.src =
        base +
        resto.map(([k, v]) => `&${k}=${encodeURIComponent(v)}`).join("") +
        "&title=" +
        encodeURIComponent(titulo.texto.value);
      previa.style.visibility = "visible";
    }, 200);
  };
  for (const control of [titulo.texto, titulo.ancho, titulo.tamano, titulo.alto, titulo.apilado]) {
    if (control) control.addEventListener("input", alTeclear);
  }

  // --- arrancar -------------------------------------------------------------

  pedir(ajustes).then((ok) => {
    if (!ok) return; // se queda el <img> de siempre: el lienzo es mejora
    previa.replaceWith(escenario);
    host.appendChild(barra);
    document.documentElement.classList.add("con-lienzo");
    pintar();
  });
})();
