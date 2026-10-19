// Página de resultado de QuickMechanic Access.
// Los pasos solo avanzan con respuestas reales del servidor. La app recibe un ticket
// de un solo uso por loopback y lo canjea por una sesión; esta página nunca decide el acceso.
(function () {
  "use strict";

  var AVATAR_PREFIX = "https://cdn.discordapp.com/";
  var STATE_RE = /^[A-Za-z0-9_-]{16,128}$/;
  var TICKET_RE = /^[A-Za-z0-9_-]{43,64}$/;
  var JOIN_URL = "https://discord.gg/pWE5yEKexW";
  var STEP_DELAY_MS = 450;

  var MESSAGES = {
    none: "No hay ninguna verificación en curso. Empieza desde la página principal.",
    denied: "Cancelaste la autorización en Discord. No se ha compartido ningún dato.",
    not_member: "Necesitas pertenecer al servidor oficial de QuickMechanic para usar la aplicación.",
    state: "Esta verificación ha caducado o ya se utilizó. Vuelve a empezar.",
    missing_code: "Discord no devolvió la autorización. Vuelve a intentarlo.",
    token_failed: "No pudimos completar la autorización con Discord. Vuelve a intentarlo.",
    not_configured: "El servicio de acceso no está disponible en este momento.",
    network: "No pudimos contactar con Discord ni con el servicio de acceso. Inténtalo de nuevo en unos minutos.",
    expired: "La sesión de verificación ha caducado. Vuelve a empezar.",
    unavailable: "El servicio de autenticación no está disponible en este momento."
  };

  // Paso en el que falla cada motivo, para mostrar la lista de pasos de forma honesta.
  var FAILED_STEP = {
    denied: "connect",
    state: "connect",
    missing_code: "connect",
    token_failed: "identity",
    not_configured: "identity",
    network: "identity",
    expired: "identity",
    not_member: "member",
    unavailable: "identity"
  };

  var STEP_ORDER = ["connect", "identity", "member", "prepare"];

  function $(id) {
    return document.getElementById(id);
  }

  var params = new URLSearchParams(window.location.search);
  var estado = params.get("estado") || "";
  var rawPort = parseInt(params.get("p") || "0", 10);
  var nonce = params.get("s") || "";
  var ticket = params.get("t") || "";

  // El ticket y el state no deben quedar en la barra de direcciones ni en el historial.
  window.history.replaceState(null, "", "/acceso/");

  var appPort = 0;
  if (Number.isInteger(rawPort) && rawPort >= 1024 && rawPort <= 65535 && STATE_RE.test(nonce)) {
    appPort = rawPort;
  }

  function showView(name) {
    ["verifying", "ok", "error"].forEach(function (view) {
      $("view-" + view).hidden = view !== name;
    });
  }

  function setStep(step, status) {
    var item = document.querySelector('#checks [data-step="' + step + '"]');
    if (!item) return;
    item.classList.remove("is-active", "is-done", "is-failed");
    if (status) item.classList.add("is-" + status);
    var dot = item.querySelector(".check-dot");
    if (status === "done") dot.textContent = "✓";
    else if (status === "failed") dot.textContent = "!";
    else dot.textContent = String(STEP_ORDER.indexOf(step) + 1);
  }

  // Marca los pasos anteriores como hechos y el indicado como fallido o activo.
  function markUntil(step, status) {
    var limit = STEP_ORDER.indexOf(step);
    STEP_ORDER.forEach(function (name, index) {
      if (index < limit) setStep(name, "done");
      else if (index === limit) setStep(name, status);
      else setStep(name, null);
    });
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function loopbackUrl(query) {
    return "http://127.0.0.1:" + appPort + "/callback?" + query;
  }

  function showError(code) {
    var message = MESSAGES[code] || MESSAGES.unavailable;
    var failed = FAILED_STEP[code];
    showView("error");
    $("error-title").textContent = code === "not_member" ? "Acceso denegado" : "No se pudo verificar el acceso";
    $("error-text").textContent = message;
    $("error-icon").classList.toggle("is-danger", true);
    $("join-link").hidden = code !== "not_member";
    // Sin la app, "Volver a comprobar" inicia de nuevo la verificación. Con la app, la reintenta desde ella.
    $("retry-link").hidden = appPort !== 0;
    $("error-app-notice").hidden = appPort === 0;
    if (appPort !== 0) {
      var back = document.createElement("a");
      back.className = "btn btn-ghost";
      back.href = loopbackUrl("s=" + encodeURIComponent(nonce) + "&error=" + encodeURIComponent(code));
      back.textContent = "Volver a QuickMechanic";
      $("error-app-notice").insertAdjacentElement("beforebegin", back);
    }
    if (failed) markUntil(failed, "failed");
  }

  function renderProfile(data) {
    var name = typeof data.name === "string" ? data.name.slice(0, 64) : "";
    $("profile-name").textContent = name || "Miembro";
    var avatarUrl = typeof data.avatar_url === "string" ? data.avatar_url : "";
    var avatar = $("avatar");
    if (avatarUrl.indexOf(AVATAR_PREFIX) === 0) {
      avatar.addEventListener("error", function () {
        avatar.hidden = true;
      });
      avatar.src = avatarUrl;
      avatar.alt = "Avatar de " + (name || "Discord");
      avatar.hidden = false;
    }
    if (typeof data.id === "string" && /^\d{5,25}$/.test(data.id)) {
      $("discord-id").textContent = data.id;
      $("discord-id-line").hidden = false;
    }
    $("verified-at").textContent = new Date().toLocaleString("es-ES", {
      dateStyle: "medium",
      timeStyle: "short"
    });
    if (appPort !== 0) {
      var open = $("open-app");
      open.addEventListener("click", function () {
        open.disabled = true;
        open.textContent = "Abriendo QuickMechanic…";
        window.location.href = loopbackUrl("s=" + encodeURIComponent(nonce) + "&t=" + encodeURIComponent(ticket));
      });
    } else {
      $("open-app").hidden = true;
      $("ok-notice").hidden = false;
    }
  }

  async function run() {
    if (!estado) {
      showError("none");
      return;
    }
    if (estado !== "ok") {
      showError(estado);
      return;
    }

    if (!TICKET_RE.test(ticket)) {
      showError("expired");
      return;
    }

    // "Conectando con Discord" ya es real: hemos vuelto desde Discord con una respuesta válida.
    markUntil("identity", "active");

    var data;
    try {
      var response = await fetch("/api/ticket?t=" + encodeURIComponent(ticket), {
        cache: "no-store",
        credentials: "omit",
        referrerPolicy: "no-referrer"
      });
      if (response.status === 404) {
        showError("expired");
        return;
      }
      if (!response.ok) {
        showError("unavailable");
        return;
      }
      data = await response.json();
    } catch (error) {
      showError("network");
      return;
    }

    // El ticket solo existe si el servidor comprobó la membresía antes de emitirlo.
    await sleep(STEP_DELAY_MS);
    markUntil("member", "active");
    await sleep(STEP_DELAY_MS);
    markUntil("prepare", "active");
    await sleep(STEP_DELAY_MS);
    setStep("member", "done");
    setStep("identity", "done");
    setStep("connect", "done");
    setStep("prepare", "done");

    renderProfile(data);
    showView("ok");
  }

  run();
})();
