# -*- coding: utf-8 -*-
"""Minimal pywebview smoke app for the frozen Windows packaging path.

This intentionally stays independent from the real bridge and real frontends.
Use it to prove that pywebview, WebView2, pythonnet/clr-loader, and a js_api
call still work after PyInstaller freezes the app.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from typing import Any


APP_NAME = "pywebview-smoke"
APP_VERSION = "0.1"


class SmokeApi:
    def ping(self) -> dict[str, Any]:
        return {
            "ok": True,
            "message": "pong",
            "frozen": bool(getattr(sys, "frozen", False)),
            "cwd": os.getcwd(),
            "python": sys.version.split()[0],
            "time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }


def _import_probe() -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "app": APP_NAME,
        "version": APP_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "modules": {},
    }
    for module_name in (
        "webview",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "clr_loader",
    ):
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            result["ok"] = False
            result["modules"][module_name] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        else:
            result["modules"][module_name] = {
                "ok": True,
                "file": str(getattr(module, "__file__", "")),
            }
    return result


def _html() -> str:
    return """<!doctype html>
<html lang="zh-Hant">
<meta charset="utf-8">
<title>pywebview smoke</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#eef4fc;color:#0c2f5e}
main{max-width:760px;margin:64px auto;padding:32px;background:white;border-radius:12px;box-shadow:0 18px 50px rgba(12,47,94,.18)}
h1{margin:0 0 8px;font-size:28px}
p{margin:0 0 18px;color:#5f7190}
pre{padding:16px;border-radius:8px;background:#f4f7fb;white-space:pre-wrap}
.ok{color:#0d8a4a}.err{color:#ba1a1a}
</style>
<main>
  <h1>pywebview packaging smoke</h1>
  <p>Waiting for pywebviewready, then calling js_api.ping().</p>
  <pre id="result">pending...</pre>
</main>
<script>
window.addEventListener("pywebviewready", async () => {
  const result = document.getElementById("result");
  try {
    const payload = await window.pywebview.api.ping();
    result.className = payload && payload.ok ? "ok" : "err";
    result.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    result.className = "err";
    result.textContent = String(error && error.stack || error);
  }
});
</script>
</html>"""


def run_window(*, debug: bool = False) -> int:
    try:
        import webview
    except ImportError:
        print("pywebview is missing. Install requirements.txt first.", file=sys.stderr)
        return 2

    webview.create_window(
        "pywebview packaging smoke",
        html=_html(),
        js_api=SmokeApi(),
        width=820,
        height=560,
        min_size=(640, 420),
    )
    try:
        webview.start(debug=debug)
    except Exception as exc:
        print(f"pywebview failed to start: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Minimal pywebview packaging smoke app")
    parser.add_argument("--health-check", action="store_true", help="probe imports without opening a window")
    parser.add_argument("--version", action="store_true", help="print the smoke app version")
    parser.add_argument("--debug", action="store_true", help="open pywebview devtools while testing")
    args = parser.parse_args(argv)

    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if args.health_check:
        result = _import_probe()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 2
    return run_window(debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
