"""Run Alfred's HTTP acceptance suite and optionally write a compact JSON report.

Examples (from the repository root):
  ai/.venv/bin/python ai/scripts/check_backend.py --local --report /tmp/backend.json
  ai/.venv/bin/python ai/scripts/check_backend.py --api-url https://synthetic.example

Tests create synthetic sessions and submit explicit fixture reviews/evaluations.
Local mode uses a temporary SQLite database and always stops its own server.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import httpx

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ROUTES = (
    ("get", "/api/v1/security/context"),
    ("post", "/api/v1/authz/evaluation"),
    ("post", "/api/v1/audit/events"),
    ("post", "/api/v1/facts/{}/review"),
    ("post", "/api/v1/patients/{}/evaluations"),
    ("get", "/api/v1/relate/family-history"),
    ("get", "/api/v1/relate/care-plans"),
    ("post", "/api/v1/security/verified-context"),
)


def normalized_path(path):
    return "/".join("{}" if part.startswith("{") and part.endswith("}") else part for part in path.split("/"))


def preflight(url):
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            response = client.get(url + "/openapi.json")
            response.raise_for_status()
        paths = response.json()["paths"]
        declared = {(method, normalized_path(path)) for path, operations in paths.items() for method in operations}
        return {"status": "checked", "missing_routes": [f"{method.upper()} {path}"
                for method, path in REQUIRED_ROUTES if (method, path) not in declared]}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        # OpenAPI availability does not substitute for executing the HTTP tests.
        return {"status": "unavailable", "missing_routes": None}


@contextmanager
def local_api(directory, env):
    missing = [name for name in ("uvicorn", "fastapi", "sqlalchemy", "pydantic_settings")
               if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError("Install ai/requirements-integration.txt; missing " + ", ".join(missing))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    child_env = dict(env, NAMAA_DATABASE_URL=f"sqlite:///{directory}/synthetic.sqlite3",
                     NAMAA_EXTRACTION_MODE="offline_fixture", NAMAA_FHIR_GATEWAY_MODE="stub")
    with (directory / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                    "--port", str(port)], cwd=ROOT, env=child_env, stdout=log, stderr=log)
        try:
            with httpx.Client(timeout=1, trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Temporary synthetic API exited during startup")
                    try:
                        if client.get(url + "/health").is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Temporary synthetic API startup timed out")
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def run_checks(url, directory, env, rule_cases):
    # Validate URL policy without printing a URL that could contain credentials.
    sys.path.insert(0, str(ROOT / "ai/src"))
    from namaa_ai.backend import BackendApiClient
    BackendApiClient(url, {"X-Namaa-Session": "url-validation-only"})
    url = url.rstrip("/")
    child_env = dict(env, NAMAA_AI_TEST_API_URL=url)
    markers = "live_security or live_bridges"
    if rule_cases:
        child_env["NAMAA_AI_TEST_RULE_CASES"] = str(Path(rule_cases).resolve())
        markers += " or live_rule_outcomes"
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "target": "synthetic_api",
              "openapi": preflight(url), "rule_outcome_fixtures_selected": bool(rule_cases),
              "hapi_commit_verified": False}
    junit = directory / "results.xml"
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no", "--require-backend",
        "-m", markers, f"--junitxml={junit}", "ai/tests/integration/test_live_backend.py"],
        cwd=ROOT, env=child_env, timeout=120)
    checks = []
    if junit.exists():
        for case in ET.parse(junit).iter("testcase"):
            status = next((tag for tag in ("failure", "error", "skipped") if case.find(tag) is not None), "passed")
            # Deliberately omit response bodies, headers, note text and traceback payloads.
            checks.append({"name": case.attrib["name"], "status": status})
    report.update(exit_code=result.returncode, checks=checks,
                  counts={status: sum(c["status"] == status for c in checks)
                          for status in ("passed", "failure", "error", "skipped")})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--local", action="store_true", help="Start an isolated local synthetic API")
    target.add_argument("--api-url", help="Existing synthetic API origin; otherwise use NAMAA_AI_TEST_API_URL")
    parser.add_argument("--rule-cases", default=os.getenv("NAMAA_AI_TEST_RULE_CASES"),
                        help="Backend seed mapping JSON; adds all four canonical-outcome tests")
    parser.add_argument("--report", type=Path, help="Write compact JSON evidence without response payloads")
    args = parser.parse_args()
    url = args.api_url or os.getenv("NAMAA_AI_TEST_API_URL")
    if not args.local and not url:
        parser.error("Use --local, --api-url, or NAMAA_AI_TEST_API_URL; no target is selected")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / "api"), str(ROOT / "ai/src"))))
    try:
        with tempfile.TemporaryDirectory(prefix="namaa-acceptance-") as name:
            directory = Path(name)
            if args.local:
                with local_api(directory, env) as local_url:
                    report = run_checks(local_url, directory, env, args.rule_cases)
                report["target"] = "temporary_local_synthetic_api"
            else:
                report = run_checks(url, directory, env, args.rule_cases)
    except subprocess.TimeoutExpired:
        report = {"exit_code": 2, "error": "acceptance_suite_timed_out", "hapi_commit_verified": False}
    except (RuntimeError, ValueError, OSError) as error:
        report = {"exit_code": 2, "error": type(error).__name__, "hapi_commit_verified": False}
        print("Acceptance setup failed. Check target configuration and integration dependencies.", file=sys.stderr)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded)
    print(encoded, end="")
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
