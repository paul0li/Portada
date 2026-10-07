// «Guardar en Fotos» (WEB-47).
//
// En un iPhone, un enlace de descarga manda el PNG a Archivos. Lo que lo manda
// a Fotos es la hoja de compartir del sistema, que trae «Guardar imagen». Esa
// hoja es `navigator.share`, y Safari solo la ofrece en un contexto seguro
// (HTTPS o localhost): con Portada por HTTP en la LAN no existe. Ahí el botón
// dice cómo hacerlo a mano —mantener presionada la imagen— en vez de no hacer
// nada.
(() => {
  const boton = document.getElementById("guardar-fotos");
  const pista = document.getElementById("guardar-pista");
  const imagen = document.getElementById("miniatura");
  if (!boton) return;
  boton.hidden = false;

  // Se baja ANTES del toque: Safari solo deja abrir la hoja de compartir como
  // respuesta directa a un toque, y esperar la descarga dentro del toque lo
  // gasta. Con el archivo ya en memoria, `share` se llama al instante.
  const nombre =
    "portada-" +
    (boton.dataset.nombre || "miniatura")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") +
    ".png";
  let archivo = null;
  if (navigator.share && navigator.canShare) {
    fetch(boton.dataset.src, { credentials: "same-origin" })
      .then((r) => r.blob())
      .then((blob) => {
        archivo = new File([blob], nombre, { type: "image/png" });
      })
      .catch(() => {});
  }

  const aMano = () => {
    pista.hidden = false;
    if (imagen) {
      imagen.classList.add("resaltada");
      imagen.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  boton.addEventListener("click", async () => {
    if (archivo && navigator.canShare({ files: [archivo] })) {
      try {
        await navigator.share({ files: [archivo] });
        return;
      } catch (error) {
        if (error.name === "AbortError") return; // cerró la hoja: no es un error
      }
    }
    aMano();
  });
})();
