// Brojač poseta: samo upis (anonimni ID iz pregledača, bez ličnih podataka). Brojevi se ne prikazuju javno.
export async function onRequestPost({ request, env }) {
  let vid = "";
  try { vid = String((await request.json()).vid || ""); } catch (e) {}
  if (!/^[a-z0-9]{12,40}$/.test(vid)) return new Response("bad id", { status: 400 });
  await env.DB.prepare("INSERT INTO posete (vid) VALUES (?)").bind(vid).run();
  return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
}
