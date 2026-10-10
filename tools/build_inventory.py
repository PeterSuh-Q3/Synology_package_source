#!/usr/bin/env python3
"""Read SPK metadata from GitHub release assets without downloading payloads."""

import concurrent.futures
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "package", "version", "description", "displayname", "maintainer",
    "maintainer_url", "distributor", "distributor_url", "arch",
    "os_min_ver", "os_max_ver", "install_dep_packages", "startable",
    "silent_upgrade", "auto_upgrade_from",
}


def read_info(asset):
    result = subprocess.run(
        ["curl", "-fsSL", "--retry", "2", "--max-time", "40", "-r", "0-1048575", asset["url"]],
        capture_output=True,
    )
    if result.returncode:
        return {**asset, "error": result.stderr.decode(errors="replace")[-250:]}
    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r|") as archive:
            for member in archive:
                if member.name in ("INFO", "./INFO"):
                    if member.size > 1048576:
                        raise ValueError("INFO file is too large")
                    info = archive.extractfile(member).read().decode("utf-8", errors="replace")
                    break
            else:
                raise ValueError("SPK has no INFO in first MiB")
        fields = {}
        for line in info.splitlines():
            match = re.fullmatch(r'([A-Za-z_][A-Za-z_0-9]*)="(.*)"', line)
            if match and match.group(1) in FIELDS:
                fields[match.group(1)] = match.group(2)
        if not all(fields.get(name) for name in ("package", "version", "arch")):
            raise ValueError("missing required package/version/arch INFO field")
        return {**asset, "info": fields}
    except Exception as exc:
        return {**asset, "error": str(exc)}


def main():
    source = Path(sys.argv[1])
    assets = json.loads(source.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        records = list(executor.map(read_info, assets))
    target = ROOT / "data" / "assets.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {len(records)} assets: {sum('info' in item for item in records)} valid; "
          f"{sum('error' in item for item in records)} errors")
    for item in records:
        if "error" in item:
            print(item["repo"], item["name"], item["error"], file=sys.stderr)


if __name__ == "__main__":
    main()
