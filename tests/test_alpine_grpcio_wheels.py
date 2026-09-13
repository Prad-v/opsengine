"""Alpine precompiled wheel pins must match poetry.lock."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ROOT / "docker" / "alpine-native-wheels.txt"
LOCK = ROOT / "poetry.lock"


def _lock_version(name: str) -> str:
    needle = f'name = "{name}"'
    lines = LOCK.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.strip() == needle:
            version = lines[i + 1].split("=", 1)[1].strip().strip('"')
            return version
    raise AssertionError(f"{name} not found in poetry.lock")


def test_alpine_native_wheel_pins_match_lock():
    pins = {}
    for raw in WHEELS.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        pkg, ver = line.split("==", 1)
        pins[pkg] = ver
    assert pins, "docker/alpine-native-wheels.txt has no package==version pins"
    for pkg, ver in pins.items():
        assert _lock_version(pkg) == ver, f"{pkg}: wheels.txt={ver} lock={_lock_version(pkg)}"
