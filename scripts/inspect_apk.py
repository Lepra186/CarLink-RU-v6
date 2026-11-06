#!/usr/bin/env python3
"""Validate packaging of an *experimental* APK; does not prove protocol behavior."""
import sys
import zipfile
import hashlib
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: python3 scripts/inspect_apk.py path/to/app.apk")
apk = Path(sys.argv[1])
if not apk.is_file() or apk.stat().st_size < 1_000_000:
    raise SystemExit("APK missing or unexpectedly small")
with zipfile.ZipFile(apk) as z:
    names = set(z.namelist())
    for required in ("AndroidManifest.xml", "classes.dex"):
        assert required in names, f"Missing {required}"
    for abi in ("arm64-v8a", "armeabi-v7a"):
        expected = f"lib/{abi}/libairplay_native.so"
        assert expected in names, f"Missing native AirPlay receiver: {expected}"
    for bad in names:
        if "offline-mfi/identity.pk8" in bad:
            raise SystemExit("Refusing candidate containing embedded accessory private key")
    print(f"APK: {apk}, bytes={apk.stat().st_size}")
    print("AirPlay ARM JNI libraries: present")
    print("Native libs:", ", ".join(sorted(n for n in names if n.endswith(".so"))))
print("SHA-256:", hashlib.sha256(apk.read_bytes()).hexdigest())
print("PACKAGE CHECK ONLY: no device/CarPlay/AirPlay functionality tested.")
