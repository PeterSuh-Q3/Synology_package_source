#!/usr/bin/env python3
"""Small Synology Package Center feed backed by PeterSuh-Q3 GitHub SPKs."""

import json
import hashlib
import hmac
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from tools.sync_releases import REPOS as TRACKED_REPOS


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "data" / "assets.json"
ICON_ROOT = ROOT / "data" / "icons"
ASSET_ROOT = ROOT / "assets"
LANDING_PAGE = ROOT / "landing.html"
CATALOG_PAGE = ROOT / "catalog.html"
EXCLUDED_PACKAGES = {"Samplepackage"}  # ScriptNotify's example package.
GITHUB_OWNER = "PeterSuh-Q3"
WEBHOOK_REPOS = {
    f"{GITHUB_OWNER}/{repo}" for repo in TRACKED_REPOS
}
MAX_WEBHOOK_BYTES = 64 * 1024
sync_requested = threading.Event()
sync_worker_lock = threading.Lock()
X64_PLATFORMS = {
    "apollolake", "avoton", "braswell", "broadwell", "broadwellnk",
    "broadwellnkv2", "broadwellntbap", "bromolow", "denverton",
    "epyc7002", "epyc7003", "epyc7003ntb", "geminilake",
    "geminilakenk", "icelaked", "kvmx64", "purley", "r1000",
    "r1000nk", "v1000", "v1000nk",
}


def numbers(value):
    return tuple(int(x) for x in re.findall(r"\d+", value or ""))


def dsm_compatible(info, name, major, minor, build):
    target = (major, minor, build)
    minimum = numbers(info.get("os_min_ver"))
    maximum = numbers(info.get("os_max_ver"))
    if minimum and target < (minimum + (0, 0, 0))[:3]:
        return False
    if maximum and target > (maximum + (99999, 99999, 99999))[:3]:
        return False
    # These two vendor-specific SPKs omit os_max_ver from INFO.
    if "kver4-dsm70" in name and (major, minor) > (7, 1):
        return False
    if "kver4-dsm72" in name and (major, minor) > (7, 4):
        return False
    return True


def arch_compatible(info, arch):
    supported = set(info.get("arch", "").split())
    return ("noarch" in supported or arch in supported or
            (arch in X64_PLATFORMS and "x86_64" in supported))


def feed(assets, query, base_url):
    try:
        arch = query["arch"][0]
        major = int(query["major"][0])
        minor = int(query["minor"][0])
        build = int(query.get("build", ["0"])[0])
    except (KeyError, ValueError, IndexError):
        return {"packages": []}
    chosen = {}
    for asset in assets:
        info = asset.get("info")
        if not info or info["package"] in EXCLUDED_PACKAGES:
            continue
        if not arch_compatible(info, arch) or not dsm_compatible(info, asset["name"], major, minor, build):
            continue
        package = info["package"]
        current = chosen.get(package)
        if current is None or (numbers(info["version"]), asset.get("published_at", "")) > (
            numbers(current["info"]["version"]), current.get("published_at", "")
        ):
            chosen[package] = asset
    packages = []
    language = (query.get("language", ["enu"])[0] or "enu").lower()
    description_field = {"krn": "description_krn", "enu": "description_enu"}.get(language, "description_enu")
    for package, asset in sorted(chosen.items()):
        info = asset["info"]
        icon_name = f"{package}.png"
        retina_name = f"{package}_256.png"
        def thumbnail_url(name):
            path = ICON_ROOT / name
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            except OSError:
                return []
            return [f"{base_url}/icons/{quote(name)}?v={digest}"]

        thumbnail = thumbnail_url(icon_name)
        thumbnail_retina = thumbnail_url(retina_name)
        row = {
            "package": package,
            "version": info["version"],
            "dname": info.get("displayname") or package,
            "desc": info.get(description_field) or info.get("description_enu") or info.get("description") or package,
            "link": asset["url"],
            "size": asset["size"],
            "download_count": asset.get("download_count", 0),
            "maintainer": info.get("maintainer") or "PeterSuh-Q3",
            "maintainer_url": info.get("maintainer_url") or "https://github.com/PeterSuh-Q3",
            "distributor": info.get("distributor") or "PeterSuh-Q3",
            "distributor_url": info.get("distributor_url") or "https://github.com/PeterSuh-Q3",
            "deppkgs": info.get("install_dep_packages") or None,
            "thumbnail": thumbnail,
            "thumbnail_retina": thumbnail_retina,
            "snapshot": [],
            "qinst": False,
            "qstart": False,
            "qupgrade": False,
            "startable": info.get("startable", "no"),
            "changelog": "",
        }
        if asset.get("md5"):
            row["md5"] = asset["md5"]
        packages.append(row)
    return {"packages": packages}


