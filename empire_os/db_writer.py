#!/usr/bin/env python3
"""db_writer.py — Tier-2 single-writer gatekeeper (the durable lock fix).

PROBLEM (2026-08-29): every daemon + the ai_email_infer batch opened its own
sqlite3 writer conn. Under WAL they collided on writes / checkpoint and the
whole pipeline wedged at 93 emails until daemons were killed.

FIX: ONE process owns the only writer connection. Everyone else sends write
jobs over a Unix socket and gets a result back. Reads still use local
sqlite3.connect (readers never block writers in WAL). Writers serialize -> zero
"database is locked".

Run as a systemd service (or: nohup /root/venv/bin/python3 db_writer.py &).
Socket: /run/empire/db_writer.sock  (fallback /tmp if no /run/empire)
Protocol: newline-delimited JSON  {"sql":..., "params":[...]}
Response: {"ok":true,"rowcount":N}  or  {"ok":false,"error":"..."}
"""
from __future__ import annotations
import socket, threading, sqlite3, os, json, sys, time

DB = "/root/empire_os/empire_os.db"


def _mk() -> bool:
    try:
        os.makedirs("/run/empire", exist_ok=True)
        return True
    except Exception:
        return False


SOCK_DIR = "/run/empire" if os.path.isdir("/run/empire") or _mk() else "/tmp"
SOCK = os.path.join(SOCK_DIR, "db_writer.sock")


def get_writer():
    c = sqlite3.connect(DB, timeout=60, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=60000")
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def handle(conn_sock: socket.socket, writer: sqlite3.Connection):
    f = conn_sock.makefile("rwb")
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                job = json.loads(line)
                sql = job.get("sql", "")
                params = job.get("params", [])
                cur = writer.execute(sql, params)
                writer.commit()
                resp = json.dumps({"ok": True, "rowcount": cur.rowcount}).encode()
            except Exception as e:
                try:
                    writer.rollback()
                except Exception:
                    pass
                resp = json.dumps({"ok": False, "error": str(e)}).encode()
            f.write(resp + b"\n")
            f.flush()
    except Exception:
        pass
    finally:
        try:
            conn_sock.close()
        except Exception:
            pass


def serve():
    if os.path.exists(SOCK):
        os.remove(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    srv.listen(64)
    os.chmod(SOCK, 0o660)
    writer = get_writer()
    print(f"[db_writer] listening on {SOCK}", flush=True)
    while True:
        cs, _ = srv.accept()
        t = threading.Thread(target=handle, args=(cs, writer), daemon=True)
        t.start()


def dbwrite(sql: str, params: list = None) -> dict:
    """Client helper. Use from daemons instead of writer sqlite3.connect."""
    params = params or []
    for _ in range(5):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(30)
            s.connect(SOCK)
            s.sendall((json.dumps({"sql": sql, "params": params}) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
            s.close()
            return json.loads(buf.decode())
        except Exception as e:
            time.sleep(0.3)
            last = str(e)
    return {"ok": False, "error": f"db_writer unreachable: {last}"}


def gatekept_conn(db_path: str = DB, timeout: int = 60):
    """Return a sqlite3 conn where WRITE statements auto-route to the gatekeeper
    and SELECTs run locally (WAL readers never block). Drop-in for
    sqlite3.connect in daemons => instant Tier-3 single-writer, zero logic rewrite.
    """
    import re
    _WRITE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|PRAGMA\s+(?!journal_mode|busy_timeout|wal_checkpoint))", re.I)
    base = sqlite3.connect(db_path, timeout=timeout, check_same_thread=False)
    base.execute("PRAGMA journal_mode=WAL")
    base.execute("PRAGMA busy_timeout=60000")

    class _G:
        def __init__(self, c):
            self._c = c
        @property
        def row_factory(self):
            return self._c.row_factory
        @row_factory.setter
        def row_factory(self, v):
            self._c.row_factory = v
        def execute(self, sql, params=()):
            if _WRITE.match(sql):
                r = dbwrite(sql, list(params))
                if not r.get("ok"):
                    raise sqlite3.OperationalError(f"db_writer: {r.get('error')}")
                return _GResult(r.get("rowcount", 0))
            return self._c.execute(sql, params)
        def executemany(self, sql, seq):
            if _WRITE.match(sql):
                n = 0
                for p in seq:
                    r = dbwrite(sql, list(p))
                    n += r.get("rowcount", 0) if r.get("ok") else 0
                return _GResult(n)
            return self._c.executemany(sql, seq)
        def executescript(self, sql):
            # split into statements, route writes, ignore SELECT
            for stmt in [s for s in sql.split(";") if s.strip()]:
                if _WRITE.match(stmt):
                    r = dbwrite(stmt, [])
                    if not r.get("ok"):
                        raise sqlite3.OperationalError(f"db_writer: {r.get('error')}")
            return None
        def commit(self):
            return None  # gatekeeper commits per-statement
        def rollback(self):
            return None
        def close(self):
            return self._c.close()
        def __getattr__(self, name):
            return getattr(self._c, name)
    return _G(base)


class _GResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount
    def fetchone(self):
        return None
    def fetchall(self):
        return []
    def __iter__(self):
        return iter([])


if __name__ == "__main__":
    serve()
