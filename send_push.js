#!/usr/bin/env node
// Получает все подписки из worker и шлёт Web Push каждому подписчику.
// Запуск:
//   node send_push.js '<JSON payload>'
// ENV:
//   PUSH_API           — https://pi-ozon-push.<sub>.workers.dev
//   BROADCAST_TOKEN    — Bearer token
//   VAPID_PUBLIC, VAPID_PRIVATE, VAPID_SUBJECT
const webpush = require('web-push');

const API   = process.env.PUSH_API;
const TOKEN = process.env.BROADCAST_TOKEN;
const PUB   = process.env.VAPID_PUBLIC;
const PRIV  = process.env.VAPID_PRIVATE;
const SUBJ  = process.env.VAPID_SUBJECT || 'mailto:noreply@example.com';

if (!API || !TOKEN || !PUB || !PRIV) {
  console.error('Missing env: PUSH_API / BROADCAST_TOKEN / VAPID_PUBLIC / VAPID_PRIVATE');
  process.exit(2);
}

webpush.setVapidDetails(SUBJ, PUB, PRIV);

const payload = process.argv[2] || JSON.stringify({ title: 'PI OZON', body: 'test' });

(async () => {
  const r = await fetch(`${API}/subscriptions`, {
    headers: { 'Authorization': `Bearer ${TOKEN}` },
  });
  if (!r.ok) { console.error('GET /subscriptions:', r.status); process.exit(3); }
  const { subscriptions } = await r.json();
  if (!subscriptions?.length) { console.log('no subscriptions'); return; }

  let ok = 0, gone = 0, err = 0;
  for (const s of subscriptions) {
    try {
      await webpush.sendNotification(s.subscription, payload, { TTL: 600 });
      ok++;
    } catch (e) {
      if (e.statusCode === 410 || e.statusCode === 404) {
        await fetch(`${API}/subscriptions/${s.id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${TOKEN}` },
        }).catch(()=>{});
        gone++;
      } else {
        err++;
        console.error(`push fail ${s.id}: ${e.statusCode} ${e.body || e.message}`);
      }
    }
  }
  console.log(`push: ok=${ok}, удалено(410)=${gone}, ошибок=${err}, всего=${subscriptions.length}`);
})();
