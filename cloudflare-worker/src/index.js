let latestEvent = null;

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { headers: cors() });
    if (url.pathname === "/health" && request.method === "GET")
      return json({ ok: true, mode: "PAPER_ONLY" });
    if (url.pathname === "/event" && request.method === "POST") {
      let event;
      try { event = await request.json(); }
      catch { return json({ error: "Invalid JSON" }, 400); }
      if (event.mode !== "PAPER_ONLY" || event.type !== "paper_opportunity")
        return json({ error: "Only paper events accepted" }, 400);
      latestEvent = event;
      return json({ accepted: true });
    }
    if (url.pathname === "/latest" && request.method === "GET")
      return json({ mode: "PAPER_ONLY", event: latestEvent });
    return json({ error: "Not found" }, 404);
  }
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status, headers: { "content-type": "application/json", ...cors() }
  });
}
function cors() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type"
  };
}
