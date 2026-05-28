const CACHE = 'pi-ozon-v2';
const SHELL = ['./', './index.html', './manifest.json',
               './icon-192.png', './icon-512.png', './apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('push', e => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch { data = { body: e.data?.text() || '' }; }
  const title = data.title || 'PI OZON';
  const body  = data.body  || 'Обновился индекс цен';
  const opts = {
    body,
    icon: 'icon-192.png',
    badge: 'icon-192.png',
    tag: data.tag || 'pi-update',
    renotify: true,
    data: { url: data.url || './' },
  };
  e.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data?.url || './';
  e.waitUntil((async () => {
    const all = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of all) {
      if (c.url.includes(self.registration.scope) && 'focus' in c) return c.focus();
    }
    if (clients.openWindow) return clients.openWindow(url);
  })());
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // data.json — network-first, кешируем последнее значение для офлайн
  if (url.pathname.endsWith('data.json')) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .then(r => {
          const copy = r.clone();
          caches.open(CACHE).then(c => c.put(e.request, copy));
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  // остальное — cache-first
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
      if (resp.ok) {
        const copy = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
      }
      return resp;
    }))
  );
});
