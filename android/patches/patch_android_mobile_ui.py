#!/usr/bin/env python3
"""Adapt PaperBoat's desktop-oriented ImGui menu to Android touch screens."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def patch_file(path: str, edits: list[tuple[str, str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if "Android mobile UI patch" in text:
        print(f"{path}: Android mobile UI patch already applied")
        return

    for old, new, label in edits:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{path}: {label}: expected 1 match, found {count}")
        text = text.replace(old, new, 1)

    # A harmless marker makes the patch idempotent and easy to verify in CI.
    text = "// Android mobile UI patch\n" + text
    target.write_text(text, encoding="utf-8")
    print(f"Patched {path}")


patch_file(
    "src/port/ui/PaperboatGui.cpp",
    [
        (
            '#include "TouchControls.h"\n#include "port/ui/devtools/hooks/EventDebugger.h"',
            '#include "TouchControls.h"\n#include "port/Engine.h"\n#include "port/ui/cvar_prefixes.h"\n#include "port/ui/devtools/hooks/EventDebugger.h"',
            "mobile UI includes",
        ),
        (
            '''    auto& style = ImGui::GetStyle();\n    style.FramePadding = ImVec2(4.0f, 6.0f);\n    style.ItemSpacing = ImVec2(8.0f, 6.0f);\n    style.Colors[ImGuiCol_MenuBarBg] = UIWidgets::ColorValues.at(UIWidgets::Colors::DarkGray);''',
            '''    auto& style = ImGui::GetStyle();\n#ifdef __ANDROID__\n    // Touch-first proportions. Keep the same PaperBoat widgets and actions,\n    // but make them comfortable to hit on a phone instead of desktop-sized.\n    style.FramePadding = ImVec2(11.0f, 9.0f);\n    style.ItemSpacing = ImVec2(12.0f, 10.0f);\n    style.ItemInnerSpacing = ImVec2(9.0f, 7.0f);\n    style.TouchExtraPadding = ImVec2(5.0f, 5.0f);\n    style.WindowRounding = 16.0f;\n    style.ChildRounding = 14.0f;\n    style.FrameRounding = 10.0f;\n    style.GrabRounding = 10.0f;\n    style.ScrollbarRounding = 10.0f;\n    style.ScrollbarSize = 24.0f;\n\n    // Upgrade existing installs once. After this, user changes are preserved.\n    if (!CVarGetInteger(CVAR_SETTING("AndroidMobileUi.Initialized"), 0)) {\n        CVarSetInteger(CVAR_SETTING("ImGuiScale"), 3); // X-Large\n        CVarSetInteger(CVAR_SETTING("Menu.SidebarSearch"), 1);\n        CVarSetFloat(CVAR_SETTING("Menu.BackgroundOpacity"), 0.94f);\n        CVarSetFloat(CVAR_TOUCH("Scale"), 1.18f);\n        CVarSetFloat(CVAR_TOUCH("Opacity"), 0.72f);\n        CVarSetInteger(CVAR_SETTING("AndroidMobileUi.Initialized"), 1);\n        Ship::Context::GetRawInstance()->GetConsoleVariables()->Save();\n        GameEngine::Instance->ScaleImGui();\n    }\n#else\n    style.FramePadding = ImVec2(4.0f, 6.0f);\n    style.ItemSpacing = ImVec2(8.0f, 6.0f);\n#endif\n    style.Colors[ImGuiCol_MenuBarBg] = UIWidgets::ColorValues.at(UIWidgets::Colors::DarkGray);''',
            "touch-first ImGui styling",
        ),
        (
            '''    mModMenuWindow = std::make_shared<PaperboatModMenuWindow>(CVAR_WINDOW("ModMenu"), "Mod Menu");\n    gui->AddGuiWindow(mModMenuWindow);''',
            '''    mModMenuWindow = std::make_shared<PaperboatModMenuWindow>(CVAR_WINDOW("ModMenu"), "Mod Menu");\n    gui->AddGuiWindow(mModMenuWindow);\n#ifdef __ANDROID__\n    // The Android menu embeds this window. Never leave the old desktop-style\n    // floating/collapsed Mods window over the game.\n    mModMenuWindow->Hide();\n    CVarSetInteger(CVAR_WINDOW("ModMenu"), 0);\n#endif''',
            "hide floating mod window",
        ),
    ],
)

patch_file(
    "src/port/ui/Menu.cpp",
    [
        (
            '''    if (windowHeight > 800) {\n        menuSize.y = windowHeight * 0.9f;\n    }''',
            '''    if (windowHeight > 800) {\n        menuSize.y = windowHeight * 0.9f;\n    }\n#ifdef __ANDROID__\n    // Phones are already wide; the desktop 16:9 width cap wastes a large part\n    // of the display. Use nearly the whole screen while keeping a small gutter.\n    menuSize.x = windowWidth * 0.96f;\n    menuSize.y = windowHeight * 0.94f;\n#endif''',
            "Android fullscreen menu size",
        ),
        (
            '''    float sidebarWidth = 200 - style.ItemSpacing.x;\n    if (menuSize.x > 1600) {\n        sidebarWidth = menuSize.x * 0.15f;\n    }''',
            '''    float sidebarWidth = 200 - style.ItemSpacing.x;\n#ifdef __ANDROID__\n    // Wide enough for finger-sized category rows and readable labels.\n    sidebarWidth = std::max(250.0f, menuSize.x * 0.22f);\n#else\n    if (menuSize.x > 1600) {\n        sidebarWidth = menuSize.x * 0.15f;\n    }\n#endif''',
            "Android sidebar width",
        ),
        (
            '''    int columns = sidebar->at(sectionIndex).columnCount;\n    size_t columnFuncs = sidebar->at(sectionIndex).columnWidgets.size();\n    if (windowWidth < 800) {\n        columns = 1;\n    }''',
            '''    int columns = sidebar->at(sectionIndex).columnCount;\n    size_t columnFuncs = sidebar->at(sectionIndex).columnWidgets.size();\n#ifdef __ANDROID__\n    // Vertical scrolling is much easier to use with touch than tiny 2/3-column\n    // desktop controls. Keep every original setting, just stack them.\n    columns = 1;\n#else\n    if (windowWidth < 800) {\n        columns = 1;\n    }\n#endif''',
            "single-column Android settings",
        ),
    ],
)

patch_file(
    "src/port/ui/PaperboatMenuSettings.cpp",
    [
        (
            '''    // Mod Menu\n    path.sidebarName = "Mod Menu";\n    path.column = SECTION_COLUMN_1;\n    AddSidebarEntry("Settings", path.sidebarName, 1);\n    AddWidget(path, "Popout Mod Menu Window", WIDGET_WINDOW_BUTTON)\n        .CVar(CVAR_WINDOW("ModMenu"))\n        .RaceDisable(false)\n        .WindowName("Mod Menu")\n        .HideInSearch(true)\n        .Options(WindowButtonOptions().Tooltip("Enables the separate Mod Menu Window."));''',
            '''    // Mod Menu\n#ifdef __ANDROID__\n    path.sidebarName = "Mods";\n    path.column = SECTION_COLUMN_1;\n    AddSidebarEntry("Settings", path.sidebarName, 1);\n    WindowButtonOptions androidModOptions;\n    androidModOptions.tooltip = "Manage enabled and disabled mods.";\n    androidModOptions.showButton = false;\n    androidModOptions.embedWindow = true;\n    AddWidget(path, "Mods", WIDGET_WINDOW_BUTTON)\n        .CVar(CVAR_WINDOW("ModMenu"))\n        .RaceDisable(false)\n        .WindowName("Mod Menu")\n        .HideInSearch(true)\n        .Options(androidModOptions);\n#else\n    path.sidebarName = "Mod Menu";\n    path.column = SECTION_COLUMN_1;\n    AddSidebarEntry("Settings", path.sidebarName, 1);\n    AddWidget(path, "Popout Mod Menu Window", WIDGET_WINDOW_BUTTON)\n        .CVar(CVAR_WINDOW("ModMenu"))\n        .RaceDisable(false)\n        .WindowName("Mod Menu")\n        .HideInSearch(true)\n        .Options(WindowButtonOptions().Tooltip("Enables the separate Mod Menu Window."));\n#endif''',
            "embed Mods in Android settings",
        ),
    ],
)
