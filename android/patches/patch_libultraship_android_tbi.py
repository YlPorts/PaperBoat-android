#!/usr/bin/env python3
"""Patch libultraship Fast3D for Android arm64 tagged heap pointers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "external" / "libultraship" / "src" / "fast" / "interpreter.cpp"
text = TARGET.read_text(encoding="utf-8")

if "CanonicalizeAndroidPointer" in text:
    print("libultraship Android pointer-tag patch already applied")
    raise SystemExit(0)


def replace_exact(old: str, new: str, expected: int = 1, label: str = "replacement") -> None:
    global text
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} match(es), found {count}")
    text = text.replace(old, new)


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

replace_exact(
    "uintptr_t i = (uintptr_t)gfx->SegAddr(cmd->words.w1);",
    "uintptr_t i = CanonicalizeAndroidPointer((uintptr_t)gfx->SegAddr(cmd->words.w1));",
    label="canonicalize G_SETTIMG address",
)
replace_exact(
    "uintptr_t w1 = (uintptr_t)cmd->words.w1;",
    "uintptr_t w1 = CanonicalizeAndroidPointer((uintptr_t)cmd->words.w1);",
    label="canonicalize OTR filepath guard",
)

replace_exact(
    "const char* fileName = (const char*)cmd->words.w1;",
    "const char* fileName = CanonicalizeAndroidString((const char*)cmd->words.w1);",
    expected=2,
    label="canonicalize const filepath handlers",
)
replace_exact(
    "char* fileName = (char*)cmd->words.w1;",
    "char* fileName = const_cast<char*>(CanonicalizeAndroidString((const char*)cmd->words.w1));",
    expected=3,
    label="canonicalize mutable filepath handlers",
)
replace_exact(
    "const char* fileName = (char*)cmd->words.w1;",
    "const char* fileName = CanonicalizeAndroidString((const char*)cmd->words.w1);",
    label="canonicalize texture filepath handler",
)
replace_exact(
    "gfx_push_current_dir((char*)(*cmd0)->words.w1);",
    "gfx_push_current_dir(const_cast<char*>(CanonicalizeAndroidString((const char*)(*cmd0)->words.w1)));",
    label="canonicalize pushcd filepath",
)
replace_exact(
    "const char* path = (const char*)gfx->SegAddr(cmd->words.w1);",
    "const char* path = CanonicalizeAndroidString((const char*)gfx->SegAddr(cmd->words.w1));",
    label="canonicalize shader filepath",
)
replace_exact(
    "uintptr_t data = (uintptr_t)bg->b.imagePtr;",
    "uintptr_t data = CanonicalizeAndroidPointer((uintptr_t)bg->b.imagePtr);",
    expected=2,
    label="canonicalize S2DEX image pointers",
)

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
