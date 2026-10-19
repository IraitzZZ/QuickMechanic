// Servicio de acceso de QuickMechanic con Discord (OAuth2 + membresía del servidor).
// El client secret y la clave de cifrado viven solo en el entorno secreto de Sites.
// La app recibe un ticket de un solo uso y lo canjea por un token de sesión opaco.
// Cada comprobación de sesión vuelve a consultar Discord: nunca se confía en estado guardado.

const CLIENT_ID = "1389598138226184282";
const GUILD_ID = "1389601848591253566";
const PUBLIC_ORIGIN = "https://site-29d5890e08c8423e8e95673bd568debd.freebuff.page";
const REDIRECT_URI = `${PUBLIC_ORIGIN}/api/discord/callback`;
const DISCORD_API = "https://discord.com/api/v10";
const DISCORD_CDN = "https://cdn.discordapp.com";
const NONCE_RE = /^[A-Za-z0-9_-]{16,128}$/;
// Puerto 0 = acceso desde la web sin la aplicación (no hay loopback al que devolver nada).
const STATE_RE = /^(0|\d{4,5})\.([A-Za-z0-9_-]{16,128})$/;
const SECRET_RE = /^[A-Za-z0-9_-]{43,64}$/; // tickets y tokens: 32 bytes en base64url
const CODE_MAX = 256;
const BODY_MAX = 2048;
const STATE_TTL_MS = 10 * 60 * 1000;
const TICKET_TTL_MS = 60 * 1000;
const SESSION_TTL_MS = 12 * 60 * 60 * 1000;
const GUILD_PAGE_SIZE = 200;
const GUILD_MAX_PAGES = 10;

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS oauth_states (
     hash TEXT PRIMARY KEY,
     expires_at INTEGER NOT NULL,
     used INTEGER NOT NULL DEFAULT 0
   )`,
  `CREATE TABLE IF NOT EXISTS tickets (
     hash TEXT PRIMARY KEY,
     discord_id TEXT NOT NULL,
     name TEXT NOT NULL,
     avatar_url TEXT NOT NULL,
     refresh_enc TEXT NOT NULL,
     expires_at INTEGER NOT NULL,
     used INTEGER NOT NULL DEFAULT 0
   )`,
  `CREATE TABLE IF NOT EXISTS sessions (
     token_hash TEXT PRIMARY KEY,
     discord_id TEXT NOT NULL,
     name TEXT NOT NULL,
     avatar_url TEXT NOT NULL,
     refresh_enc TEXT NOT NULL,
     created_at INTEGER NOT NULL,
     last_verified_at INTEGER NOT NULL,
     expires_at INTEGER NOT NULL,
     revoked INTEGER NOT NULL DEFAULT 0
   )`,
];

// Un esquema por base de datos: cada entorno (y cada test) tiene su propio DB.
const schemaReady = new WeakMap();

class DiscordError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// ---------------------------------------------------------------- respuestas

function noStore(headers = {}) {
  return { "Cache-Control": "no-store", ...headers };
}

function textResponse(status, message) {
  return new Response(message, {
    status,
    headers: noStore({ "Content-Type": "text/plain; charset=utf-8" }),
  });
}

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: noStore({ "Content-Type": "application/json; charset=utf-8" }),
  });
}

// Redirige a la página de resultado. Nunca incluye secretos salvo el ticket de un solo uso.
function resultRedirect(estado, port, nonce, extra = {}) {
  const target = new URL("/acceso/", PUBLIC_ORIGIN);
  target.searchParams.set("estado", estado);
  target.searchParams.set("p", String(port));
  target.searchParams.set("s", nonce);
  for (const [key, value] of Object.entries(extra)) {
    target.searchParams.set(key, value);
  }
  return new Response(null, {
    status: 302,
    headers: noStore({ Location: target.toString(), "Referrer-Policy": "no-referrer" }),
  });
}

// Redirige a la web sin datos de la app (sin puerto ni estado).
function pageRedirect(estado) {
  const target = new URL("/acceso/", PUBLIC_ORIGIN);
  target.searchParams.set("estado", estado);
  return new Response(null, {
    status: 302,
    headers: noStore({ Location: target.toString(), "Referrer-Policy": "no-referrer" }),
  });
}

// ---------------------------------------------------------------- criptografía

function base64url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomSecret(byteLength = 32) {
  return base64url(crypto.getRandomValues(new Uint8Array(byteLength)));
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

let cachedKey = null;

async function aesKey(env) {
  if (cachedKey && cachedKey.source === env.SESSION_KEY) return cachedKey.key;
  const raw = Uint8Array.from(atob(env.SESSION_KEY), (c) => c.charCodeAt(0));
  if (raw.length !== 32) throw new Error("SESSION_KEY inválida");
  const key = await crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
  cachedKey = { source: env.SESSION_KEY, key };
  return key;
}

async function encryptSecret(env, plaintext) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const cipher = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    await aesKey(env),
    new TextEncoder().encode(plaintext),
  );
  const bytes = new Uint8Array(iv.length + cipher.byteLength);
  bytes.set(iv, 0);
  bytes.set(new Uint8Array(cipher), iv.length);
  return base64url(bytes);
}

async function decryptSecret(env, stored) {
  const bytes = Uint8Array.from(atob(stored.replace(/-/g, "+").replace(/_/g, "/")), (c) =>
    c.charCodeAt(0),
  );
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: bytes.slice(0, 12) },
    await aesKey(env),
    bytes.slice(12),
  );
  return new TextDecoder().decode(plain);
}

// ---------------------------------------------------------------- base de datos

function ensureSchema(env) {
  if (!schemaReady.has(env.DB)) {
    const ready = env.DB.batch(SCHEMA.map((sql) => env.DB.prepare(sql))).catch((error) => {
      schemaReady.delete(env.DB);
      throw error;
    });
    schemaReady.set(env.DB, ready);
  }
  return schemaReady.get(env.DB);
}

// El state se guarda al iniciar y se consume una sola vez al volver de Discord (anti-CSRF y anti-replay).
async function storeOAuthState(env, nonce) {
  await ensureSchema(env);
  const now = Date.now();
  // Solo se limpian los caducados: un state usado debe recordarse hasta que caduque.
  await env.DB.prepare("DELETE FROM oauth_states WHERE expires_at <= ?").bind(now).run();
  // OR IGNORE: reiniciar con un state ya usado no lo revive.
  await env.DB.prepare("INSERT OR IGNORE INTO oauth_states (hash, expires_at, used) VALUES (?, ?, 0)")
    .bind(await sha256Hex(nonce), now + STATE_TTL_MS)
    .run();
}

async function consumeOAuthState(env, nonce) {
  await ensureSchema(env);
  const update = await env.DB.prepare(
    "UPDATE oauth_states SET used = 1 WHERE hash = ? AND used = 0 AND expires_at > ?",
  )
    .bind(await sha256Hex(nonce), Date.now())
    .run();
  return Boolean(update.meta && update.meta.changes === 1);
}

// Consume el ticket de forma atómica: solo una petición puede ganar el UPDATE.
async function consumeTicket(env, hash, now) {
  await ensureSchema(env);
  const update = await env.DB.prepare(
    "UPDATE tickets SET used = 1 WHERE hash = ? AND used = 0 AND expires_at > ?",
  )
    .bind(hash, now)
    .run();
  if (!update.meta || update.meta.changes !== 1) return null;
  return env.DB.prepare("SELECT * FROM tickets WHERE hash = ?").bind(hash).first();
}

async function loadSession(env, tokenHash) {
  await ensureSchema(env);
  return env.DB.prepare("SELECT * FROM sessions WHERE token_hash = ?").bind(tokenHash).first();
}

async function revokeSession(env, tokenHash) {
  await env.DB.prepare("UPDATE sessions SET revoked = 1, refresh_enc = '' WHERE token_hash = ?")
    .bind(tokenHash)
    .run();
}

// ---------------------------------------------------------------- Discord

async function discordRequest(path, init) {
  const response = await fetch(`${DISCORD_API}${path}`, init);
  if (!response.ok) {
    throw new DiscordError(`Discord ${path} respondió ${response.status}`, response.status);
  }
  return response.json();
}

async function discordGet(path, accessToken) {
  return discordRequest(path, { headers: { Authorization: `Bearer ${accessToken}` } });
}

async function exchangeCode(env, code) {
  return discordRequest("/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: env.DISCORD_CLIENT_SECRET,
      grant_type: "authorization_code",
      code,
      redirect_uri: REDIRECT_URI,
    }),
  });
}

async function refreshAccess(env, refreshToken) {
  return discordRequest("/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: env.DISCORD_CLIENT_SECRET,
      grant_type: "refresh_token",
      refresh_token: refreshToken,
    }),
  });
}

async function revokeDiscordToken(env, token, hint) {
  await fetch(`${DISCORD_API}/oauth2/token/revoke`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: env.DISCORD_CLIENT_SECRET,
      token,
      token_type_hint: hint,
    }),
  }).catch(() => {});
}

async function isGuildMember(accessToken) {
  let after = "";
  for (let page = 0; page < GUILD_MAX_PAGES; page++) {
    const query = new URLSearchParams({ limit: String(GUILD_PAGE_SIZE) });
    if (after) query.set("after", after);
    const guilds = await discordGet(`/users/@me/guilds?${query}`, accessToken);
    if (guilds.some((guild) => guild.id === GUILD_ID)) return true;
    if (guilds.length < GUILD_PAGE_SIZE) return false;
    after = guilds[guilds.length - 1].id;
  }
  return false;
}

// Avatar según la documentación de Discord: imagen propia o avatar por defecto.
function avatarUrl(user) {
  if (user.avatar) {
    const ext = user.avatar.startsWith("a_") ? "gif" : "png";
    return `${DISCORD_CDN}/avatars/${user.id}/${user.avatar}.${ext}?size=256`;
  }
  const index = Number((BigInt(user.id) >> 22n) % 6n);
  return `${DISCORD_CDN}/embed/avatars/${index}.png`;
}

function displayName(user) {
  return String(user.global_name || user.username || "").slice(0, 64);
}

// ---------------------------------------------------------------- rutas de OAuth

async function handleStart(url, env) {
  const rawPort = url.searchParams.get("port");
  const port = rawPort === null ? 0 : Number(rawPort);
  const nonce = url.searchParams.get("state") || randomSecret(18);
  const validPort = port === 0 || (Number.isInteger(port) && port >= 1024 && port <= 65535);
  if (!validPort || !NONCE_RE.test(nonce)) {
    return textResponse(400, "Parámetros no válidos.");
  }
  if (!env.DB) return textResponse(503, "Servicio no disponible.");
  try {
    await storeOAuthState(env, nonce);
  } catch {
    return textResponse(503, "Servicio no disponible.");
  }
  const authorize = new URL("https://discord.com/oauth2/authorize");
  authorize.searchParams.set("client_id", CLIENT_ID);
  authorize.searchParams.set("response_type", "code");
  authorize.searchParams.set("redirect_uri", REDIRECT_URI);
  authorize.searchParams.set("scope", "identify guilds");
  authorize.searchParams.set("state", `${port}.${nonce}`);
  return new Response(null, {
    status: 302,
    headers: noStore({ Location: authorize.toString(), "Referrer-Policy": "no-referrer" }),
  });
}

async function handleCallback(url, env) {
  const match = STATE_RE.exec(url.searchParams.get("state") || "");
  if (!match) return textResponse(400, "Estado no válido.");
  const port = Number(match[1]);
  const nonce = match[2];
  if (port !== 0 && (port < 1024 || port > 65535)) return textResponse(400, "Estado no válido.");
  // Un state desconocido, caducado o ya usado no devuelve nada a la app: solo a la web.
  let stateValid = false;
  try {
    stateValid = env.DB ? await consumeOAuthState(env, nonce) : false;
  } catch {
    return pageRedirect("network");
  }
  if (!stateValid) return pageRedirect("state");
  const result = (estado, extra) => resultRedirect(estado, port, nonce, extra);

  if (url.searchParams.has("error")) return result("denied");
  const code = url.searchParams.get("code") || "";
  if (!code || code.length > CODE_MAX) return result("missing_code");
  if (!env.DISCORD_CLIENT_SECRET || !env.SESSION_KEY || !env.DB) return result("not_configured");

  let tokens = null;
  try {
    tokens = await exchangeCode(env, code);
  } catch {
    return result("token_failed");
  }
  if (!tokens.access_token || !tokens.refresh_token) return result("token_failed");

  try {
    const user = await discordGet("/users/@me", tokens.access_token);
    if (!(await isGuildMember(tokens.access_token))) {
      await revokeDiscordToken(env, tokens.access_token, "access_token");
      return result("not_member");
    }
    await ensureSchema(env);
    const ticket = randomSecret();
    await env.DB.prepare(
      "INSERT INTO tickets (hash, discord_id, name, avatar_url, refresh_enc, expires_at, used) VALUES (?, ?, ?, ?, ?, ?, 0)",
    )
      .bind(
        await sha256Hex(ticket),
        String(user.id),
        displayName(user),
        avatarUrl(user),
        await encryptSecret(env, tokens.refresh_token),
        Date.now() + TICKET_TTL_MS,
      )
      .run();
    return result("ok", { t: ticket });
  } catch {
    // Discord caído, límite de peticiones o error de base de datos: no se revela el detalle.
    return result("network");
  }
}

// ---------------------------------------------------------------- API de sesión

function bearerToken(request) {
  const header = request.headers.get("Authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  return SECRET_RE.test(token) ? token : null;
}

async function readJson(request) {
  const text = await request.text();
  if (text.length > BODY_MAX) return { error: "too_large" };
  try {
    const body = JSON.parse(text);
    return body && typeof body === "object" ? body : { error: "bad_json" };
  } catch {
    return { error: "bad_json" };
  }
}

// Vista previa del ticket para la página de resultado. No lo consume.
async function handleTicketProfile(url, env) {
  const ticket = url.searchParams.get("t") || "";
  if (!SECRET_RE.test(ticket)) return json(404, { error: "ticket_invalid" });
  await ensureSchema(env);
  const row = await env.DB.prepare(
    "SELECT discord_id, name, avatar_url FROM tickets WHERE hash = ? AND used = 0 AND expires_at > ?",
  )
    .bind(await sha256Hex(ticket), Date.now())
    .first();
  if (!row) return json(404, { error: "ticket_invalid" });
  return json(200, { id: row.discord_id, name: row.name, avatar_url: row.avatar_url });
}

async function handleExchange(request, env) {
  const body = await readJson(request);
  if (body.error) return json(400, { error: body.error });
  if (typeof body.ticket !== "string" || !SECRET_RE.test(body.ticket)) {
    return json(401, { error: "ticket_invalid" });
  }
  const now = Date.now();
  const row = await consumeTicket(env, await sha256Hex(body.ticket), now);
  if (!row) return json(401, { error: "ticket_invalid" });

  const token = randomSecret();
  await env.DB.prepare(
    "INSERT INTO sessions (token_hash, discord_id, name, avatar_url, refresh_enc, created_at, last_verified_at, expires_at, revoked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
  )
    .bind(
      await sha256Hex(token),
      row.discord_id,
      row.name,
      row.avatar_url,
      row.refresh_enc,
      now,
      now,
      now + SESSION_TTL_MS,
    )
    .run();
  await env.DB.prepare("DELETE FROM tickets WHERE hash = ?").bind(await sha256Hex(body.ticket)).run();
  return json(200, {
    token,
    user: { id: row.discord_id, name: row.name, avatar_url: row.avatar_url },
    verified_at: now,
    expires_at: now + SESSION_TTL_MS,
  });
}

async function handleCheck(request, env) {
  const token = bearerToken(request);
  if (!token) return json(401, { error: "session_invalid" });
  const now = Date.now();
  const row = await loadSession(env, await sha256Hex(token));
  if (!row || row.revoked || row.expires_at <= now) {
    return json(401, { error: "session_invalid" });
  }
  if (!env.DISCORD_CLIENT_SECRET || !env.SESSION_KEY) {
    return json(503, { error: "discord_unavailable" });
  }

  let tokens;
  try {
    tokens = await refreshAccess(env, await decryptSecret(env, row.refresh_enc));
  } catch (error) {
    // 400/401 de Discord: el grant ya no vale (revocado o caducado). Otro error es temporal.
    if (error instanceof DiscordError && (error.status === 400 || error.status === 401)) {
      await revokeSession(env, await sha256Hex(token));
      return json(401, { error: "session_invalid" });
    }
    return json(503, { error: "discord_unavailable" });
  }

  // Discord rota el refresh token en cada uso: guardamos el nuevo antes de consultar el servidor,
  // para que un fallo temporal posterior no deje la sesión con un token ya gastado.
  const tokenHash = await sha256Hex(token);
  await env.DB.prepare("UPDATE sessions SET refresh_enc = ? WHERE token_hash = ?")
    .bind(await encryptSecret(env, tokens.refresh_token), tokenHash)
    .run();

  let member = false;
  try {
    member = await isGuildMember(tokens.access_token);
  } catch {
    return json(503, { error: "discord_unavailable" });
  }
  if (!member) {
    await revokeSession(env, tokenHash);
    await revokeDiscordToken(env, tokens.refresh_token, "refresh_token");
    return json(403, { error: "not_member" });
  }

  await env.DB.prepare("UPDATE sessions SET last_verified_at = ? WHERE token_hash = ?")
    .bind(now, tokenHash)
    .run();
  return json(200, {
    ok: true,
    verified_at: now,
    user: { id: row.discord_id, name: row.name, avatar_url: row.avatar_url },
  });
}

async function handleLogout(request, env) {
  const token = bearerToken(request);
  if (token) {
    const row = await loadSession(env, await sha256Hex(token));
    if (row && !row.revoked && row.refresh_enc && env.DISCORD_CLIENT_SECRET && env.SESSION_KEY) {
      const refresh = await decryptSecret(env, row.refresh_enc).catch(() => null);
      if (refresh) await revokeDiscordToken(env, refresh, "refresh_token");
    }
    if (row) await revokeSession(env, await sha256Hex(token));
  }
  return new Response(null, { status: 204, headers: noStore() });
}

// ---------------------------------------------------------------- enrutado

// Cabeceras de seguridad para las páginas. El ticket viaja en la URL: no debe filtrarse por Referer.
function withSecurityHeaders(response) {
  const headers = new Headers(response.headers);
  headers.set(
    "Content-Security-Policy",
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://cdn.discordapp.com data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  );
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

async function routeApi(request, env, url) {
  const { pathname } = url;
  if (pathname === "/api/discord/start") {
    return request.method === "GET" ? handleStart(url, env) : textResponse(405, "Método no permitido.");
  }
  if (pathname === "/api/discord/callback") {
    return request.method === "GET" ? handleCallback(url, env) : textResponse(405, "Método no permitido.");
  }
  if (pathname === "/api/ticket") {
    return request.method === "GET" ? handleTicketProfile(url, env) : json(405, { error: "method" });
  }
  if (pathname === "/api/session/exchange") {
    return request.method === "POST" ? handleExchange(request, env) : json(405, { error: "method" });
  }
  if (pathname === "/api/session/check") {
    return request.method === "POST" ? handleCheck(request, env) : json(405, { error: "method" });
  }
  if (pathname === "/api/session/logout") {
    return request.method === "POST" ? handleLogout(request, env) : json(405, { error: "method" });
  }
  return json(404, { error: "not_found" });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) {
      return routeApi(request, env, url);
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return textResponse(405, "Método no permitido.");
    }
    if (!env.ASSETS) return textResponse(404, "No encontrado.");
    return withSecurityHeaders(await env.ASSETS.fetch(request));
  },
};
