// Cloudflare Worker: хранилище подписок Web Push для дашборда PI OZON.
//
// Routes:
//   POST /subscribe       — { subscription }                  : сохраняет в KV
//   POST /unsubscribe     — { endpoint }                      : удаляет из KV
//   GET  /subscriptions   — Bearer BROADCAST_TOKEN            : возвращает все подписки
//   POST /broadcast       — Bearer BROADCAST_TOKEN, { ... }   : дамп payload в KV под ключом "last_payload"
//                                                                (фактическую отправку push делает мак из публикация_дашборда.py)
//
// CORS: пускаем GitHub Pages origin.

const ALLOWED_ORIGINS = [
  'https://maksimdodychin.github.io',
];

function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Max-Age': '86400',
  };
}

async function hashEndpoint(endpoint) {
  const data = new TextEncoder().encode(endpoint);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2,'0')).join('').slice(0, 32);
}

function json(status, body, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
  });
}

function unauthorized(env, req) {
  const auth = req.headers.get('Authorization') || '';
  return !env.BROADCAST_TOKEN || auth !== `Bearer ${env.BROADCAST_TOKEN}`;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const origin = req.headers.get('Origin') || '';

    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    try {
      if (url.pathname === '/subscribe' && req.method === 'POST') {
        const body = await req.json();
        const sub = body?.subscription;
        if (!sub?.endpoint || !sub?.keys?.p256dh || !sub?.keys?.auth) {
          return json(400, { error: 'invalid subscription' }, origin);
        }
        const key = await hashEndpoint(sub.endpoint);
        const record = { subscription: sub, ua: req.headers.get('User-Agent') || '',
                         created_at: new Date().toISOString() };
        await env.SUBS.put(key, JSON.stringify(record));
        return json(200, { ok: true, id: key }, origin);
      }

      if (url.pathname === '/unsubscribe' && req.method === 'POST') {
        const { endpoint } = await req.json();
        if (!endpoint) return json(400, { error: 'no endpoint' }, origin);
        const key = await hashEndpoint(endpoint);
        await env.SUBS.delete(key);
        return json(200, { ok: true }, origin);
      }

      if (url.pathname === '/subscriptions' && req.method === 'GET') {
        if (unauthorized(env, req)) return json(401, { error: 'unauthorized' }, origin);
        const list = await env.SUBS.list();
        const out = [];
        for (const k of list.keys) {
          const v = await env.SUBS.get(k.name);
          if (v) {
            try { out.push({ id: k.name, ...JSON.parse(v) }); } catch {}
          }
        }
        return json(200, { count: out.length, subscriptions: out }, origin);
      }

      // Удалить конкретную подписку (по id), напр. если push-сервис вернул 410 Gone
      if (url.pathname.startsWith('/subscriptions/') && req.method === 'DELETE') {
        if (unauthorized(env, req)) return json(401, { error: 'unauthorized' }, origin);
        const id = url.pathname.split('/').pop();
        await env.SUBS.delete(id);
        return json(200, { ok: true }, origin);
      }

      if (url.pathname === '/broadcast' && req.method === 'POST') {
        if (unauthorized(env, req)) return json(401, { error: 'unauthorized' }, origin);
        const payload = await req.json();
        await env.SUBS.put('__last_payload', JSON.stringify({
          payload, ts: new Date().toISOString()
        }));
        return json(200, { ok: true }, origin);
      }

      if (url.pathname === '/' || url.pathname === '/health') {
        return json(200, { ok: true, service: 'pi-ozon-push' }, origin);
      }

      return json(404, { error: 'not found' }, origin);
    } catch (e) {
      return json(500, { error: String(e?.message || e) }, origin);
    }
  }
};
