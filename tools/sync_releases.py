#!/usr/bin/env python3
"""Refresh the SPK catalog from the owner's public GitHub releases."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from tools.build_inventory import read_info


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "assets.json"
REPOS = (
    "ChangePanelSize", "mshell-manager-rel", "ScriptNotify",
    "syno-amdgpu-driver", "syno-amdgpu-top", "syno-gpu-monitor",
    "syno-intel-gpu-top", "SynoSmartInfo", "syno_nvidia_driver",
)


def github_releases(repo):
    result = subprocess.run(
        ["curl", "-fsSL", "--retry", "2", "--max-time", "30",
         "-H", "Accept: application/vnd.github+json", "-H", "User-Agent: petersuh-package-source",
         f"https://api.github.com/repos/PeterSuh-Q3/{repo}/releases?per_page=100"],
        capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(f"GitHub releases unavailable for {repo}: {result.stderr[-200:]}")
    releases = json.loads(result.stdout)
    if not isinstance(releases, list):
        raise RuntimeError(f"Unexpected GitHub response for {repo}")
    return releases


def sync():
    existing = json.loads(TARGET.read_text())
    by_url = {item["url"]: item for item in existing}
    added = 0
    counts_updated = 0
    changed = False
    for repo in REPOS:
        for release in github_releases(repo):
            if release.get("draft") or release.get("prerelease"):
                continue
            for asset in release.get("assets", []):
                if not asset["name"].lower().endswith(".spk"):
                    continue
                url = asset["browser_download_url"]
                download_count = asset.get("download_count")
                current = by_url.get(url)
                if current is not None:
                    if isinstance(download_count, int) and current.get("download_count") != download_count:
                        current["download_count"] = download_count
                        counts_updated += 1
                        changed = True
                    continue
                record = read_info({
                    "repo": repo, "tag": release["tag_name"],
                    "published_at": release.get("published_at"),
                    "name": asset["name"], "url": url, "size": asset["size"],
                })
                if "info" not in record:
                    print(f"skipping {repo}/{asset['name']}: {record.get('error')}", flush=True)
                    continue
                if isinstance(download_count, int):
                    record["download_count"] = download_count
                by_url[url] = record
                added += 1
                changed = True
    if changed:
        TARGET.parent.mkdir(exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="assets-", suffix=".json", dir=TARGET.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(list(by_url.values()), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, TARGET)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(f"release sync complete: {added} new SPKs, {counts_updated} download counts updated, "
          f"{len(by_url)} total", flush=True)


if __name__ == "__main__":
    sync()
