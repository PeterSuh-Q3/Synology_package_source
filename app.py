#!/usr/bin/env python3
"""Small Synology Package Center feed backed by PeterSuh-Q3 GitHub SPKs."""

import json
import hashlib
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "data" / "assets.json"
ICON_ROOT = ROOT / "data" / "icons"
ASSET_ROOT = ROOT / "assets"
LANDING_PAGE = ROOT / "landing.html"
EXCLUDED_PACKAGES = {"Samplepackage"}  # ScriptNotify's example package.
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
            "desc": info.get("description") or package,
            "link": asset["url"],
            "size": asset["size"],
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
        self.send_header("Cache-Control", "public, max-age=300")
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
                     "version": a.get("info", {}).get("version")}
                    for a in assets]
            return self.send_body(200, json.dumps({"assets": rows}, ensure_ascii=False),
                                  "application/json; charset=utf-8")
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


def periodic_sync():
    while True:
        try:
            from tools.sync_releases import sync
            from tools.sync_icons import sync as sync_icons
            sync()
            sync_icons()
        except Exception as exc:
            print(f"release sync failed: {exc}", flush=True)
        time.sleep(6 * 3600)


if __name__ == "__main__":
    if os.environ.get("SYNC_RELEASES", "1") == "1":
        threading.Thread(target=periodic_sync, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8765"))), Handler).serve_forever()