class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, body, content_type):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        cache_control = "no-store" if self.command == "POST" else "public, max-age=300"
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            return self.send_body(200, "ok\n", "text/plain; charset=utf-8")
        if parsed.path.startswith("/assets/"):
            name = parsed.path.removeprefix("/assets/")
            if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", name):
                return self.send_body(404, "not found\n", "text/plain; charset=utf-8")
            try:
                return self.send_body(200, (ASSET_ROOT / name).read_bytes(), "image/png")
            except OSError:
                return self.send_body(404, "not found\n", "text/plain; charset=utf-8")
        if parsed.path.startswith("/icons/"):
            name = parsed.path.removeprefix("/icons/")
            if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", name):
                return self.send_body(404, "not found\n", "text/plain; charset=utf-8")
            try:
                return self.send_body(200, (ICON_ROOT / name).read_bytes(), "image/png")
            except OSError:
                return self.send_body(404, "not found\n", "text/plain; charset=utf-8")
        try:
            assets = json.loads(INVENTORY.read_text())
        except (OSError, json.JSONDecodeError):
            return self.send_body(503, "inventory unavailable\n", "text/plain; charset=utf-8")
        if parsed.path == "/catalog.json":
            rows = [{"repo": a["repo"], "name": a["name"], "url": a["url"],
                     "package": a.get("info", {}).get("package"),
                     "displayname": a.get("info", {}).get("displayname"),
                     "version": a.get("info", {}).get("version"),
                     "download_count": a.get("download_count"),
                     "size": a.get("size")}
                    for a in assets]
            return self.send_body(200, json.dumps({"assets": rows}, ensure_ascii=False),
                                  "application/json; charset=utf-8")
        if parsed.path == "/catalog":
            try:
                body = CATALOG_PAGE.read_bytes()
            except OSError:
                return self.send_body(503, "catalog page unavailable\n", "text/plain; charset=utf-8")
            return self.send_body(200, body, "text/html; charset=utf-8")
        if parsed.path != "/":
            return self.send_body(404, "not found\n", "text/plain; charset=utf-8")
        query = parse_qs(parsed.query)
        if "arch" in query and "major" in query and "minor" in query:
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
            proto = self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip()
            if not proto:
                proto = "https" if host == "nas.dante90.mmv.kr" else "http"
            if proto not in {"http", "https"}:
                proto = "https"
            base_url = f"{proto}://{host}"
            return self.send_body(200, json.dumps(feed(assets, query, base_url), ensure_ascii=False),
                                  "application/json; charset=utf-8")
        try:
            body = LANDING_PAGE.read_bytes()
        except OSError:
            return self.send_body(503, "landing page unavailable\n", "text/plain; charset=utf-8")
        return self.send_body(200, body, "text/html; charset=utf-8")

    def do_POST(self):
        parsed = urlsplit(self.path)
        if parsed.path != "/webhook/github":
            return self.send_body(404, "not found\n", "text/plain; charset=utf-8")
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
        if not secret:
            return self.send_body(503, "webhook is not configured\n", "text/plain; charset=utf-8")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_body(400, "invalid content length\n", "text/plain; charset=utf-8")
        if length <= 0 or length > MAX_WEBHOOK_BYTES:
            return self.send_body(413, "invalid webhook payload size\n", "text/plain; charset=utf-8")
        body = self.rfile.read(length)
        signature = self.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return self.send_body(401, "invalid webhook signature\n", "text/plain; charset=utf-8")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.send_body(400, "invalid JSON payload\n", "text/plain; charset=utf-8")
        if not isinstance(payload, dict) or not isinstance(payload.get("repository"), dict):
            return self.send_body(400, "invalid GitHub payload shape\n", "text/plain; charset=utf-8")
        repository = payload["repository"].get("full_name", "")
        event = self.headers.get("X-GitHub-Event", "")
        action = payload.get("action", "")
        if repository not in WEBHOOK_REPOS:
            return self.send_body(403, "repository is not tracked\n", "text/plain; charset=utf-8")
        if event == "release":
            if action not in {"published", "released", "edited", "prereleased"}:
                return self.send_body(202, "ignored event\n", "text/plain; charset=utf-8")
        elif event != "release_asset_upload":
            return self.send_body(202, "ignored event\n", "text/plain; charset=utf-8")
        queue_release_sync()
        return self.send_body(202, "release sync queued\n", "text/plain; charset=utf-8")


def periodic_sync():
    while True:
        queue_release_sync()
        time.sleep(6 * 3600)


def sync_catalog_once():
    from tools.sync_releases import sync
    from tools.sync_icons import sync as sync_icons
    sync()
    sync_icons()


def _sync_worker():
    try:
        while sync_requested.wait():
            sync_requested.clear()
            try:
                sync_catalog_once()
            except Exception as exc:
                print(f"release sync failed: {exc}", flush=True)
    finally:
        sync_worker_lock.release()
        # Close the race where a request arrived as the worker was exiting.
        if sync_requested.is_set():
            queue_release_sync()


def queue_release_sync():
    sync_requested.set()
    if sync_worker_lock.acquire(blocking=False):
        threading.Thread(target=_sync_worker, daemon=True).start()


if __name__ == "__main__":
    if os.environ.get("SYNC_RELEASES", "1") == "1":
        threading.Thread(target=periodic_sync, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8765"))), Handler).serve_forever()
