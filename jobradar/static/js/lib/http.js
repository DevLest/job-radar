/* POST to the app; always resolves to the JSON body ({ ok, message, ... }). */
export async function post(url, data = {}, asForm = false) {
  const opts = { method: 'POST', headers: { 'X-Requested-With': 'fetch' } };
  if (asForm) opts.body = data; else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(data); }
  const r = await fetch(url, opts);
  let body = {};
  try { body = await r.json(); } catch (e) { body = { ok: false, message: 'Something went wrong' }; }
  if (!r.ok && body.ok === undefined) body.ok = false;
  return body;
}
