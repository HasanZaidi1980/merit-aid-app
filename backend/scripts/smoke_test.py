"""Boot the real server over generated sample data and hit it over HTTP.

What this adds over `pytest`. The suite calls the app in-process through TestClient,
which never starts uvicorn, never binds a socket and never reads $DATA_DIR the way a
container does. This script does: it generates the sample dataset into a throwaway
directory, launches `uvicorn app.main:app`, waits for `/api/health`, and then asks
the questions a deployment check asks -- is the dataset there, does the ranking come
back, and does bad input still get refused by a real server rather than only by the
test client.

Everything here is synthetic. `make_sample_data.py` invents its colleges (UNITID
100000+), so no figure this prints describes a real institution, and no row can carry
a merit-aid verdict -- which the script asserts, because attaching a real
institution's published aid policy to an invented college would be worse than leaving
the column dark.

    cd backend && python scripts/smoke_test.py

Writes nothing to backend/data/. Exits 0 on success, 1 with the reason on failure.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOT_TIMEOUT_S = 90
EXPECTED_FIELDS = 27


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, timeout: float = 30.0):
    """GET returning (status, parsed body). A 4xx/5xx is an answer here, not a crash."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (localhost)
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, body.decode("utf-8", "replace")


def _wait_for_health(url: str, proc: subprocess.Popen) -> None:
    deadline = time.time() + BOOT_TIMEOUT_S
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited during boot with code {proc.returncode}")
        try:
            status, body = _get(url, timeout=2.0)
            if status == 200 and body == {"ok": True}:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.4)
    raise RuntimeError(f"server never answered {url} within {BOOT_TIMEOUT_S}s")


def _check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{label}: {detail}" if detail else label)
    print(f"  ok   {label}")


def main() -> int:
    data_dir = tempfile.mkdtemp(prefix="merit-aid-smoke-")
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    proc = None
    try:
        print(f"[1/4] generating sample data in {data_dir}")
        subprocess.run([sys.executable, os.path.join(BACKEND, "scripts", "make_sample_data.py"),
                        data_dir], check=True, cwd=BACKEND)
        with open(os.path.join(data_dir, "HD2022.csv"), encoding="latin-1") as f:
            sampled = sum(1 for _ in f) - 1          # minus the header

        print(f"[2/4] booting uvicorn on {port}")
        env = {**os.environ, "DATA_DIR": data_dir, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=BACKEND, env=env)
        _wait_for_health(f"{base}/api/health", proc)
        print("  ok   /api/health")

        print("[3/4] checking the endpoints a deployment check would call")
        status, meta = _get(f"{base}/api/meta")
        _check("/api/meta answers 200", status == 200, str(status))
        # Every sampled college reports tuition, a grant and a net price by
        # construction, so none should be dropped. A mismatch means the generator and
        # the read path have drifted apart.
        _check("the whole sample dataset loaded",
               meta["colleges_in_dataset"] == sampled,
               f"{meta['colleges_in_dataset']} of {sampled} rows survived cleaning")
        _check("the methodology notes ship with the numbers",
               "need-based and merit" in meta["metric_notes"]["grant_aid"])
        _check("coverage is reported as resolved of attempted",
               {"verified", "attempted", "scope"} <= set(meta["merit_policy_coverage"]))

        status, body = _get(f"{base}/api/colleges?top_n=5")
        _check("/api/colleges answers 200", status == 200, str(status))
        _check("the ranking comes back", body["count"] == 5, str(body["count"]))
        rows = body["colleges"]
        _check(f"each row carries {EXPECTED_FIELDS} fields",
               all(len(r) == EXPECTED_FIELDS for r in rows),
               f"{sorted(len(r) for r in rows)}")
        _check("RANK is 1..n with no gaps",
               [r["RANK"] for r in rows] == [1, 2, 3, 4, 5])
        _check("VALUE_SCORE is present and descending",
               all(r["VALUE_SCORE"] is not None for r in rows)
               and [r["VALUE_SCORE"] for r in rows] == sorted(
                   (r["VALUE_SCORE"] for r in rows), reverse=True))
        # The honesty property of sample mode: invented colleges get no verdict.
        _check("no invented college carries a merit-aid verdict",
               {r["MERIT_POLICY"] for r in rows} == {"unknown"},
               str({r["MERIT_POLICY"] for r in rows}))

        print("[4/4] checking bad input is refused by a real server, not just TestClient")
        status, body = _get(f"{base}/api/colleges?top_n=-1")
        _check("top_n=-1 is a 422, not a 200 with n-1 colleges", status == 422, str(status))
        status, body = _get(f"{base}/api/colleges?max_netprice=60000")
        _check("an unknown filter is a 400 naming it",
               status == 400 and "max_netprice" in json.dumps(body), str(status))

        print("\nSMOKE OK -- server booted over sample data and answered correctly.")
        print("(Every figure above is synthetic: see scripts/make_sample_data.py.)")
        return 0
    except Exception as e:
        print(f"\nSMOKE FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
