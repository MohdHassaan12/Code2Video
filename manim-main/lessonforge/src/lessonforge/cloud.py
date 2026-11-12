"""Cloud storage for the viewer site: Cloudflare R2 for files and records, Cloudflare D1 for what viewers write.

Lessons are MADE on the GPU machine (the studio server); the finished ones are shown from Render
(``lessonforge/viewer.py``, ``docs/DEPLOY_RENDER_VIEWER.md``). Render's own disk keeps nothing across a deploy,
so everything that must last lives here:

* **R2** (S3-compatible object storage, reached with boto3): the published lessons' files under
  ``lessons/<job_id>/…``, each lesson's record under ``api/jobs/<job_id>.json`` and the list under
  ``api/jobs.json`` (``harness/publish.py`` writes them).
* **D1** (Cloudflare's SQLite, reached over its REST API): reviews, try-it answers and the dashboard's
  events written by viewers (:data:`SCHEMA`; the viewer creates the tables).

``LESSONFORGE_CLOUD_DIR`` replaces both with a folder on this machine (objects as files, the database as
an SQLite file running the SAME SQL), so tests and a trial run need no Cloudflare at all.

Settings (the owner's names, the same as in their other project): ``CLOUDFLARE_ACCOUNT_ID``,
``CLOUDFLARE_R2_BUCKET``, ``CLOUDFLARE_R2_ACCESS_KEY_ID``, ``CLOUDFLARE_R2_SECRET_ACCESS_KEY``,
``CLOUDFLARE_D1_DATABASE_ID`` and ``CLOUDFLARE_API_TOKEN`` (or ``CLOUDFLARE_EMAIL`` with the global
``CLOUDFLARE_API_KEY``). An error always names the settings that are missing.

Nothing here imports the engine, the renderer or the harness: the viewer's image has none of them.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import quote

ENV_DIR = "LESSONFORGE_CLOUD_DIR"
ACCOUNT = "CLOUDFLARE_ACCOUNT_ID"
R2_SETTINGS = (ACCOUNT, "CLOUDFLARE_R2_BUCKET", "CLOUDFLARE_R2_ACCESS_KEY_ID", "CLOUDFLARE_R2_SECRET_ACCESS_KEY")
D1_SETTINGS = (ACCOUNT, "CLOUDFLARE_D1_DATABASE_ID")
TOKEN, EMAIL, GLOBAL_KEY = "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_EMAIL", "CLOUDFLARE_API_KEY"

#: Where things live in the bucket. The viewer reads exactly what ``harness/publish.py`` writes.
JOBS_KEY = "api/jobs.json"
PRESIGN_SECONDS = 6 * 3600            # a video link handed to a browser stays good for a long lesson and its seeks
D1_PARAMS_PER_QUERY = 100             # D1 refuses a statement with more bound parameters

#: The viewer's tables. Every statement runs on D1 and on the local SQLite file alike.
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL, job_id TEXT, "
    "form_version TEXT, reviewer TEXT, contact TEXT, lesson TEXT, answers TEXT NOT NULL, auto TEXT)",
    "CREATE INDEX IF NOT EXISTS reviews_by_job ON reviews (kind, job_id, at)",
    "CREATE TABLE IF NOT EXISTS tryit (id TEXT PRIMARY KEY, at REAL NOT NULL, job_id TEXT NOT NULL, reviewer TEXT, "
    "done_in_class INTEGER NOT NULL DEFAULT 0, prediction TEXT, observation TEXT, answer TEXT)",
    "CREATE INDEX IF NOT EXISTS tryit_by_job ON tryit (job_id, at)",
    "CREATE TABLE IF NOT EXISTS events (at REAL NOT NULL, event TEXT NOT NULL, visitor TEXT NOT NULL, role TEXT, "
    "device TEXT, browser TEXT, os TEXT, country TEXT, test INTEGER NOT NULL DEFAULT 0, job_id TEXT, value TEXT, "
    "extra TEXT)",
    "CREATE INDEX IF NOT EXISTS events_by_time ON events (at)",
)

_JOB_ID = re.compile(r"^[\w.-]{1,80}$")


class NotConfigured(RuntimeError):
    """A cloud service was asked for and its settings are not there; the message names them."""


class CloudError(RuntimeError):
    """The service answered with an error (the message is the service's own, never a key)."""


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def safe_job_id(job_id: str) -> bool:
    return bool(_JOB_ID.match(str(job_id or ""))) and not str(job_id).startswith(".")


def job_key(job_id: str) -> str:
    return f"api/jobs/{job_id}.json"


def lesson_prefix(job_id: str) -> str:
    return f"lessons/{job_id}/"


def lesson_key(job_id: str, rel: str) -> str:
    return lesson_prefix(job_id) + rel


def content_type(name: str) -> str:
    lower = name.lower()
    for ending, kind in ((".vtt", "text/vtt; charset=utf-8"), (".json", "application/json"),
                         (".md", "text/markdown; charset=utf-8"), (".html", "text/html; charset=utf-8"),
                         (".mp4", "video/mp4"), (".webm", "video/webm")):
        if lower.endswith(ending):
            return kind
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _md5_file(path: Path) -> str:
    digest = hashlib.md5()                               # noqa: S324 - a content fingerprint, as S3's ETag is
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ── what is configured ────────────────────────────────────────────────────────

def local_dir() -> Path | None:
    raw = _env(ENV_DIR)
    return Path(raw).expanduser().resolve() if raw else None


def missing_r2() -> list[str]:
    return [name for name in R2_SETTINGS if not _env(name)]


def missing_d1() -> list[str]:
    missing = [name for name in D1_SETTINGS if not _env(name)]
    if not _env(TOKEN) and not (_env(EMAIL) and _env(GLOBAL_KEY)):
        missing.append(f"{TOKEN} (or {EMAIL} and {GLOBAL_KEY})")
    return missing


def configured() -> bool:
    """Whether finished lessons can be published: R2 is set up, or a local folder stands in for it."""
    return local_dir() is not None or not missing_r2()


def describe() -> dict:
    """What this process would use, without contacting anything (for ``/healthz`` and the publish command)."""
    folder = local_dir()
    return {"objects": "local" if folder else ("r2" if not missing_r2() else None),
            "database": "local" if folder else ("d1" if not missing_d1() else None),
            "missing": [] if folder else sorted(set(missing_r2() + missing_d1()))}


_CLIENTS: dict[tuple, object] = {}
_CLIENTS_LOCK = threading.Lock()


def objects():
    """The object store in force: :class:`LocalObjects` with ``LESSONFORGE_CLOUD_DIR``, else :class:`R2`."""
    folder = local_dir()
    key = ("objects", str(folder)) if folder else ("objects",) + tuple(_env(n) for n in R2_SETTINGS)
    with _CLIENTS_LOCK:
        if key not in _CLIENTS:
            if folder:
                _CLIENTS[key] = LocalObjects(folder)
            else:
                missing = missing_r2()
                if missing:
                    raise NotConfigured("Cloudflare R2 is not set up: " + ", ".join(missing) + " missing "
                                        f"(or set {ENV_DIR} to a folder for a trial on this machine).")
                _CLIENTS[key] = R2(*(_env(n) for n in R2_SETTINGS))
        return _CLIENTS[key]


def database():
    """The viewer's database: :class:`LocalD1` with ``LESSONFORGE_CLOUD_DIR``, else :class:`D1`."""
    folder = local_dir()
    key = ("db", str(folder)) if folder else ("db",) + tuple(_env(n) for n in D1_SETTINGS + (TOKEN, EMAIL, GLOBAL_KEY))
    with _CLIENTS_LOCK:
        if key not in _CLIENTS:
            if folder:
                _CLIENTS[key] = LocalD1(folder / "d1.sqlite3")
            else:
                missing = missing_d1()
                if missing:
                    raise NotConfigured("Cloudflare D1 is not set up: " + ", ".join(missing) + " missing "
                                        f"(or set {ENV_DIR} to a folder for a trial on this machine).")
                _CLIENTS[key] = D1(_env(ACCOUNT), _env("CLOUDFLARE_D1_DATABASE_ID"), token=_env(TOKEN),
                                   email=_env(EMAIL), key=_env(GLOBAL_KEY))
        return _CLIENTS[key]


def schema(db=None) -> None:
    """Create the viewer's tables when they are missing (idempotent; one statement per request)."""
    db = db or database()
    for statement in SCHEMA:
        db.query(statement)


def insert_many(db, table: str, columns: tuple[str, ...], rows: list[tuple]) -> int:
    """Several rows in as few statements as D1's parameter limit allows. Returns how many were written."""
    if not rows:
        return 0
    per = max(1, D1_PARAMS_PER_QUERY // len(columns))
    one = "(" + ",".join("?" * len(columns)) + ")"
    for start in range(0, len(rows), per):
        chunk = rows[start:start + per]
        db.query(f"INSERT INTO {table} ({','.join(columns)}) VALUES " + ",".join([one] * len(chunk)),
                 [value for row in chunk for value in row])
    return len(rows)


# ── R2 ────────────────────────────────────────────────────────────────────────

class _Objects:
    """What both stores add on top of their own get/put/list/delete."""

    def put_json(self, key: str, data) -> bool:
        return self.put_bytes(key, _json_bytes(data), "application/json")

    def get_json(self, key: str):
        return _json_or_none(self.get_bytes(key))

    def delete_prefix(self, prefix: str) -> int:
        keys = self.list(prefix)
        for key in keys:
            self.delete(key)
        return len(keys)


class R2(_Objects):
    """A bucket through R2's S3 API. Every method is safe to call again: uploads skip what is already there."""

    kind = "r2"

    def __init__(self, account: str, bucket: str, key_id: str, secret: str):
        import boto3
        from botocore.config import Config

        settings = dict(region_name="auto", signature_version="s3v4", connect_timeout=10, read_timeout=120,
                        retries={"max_attempts": 3, "mode": "standard"})
        try:   # newer botocore adds checksums R2 may not accept; ask for them only when an operation needs one
            config = Config(**settings, request_checksum_calculation="when_required",
                            response_checksum_validation="when_required")
        except TypeError:
            config = Config(**settings)
        self.bucket = bucket
        self.s3 = boto3.client("s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
                               aws_access_key_id=key_id, aws_secret_access_key=secret, config=config)

    @staticmethod
    def _missing(exc) -> bool:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        return code in ("404", "NoSuchKey", "NotFound")

    def head(self, key: str) -> dict | None:
        from botocore.exceptions import ClientError
        try:
            r = self.s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if self._missing(exc):
                return None
            raise
        return {"size": int(r.get("ContentLength") or 0), "etag": str(r.get("ETag") or "").strip('"'),
                "md5": str((r.get("Metadata") or {}).get("md5") or "")}

    def exists(self, key: str) -> bool:
        return self.head(key) is not None

    def _same(self, key: str, size: int, md5: str) -> bool:
        there = self.head(key)
        # A file sent in parts has an ETag that is not its MD5: the MD5 kept beside it says the same.
        return bool(there) and there["size"] == size and md5 in (there["md5"], there["etag"])

    def upload_file(self, path, key: str, kind: str | None = None) -> bool:
        """Send a file unless the bucket already has it byte for byte. True when it was sent."""
        path = Path(path)
        size, md5 = path.stat().st_size, _md5_file(path)
        if self._same(key, size, md5):
            return False
        self.s3.upload_file(str(path), self.bucket, key,
                            ExtraArgs={"ContentType": kind or content_type(path.name), "Metadata": {"md5": md5}})
        return True

    def put_bytes(self, key: str, data: bytes, kind: str = "application/octet-stream") -> bool:
        md5 = hashlib.md5(data).hexdigest()               # noqa: S324
        if self._same(key, len(data), md5):
            return False
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=kind, Metadata={"md5": md5})
        return True

    def get_bytes(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if self._missing(exc):
                return None
            raise

    def list(self, prefix: str = "") -> list[str]:
        keys = []
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys += [item["Key"] for item in page.get("Contents") or []]
        return keys

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)

    def presign(self, key: str, seconds: int = PRESIGN_SECONDS) -> str:
        """A link anyone may GET (with ranges) until it expires. Made here; nothing is asked of R2."""
        return self.s3.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key},
                                              ExpiresIn=int(seconds))


