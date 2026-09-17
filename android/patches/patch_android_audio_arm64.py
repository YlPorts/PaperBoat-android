#!/usr/bin/env python3
"""Fix 64-bit audio sample addresses used by RAW16 voices on Android arm64."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
target = ROOT / "src/audio/core/pull_voice.c"
text = target.read_text(encoding="utf-8")
marker = "Android arm64 RAW16 audio pointer fix"

if marker in text:
    print("pull_voice.c: audio pointer fix already applied")
    raise SystemExit(0)

old = '''            s32 op;\n            s32 dramAlign;\n            s32 dramLoc;\n            s32 dmemAlign;'''
new = '''            s32 op;\n            s32 dramAlign;\n            // Android arm64 RAW16 audio pointer fix: dmaFunc returns a host/physical\n            // address that is pointer-sized in the port. Keeping it in s32 truncates\n            // the upper 32 bits and makes some short character/SFX samples silent.\n            intptr_t dramLoc;\n            s32 dmemAlign;'''

count = text.count(old)
if count != 1:
    raise RuntimeError(f"pull_voice.c: expected one RAW16 dramLoc declaration, found {count}")

text = text.replace(old, new, 1)
text = f"// {marker}\n" + text
target.write_text(text, encoding="utf-8")
print("Patched src/audio/core/pull_voice.c for arm64 RAW16 audio")
