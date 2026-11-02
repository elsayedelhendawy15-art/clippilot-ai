const MAX_BODY_BYTES = 8192;
const MAX_EVENT_AGE_MS = 5 * 60 * 1000;
let latestEvent = null; // in-memory only; D1 history comes in a later step

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(env.ALLOWED_ORIGIN || "https://clippilot-ai.pages.dev");

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });

    if (url.pathname === "/health") {
      if (request.method !== "GET") return json({ error: "Method not allowed" }, 405, cors);
      return json({ ok: true, mode: "PAPER_ONLY" }, 200, cors);
    }

    if (url.pathname === "/latest") {
      if (request.method !== "GET") return json({ error: "Method not allowed" }, 405, cors);
      return json({ mode: "PAPER_ONLY", event: latestEvent }, 200, cors);
    }

    if (url.pathname === "/event") {
      if (request.method !== "POST") return json({ error: "Method not allowed" }, 405, cors);
      if (!env.INGEST_TOKEN) return json({ error: "Server not configured" }, 503, cors);
      if (!(await authorized(request, env.INGEST_TOKEN))) return json({ error: "Unauthorized" }, 401, cors);

      if (Number(request.headers.get("content-length") || 0) > MAX_BODY_BYTES)
        return json({ error: "Payload too large" }, 413, cors);
      const text = await request.text();
      if (text.length > MAX_BODY_BYTES) return json({ error: "Payload too large" }, 413, cors);

      let raw;
      try { raw = JSON.parse(text); }
      catch { return json({ error: "Invalid JSON" }, 400, cors); }

      const event = validateEvent(raw);
      if (!event) return json({ error: "Invalid event" }, 400, cors);
      latestEvent = event;
      return json({ accepted: true }, 200, cors);
    }

    return json({ error: "Not found" }, 404, cors);
  }
};

async function authorized(request, token) {
  const header = request.headers.get("authorization") || "";
  const provided = header.startsWith("Bearer ") ? header.slice(7) : "";
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(provided)),
    crypto.subtle.digest("SHA-256", enc.encode(token))
  ]);
  const x = new Uint8Array(a), y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const isStr = (v, max) => typeof v === "string" && v.length > 0 && v.length <= max;

function validateEvent(e) {
  if (!e || typeof e !== "object" || Array.isArray(e)) return null;
  if (e.mode !== "PAPER_ONLY" || e.type !== "paper_opportunity") return null;
  if (!isNum(e.timestamp_ms)) return null;
  const now = Date.now();
  if (Math.abs(now - e.timestamp_ms) > MAX_EVENT_AGE_MS) return null;

  if (!Array.isArray(e.cycle) || e.cycle.length < 3 || e.cycle.length > 5) return null;
  if (!e.cycle.every((s) => isStr(s, 12))) return null;
  if (e.cycle[0] !== e.cycle[e.cycle.length - 1]) return null;
  if (!isStr(e.start_asset, 12)) return null;
  for (const k of ["start_amount", "end_amount", "profit", "profit_bps"])
    if (!isNum(e[k])) return null;
  if (e.start_amount <= 0) return null;
  if (Math.abs(e.end_amount - e.start_amount - e.profit) > 1e-6 * Math.max(1, e.start_amount)) return null;

  if (!Array.isArray(e.legs) || e.legs.length !== e.cycle.length - 1) return null;
  const legs = [];
  for (const l of e.legs) {
    if (!l || !isStr(l.from, 12) || !isStr(l.to, 12)) return null;
    if (!isNum(l.input) || !isNum(l.rate) || !isNum(l.output_after_costs)) return null;
    legs.push({ from: l.from, to: l.to, input: l.input, rate: l.rate, output_after_costs: l.output_after_costs });
  }

  return {
    type: "paper_opportunity", mode: "PAPER_ONLY",
    timestamp_ms: e.timestamp_ms, received_ms: now,
    cycle: [...e.cycle], start_asset: e.start_asset,
    start_amount: e.start_amount, end_amount: e.end_amount,
    profit: e.profit, profit_bps: e.profit_bps, legs
  };
}

function json(data, status, cors) {
  return new Response(JSON.stringify(data), {
    status, headers: { "content-type": "application/json", ...cors }
  });
}

function corsHeaders(origin) {
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,OPTIONS",
    "access-control-allow-headers": "content-type",
    "vary": "origin"
  };
}
