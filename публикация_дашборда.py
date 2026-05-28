#!/usr/bin/env python3
"""Сгенерировать data.json для PWA-дашборда, запушить в GitHub Pages и отправить
Web Push подписчикам, если данные изменились.

Запускается:
  - вручную: python3 публикация_дашборда.py
  - из утреннего пайплайна, после обновить_pi.py / пересчитать_после_загрузки.py
"""
import os, sys, json, subprocess
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_SCRIPT = os.path.expanduser('~/Desktop/Massimo/Скрипты/утро/дашборд_данные.py')
DATA_JSON = os.path.join(HERE, 'data.json')
SECRETS_DIR = os.path.join(HERE, '.secrets')
PUSH_CONFIG = os.path.join(SECRETS_DIR, 'push_config.json')  # { api, token } — записывается после деплоя worker
VAPID_FILE = os.path.join(SECRETS_DIR, 'vapid.json')
SEND_PUSH_JS = os.path.join(HERE, 'send_push.js')

def msk_now_iso():
    return datetime.now(timezone(timedelta(hours=3))).isoformat(timespec='seconds')

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def _core_snapshot(data):
    """Сравнимая часть data.json — без updated_at, чтобы не пушить просто из-за времени."""
    keep = {}
    for k in ('date', 'ko', 'at', 'itogo'):
        keep[k] = data.get(k)
    return json.dumps(keep, sort_keys=True, ensure_ascii=False)

def build_data():
    # Загрузить старое для дельты
    old = None
    if os.path.exists(DATA_JSON):
        try:
            with open(DATA_JSON, encoding='utf-8') as f: old = json.load(f)
        except: old = None

    r = run(['/usr/bin/python3', DATA_SCRIPT])
    if r.returncode != 0:
        print('❌ дашборд_данные.py упал:', r.stderr, file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(r.stdout.strip())
    except json.JSONDecodeError as e:
        print('❌ Некорректный JSON:', e, file=sys.stderr)
        print(r.stdout[:500], file=sys.stderr)
        sys.exit(1)
    data['updated_at'] = msk_now_iso()
    with open(DATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'✅ Записан {DATA_JSON}')

    changed = (old is None) or (_core_snapshot(old) != _core_snapshot(data))
    return data, old, changed

def git_push():
    if not os.path.isdir(os.path.join(HERE, '.git')):
        print('ℹ️  git-репо ещё не инициализирован — пропускаю push.')
        print('   Massimo: см. ИНСТРУКЦИЯ.md в этой же папке.')
        return
    # Есть ли remote?
    rem = run(['git', '-C', HERE, 'remote'])
    if not rem.stdout.strip():
        print('ℹ️  remote ещё не настроен — пропускаю push.')
        return
    # Проверим, есть ли что коммитить
    st = run(['git', '-C', HERE, 'status', '--porcelain'])
    if not st.stdout.strip():
        print('ℹ️  Нет изменений для коммита.')
        return
    run(['git', '-C', HERE, 'add', '-A'])
    msg = f'data: {msk_now_iso()}'
    c = run(['git', '-C', HERE, 'commit', '-m', msg])
    if c.returncode != 0:
        print('⚠️  commit:', c.stderr.strip()); return
    p = run(['git', '-C', HERE, 'push'])
    if p.returncode != 0:
        print('⚠️  push:', p.stderr.strip()); return
    print(f'✅ Запушено: {msg}')

def send_push(data, old):
    """Отправить Web Push подписчикам через send_push.js. Триггер — только если
    «ядро» data.json изменилось (см. _core_snapshot)."""
    if not os.path.exists(PUSH_CONFIG) or not os.path.exists(VAPID_FILE):
        print('ℹ️  push ещё не настроен (нет .secrets/push_config.json) — пропускаю.')
        return
    if not os.path.exists(SEND_PUSH_JS):
        print('ℹ️  send_push.js не найден — пропускаю.'); return
    try:
        cfg = json.load(open(PUSH_CONFIG, encoding='utf-8'))
        vapid = json.load(open(VAPID_FILE, encoding='utf-8'))
    except Exception as e:
        print('⚠️  push config:', e); return

    ko = (data.get('ko') or {})
    at = (data.get('at') or {})
    itogo = (data.get('itogo') or {})

    def fmt(v): return '—' if v is None else f'{v:.3f}'
    def delta_str(d):
        if d is None or d == 0: return ''
        return f' ({"+" if d>0 else ""}{d:.3f})'

    title = f'PI OZON: КО {fmt(ko.get("f1"))} · АТ {fmt(at.get("f1"))}'
    body_parts = [
        f'КО {fmt(ko.get("f1"))}{delta_str(ko.get("delta"))} {ko.get("status","")}',
        f'АТ {fmt(at.get("f1"))}{delta_str(at.get("delta"))} {at.get("status","")}',
        f'ИТОГО {fmt(itogo.get("f1"))}{delta_str(itogo.get("delta"))}',
    ]
    payload = json.dumps({
        'title': title,
        'body': '\n'.join(body_parts),
        'tag': 'pi-' + (data.get('date','').split(' ')[0] if data.get('date') else 'now'),
        'url': 'https://maksimdodychin.github.io/PI-Ozon/',
    }, ensure_ascii=False)

    env = {
        **os.environ,
        'PUSH_API':         cfg.get('api',''),
        'BROADCAST_TOKEN':  cfg.get('token',''),
        'VAPID_PUBLIC':     vapid.get('publicKey',''),
        'VAPID_PRIVATE':    vapid.get('privateKey',''),
        'VAPID_SUBJECT':    vapid.get('subject','mailto:noreply@example.com'),
    }
    r = subprocess.run(['/usr/bin/env', 'node', SEND_PUSH_JS, payload],
                       capture_output=True, text=True, env=env, timeout=60)
    if r.stdout: print(r.stdout.rstrip())
    if r.returncode != 0:
        print('⚠️  send_push:', r.stderr.rstrip())

def main():
    data, old, changed = build_data()
    git_push()
    if changed:
        send_push(data, old)
    else:
        print('ℹ️  core не изменился — push не шлю.')

if __name__ == '__main__':
    main()
