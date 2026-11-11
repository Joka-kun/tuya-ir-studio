#!/usr/bin/env python3
"""Read-only Marketplace icon delivery probe: no token, no local HA access.

The Marketplace brand service reads icons from the latest GitHub release,
not the working tree. A local brand file alone is not evidence of delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import base64
from PIL import Image
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
            elif raw_result["valid_png"] is True:
                with Image.open(BytesIO(raw.data)) as source:
                    source.load()
                    source_pixels = source.convert("RGBA").tobytes()
                    source_size = source.size
                with Image.open(BytesIO(delivered.data)) as public:
                    public.load()
                    public_pixels = public.convert("RGBA").tobytes()
                    public_size = public.size
                same_pixels = source_size == public_size and source_pixels == public_pixels
                if image == "icon.png":
                    for label, contents in (("released", raw.data), ("marketplace", delivered.data)):
                        with Image.open(BytesIO(contents)) as icon:
                            preview = icon.convert("RGBA").resize((96, 96), Image.Resampling.LANCZOS)
                            out = BytesIO()
                            preview.save(out, "PNG", optimize=True)
                            print(f"PREVIEW_IMAGE domain={domain} source={label} png_base64={base64.b64encode(out.getvalue()).decode('ascii')}")
                print(json.dumps({
                    "case": f"{domain}/pixels/{image}",
                    "source_dimensions": source_size,
                    "public_dimensions": public_size,
                    "same_pixels": same_pixels,
                    "source_pixel_sha256": hashlib.sha256(source_pixels).hexdigest(),
                    "public_pixel_sha256": hashlib.sha256(public_pixels).hexdigest(),
                }, sort_keys=True))
                if not same_pixels:
                    print(f"DELIVERY_IMAGE_MISMATCH domain={domain} image={image}")
                    if domain == "ir_studio":
                        failed = True
                elif raw.data != delivered.data:
                    print(f"DELIVERY_SAME_PIXELS_OPTIMIZED domain={domain} image={image}")
                else:
                    print(f"DELIVERY_MATCH domain={domain} image={image}")
    # Upstream may return 503 or not have indexed the current release; leave
    # the CI pass/fail gate to the release integrity check, report delivery
    # differences as diagnostic evidence only.
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
