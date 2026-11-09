"""Legacy HACS repository icons must mirror Home Assistant brand assets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("icon.png", "icon@2x.png", "dark_icon.png", "dark_icon@2x.png")


def test_repository_root_brand_matches_integration_brand():
    for name in FILES:
        root = (ROOT / "brand" / name).read_bytes()
        integration = (
            ROOT / "custom_components" / "ir_studio" / "brand" / name
        ).read_bytes()
        assert root == integration, f"brand/{name} must match the integration asset"


def test_all_new_brand_icons_are_valid_rgba_pngs_with_correct_resolution():
    """Reject corrupted assets; repository and integration icons use same art."""
    import struct
    import zlib

    for name in FILES:
        payload = (ROOT / "brand" / name).read_bytes()
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(payload) <= 2 * 1024 * 1024, "Marketplace brand-service image size limit"
        offset = 8
        chunks = []
        pixel_data = bytearray()
        width = height = None
        while offset < len(payload):
            length = struct.unpack(">I", payload[offset:offset + 4])[0]
            kind = payload[offset + 4:offset + 8]
            data = payload[offset + 8:offset + 8 + length]
            checksum = struct.unpack(
                ">I", payload[offset + 8 + length:offset + 12 + length]
            )[0]
            assert zlib.crc32(kind + data) & 0xFFFFFFFF == checksum
            offset += 12 + length
            chunks.append(kind)
            if kind == b"IHDR":
                width, height = struct.unpack(">II", data[:8])
                assert data[8:10] == bytes([8, 6])  # RGBA
            if kind == b"IDAT":
                pixel_data.extend(data)
            if kind == b"IEND":
                break
        expected = 512 if "@2x" in name else 256
        assert (width, height) == (expected, expected)
        assert chunks[0] == b"IHDR" and chunks[-1] == b"IEND"
        decoded = zlib.decompress(pixel_data)
        assert len(decoded) == height * (1 + width * 4)



def test_sidebar_logo_uses_small_standard_brand_icon():
    """The 34px navbar logo must not ship the 512px (1 MB) retina asset."""
    normal = (ROOT / "brand" / "icon.png").read_bytes()
    sidebar = (ROOT / "custom_components" / "ir_studio"
               / "frontend" / "icon.png").read_bytes()
    assert sidebar == normal
    assert len(sidebar) < 350_000
