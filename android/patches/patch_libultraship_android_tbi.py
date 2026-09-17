#!/usr/bin/env python3
"""Patch libultraship's Fast3D interpreter for Android arm64 tagged pointers.

Android's arm64 allocator can return pointers whose top byte contains a tag
(TBI/MTE-style address tagging). AArch64 hardware dereferences those pointers,
but numeric pointer-range checks must ignore the tag. Fast3D's resource-path
checks otherwise reject valid OTR path pointers and the game can interpret path
bytes/stale state as texture data.

The parent repository pins libultraship as a submodule, so keep this Android-only
build patch here instead of modifying the upstream submodule checkout.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "external" / "libultraship" / "src" / "fast" / "interpreter.cpp"

text = TARGET.read_text(encoding="utf-8")

SENTINEL = "CanonicalizeAndroidPointer"
if SENTINEL in text:
    print("libultraship Android pointer-tag patch already applied")
    raise SystemExit(0)


def replace_exact(old: str, new: str, expected: int = 1, label: str = "replacement") -> None:
    global text
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} match(es), found {count}")
    text = text.replace(old, new)


# Put the helper before every handler that needs it.
needle = """// A resolved address still in the N64 segmented range (<= 0x0FFFFFFF) usually means SegAddr
// failed to resolve it (segment not set up). Keep it only if it belongs to a loaded module,
"""
helper = """// Android arm64 uses the top byte of heap pointers as an allocation tag. The CPU
// ignores it when dereferencing (Top Byte Ignore), but numeric range checks and
// pointer-keyed resource paths must use the canonical address or valid OTR assets
// can be rejected as kernel/sentinel addresses.
static inline uintptr_t CanonicalizeAndroidPointer(uintptr_t addr) {
#if defined(__ANDROID__) && UINTPTR_MAX > 0xFFFFFFFFu
    return addr & 0x00FFFFFFFFFFFFFFull;
#else
    return addr;
#endif
}

static inline const char* CanonicalizeAndroidString(const char* ptr) {
    return reinterpret_cast<const char*>(CanonicalizeAndroidPointer(reinterpret_cast<uintptr_t>(ptr)));
}

// A resolved address still in the N64 segmented range (<= 0x0FFFFFFF) usually means SegAddr
// failed to resolve it (segment not set up). Keep it only if it belongs to a loaded module,
"""
replace_exact(needle, helper, label="insert canonical pointer helper")

# Standard RDP G_SETTIMG path: signature detection and resource lookup must see
# the canonical pointer, not the Android allocation tag.
replace_exact(
    "uintptr_t i = (uintptr_t)gfx->SegAddr(cmd->words.w1);",
    "uintptr_t i = CanonicalizeAndroidPointer((uintptr_t)gfx->SegAddr(cmd->words.w1));",
    label="canonicalize G_SETTIMG address",
)

# OTR filepath opcodes are filtered before reaching their handlers. This was the
# remaining range check that still rejected tagged Android heap pointers.
replace_exact(
    "uintptr_t w1 = (uintptr_t)cmd->words.w1;",
    "uintptr_t w1 = CanonicalizeAndroidPointer((uintptr_t)cmd->words.w1);",
    label="canonicalize OTR filepath guard",
)

# Filepath handlers use pointer identity for caches/resource lookups in several
# places. Canonicalize those paths at their entry points as well.
replace_exact(
    "const char* fileName = (const char*)cmd->words.w1;",
    "const char* fileName = CanonicalizeAndroidString((const char*)cmd->words.w1);",
    expected=2,
    label="canonicalize const filepath handlers",
)
replace_exact(
    "char* fileName = (char*)cmd->words.w1;",
    "char* fileName = const_cast<char*>(CanonicalizeAndroidString((const char*)cmd->words.w1));",
    expected=2,
    label="canonicalize mutable filepath handlers",
)
replace_exact(
    "const char* fileName = (char*)cmd->words.w1;",
    "const char* fileName = CanonicalizeAndroidString((const char*)cmd->words.w1);",
    label="canonicalize texture filepath handler",
)
replace_exact(
    "gfx_push_current_dir((char*)(*cmd0)->words.w1);",
    "gfx_push_current_dir(const_cast<char*>(CanonicalizeAndroidString((const char*)(*cmd0)->words.w1)));"," + "
    label="canonicalize pushcd filepath",
)
replace_exact(
    "const char* path = (const char*)gfx->SegAddr(cmd->words.w1);",
    "const char* path = CanonicalizeAndroidString((const char*)gfx->SegAddr(cmd->words.w1));",
    label="canonicalize shader filepath",
)

# S2DEX backgrounds can also carry an OTR path in imagePtr.
replace_exact(
    "uintptr_t data = (uintptr_t)bg->b.imagePtr;",
    "uintptr_t data = CanonicalizeAndroidPointer((uintptr_t)bg->b.imagePtr);",
    expected=2,
    label="canonicalize S2DEX image pointers",
)

# Make the signature helper itself dereference the canonical address. The
# upstream fix masked only the numeric comparison; this keeps both validation
# and the actual resource signature read on the same address.
replace_exact(
    """int32_t gfx_check_image_signature(const char* imgData) {
    uintptr_t i = (uintptr_t)(imgData);
""",
    """int32_t gfx_check_image_signature(const char* imgData) {
    uintptr_t i = CanonicalizeAndroidPointer((uintptr_t)(imgData));
    const char* canonicalImgData = reinterpret_cast<const char*>(i);
""",
    label="canonicalize signature pointer",
)
replace_exact(
    "if ((i & 0x00FFFFFFFFFFFFFFull) > 0x0000FFFFFFFFFFFFull) {",
    "if (i > 0x0000FFFFFFFFFFFFull) {",
    label="use canonical range check",
)
replace_exact(
    "return Ship::Context::GetRawInstance()->GetResourceManager()->OtrSignatureCheck(imgData);",
    "return Ship::Context::GetRawInstance()->GetResourceManager()->OtrSignatureCheck(canonicalImgData);",
    label="signature dereference canonical pointer",
)

TARGET.write_text(text, encoding="utf-8")
print(f"Patched {TARGET.relative_to(ROOT)} for Android arm64 tagged pointers")
