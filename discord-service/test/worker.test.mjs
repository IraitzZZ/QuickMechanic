// Pruebas del Worker de acceso. Usan SQLite real (node:sqlite) como D1 y un Discord simulado:
// NO hay red real. Las pruebas con Discord de verdad se hacen a mano (ver README de la app).
import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import worker from "../worker.js";

const ORIGIN = "https://site-29d5890e08c8423e8e95673bd568debd.freebuff.page";
const GUILD = "1389601848591253566";
const CLIENT_SECRET = "test-client-secret-value";
const SESSION_KEY = Buffer.alloc(32, 7).toString("base64");
const NONCE = "abcdefghijklmnop1234";
const PORT = 52000;
const USER_ID = "123456789012345678";

// ---------------------------------------------------------------- D1 sobre SQLite real

function makeDb() {
  const db = new DatabaseSync(":memory:");
  const statement = (sql, args = []) => ({
    bind: (...values) => statement(sql, values),
    first: async () => db.prepare(sql).get(...args) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(sql).run(...args).changes) } }),
    all: async () => ({ results: db.prepare(sql).all(...args) }),
  });
  return {
    raw: db,
    prepare: (sql) => statement(sql),
    batch: async (statements) => {
      const out = [];
      for (const stmt of statements) out.push(await stmt.run());
      return out;
    },
  };
}

// ---------------------------------------------------------------- Discord simulado

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function newFake() {
  return {
    calls: [],
    tokenStatus: 200,
    tokenThrows: false,
    tokenBody: null,
    refreshStatus: 200,
    refreshThrows: false,
    userStatus: 200,
    user: { id: USER_ID, username: "piloto", global_name: "Piloto QM", avatar: null },
    guildPages: [[{ id: GUILD, name: "QuickMechanic" }]],
    guildsThrow: false,
    guildsStatus: 200,
  };
}

function fakeFetch(fake) {
  return async (input, init = {}) => {
    const url = new URL(String(input));
    if (url.origin !== "https://discord.com") {
      throw new Error(`Salida de red no permitida en pruebas: ${url}`);
    }
    const method = init.method || "GET";
    if (url.pathname === "/api/v10/oauth2/token" && method === "POST") {
      const params = Object.fromEntries(new URLSearchParams(init.body));
      fake.calls.push({ kind: "token", params });
      if (params.grant_type === "refresh_token") {
        if (fake.refreshThrows) throw new TypeError("fetch failed");
        if (fake.refreshStatus !== 200) return jsonResponse(fake.refreshStatus, { error: "invalid_grant" });
        return jsonResponse(200, {
          access_token: "acc-refreshed",
          refresh_token: `${params.refresh_token}+`,
          token_type: "Bearer",
          expires_in: 604800,
        });
      }
      if (fake.tokenThrows) throw new TypeError("fetch failed");
      if (fake.tokenStatus !== 200) return jsonResponse(fake.tokenStatus, { error: "invalid_grant" });
      if (fake.tokenBody) return jsonResponse(200, fake.tokenBody(params));
      return jsonResponse(200, {
        access_token: "acc-1",
        refresh_token: "ref-1",
        token_type: "Bearer",
        expires_in: 604800,
      });
    }
    if (url.pathname === "/api/v10/users/@me" && method === "GET") {
      fake.calls.push({ kind: "user" });
      if (fake.userStatus !== 200) return jsonResponse(fake.userStatus, { message: "error" });
      return jsonResponse(200, fake.user);
    }
    if (url.pathname === "/api/v10/users/@me/guilds" && method === "GET") {
      fake.calls.push({ kind: "guilds" });
      if (fake.guildsThrow) throw new TypeError("fetch failed");
      if (fake.guildsStatus !== 200) return jsonResponse(fake.guildsStatus, { message: "error" });
      const page = url.searchParams.has("after") ? 1 : 0;
      return jsonResponse(200, fake.guildPages[page] || []);
    }
    if (url.pathname === "/api/v10/oauth2/token/revoke" && method === "POST") {
      fake.calls.push({ kind: "revoke", params: Object.fromEntries(new URLSearchParams(init.body)) });
      return new Response(null, { status: 200 });
    }
    return jsonResponse(404, { message: "not found" });
  };
}

