#!/usr/bin/env python3
"""Сгенерировать data.json для PWA-дашборда и запушить в GitHub Pages.

Запускается:
  - вручную: python3 публикация_дашборда.py
  - из утреннего пайплайна, после обновить_pi.py / корректировка_pi.py
"""
import os, sys, json, subprocess
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_SCRIPT = os.path.expanduser('~/Desktop/Massimo/Скрипты/утро/дашборд_данные.py')
DATA_JSON = os.path.join(HERE, 'data.json')

def msk_now_iso():
    return datetime.now(timezone(timedelta(hours=3))).isoformat(timespec='seconds')

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def build_data():
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
    return data

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

def main():
    build_data()
    git_push()

if __name__ == '__main__':
    main()