class LocalObjects(_Objects):
    """R2 stood in for by a folder (``LESSONFORGE_CLOUD_DIR/r2``). Its links are signed paths the viewer serves."""

    kind = "local"
    ROUTE = "/_cloud/object/"

    def __init__(self, root: Path):
        self.base = Path(root)
        self.root = self.base / "r2"
        self.root.mkdir(parents=True, exist_ok=True)
        secret = self.base / "link_secret"
        if not secret.is_file():
            secret.write_text(secrets.token_hex(24), encoding="utf-8")
        self._secret = secret.read_text(encoding="utf-8").strip().encode()

    def path(self, key: str) -> Path:
        parts = [p for p in str(key).split("/") if p]
        if not parts or any(p in (".", "..") for p in parts) or str(key).startswith("/"):
            raise ValueError(f"not an object key: {key!r}")
        return self.root.joinpath(*parts)

    def head(self, key: str) -> dict | None:
        path = self.path(key)
        if not path.is_file():
            return None
        md5 = _md5_file(path)
        return {"size": path.stat().st_size, "etag": md5, "md5": md5}

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def _same(self, key: str, size: int, md5: str) -> bool:
        there = self.head(key)
        return bool(there) and there["size"] == size and there["md5"] == md5

    def upload_file(self, path, key: str, kind: str | None = None) -> bool:
        path = Path(path)
        if self._same(key, path.stat().st_size, _md5_file(path)):
            return False
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        shutil.copyfile(path, part)
        os.replace(part, target)
        return True

    def put_bytes(self, key: str, data: bytes, kind: str = "application/octet-stream") -> bool:
        if self._same(key, len(data), hashlib.md5(data).hexdigest()):   # noqa: S324
            return False
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        part.write_bytes(data)
        os.replace(part, target)
        return True

    def get_bytes(self, key: str) -> bytes | None:
        path = self.path(key)
        return path.read_bytes() if path.is_file() else None

    def list(self, prefix: str = "") -> list[str]:
        keys = []
        for path in self.root.rglob("*"):
            if path.is_file() and not path.name.endswith(".part"):
                key = path.relative_to(self.root).as_posix()
                if key.startswith(prefix):
                    keys.append(key)
        return sorted(keys)

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def _signature(self, key: str, expires: int) -> str:
        return hmac.new(self._secret, f"{key}|{expires}".encode(), hashlib.sha256).hexdigest()[:32]

    def presign(self, key: str, seconds: int = PRESIGN_SECONDS) -> str:
        expires = int(time.time() + seconds)
        return f"{self.ROUTE}{quote(key)}?e={expires}&s={self._signature(key, expires)}"

    def signed(self, key: str, expires: str, signature: str) -> bool:
        try:
            when = int(expires)
        except (TypeError, ValueError):
            return False
        return when >= time.time() and hmac.compare_digest(self._signature(key, when), str(signature or ""))