// ---------------------------------------------------------------- ayudas

let fake;
let originalFetch;
let env;

beforeEach(() => {
  fake = newFake();
  originalFetch = globalThis.fetch;
  globalThis.fetch = fakeFetch(fake);
  env = { DB: makeDb(), DISCORD_CLIENT_SECRET: CLIENT_SECRET, SESSION_KEY };
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

const get = (path, currentEnv = env) => worker.fetch(new Request(ORIGIN + path), currentEnv);

function post(path, { body, token, raw, currentEnv = env } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (raw !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = raw;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  return worker.fetch(new Request(ORIGIN + path, { method: "POST", headers, body: payload }), currentEnv);
}

// Como la app real: el state se registra al iniciar y se consume una sola vez al volver de Discord.
let nonceSeq = 0;
const nextNonce = () => `${NONCE.slice(0, 12)}${String(++nonceSeq).padStart(8, "0")}`;
const startFlow = (nonce, currentEnv = env) => get(`/api/discord/start?port=${PORT}&state=${nonce}`, currentEnv);
async function callback(query, currentEnv = env) {
  await startFlow(NONCE, currentEnv);
  return get(`/api/discord/callback?${query}`, currentEnv);
}
// Cada flujo completo usa un state nuevo (los states usados no se reutilizan).
async function okCallback(currentEnv = env) {
  const nonce = nextNonce();
  await startFlow(nonce, currentEnv);
  return get(`/api/discord/callback?code=auth-code&state=${PORT}.${nonce}`, currentEnv);
}

function resultParams(res) {
  assert.equal(res.status, 302);
  return new URL(res.headers.get("location")).searchParams;
}

// Completa el login (callback correcto) y devuelve el ticket de un solo uso.
async function loginTicket(currentEnv = env) {
  const params = resultParams(await okCallback(currentEnv));
  assert.equal(params.get("estado"), "ok");
  return params.get("t");
}

async function sessionFromTicket(currentEnv = env) {
  const ticket = await loginTicket(currentEnv);
  const res = await post("/api/session/exchange", { body: { ticket }, currentEnv });
  assert.equal(res.status, 200);
  return res.json();
}

// ---------------------------------------------------------------- inicio de OAuth2

test("inicio: redirige a Discord con identify+guilds y sin secretos", async () => {
  const res = await get(`/api/discord/start?port=${PORT}&state=${NONCE}`);
  assert.equal(res.status, 302);
  const location = res.headers.get("location");
  const url = new URL(location);
  assert.equal(url.origin + url.pathname, "https://discord.com/oauth2/authorize");
  assert.equal(url.searchParams.get("scope"), "identify guilds");
  assert.equal(url.searchParams.get("state"), `${PORT}.${NONCE}`);
  assert.equal(url.searchParams.get("redirect_uri"), `${ORIGIN}/api/discord/callback`);
  assert.equal(url.searchParams.get("response_type"), "code");
  assert.ok(!location.includes(CLIENT_SECRET));
});

test("inicio: rechaza puertos fuera de rango y estados mal formados", async () => {
  assert.equal((await get(`/api/discord/start?port=80&state=${NONCE}`)).status, 400);
  assert.equal((await get(`/api/discord/start?port=99999&state=${NONCE}`)).status, 400);
  assert.equal((await get(`/api/discord/start?port=${PORT}&state=corto`)).status, 400);
});

test("inicio sin app: acepta el flujo web (puerto 0) con estado generado", async () => {
  const res = await get("/api/discord/start");
  assert.equal(res.status, 302);
  const state = new URL(res.headers.get("location")).searchParams.get("state");
  assert.match(state, /^0\.[A-Za-z0-9_-]{16,128}$/);
});

// ---------------------------------------------------------------- callback

test("callback: autorización cancelada no llama a Discord y devuelve 'denied'", async () => {
  const params = resultParams(await callback(`error=access_denied&state=${PORT}.${NONCE}`));
  assert.equal(params.get("estado"), "denied");
  assert.equal(params.get("p"), String(PORT));
  assert.equal(params.get("s"), NONCE);
  assert.equal(params.get("t"), null);
  assert.equal(fake.calls.length, 0);
});

test("callback: state inválido o ausente se rechaza sin redirigir", async () => {
  assert.equal((await callback("code=x&state=mal")).status, 400);
  assert.equal((await callback("code=x")).status, 400);
  assert.equal((await callback(`code=x&state=${PORT}.corto`)).status, 400);
  assert.equal(fake.calls.length, 0);
});

test("callback: un state ya usado (replay) no devuelve datos a la app ni llama a Discord", async () => {
  const nonce = nextNonce();
  await startFlow(nonce);
  const url = `/api/discord/callback?code=auth-code&state=${PORT}.${nonce}`;
  assert.equal(resultParams(await get(url)).get("estado"), "ok");
  const params = resultParams(await get(url));
  assert.equal(params.get("estado"), "state");
  assert.equal(params.get("p"), null);
  assert.equal(params.get("s"), null);
  assert.equal(params.get("t"), null);
  assert.equal(fake.calls.filter((c) => c.kind === "token").length, 1);
});

test("callback: un state caducado se rechaza", async () => {
  const OTHER = "zyxwvutsrqponmlk9876";
  await get(`/api/discord/start?port=${PORT}&state=${OTHER}`, env);
  env.DB.raw.prepare("UPDATE oauth_states SET expires_at = 0").run();
  const params = resultParams(await get(`/api/discord/callback?code=auth-code&state=${PORT}.${OTHER}`, env));
  assert.equal(params.get("estado"), "state");
  assert.equal(fake.calls.filter((c) => c.kind === "token").length, 0);
});

test("callback: sin código devuelve 'missing_code'", async () => {
  assert.equal(resultParams(await callback(`state=${PORT}.${NONCE}`)).get("estado"), "missing_code");
});

test("callback: secreto o clave no configurados devuelve 'not_configured' sin llamar a Discord", async () => {
  const noSecret = { DB: makeDb(), SESSION_KEY };
  assert.equal(resultParams(await okCallback(noSecret)).get("estado"), "not_configured");
  const noKey = { DB: makeDb(), DISCORD_CLIENT_SECRET: CLIENT_SECRET };
  assert.equal(resultParams(await okCallback(noKey)).get("estado"), "not_configured");
  assert.equal(fake.calls.length, 0);
});

test("callback: código OAuth inválido devuelve 'token_failed'", async () => {
  fake.tokenStatus = 400;
  assert.equal(resultParams(await okCallback()).get("estado"), "token_failed");
});

test("callback: respuesta de token malformada devuelve 'token_failed'", async () => {
  fake.tokenBody = () => ({ access_token: "acc-1" });
  assert.equal(resultParams(await okCallback()).get("estado"), "token_failed");
});

test("callback: Discord caído o timeout al canjear el código devuelve 'token_failed'", async () => {
  fake.tokenThrows = true;
  assert.equal(resultParams(await okCallback()).get("estado"), "token_failed");
});

test("callback: usuario miembro del servidor obtiene ticket y el token se envía a Discord sin secretos en la URL", async () => {
  const res = await okCallback();
  const params = resultParams(res);
  assert.equal(params.get("estado"), "ok");
  const ticket = params.get("t");
  assert.match(ticket, /^[A-Za-z0-9_-]{43}$/);
  assert.ok(!res.headers.get("location").includes("ref-1"));
  assert.ok(!res.headers.get("location").includes("acc-1"));
  assert.ok(!res.headers.get("location").includes(CLIENT_SECRET));
  const tokenCall = fake.calls.find((c) => c.kind === "token");
  assert.equal(tokenCall.params.client_secret, CLIENT_SECRET);
});

test("callback: usuario que NO pertenece al servidor devuelve 'not_member' y revoca el acceso", async () => {
  fake.guildPages = [[{ id: "999999999999999999" }]];
  assert.equal(resultParams(await okCallback()).get("estado"), "not_member");
  const revoke = fake.calls.find((c) => c.kind === "revoke");
  assert.ok(revoke, "debe revocar el token de acceso");
  assert.equal(revoke.params.token_type_hint, "access_token");
});

test("callback: el servidor del guild se busca paginando la lista de servidores", async () => {
  const firstPage = Array.from({ length: 200 }, (_, i) => ({ id: String(1000 + i) }));
  fake.guildPages = [firstPage, [{ id: GUILD }]];
  assert.equal(resultParams(await okCallback()).get("estado"), "ok");
});

test("callback: error de red o límite de Discord al consultar servidores devuelve 'network'", async () => {
  fake.guildsThrow = true;
  assert.equal(resultParams(await okCallback()).get("estado"), "network");
  fake.guildsThrow = false;
  fake.guildsStatus = 429;
  assert.equal(resultParams(await okCallback()).get("estado"), "network");
});

test("callback: error de Discord al leer el perfil devuelve 'network'", async () => {
  fake.userStatus = 500;
  assert.equal(resultParams(await okCallback()).get("estado"), "network");
});

// ---------------------------------------------------------------- ticket y canje

test("ticket: la vista previa no consume el ticket y el canje solo funciona una vez", async () => {
  const ticket = await loginTicket();
  const preview = await get(`/api/ticket?t=${ticket}`);
  assert.equal(preview.status, 200);
  const profile = await preview.json();
  assert.equal(profile.id, USER_ID);
  assert.equal(profile.name, "Piloto QM");
  assert.ok(!("refresh_enc" in profile));

  const first = await post("/api/session/exchange", { body: { ticket } });
  assert.equal(first.status, 200);
  const session = await first.json();
  assert.match(session.token, /^[A-Za-z0-9_-]{43}$/);
  assert.equal(session.user.id, USER_ID);

  const replay = await post("/api/session/exchange", { body: { ticket } });
  assert.equal(replay.status, 401);
  assert.equal((await replay.json()).error, "ticket_invalid");
  assert.equal((await get(`/api/ticket?t=${ticket}`)).status, 404);
});

test("ticket: caducado no se puede canjear", async () => {
  const ticket = await loginTicket();
  env.DB.raw.prepare("UPDATE tickets SET expires_at = 0").run();
  const res = await post("/api/session/exchange", { body: { ticket } });
  assert.equal(res.status, 401);
});

test("ticket: formato inválido o inventado devuelve 401", async () => {
  assert.equal((await post("/api/session/exchange", { body: { ticket: "inventado" } })).status, 401);
  assert.equal((await post("/api/session/exchange", { body: {} })).status, 401);
  assert.equal((await get("/api/ticket?t=nope")).status, 404);
});

test("ticket: el token de sesión se guarda solo como hash", async () => {
  const session = await sessionFromTicket();
  const rows = env.DB.raw.prepare("SELECT * FROM sessions").all();
  assert.equal(rows.length, 1);
  for (const value of Object.values(rows[0])) {
    assert.ok(String(value) !== session.token);
    assert.ok(!String(value).includes(session.token));
  }
});

test("refresh token: se guarda cifrado en D1, nunca en claro", async () => {
  await sessionFromTicket();
  const row = env.DB.raw.prepare("SELECT refresh_enc FROM sessions").get();
  assert.ok(row.refresh_enc.length > 0);
  assert.ok(!row.refresh_enc.includes("ref-1"));
});

// ---------------------------------------------------------------- comprobación de sesión

test("check: sesión válida revalida contra Discord con el refresh token descifrado", async () => {
  const session = await sessionFromTicket();
  fake.calls.length = 0;
  const res = await post("/api/session/check", { token: session.token });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.equal(body.user.id, USER_ID);
  assert.equal(typeof body.verified_at, "number");
  const refresh = fake.calls.find((c) => c.kind === "token" && c.params.grant_type === "refresh_token");
  assert.equal(refresh.params.refresh_token, "ref-1");
  assert.ok(fake.calls.some((c) => c.kind === "guilds"), "debe comprobar el servidor en cada check");
});

test("check: el refresh token rota y se usa el nuevo en la siguiente comprobación", async () => {
  const session = await sessionFromTicket();
  assert.equal((await post("/api/session/check", { token: session.token })).status, 200);
  assert.equal((await post("/api/session/check", { token: session.token })).status, 200);
  const grants = fake.calls.filter((c) => c.kind === "token" && c.params.grant_type === "refresh_token");
  assert.deepEqual(grants.map((g) => g.params.refresh_token), ["ref-1", "ref-1+"]);
});

test("check: usuario que abandona el servidor pierde la sesión en la siguiente comprobación", async () => {
  const session = await sessionFromTicket();
  fake.guildPages = [[]];
  const res = await post("/api/session/check", { token: session.token });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "not_member");
  const revoke = fake.calls.find((c) => c.kind === "revoke" && c.params.token_type_hint === "refresh_token");
  assert.ok(revoke, "debe revocar el refresh token en Discord");

  fake.guildPages = [[{ id: GUILD }]];
  const again = await post("/api/session/check", { token: session.token });
  assert.equal(again.status, 401);
  assert.equal((await again.json()).error, "session_invalid");
});

test("check: refresh rechazado por Discord revoca la sesión", async () => {
  const session = await sessionFromTicket();
  fake.refreshStatus = 400;
  const res = await post("/api/session/check", { token: session.token });
  assert.equal(res.status, 401);
  fake.refreshStatus = 200;
  assert.equal((await post("/api/session/check", { token: session.token })).status, 401);
});

test("check: error temporal de Discord responde 503 y NO revoca la sesión", async () => {
  const session = await sessionFromTicket();
  fake.refreshStatus = 500;
  const res = await post("/api/session/check", { token: session.token });
  assert.equal(res.status, 503);
  assert.equal((await res.json()).error, "discord_unavailable");

  fake.refreshStatus = 200;
  assert.equal((await post("/api/session/check", { token: session.token })).status, 200);
});

test("check: timeout o desconexión con Discord responde 503", async () => {
  const session = await sessionFromTicket();
  fake.refreshThrows = true;
  assert.equal((await post("/api/session/check", { token: session.token })).status, 503);
  fake.refreshThrows = false;
  fake.guildsThrow = true;
  assert.equal((await post("/api/session/check", { token: session.token })).status, 503);
  fake.guildsThrow = false;
  assert.equal((await post("/api/session/check", { token: session.token })).status, 200);
});

test("check: si el servidor de Discord falla tras rotar, el refresh nuevo queda guardado", async () => {
  const session = await sessionFromTicket();
  fake.guildsThrow = true;
  assert.equal((await post("/api/session/check", { token: session.token })).status, 503);
  fake.guildsThrow = false;
  assert.equal((await post("/api/session/check", { token: session.token })).status, 200);
  const grants = fake.calls.filter((c) => c.kind === "token" && c.params.grant_type === "refresh_token");
  assert.deepEqual(grants.map((g) => g.params.refresh_token), ["ref-1", "ref-1+"]);
});

test("check: sin token, con token inventado o con formato erróneo devuelve 401", async () => {
  await sessionFromTicket();
  assert.equal((await post("/api/session/check")).status, 401);
  assert.equal((await post("/api/session/check", { token: "inventado" })).status, 401);
  assert.equal((await post("/api/session/check", { token: "x".repeat(43) })).status, 401);
});

test("check: sesión caducada devuelve 401 aunque Discord responda bien", async () => {
  const session = await sessionFromTicket();
  env.DB.raw.prepare("UPDATE sessions SET expires_at = 0").run();
  fake.calls.length = 0;
  const res = await post("/api/session/check", { token: session.token });
  assert.equal(res.status, 401);
  assert.equal(fake.calls.length, 0, "no debe consultar Discord con una sesión caducada");
});

test("check: sin configuración de secreto no revalida y responde 503", async () => {
  const session = await sessionFromTicket();
  const noSecret = { ...env, DISCORD_CLIENT_SECRET: undefined };
  assert.equal((await post("/api/session/check", { token: session.token, currentEnv: noSecret })).status, 503);
});

// ---------------------------------------------------------------- cierre de sesión

test("logout: revoca la sesión y el refresh token en Discord", async () => {
  const session = await sessionFromTicket();
  const res = await post("/api/session/logout", { token: session.token });
  assert.equal(res.status, 204);
  const revoke = fake.calls.find((c) => c.kind === "revoke");
  assert.equal(revoke.params.token_type_hint, "refresh_token");
  assert.equal(revoke.params.token, "ref-1");
  assert.equal((await post("/api/session/check", { token: session.token })).status, 401);
});

test("logout: idempotente, responde 204 aunque el token ya no sea válido", async () => {
  assert.equal((await post("/api/session/logout")).status, 204);
  assert.equal((await post("/api/session/logout", { token: "inventado" })).status, 204);
});

// ---------------------------------------------------------------- entrada y enrutado

test("entrada: JSON inválido, demasiado grande o sin ticket se rechaza", async () => {
  assert.equal((await post("/api/session/exchange", { raw: "no es json" })).status, 400);
  assert.equal((await post("/api/session/exchange", { raw: "x".repeat(3000) })).status, 400);
  assert.equal((await post("/api/session/exchange", { raw: "[1,2]" })).status, 401);
});

test("enrutado: métodos incorrectos y rutas desconocidas", async () => {
  assert.equal((await get("/api/session/check")).status, 405);
  assert.equal((await post("/api/ticket")).status, 405);
  assert.equal((await get("/api/discord/callback-raro")).status, 404);
  assert.equal((await post("/otra-ruta")).status, 405);
});

test("avatar: usa el avatar propio (png o gif animado) o el avatar por defecto oficial", async () => {
  const cdn = "https://cdn.discordapp.com";
  fake.user = { id: USER_ID, username: "a", avatar: "abc123" };
  let ticket = await loginTicket();
  assert.equal((await (await get(`/api/ticket?t=${ticket}`)).json()).avatar_url,
    `${cdn}/avatars/${USER_ID}/abc123.png?size=256`);

  fake.user = { id: USER_ID, username: "a", avatar: "a_xyz" };
  ticket = await loginTicket();
  assert.equal((await (await get(`/api/ticket?t=${ticket}`)).json()).avatar_url,
    `${cdn}/avatars/${USER_ID}/a_xyz.gif?size=256`);

  fake.user = { id: USER_ID, username: "a", avatar: null };
  ticket = await loginTicket();
  const index = Number((BigInt(USER_ID) >> 22n) % 6n);
  assert.equal((await (await get(`/api/ticket?t=${ticket}`)).json()).avatar_url,
    `${cdn}/embed/avatars/${index}.png`);
});

// ---------------------------------------------------------------- páginas estáticas

test("páginas: añade cabeceras de seguridad y no-store a la web estática", async () => {
  const assets = {
    fetch: async () => new Response("<!doctype html>", { headers: { "Content-Type": "text/html" } }),
  };
  const res = await worker.fetch(new Request(`${ORIGIN}/acceso/`), { ...env, ASSETS: assets });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Referrer-Policy"), "no-referrer");
  assert.equal(res.headers.get("X-Content-Type-Options"), "nosniff");
  assert.equal(res.headers.get("X-Frame-Options"), "DENY");
  assert.match(res.headers.get("Content-Security-Policy"), /frame-ancestors 'none'/);
  assert.match(res.headers.get("Content-Security-Policy"), /script-src 'self'/);
  assert.equal(res.headers.get("Content-Type"), "text/html");
});

test("páginas: sin binding de activos responde 404 y no escribe nada", async () => {
  assert.equal((await get("/")).status, 404);
});

// ---------------------------------------------------------------- respuestas sin secretos

test("seguridad: ninguna respuesta de la API contiene el secreto ni el refresh token", async () => {
  const session = await sessionFromTicket();
  const responses = [
    await post("/api/session/check", { token: session.token }),
    await post("/api/session/check", { token: "inventado" }),
    await post("/api/session/exchange", { body: { ticket: "inventado" } }),
  ];
  for (const res of responses) {
    const text = await res.text();
    assert.ok(!text.includes(CLIENT_SECRET));
    assert.ok(!text.includes("ref-1"));
    assert.ok(!text.includes("acc-"));
  }
});
