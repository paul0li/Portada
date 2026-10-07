// Los dos botones del resultado que mandan el PNG fuera de Portada por la hoja
// de compartir del sistema: «Guardar en Fotos» (WEB-47) y «Mejorar en ChatGPT»
// (WEB-49).
//
// Esa hoja es `navigator.share`, y Safari solo la ofrece en un contexto seguro
// (HTTPS o localhost): con Portada por HTTP en la LAN no existe. Ahí cada
// botón dice cómo hacerlo a mano en vez de no hacer nada.
(() => {
  const guardar = document.getElementById("guardar-fotos");
  const mejorar = document.getElementById("mejorar-chatgpt");
  if (!guardar && !mejorar) return;
  const src = (guardar || mejorar).dataset.src;

  // Se baja ANTES del toque: Safari solo deja abrir la hoja de compartir como
  // respuesta directa a un toque, y esperar la descarga dentro del toque lo
  // gasta. Con el archivo ya en memoria, `share` se llama al instante.
  const nombre =
    "portada-" +
    ((guardar && guardar.dataset.nombre) || "miniatura")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") +
    ".png";
  let archivo = null;
  if (navigator.share && navigator.canShare) {
    fetch(src, { credentials: "same-origin" })
      .then((r) => r.blob())
      .then((blob) => {
        archivo = new File([blob], nombre, { type: "image/png" });
      })
      .catch(() => {});
  }
  const puedeCompartir = () => archivo && navigator.canShare({ files: [archivo] });

  // Devuelve true si se abrió la hoja (o se cerró sin elegir nada).
  const compartir = async (datos) => {
    if (!puedeCompartir()) return false;
    try {
      await navigator.share({ files: [archivo], ...datos });
      return true;
    } catch (error) {
      return error.name === "AbortError"; // cerró la hoja: no es un error
    }
  };

  // --- Guardar en Fotos ----------------------------------------------------

  if (guardar) {
    const pista = document.getElementById("guardar-pista");
    const imagen = document.getElementById("miniatura");
    guardar.hidden = false;
    guardar.addEventListener("click", async () => {
      if (await compartir({})) return;
      pista.hidden = false;
      if (imagen) {
        imagen.classList.add("resaltada");
        imagen.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  // --- Mejorar en ChatGPT --------------------------------------------------
  //
  // No hay forma de abrir ChatGPT con una imagen ya adjunta: el parámetro `q`
  // de chatgpt.com solo lleva texto, y además lo ENVÍA al instante, sin la
  // imagen. Así que la imagen va por la hoja de compartir con la instrucción, y
  // la instrucción queda también copiada, por si la app que la recibe solo toma
  // la imagen.

  if (mejorar) {
    const tarjeta = document.getElementById("mejorar");
    const subtitulo = document.getElementById("subtitulo-chatgpt");
    const pista = document.getElementById("mejorar-pista");
    tarjeta.hidden = false;

    const instruccion = () => {
      const texto = subtitulo.value.trim();
      const base = mejorar.dataset.instruccion;
      return texto ? `${base} Agrega un subtítulo que diga: «${texto}».` : base;
    };

    // `execCommand` como red: `navigator.clipboard` también pide contexto seguro.
    const copiar = (texto) => {
      const aMano = () => {
        const campo = document.createElement("textarea");
        campo.value = texto;
        campo.setAttribute("readonly", "");
        campo.style.position = "fixed";
        campo.style.opacity = "0";
        document.body.appendChild(campo);
        campo.select();
        campo.setSelectionRange(0, texto.length);
        try {
          document.execCommand("copy");
        } catch (_) {}
        campo.remove();
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).catch(aMano);
      } else {
        aMano();
      }
    };

    const avisa = (texto, enlace) => {
      pista.textContent = texto;
      if (enlace) {
        const a = document.createElement("a");
        a.href = "https://chatgpt.com/";
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = " Abrir ChatGPT ›";
        pista.appendChild(a);
      }
      pista.hidden = false;
    };

    mejorar.addEventListener("click", async () => {
      const texto = instruccion();
      // Las dos cosas dentro del mismo toque, sin esperar entre ellas: Safari
      // solo deja abrir la hoja como respuesta directa a un toque.
      copiar(texto);
      if (puedeCompartir()) {
        avisa("Elige ChatGPT. Si la instrucción no aparece, pégala: ya está copiada.");
        await compartir({ text: texto });
        return;
      }
      avisa("Instrucción copiada. Descarga el PNG, adjúntalo en ChatGPT y pega la instrucción.", true);
    });
  }
})();
