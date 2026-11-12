"""Shared test setup.

The script path may ask a small reader model how a pasted document is laid out
(``scripted._reading``). No test may reach a real model because a key happens to be in the
shell: the reader is off unless a test turns it on for a stub. The same goes for the diagram
service a script's plan may ask a picture from (``scripted.prepared_picture``).

Switching features off one by one was not enough. Importing the engine loads ``.env``, so every
test runs with the owner's real keys, and each new feature that asks a model needed its own
line below; the one nobody thought of (word alignment) sent 21 paid requests a run for two days
and wrote them into the owner's ledger. So nothing leaves the machine at all (``_nothing_leaves``):
a request to anywhere but the test's own server is refused as a connection error, which is what
the code under test would see with the network down, and listed when the run ends.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

# The components kit reads a pinned snapshot of six of the owner's component files (tests/unit/fixtures/lv_components,
# see its README), never the owner's moving lesson-visuals checkout. LESSON_VISUALS_DIR is pointed there before any test
# module imports the kits. What the shell had in it is kept in LF_TEST_REAL_LV: the one optional test that checks the kit
# against a whole real tree (test_kits_components.py) uses it and is skipped when it is empty.
# (This lives here, not in tests/unit/conftest.py: two files named conftest.py share one module name without
# __init__.py files, and test_no_network.py then cannot find REFUSED.)
os.environ.setdefault("LF_TEST_REAL_LV", os.environ.get("LESSON_VISUALS_DIR", ""))
os.environ["LESSON_VISUALS_DIR"] = str(Path(__file__).parent / "unit" / "fixtures" / "lv_components")

LOCAL = {"testserver", "localhost", "127.0.0.1", "::1", "test", ""}
REFUSED: list[tuple[str, str, str]] = []          # (host, path, test) for every outside request a test tried to make


def _refuse(url) -> bool:
    """True, and noted, when ``url`` is outside this machine. Host and path only: never a query or a key."""
    parts = urlsplit(str(url))
    if parts.scheme == "file" or (parts.hostname or "") in LOCAL:
        return False
    REFUSED.append((parts.hostname or "", parts.path[:60], os.environ.get("PYTEST_CURRENT_TEST", "").split(" ")[0]))
    return True


@pytest.fixture(autouse=True, scope="session")
def _nothing_leaves():
    """No test reaches the network, whatever keys are in the environment. A test that needs an answer stubs the call."""
    import urllib.error
    import urllib.request

    import httpx

    send, asend, opened = httpx.Client.send, httpx.AsyncClient.send, urllib.request.urlopen

    def watched(self, request, *args, **kwargs):
        if _refuse(request.url):
            raise httpx.ConnectError("tests do not reach the network: stub this call", request=request)
        return send(self, request, *args, **kwargs)

    async def awatched(self, request, *args, **kwargs):
        if _refuse(request.url):
            raise httpx.ConnectError("tests do not reach the network: stub this call", request=request)
        return await asend(self, request, *args, **kwargs)

    def urlopen(url, *args, **kwargs):
        if _refuse(getattr(url, "full_url", url)):
            raise urllib.error.URLError("tests do not reach the network: stub this call")
        return opened(url, *args, **kwargs)

    httpx.Client.send, httpx.AsyncClient.send, urllib.request.urlopen = watched, awatched, urlopen
    try:
        import requests
    except ImportError:
        requests = None
    if requests is not None:
        rsend = requests.Session.send

        def session_send(self, request, **kwargs):
            if _refuse(request.url):
                raise requests.ConnectionError("tests do not reach the network: stub this call")
            return rsend(self, request, **kwargs)

        requests.Session.send = session_send
    # boto3 (Cloudflare R2, lessonforge/cloud.py) talks through urllib3 directly, past every guard above.
    try:
        import urllib3
        from urllib3.connectionpool import HTTPConnectionPool
    except ImportError:
        urllib3 = None
    if urllib3 is not None:
        pool_open = HTTPConnectionPool.urlopen

        def pool_urlopen(self, method, url, *args, **kwargs):
            if _refuse(f"{self.scheme}://{self.host}{url if str(url).startswith('/') else '/'}"):
                raise urllib3.exceptions.NewConnectionError(self, "tests do not reach the network: stub this call")
            return pool_open(self, method, url, *args, **kwargs)

        HTTPConnectionPool.urlopen = pool_urlopen
    yield
    httpx.Client.send, httpx.AsyncClient.send, urllib.request.urlopen = send, asend, opened
    if requests is not None:
        requests.Session.send = rsend
    if urllib3 is not None:
        HTTPConnectionPool.urlopen = pool_open


def pytest_terminal_summary(terminalreporter):
    """Say so when a test tried to reach the outside: it was refused, and the call it came from wants a stub."""
    if not REFUSED:
        return
    seen: dict[tuple[str, str, str], int] = {}
    for item in REFUSED:
        seen[item] = seen.get(item, 0) + 1
    terminalreporter.section("outside requests refused (stub these calls)")
    for (host, path, test), count in sorted(seen.items(), key=lambda kv: -kv[1])[:20]:
        terminalreporter.write_line(f"{count:4d}  {host}{path}  from {test}")


@pytest.fixture(autouse=True)
def _no_reader_model(monkeypatch):
    monkeypatch.setenv("HARNESS_SCRIPT_READER", "0")
    monkeypatch.setenv("HARNESS_SCRIPT_PICTURES", "0")
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "0")      # the writer path's own asking (diagrams.for_brief)
    monkeypatch.setenv("HARNESS_TOPIC_READ", "0")          # the small model that puts a typed topic right (library.read_topic)
    monkeypatch.setenv("HARNESS_JUDGE_PICTURES", "0")      # the vision model that looks at a drawing (diagrams.judge)
    monkeypatch.setenv("HARNESS_TYPESET_NAMES", "0")       # the vision model that reads a typeset drawing's labels (typeset.names)
    monkeypatch.setenv("HARNESS_SCRIPT_REFERENCES", "0")   # reference lectures for a pasted script (library.reference_for_script)
    monkeypatch.setenv("HARNESS_PICTURE_HOLDS", "0")       # the vision model that reads what a drawing holds (card.add_holds)
    monkeypatch.setenv("HARNESS_DRAW_WITH_WORDS", "0")     # the model that plans when each thing of a drawing is drawn (sequence.with_words)
    monkeypatch.setenv("HARNESS_ANNOTATE", "0")            # the model that ideates what a hand adds to a drawing (annotate.for_lesson)
    monkeypatch.setenv("HARNESS_LECTURER_VOICE", "0")      # lectures found on YouTube for the writer's manner (voice.examples_for)
    monkeypatch.setenv("HARNESS_CONCEPTS", "0")            # the concept knowledge base (harness/concepts.py): a test that wants it turns it on
    monkeypatch.setenv("HARNESS_EXPLANATIONS", "0")        # the NCERT explanation table (harness/explanations.py)
    # A finished lesson is sent to Cloudflare R2 when its keys are in .env (harness/publish.py); a test that wants
    # publishing points LESSONFORGE_CLOUD_DIR at a folder and turns it on.
    monkeypatch.setenv("LESSONFORGE_PUBLISH", "0")
    monkeypatch.delenv("LESSONFORGE_CLOUD_DIR", raising=False)
    # Word alignment is on whenever a key is set, and importing the engine loads .env: five tests in test_longform
    # sent 21 real speech-recognition requests a run and wrote them into the owner's own ledger (147 rows of
    # "0 words" by 2026-10-09). A test that wants alignment asks for it (BuildOptions(align="on")) with a stub.
    monkeypatch.setenv("LESSONFORGE_ALIGN", "0")
