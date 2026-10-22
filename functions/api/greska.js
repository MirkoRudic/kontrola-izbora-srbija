// Greške iz pregledača (za praćenje rada aplikacije). Bez ličnih podataka; ograničena veličina.
export async function onRequestPost({ request, env }) {
  let d = {};
  try { d = await request.json(); } catch (e) {}
  const s = (x, n) => String(x == null ? "" : x).slice(0, n);
  const msg = s(d.msg, 400); if (!msg) return new Response("prazno", { status: 400 });
  try {
    await env.DB.prepare("INSERT INTO greske (msg, src, ua, url) VALUES (?, ?, ?, ?)")
      .bind(msg, s(d.src, 200), s(request.headers.get("user-agent"), 160), s(d.url, 120)).run();
  } catch (e) { return new Response("db", { status: 500 }); }
  return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
}
