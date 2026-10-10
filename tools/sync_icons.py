#!/usr/bin/env python3
"""Extract Package Center icons from the latest SPKs without downloading full packages."""

import concurrent.futures
import base64
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "assets.json"
ICON_ROOT = ROOT / "data" / "icons"
MANIFEST = ICON_ROOT / "index.json"
RANGE_BYTES = 1048576


def version_key(value):
    return tuple(int(part) for part in re.findall(r"\d+", value or ""))


def latest_assets(assets):
    chosen = {}
    for asset in assets:
        info = asset.get("info") or {}
        package = info.get("package", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", package):
            continue
        current = chosen.get(package)
        rank = (version_key(info.get("version")), asset.get("published_at", ""))
        current_rank = ((version_key(current["info"].get("version")),
                         current.get("published_at", "")) if current else None)
        if current is None or rank > current_rank:
            chosen[package] = asset
    return chosen


def fetch_range(url, start):
    result = subprocess.run(
        ["curl", "-fsSL", "--retry", "2", "--max-time", "60", "-r",
         f"{start}-{start + RANGE_BYTES - 1}", url],
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-250:])
    return result.stdout


def extract_icons(data):
    found = {}
    next_offset = None
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r|*") as archive:
            for member in archive:
                basename = member.name.rsplit("/", 1)[-1]
                key = {"PACKAGE_ICON.PNG": "icon", "PACKAGE_ICON_256.PNG": "retina"}.get(basename)
                if key and member.isfile() and member.size <= 2 * 1024 * 1024:
                    stream = archive.extractfile(member)
                    data = stream.read() if stream else b""
                    if data.startswith(b"\x89PNG\r\n\x1a\n"):
                        found[key] = data
                elif basename == "INFO" and member.isfile() and member.size <= RANGE_BYTES:
                    stream = archive.extractfile(member)
                    raw_info = stream.read().decode("utf-8", errors="replace") if stream else ""
                    for line in raw_info.splitlines():
                        match = re.fullmatch(r'package_icon(_256)?="([A-Za-z0-9+/=]+)"', line)
                        if match:
                            key = "retina" if match.group(1) else "icon"
                            decoded = base64.b64decode(match.group(2))
                            if decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                                found[key] = decoded
                if basename == "package.tgz" and member.isfile():
                    next_offset = member.offset_data + ((member.size + 511) // 512) * 512
                    break
                if len(found) == 2:
                    break
    except (tarfile.TarError, EOFError):
        pass
    return found, next_offset


def download_icon_files(asset):
    data = fetch_range(asset["url"], 0)
    found, next_offset = extract_icons(data)
    if len(found) < 2 and next_offset is not None:
        later, _ = extract_icons(fetch_range(asset["url"], next_offset))
        found.update(later)

    if not found:
        raise RuntimeError("SPK range contains no valid PACKAGE_ICON PNG")
    return found


def extract_one(item):
    package, asset, manifest = item
    icon = ICON_ROOT / f"{package}.png"
    retina = ICON_ROOT / f"{package}_256.png"
    existing = manifest.get(package, {})
    if existing.get("url") == asset["url"]:
        if icon.is_file() and retina.is_file():
            return package, "unchanged"
        if existing.get("missing_icon"):
            return package, "unchanged-missing"

    try:
        files = download_icon_files(asset)
    except Exception as exc:
        return package, f"missing ({exc})"
    if "retina" not in files:
        files["retina"] = files.get("icon")
    if "icon" not in files:
        files["icon"] = files["retina"]
    ICON_ROOT.mkdir(parents=True, exist_ok=True)
    for path, key in ((icon, "icon"), (retina, "retina")):
        fd, temporary = tempfile.mkstemp(prefix="icon-", dir=ICON_ROOT)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(files[key])
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return package, "updated"


def sync():
    assets = json.loads(INVENTORY.read_text())
    try:
        manifest = json.loads(MANIFEST.read_text())
    except (OSError, json.JSONDecodeError):
        manifest = {}
    selected = latest_assets(assets)
    ICON_ROOT.mkdir(parents=True, exist_ok=True)

    items = [(package, asset, manifest) for package, asset in selected.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(extract_one, items))

    statuses = dict(results)
    new_manifest = {}
    for package, asset in selected.items():
        new_manifest[package] = {
            "url": asset["url"],
            "version": asset.get("info", {}).get("version", ""),
            "missing_icon": (statuses.get(package, "").startswith("missing") or
                             statuses.get(package) == "unchanged-missing"),
        }
    temporary = MANIFEST.with_suffix(".tmp")
    temporary.write_text(json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, MANIFEST)

    updated = sum(status == "updated" for _, status in results)
    print(f"icon sync complete: {updated} updated, {len(results)} packages", flush=True)
    for package, status in results:
        if status not in {"unchanged", "unchanged-missing"}:
            print(f"icon {status}: {package}", flush=True)


if __name__ == "__main__":
    sync()
