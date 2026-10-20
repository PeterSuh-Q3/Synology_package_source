#!/usr/bin/env python3
"""Refresh the SPK catalog from the owner's public GitHub releases."""

import json
import os
import re
import subprocess
import tempfile
import sys
from pathlib import Path

from tools.build_inventory import read_info


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "assets.json"
NVIDIA_ALLOWLIST = ROOT / "data" / "nvidia-packages.json"
REPOS = (
    "ChangePanelSize", "mshell-manager-rel", "ScriptNotify",
    "syno-amdgpu-driver", "syno-amdgpu-top", "syno-gpu-monitor",
    "syno-intel-gpu-top", "SynoSmartInfo", "syno_nvidia_driver",
)


def version_numbers(value):
    return tuple(int(part) for part in re.findall(r"\d+", value or ""))


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


def latest_allowed_nvidia(records, allowlist):
    allowed = {(details["repo"], package_id) for package_id, details in allowlist.items()}
    latest = {}
    for record in records:
        info = record.get("info") or {}
        key = (record.get("repo"), info.get("package"))
        if key not in allowed:
            continue
        version_key = (version_numbers(info.get("version")), record.get("published_at", ""))
        if key not in latest or version_key > latest[key][0]:
            latest[key] = (version_key, info.get("version"))

    selected = []
    removed = 0
    managed_repos = {details["repo"] for details in allowlist.values()}
    for record in records:
        info = record.get("info") or {}
        key = (record.get("repo"), info.get("package"))
        if key in allowed:
            if info.get("version") != latest.get(key, (None, None))[1]:
                removed += 1
                continue
        elif record.get("repo") in managed_repos and info.get("package", "").startswith("syno-nvidia-"):
            # Do not resurrect retired NVIDIA package IDs from old releases.
            removed += 1
            continue
        selected.append(record)
    return selected, removed


def sync():
    existing = json.loads(TARGET.read_text())
    nvidia_allowed = json.loads(NVIDIA_ALLOWLIST.read_text())
    allowed_nvidia = {
        (details["repo"], package_id)
        for package_id, details in nvidia_allowed.items()
    }
    by_url = {item["url"]: item for item in existing}
    added = 0
    counts_updated = 0
    changed = False
    selected_repos = ("syno-gpu-monitor", "syno_nvidia_driver") if "--nvidia-only" in sys.argv[1:] else REPOS
    for repo in selected_repos:
        for release in github_releases(repo):
            if release.get("draft") or release.get("prerelease"):
                continue
            for asset in release.get("assets", []):
                if not asset["name"].lower().endswith(".spk"):
                    continue
                if repo in {"syno_nvidia_driver", "syno-gpu-monitor"}:
                    allowed_name = any(
                        allowed_repo == repo and asset["name"].startswith(f"{package_id}-")
                        for allowed_repo, package_id in allowed_nvidia
                    )
                    if not allowed_name:
                        continue
                url = asset["browser_download_url"]
                download_count = asset.get("download_count")
                current = by_url.get(url)
                if current is not None:
                    identity_changed = (
                        current.get("size") != asset.get("size") or
                        (repo, current.get("info", {}).get("package")) in allowed_nvidia and
                        current.get("github_asset_id") is None and asset.get("id") is not None or
                        (current.get("github_asset_id") is not None and (
                            current.get("github_asset_id") != asset.get("id") or
                            current.get("asset_updated_at") != asset.get("updated_at")
                        ))
                    )
                    if identity_changed:
                        refreshed = read_info({
                            "repo": repo, "tag": release["tag_name"],
                            "published_at": release.get("published_at"),
                            "name": asset["name"], "url": url, "size": asset["size"],
                        })
                        if "info" in refreshed:
                            if isinstance(download_count, int):
                                refreshed["download_count"] = download_count
                            refreshed["github_asset_id"] = asset.get("id")
                            refreshed["asset_updated_at"] = asset.get("updated_at")
                            by_url[url] = refreshed
                            current = refreshed
                            changed = True
                        else:
                            print(f"keeping cached metadata for {repo}/{asset['name']}: "
                                  f"{refreshed.get('error')}", flush=True)
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
                record["github_asset_id"] = asset.get("id")
                record["asset_updated_at"] = asset.get("updated_at")
                by_url[url] = record
                added += 1
                changed = True
    # The allowlist controls which package IDs may enter the catalog; the
    # newest version is discovered from SPK INFO instead of being pinned here.
    # This keeps withdrawn/renamed IDs out while allowing new revisions to
    # appear automatically as soon as a release is synchronized.
    filtered, removed = latest_allowed_nvidia(list(by_url.values()), nvidia_allowed)
    if removed:
        changed = True
    if changed:
        TARGET.parent.mkdir(exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="assets-", suffix=".json", dir=TARGET.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(filtered, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, TARGET)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(f"release sync complete: {added} new SPKs, {counts_updated} download counts updated, "
          f"{removed} obsolete NVIDIA records removed, {len(filtered)} total", flush=True)


if __name__ == "__main__":
    sync()
