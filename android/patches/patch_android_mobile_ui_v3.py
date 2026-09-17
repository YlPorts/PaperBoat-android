#!/usr/bin/env python3
"""Refine Android mobile UI after the V2 patch.

This patch is intentionally applied after patch_android_mobile_ui.py in CI.
It increases phone readability and removes the WindowButton wrapper around the
embedded Mods page so no floating/ghost Mods button can be rendered.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str, label: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: {label}: expected 1 match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Patched {path}: {label}")


# Existing installs already have AndroidMobileUi.V2=1. Use a new migration key
# so this build actually applies the larger scale once, while still preserving
# any changes the user makes afterwards.
replace_once(
    "src/port/ui/PaperboatGui.cpp",
    '''        CVarSetInteger(CVAR_SETTING("AndroidMobileUi.V2"), 1);\n        Ship::Context::GetRawInstance()->GetConsoleVariables()->Save();\n        GameEngine::Instance->ScaleImGui();\n    }\n#else''',
    '''        CVarSetInteger(CVAR_SETTING("AndroidMobileUi.V2"), 1);\n        Ship::Context::GetRawInstance()->GetConsoleVariables()->Save();\n        GameEngine::Instance->ScaleImGui();\n    }\n\n    // V3: the dedicated mobile layout can comfortably use the 2.0x ImGui\n    // scale. This is deliberately a one-time migration for existing installs.\n    if (!CVarGetInteger(CVAR_SETTING("AndroidMobileUi.V3"), 0)) {\n        CVarSetInteger(CVAR_SETTING("ImGuiScale"), 3); // X-Large / 2.0x.\n        CVarSetInteger(CVAR_SETTING("AndroidMobileUi.V3"), 1);\n        Ship::Context::GetRawInstance()->GetConsoleVariables()->Save();\n        GameEngine::Instance->ScaleImGui();\n    }\n#else''',
    "V3 scale migration",
)

# Explicit pixel-sized navigation controls are not affected by FontGlobalScale,
# so grow them separately for modern high-DPI Android displays.
replace_once(
    "src/port/ui/Menu.cpp",
    '''    const float closeWidth = 110.0f;\n    const float closeX = ImGui::GetWindowContentRegionMax().x - closeWidth;''',
    '''    const float closeWidth = 140.0f;\n    const float closeX = ImGui::GetWindowContentRegionMax().x - closeWidth;''',
    "larger close button width",
)
replace_once(
    "src/port/ui/Menu.cpp",
    '''    if (ImGui::Button("Close", ImVec2(closeWidth, 46.0f))) {''',
    '''    if (ImGui::Button("Close", ImVec2(closeWidth, 58.0f))) {''',
    "larger close button height",
)
replace_once(
    "src/port/ui/Menu.cpp",
    '''        "AndroidMainTabs", ImVec2(0.0f, 64.0f), ImGuiChildFlags_None,''',
    '''        "AndroidMainTabs", ImVec2(0.0f, 80.0f), ImGuiChildFlags_None,''',
    "larger main tab strip",
)
replace_once(
    "src/port/ui/Menu.cpp",
    '''        float tabWidth = ImGui::CalcTextSize(label.c_str()).x + 52.0f;\n        if (tabWidth < 150.0f) {\n            tabWidth = 150.0f;\n        }\n        if (ImGui::Button(label.c_str(), ImVec2(tabWidth, 48.0f))) {''',
    '''        float tabWidth = ImGui::CalcTextSize(label.c_str()).x + 58.0f;\n        if (tabWidth < 170.0f) {\n            tabWidth = 170.0f;\n        }\n        if (ImGui::Button(label.c_str(), ImVec2(tabWidth, 60.0f))) {''',
    "larger main tabs",
)
replace_once(
    "src/port/ui/Menu.cpp",
    '''            "AndroidCategoryTabs", ImVec2(0.0f, 62.0f), ImGuiChildFlags_None,''',
    '''            "AndroidCategoryTabs", ImVec2(0.0f, 74.0f), ImGuiChildFlags_None,''',
    "larger category strip",
)
replace_once(
    "src/port/ui/Menu.cpp",
    '''            float chipWidth = ImGui::CalcTextSize(sidebarLabel.c_str()).x + 44.0f;\n            if (chipWidth < 130.0f) {\n                chipWidth = 130.0f;\n            }\n            if (ImGui::Button(sidebarLabel.c_str(), ImVec2(chipWidth, 46.0f))) {''',
    '''            float chipWidth = ImGui::CalcTextSize(sidebarLabel.c_str()).x + 50.0f;\n            if (chipWidth < 150.0f) {\n                chipWidth = 150.0f;\n            }\n            if (ImGui::Button(sidebarLabel.c_str(), ImVec2(chipWidth, 56.0f))) {''',
    "larger category chips",
)

# The V2 implementation embedded the window through WIDGET_WINDOW_BUTTON. On
# Android that still allowed a WindowButton control to leak into the page on
# some builds. A custom widget renders only the window contents and cannot
# create a separate Mods button.
replace_once(
    "src/port/ui/PaperboatMenuSettings.cpp",
    '''    WindowButtonOptions androidModOptions;\n    androidModOptions.tooltip = "Manage installed mods.";\n    androidModOptions.showButton = false;\n    androidModOptions.embedWindow = true;\n    AddWidget(path, "Mods", WIDGET_WINDOW_BUTTON)\n        .CVar(CVAR_WINDOW("ModMenu"))\n        .RaceDisable(false)\n        .WindowName("Mod Menu")\n        .HideInSearch(true)\n        .Options(androidModOptions);''',
    '''    AddWidget(path, "Mods", WIDGET_CUSTOM)\n        .RaceDisable(false)\n        .HideInSearch(true)\n        .CustomFunction([](WidgetInfo&) {\n            auto modWindow = Ship::Context::GetRawInstance()->GetWindow()->GetGui()->GetGuiWindow("Mod Menu");\n            if (modWindow) {\n                // Keep the desktop window permanently hidden on Android and\n                // render only its contents in this Settings > Mods page.\n                if (modWindow->IsVisible()) {\n                    modWindow->Hide();\n                }\n                modWindow->DrawElement();\n            }\n        });''',
    "direct embedded Mods page",
)
