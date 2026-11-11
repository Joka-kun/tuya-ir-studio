#!/usr/bin/env python3
"""Read-only Marketplace icon delivery probe: no token, no local HA access.

The Marketplace brand service reads icons from the latest GitHub release,
not the working tree. A local brand file alone is not evidence of delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import urllib.error
import urllib.request

REPOS = {
    "ir_studio": "Joka-kun/tuya-ir-studio",
    "so_diffuser_ble": "Joka-kun/xiaomi-so-diffuser-ble",
}
IMAGES = ("icon.png", "icon@2x.png")


@dataclass(frozen=True)
class Probe:
    url: str
    code: int
    mime: str
    data: bytes
    error: str = ""


def read(url: str) -> Probe:
    request = urllib.request.Request(
        url, headers={"User-Agent": "HACS-Brand-Delivery-Audit/1.0",
                      "Accept": "image/png,application/octet-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            data = response.read(2 * 1024 * 1024 + 1)
            return Probe(url, response.status, response.headers.get_content_type(), data)
    except urllib.error.HTTPError as exc:
        return Probe(url, exc.code, exc.headers.get_content_type(), b"", str(exc.reason))
    except Exception as exc:
        return Probe(url, 0, "", b"", type(exc).__name__)


def describe(label: str, probe: Probe) -> dict[str, object]:
    # No auth or local URLs are requested, and never print response bodies.
    result: dict[str, object] = {
        "case": label,
        "http": probe.code,
        "mime": probe.mime,
        "bytes": len(probe.data),
        "valid_png": probe.data.startswith(b"\x89PNG\r\n\x1a\n"),
    }
    if probe.data:
        result["sha256"] = hashlib.sha256(probe.data).hexdigest()
    if probe.error:
        result["error"] = probe.error
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    failed = False
    for domain, repository in REPOS.items():
        for image in IMAGES:
            raw = read(
                f"https://raw.githubusercontent.com/{repository}/v1.0.8/"
                f"custom_components/{domain}/brand/{image}"
            )
            delivered = read(
                f"https://brands.home-assistant.io/marketplace/{domain}/{image}"
            )
            raw_result = describe(f"{domain}/v1.0.8/{image}", raw)
            live_result = describe(f"{domain}/marketplace/{image}", delivered)
            if domain == "ir_studio" and raw_result["valid_png"] is not True:
                failed = True  # Owner's release must contain a valid PNG.
            if live_result["valid_png"] is not True:
                print(f"DELIVERY_GAP domain={domain} image={image}")
            elif raw.data != delivered.data:
                # Re-indexing may lag behind a newer tag; do not conflate with a bad source file.
                print(f"DELIVERY_DIFF domain={domain} image={image}")
            else:
                print(f"DELIVERY_MATCH domain={domain} image={image}")
    # Upstream may return 503 or not have indexed the current release; leave
    # the CI pass/fail gate to the release integrity check, report delivery
    # differences as diagnostic evidence only.
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
