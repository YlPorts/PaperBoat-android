#!/usr/bin/env python3
"""Give the Android overlay large, readable and repositionable Paper Mario touch controls."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "src" / "port" / "ui" / "TouchControls.cpp"
text = TARGET.read_text(encoding="utf-8")

if "Android touch-first Paper Mario layout" in text:
    print("Android touch-control patch already applied")
    raise SystemExit(0)


def replace_exact(old: str, new: str, expected: int = 1, label: str = "replacement") -> None:
    global text
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} match(es), found {count}")
    text = text.replace(old, new)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"{label}: start marker not found")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"{label}: end marker not found")
    text = text[:a] + replacement + text[b:]


# Bigger mobile-first defaults. The in-menu scale/opacity sliders still let the
# player tune these values, and Edit Touch Layout persists custom positions.
replace_exact(
    '    CVarRegisterFloat(CVAR_TOUCH("Scale"), 1.0f);\n    CVarRegisterFloat(CVAR_TOUCH("Opacity"), 0.8f);',
    '    CVarRegisterFloat(CVAR_TOUCH("Scale"), 1.18f);\n    CVarRegisterFloat(CVAR_TOUCH("Opacity"), 0.72f);',
    label="touch defaults",
)

replace_exact(
    '    state.stickTravel = 2.4f * u;\n    state.nubRadius = 1.6f * u;\n    state.stickRest = LoadPos("Stick", ImVec2(4.8f * u, h - 4.8f * u), w, h);',
    '    state.stickTravel = 2.15f * u;\n    state.nubRadius = 1.10f * u;\n    state.stickRest = LoadPos("Stick", ImVec2(3.75f * u, h - 3.65f * u), w, h);',
    label="large stick",
)

# Face buttons: large enough for thumbs and pulled slightly inward from gesture
# navigation edges.
replace_exact(
    'kBlue, 0, 0, ImVec2(w - 2.6f * u, h - 3.0f * u), 1.5f * u',
    'kBlue, 0, 0, ImVec2(w - 2.55f * u, h - 2.85f * u), 1.45f * u',
    label="A layout",
)
replace_exact(
    'kGreen, 0, 0, ImVec2(w - 5.6f * u, h - 4.2f * u), 1.25f * u',
    'kGreen, 0, 0, ImVec2(w - 5.35f * u, h - 3.75f * u), 1.18f * u',
    label="B layout",
)
replace_exact(
    '    const ImVec2 c(w - 3.3f * u, h - 8.8f * u);\n    const float cOff = 1.5f * u;\n    const float cR = 0.85f * u;',
    '    const ImVec2 c(w - 3.65f * u, h - 7.35f * u);\n    const float cOff = 1.55f * u;\n    const float cR = 0.95f * u;',
    label="C cluster",
)

# Android touch-first Paper Mario layout: L and the D-pad are not needed by the
# game in normal play. Keep R because menus use it, plus Z/Start and all C inputs.
replace_between(
    '    // Shoulder / trigger bars: L top-left (clear of the menu button), R and Z top-right.\n',
    '    // D-pad cross on the left, above the stick area. Each texture is one arm\n',
    '''    // Android touch-first Paper Mario layout: compact labelled R/Z buttons.\n    state.gameButtons.push_back(make(\n        BTN_R, "R", "R", "R-Btn", "textures/buttons/RBtn.png", "R-Btn Outline", "textures/buttons/RBtnOutline.png", rStart,\n        kGray, 0, 0, ImVec2(w - 1.85f * u, 1.65f * u), 0.88f * u\n    ));\n    state.gameButtons.push_back(make(\n        BTN_Z, "Z", "Z", "Z-Btn", "textures/buttons/ZBtn.png", "Z-Btn Outline", "textures/buttons/ZBtnOutline.png", rStart,\n        kGray, 0, 0, ImVec2(w - 3.95f * u, 1.65f * u), 0.88f * u\n    ));\n''',
    "replace shoulders",
)
replace_between(
    '    // D-pad cross on the left, above the stick area. Each texture is one arm\n',
    '    // Start, bottom-center.\n',
    '',
    "remove unused dpad",
)

replace_exact(
    '''    // Start, bottom-center.\n    state.gameButtons.push_back(make(\n        BTN_START, "Start", "S", "Start-Btn", "textures/buttons/StartBtn.png", "Start-Btn Outline",\n        "textures/buttons/StartBtnOutline.png", rStart, kRed, 0, 0, ImVec2(w * 0.5f, h - 1.7f * u), 0.9f * u\n    ));''',
    '''    // START stays centered and reachable without covering gameplay.\n    state.gameButtons.push_back(make(\n        BTN_START, "Start", "START", "Start-Btn", "textures/buttons/StartBtn.png", "Start-Btn Outline",\n        "textures/buttons/StartBtnOutline.png", rR, kRed, 0, 0, ImVec2(w * 0.5f, h - 1.10f * u), 0.46f * u\n    ));''',
    label="Start pill",
)

# Replace the old texture-outline look with a purpose-built vector overlay. This
# avoids missing/empty button artwork on GLES and stays crisp at every density.
replace_between(
    '    for (const auto& button : sState.gameButtons) {\n        ImTextureID solidTex = gui->GetTextureByName(button.texName);\n',
    '\n    // Stick: AnalogStickOutline is the housing/gate ring (base), AnalogStick is\n',
    '''    for (const auto& button : sState.gameButtons) {\n        const bool isStart = button.mask == BTN_START;\n        const float r = std::min<float>(button.halfW, button.halfH);\n        const ImU32 fill = rgb(button.color) | alpha(button.pressed ? 0.94f : 0.56f);\n        const ImU32 border = IM_COL32(255, 255, 255, 0) | alpha(button.pressed ? 1.0f : 0.76f);\n\n        if (isStart) {\n            const ImVec2 pMin(button.center.x - button.halfW, button.center.y - button.halfH);\n            const ImVec2 pMax(button.center.x + button.halfW, button.center.y + button.halfH);\n            drawList->AddRectFilled(pMin, pMax, fill, button.halfH);\n            drawList->AddRect(pMin, pMax, border, button.halfH, 0, stroke);\n            text(button.center, button.halfH * 1.12f, button.label, IM_COL32(255, 255, 255, 0) | alpha(0.98f));\n            continue;\n        }\n\n        drawList->AddCircleFilled(button.center, r, fill, 40);\n        drawList->AddCircle(button.center, r, border, 40, stroke);\n\n        if (button.dirX != 0 || button.dirY != 0) {\n            // C-buttons: clear directional arrow on the yellow face.\n            const float a = r * 0.48f;\n            const float side = r * 0.34f;\n            const ImVec2 tip(button.center.x + button.dirX * a, button.center.y + button.dirY * a);\n            const ImVec2 tail(button.center.x - button.dirX * a * 0.55f, button.center.y - button.dirY * a * 0.55f);\n            const ImVec2 b1(tail.x + button.dirY * side, tail.y - button.dirX * side);\n            const ImVec2 b2(tail.x - button.dirY * side, tail.y + button.dirX * side);\n            drawList->AddTriangleFilled(tip, b1, b2, IM_COL32(32, 26, 12, 0) | alpha(0.94f));\n        } else {\n            text(button.center, r * 1.20f, button.label, IM_COL32(255, 255, 255, 0) | alpha(0.98f));\n        }\n    }\n\n''',
    "vector buttons",
)

# Replace the N64 stick sprites with a simple translucent virtual stick.
replace_between(
    '    // Stick: AnalogStickOutline is the housing/gate ring (base), AnalogStick is\n',
    '    // Layout-edit chrome: highlight the dragged widget, Done/Reset pills, hint.\n',
    '''    // Vector analog stick. Edit Touch Layout can drag its resting position,\n    // while the general Touch Controls Scale changes its size together with buttons.\n    const ImVec2 base = sState.stickHeld ? sState.stickAnchor : sState.stickRest;\n    const ImVec2 nub = sState.stickHeld ? sState.stickPos : sState.stickRest;\n    const float heldBoost = sState.stickHeld ? 1.0f : 0.78f;\n    drawList->AddCircleFilled(base, sState.stickTravel, IM_COL32(18, 20, 26, 0) | alpha(0.25f * heldBoost), 56);\n    drawList->AddCircle(base, sState.stickTravel, IM_COL32(255, 255, 255, 0) | alpha(0.54f * heldBoost), 56, stroke);\n    drawList->AddCircleFilled(nub, sState.nubRadius, IM_COL32(180, 186, 198, 0) | alpha(0.72f * heldBoost), 48);\n    drawList->AddCircle(nub, sState.nubRadius, IM_COL32(255, 255, 255, 0) | alpha(0.82f * heldBoost), 48, stroke);\n    drawList->AddCircleFilled(nub, sState.nubRadius * 0.20f, IM_COL32(255, 255, 255, 0) | alpha(0.54f * heldBoost), 24);\n\n''',
    "vector stick",
)

# The old '=' glyph looks like a debug button. Draw a standard three-line menu icon.
replace_exact(
    '    text(sState.menuCenter, sState.menuRadius * 1.1f, "=", IM_COL32(255, 255, 255, 0) | alpha(0.9f));',
    '''    const float menuLine = sState.menuRadius * 0.42f;\n    for (int row = -1; row <= 1; row++) {\n        const float y = sState.menuCenter.y + row * sState.menuRadius * 0.30f;\n        drawList->AddLine(\n            ImVec2(sState.menuCenter.x - menuLine, y), ImVec2(sState.menuCenter.x + menuLine, y),\n            IM_COL32(255, 255, 255, 0) | alpha(0.94f), stroke\n        );\n    }''',
    label="menu icon",
)

TARGET.write_text(text, encoding="utf-8")
print(f"Patched {TARGET.relative_to(ROOT)} with Android touch-first Paper Mario layout")