def _json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _json_or_none(raw: bytes | None):
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


# ── D1 ────────────────────────────────────────────────────────────────────────

class D1:
    """One D1 database through Cloudflare's REST API: ``POST …/d1/database/{id}/query`` with ``{sql, params}``."""

    kind = "d1"
    URL = "https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{database}/query"

    def __init__(self, account: str, database: str, token: str = "", email: str = "", key: str = "", timeout: float = 20.0):
        self.url = self.URL.format(account=account, database=database)
        self.headers = ({"Authorization": f"Bearer {token}"} if token else {"X-Auth-Email": email, "X-Auth-Key": key})
        self.timeout = timeout

    def query(self, sql: str, params=()) -> list[dict]:
        """The rows the statement returns (an empty list for one that returns none). ``CloudError`` on a refusal."""
        import httpx

        body = {"sql": sql, "params": [int(p) if isinstance(p, bool) else p for p in params]}
        last = None
        for attempt in range(2):                      # once more on a dropped connection or a 5xx
            try:
                reply = httpx.post(self.url, json=body, headers=self.headers, timeout=self.timeout)
            except httpx.HTTPError as exc:
                last = CloudError(f"D1 could not be reached: {type(exc).__name__}")
                continue
            if reply.status_code >= 500 and attempt == 0:
                last = CloudError(f"D1 answered {reply.status_code}")
                continue
            try:
                data = reply.json()
            except ValueError:
                raise CloudError(f"D1 answered {reply.status_code} with something that is not JSON")
            if reply.status_code >= 400 or not data.get("success", False):
                errors = "; ".join(str(e.get("message", e)) for e in data.get("errors") or []) or str(reply.status_code)
                raise CloudError(f"D1 refused the query: {errors[:300]}")
            result = data.get("result") or []
            return list((result[0] or {}).get("results") or []) if result else []
        raise last or CloudError("D1 query failed")


class LocalD1:
    """D1 stood in for by an SQLite file, running the same SQL with the same ``?`` parameters."""

    kind = "local"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def query(self, sql: str, params=()) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(self.path, timeout=10)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql, [int(p) if isinstance(p, bool) else p for p in params])
                rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
                conn.commit()
                return rows
            except sqlite3.Error as exc:
                raise CloudError(f"the local database refused the query: {exc}") from exc
            finally:
                conn.close()
