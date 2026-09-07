"""Private, versioned ledger. Replay is intentionally confined to one personal account."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .domain import Conflict, Invalid, apply, digest, encoded, initial, stamp


def now():
    return datetime.now(timezone.utc).isoformat()


class PortfolioStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise Invalid('个人数据库版本高于当前服务，须使用兼容代码')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS account_history(id INTEGER PRIMARY KEY, payload TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL, replaces INTEGER REFERENCES events(id), reversed_by INTEGER, reason TEXT);
                CREATE TABLE IF NOT EXISTS ledger_snapshots(version INTEGER PRIMARY KEY, state TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS submissions(key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS valuations(id INTEGER PRIMARY KEY, at TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL, version INTEGER NOT NULL, valid INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, dedupe TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, result TEXT, error TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, report_id INTEGER, mode TEXT NOT NULL, at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS suggestions(id TEXT PRIMARY KEY, report_id INTEGER NOT NULL REFERENCES reports(id), payload TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, at TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')
        self.path.chmod(0o600)

    def _account(self, db):
        row = db.execute('SELECT * FROM account WHERE id=1').fetchone()
        return {'account': json.loads(row['payload']), 'version': row['version']} if row else None

    def account(self):
        with self.connection() as db:
            result = self._account(db)
            if not result:
                return {'account': None, 'version': 0, 'state': None}
            result['state'] = self.replay(db, result['account'])
            return result

    def active_events(self, db, until=None):
        rows = [dict(r) for r in db.execute('SELECT * FROM events WHERE reversed_by IS NULL')]
        for row in rows:
            row['payload'] = json.loads(row['payload'])
        rows.sort(key=lambda r: (stamp(r['payload']['at']), r['id']))
        return [r for r in rows if until is None or stamp(r['payload']['at']) <= stamp(until)]

    def replay(self, db, account, *, until=None, replace=None, extra=None):
        state = initial(account)
        events = [r for r in self.active_events(db, until) if r['id'] != replace]
        if extra:
            events.append({'id': 'new', 'payload': extra})
        events.sort(key=lambda r: (stamp(r['payload']['at']), int(r['id']) if r['id'] != 'new' else 2**63))
        for row in events:
            state, _ = apply(state, account, row['payload'], str(row['id']))
        return state

    def save_account(self, payload):
        account = payload['account']
        state = initial(account)
        with self.connection(True) as db:
            old = self._account(db)
            version = old['version'] if old else 0
            if payload.get('version') != version:
                raise Conflict('账户版本已变化，请重新读取')
            if old and not payload.get('reason'):
                raise Invalid('修订期初须填写原因')
            if old:
                self.replay(db, account)
            db.execute('INSERT INTO account_history(payload,reason,created_at) VALUES(?,?,?)', (encoded(account), payload.get('reason', '期初建账'), now()))
            db.execute('INSERT OR REPLACE INTO account VALUES(1,?,?)', (encoded(account), version+1))
            db.execute('INSERT INTO ledger_snapshots VALUES(?,?,?)',(version+1,encoded(self.replay(db,account)),now()))
            db.execute('UPDATE valuations SET valid=0')
            db.execute('INSERT INTO audit(kind,payload,at) VALUES(?,?,?)', ('account', encoded({'version': version+1}), now()))
        return self.account()

    def events(self):
        with self.connection() as db:
            return [{**dict(r), 'payload': json.loads(r['payload'])} for r in db.execute('SELECT * FROM events ORDER BY id DESC')]

    def _preview(self, db, request):
        current = self._account(db)
        if not current:
            raise Invalid('请先建立个人账户')
        if request.get('version') != current['version']:
            raise Conflict('账本已变化，请保留输入并重新预览')
        event = request['event']
        replacement = request.get('replaces')
        old = db.execute('SELECT * FROM events WHERE id=? AND reversed_by IS NULL', (replacement,)).fetchone() if replacement else None
        if replacement and (not old or not request.get('reason')):
            raise Invalid('修订须指定有效原记录和修订原因')
        # Replay the affected timeline first. This also detects invalid future closes after a correction.
        final = self.replay(db, current['account'], replace=replacement, extra=event)
        previous = self.replay(db, current['account'], until=event['at'], replace=replacement)
        _, summary = apply(previous, current['account'], event)
        duplicate = any(digest(r['payload']) == digest(event) for r in self.active_events(db) if r['id'] != replacement)
        if duplicate:
            summary['warnings'].append('发现疑似重复事件，请核对并显式确认')
        token = digest({'version': current['version'], 'event': event, 'replaces': replacement, 'reason': request.get('reason'), 'summary': summary})
        return {'version': current['version'], 'preview_hash': token, 'summary': summary,
                'duplicate': duplicate, 'state': final}

    def preview(self, request):
        with self.connection() as db:
            result = self._preview(db, request)
            result.pop('state')
            return result

    def commit(self, request):
        key = request.get('idempotency_key')
        if not isinstance(key, str) or not 8 <= len(key) <= 128:
            raise Invalid('提交编号须为 8–128 字符')
        request_hash = digest(request)
        with self.connection(True) as db:
            old = db.execute('SELECT * FROM submissions WHERE key=?', (key,)).fetchone()
            if old:
                if old['request_hash'] != request_hash:
                    raise Conflict('相同提交编号对应不同内容')
                return json.loads(old['result'])
            result = self._preview(db, request)
            if request.get('preview_hash') != result['preview_hash']:
                raise Conflict('预览摘要已失效，请重新预览')
            if result['duplicate'] and not request.get('confirm_duplicate'):
                raise Invalid('须显式核对疑似重复事件')
            event_id = db.execute('INSERT INTO events(payload,created_at,replaces,reason) VALUES(?,?,?,?)',
                                  (encoded(request['event']), now(), request.get('replaces'), request.get('reason'))).lastrowid
            affected = stamp(request['event']['at'])
            if request.get('replaces'):
                old_event = json.loads(db.execute('SELECT payload FROM events WHERE id=?', (request['replaces'],)).fetchone()[0])
                affected = min(affected, stamp(old_event['at']))
                db.execute('UPDATE events SET reversed_by=? WHERE id=?', (event_id, request['replaces']))
            db.execute('UPDATE account SET version=version+1 WHERE id=1')
            for v in db.execute('SELECT id,at FROM valuations WHERE valid=1').fetchall():
                if stamp(v['at']) >= affected:
                    db.execute('UPDATE valuations SET valid=0 WHERE id=?', (v['id'],))
            db.execute('INSERT INTO ledger_snapshots VALUES(?,?,?)',(result['version']+1,encoded(self.replay(db,self._account(db)['account'])),now()))
            result.pop('state')
            result.update(event_id=event_id, version=result['version']+1)
            db.execute('INSERT INTO submissions VALUES(?,?,?)', (key, request_hash, encoded(result)))
            return result

    def setting(self):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM settings WHERE id=1').fetchone()
            return json.loads(row[0]) if row else {}

    def set_setting(self, value):
        with self.connection(True) as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES(1,?)', (encoded(value),))
