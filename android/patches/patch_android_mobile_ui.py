#!/usr/bin/env python3
"""Build a real touch-first PaperBoat menu for Android without changing desktop UI."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def patch_file(path: str, edits: list[tuple[str, str, str]], marker: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        print(f"{path}: {marker} already applied")
        return

    for old, new, label in edits:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{path}: {label}: expected 1 match, found {count}")
        text = text.replace(old, new, 1)

    text = f"// {marker}\n" + text
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
            '''    auto& style = ImGui::GetStyle();\n#ifdef __ANDROID__\n    // Android V2: use touch spacing, but do not inflate the old desktop layout.\n    style.FramePadding = ImVec2(9.0f, 8.0f);\n    style.ItemSpacing = ImVec2(10.0f, 9.0f);\n    style.ItemInnerSpacing = ImVec2(8.0f, 7.0f);\n    style.TouchExtraPadding = ImVec2(5.0f, 5.0f);\n    style.WindowRounding = 12.0f;\n    style.ChildRounding = 12.0f;\n    style.FrameRounding = 10.0f;\n    style.GrabRounding = 10.0f;\n    style.ScrollbarRounding = 10.0f;\n    style.ScrollbarSize = 24.0f;\n\n    // Migrate devices that installed the previous X-Large desktop-style build.\n    if (!CVarGetInteger(CVAR_SETTING("AndroidMobileUi.V2"), 0)) {\n        CVarSetInteger(CVAR_SETTING("ImGuiScale"), 2); // Large, not X-Large.\n        CVarSetInteger(CVAR_SETTING("Menu.SidebarSearch"), 0);\n        CVarSetFloat(CVAR_SETTING("Menu.BackgroundOpacity"), 0.96f);\n        CVarSetFloat(CVAR_TOUCH("Scale"), 1.18f);\n        CVarSetFloat(CVAR_TOUCH("Opacity"), 0.72f);\n        CVarSetInteger(CVAR_SETTING("AndroidMobileUi.V2"), 1);\n        Ship::Context::GetRawInstance()->GetConsoleVariables()->Save();\n        GameEngine::Instance->ScaleImGui();\n    }\n#else\n    style.FramePadding = ImVec2(4.0f, 6.0f);\n    style.ItemSpacing = ImVec2(8.0f, 6.0f);\n#endif\n    style.Colors[ImGuiCol_MenuBarBg] = UIWidgets::ColorValues.at(UIWidgets::Colors::DarkGray);''',
            "Android V2 style and migration",
        ),
        (
            '''    mModMenuWindow = std::make_shared<PaperboatModMenuWindow>(CVAR_WINDOW("ModMenu"), "Mod Menu");\n    gui->AddGuiWindow(mModMenuWindow);''',
            '''    mModMenuWindow = std::make_shared<PaperboatModMenuWindow>(CVAR_WINDOW("ModMenu"), "Mod Menu");\n    gui->AddGuiWindow(mModMenuWindow);\n#ifdef __ANDROID__\n    // Mods are rendered inside the mobile settings page, never as a floating desktop window.\n    mModMenuWindow->Hide();\n    CVarSetInteger(CVAR_WINDOW("ModMenu"), 0);\n#endif''',
            "hide floating Android mod window",
        ),
    ],
    "Android mobile UI v2 patch",
)


mobile_menu = r'''#ifdef __ANDROID__
    // -------------------------------------------------------------------------
    // Android touch UI
    // -------------------------------------------------------------------------
    // This deliberately does not reuse the desktop sidebar layout. Main pages
    // are large horizontal tabs, sub-pages are swipeable chips, and the active
    // page owns the full width of the phone/tablet in a single vertical feed.
    std::string headerIndex = CVarGetString(headerCvar, "Settings");
    if (!menuEntries.contains(headerIndex) && !menuOrder.empty()) {
        headerIndex = menuOrder.front();
        CVarSetString(headerCvar, headerIndex.c_str());
    }

    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 12.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_ChildRounding, 12.0f);

    ImGui::PushFont(GameEngine::Instance->fontStandardLargest);
    ImGui::TextUnformatted("PaperBoat");
    ImGui::PopFont();
    ImGui::SameLine();
    ImGui::TextDisabled("Android");

    const float closeWidth = 110.0f;
    const float closeX = ImGui::GetWindowContentRegionMax().x - closeWidth;
    if (ImGui::GetCursorPosX() < closeX) {
        ImGui::SameLine(closeX);
    }
    UIWidgets::PushStyleButton(menuThemeIndex);
    if (ImGui::Button("Close", ImVec2(closeWidth, 46.0f))) {
        ToggleVisibility();
    }
    UIWidgets::PopStyleButton();

    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();

    // Primary navigation: large, horizontally scrollable page buttons.
    ImGui::BeginChild(
        "AndroidMainTabs", ImVec2(0.0f, 64.0f), ImGuiChildFlags_None,
        ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_HorizontalScrollbar
    );
    bool firstMain = true;
    for (auto& label : menuOrder) {
        if (!firstMain) {
            ImGui::SameLine();
        }
        firstMain = false;
        const bool selected = headerIndex == label;
        if (selected) {
            ImGui::PushStyleColor(ImGuiCol_Button, UIWidgets::ColorValues.at(menuThemeIndex));
        } else {
            ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.13f, 0.13f, 0.15f, 0.96f));
        }
        float tabWidth = ImGui::CalcTextSize(label.c_str()).x + 52.0f;
        if (tabWidth < 150.0f) {
            tabWidth = 150.0f;
        }
        if (ImGui::Button(label.c_str(), ImVec2(tabWidth, 48.0f))) {
            headerIndex = label;
            CVarSetString(headerCvar, label.c_str());
            menuSearch.Clear();
            CVarSave();
        }
        ImGui::PopStyleColor();
    }
    ImGui::EndChild();

    if (menuEntries.contains(headerIndex)) {
        auto& mobileEntry = menuEntries.at(headerIndex);
        const char* mobileSidebarCvar = mobileEntry.sidebarCvar;
        std::string sectionIndex = CVarGetString(mobileSidebarCvar, "");
        if (!mobileEntry.sidebars.contains(sectionIndex) && !mobileEntry.sidebarOrder.empty()) {
            sectionIndex = mobileEntry.sidebarOrder.front();
            CVarSetString(mobileSidebarCvar, sectionIndex.c_str());
        }

        // Secondary navigation: category chips instead of a permanent desktop sidebar.
        ImGui::BeginChild(
            "AndroidCategoryTabs", ImVec2(0.0f, 62.0f), ImGuiChildFlags_None,
            ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_HorizontalScrollbar
        );
        bool firstCategory = true;
        for (auto& sidebarLabel : mobileEntry.sidebarOrder) {
            if (!firstCategory) {
                ImGui::SameLine();
            }
            firstCategory = false;
            const bool selected = sectionIndex == sidebarLabel;
            if (selected) {
                ImGui::PushStyleColor(ImGuiCol_Button, UIWidgets::ColorValues.at(menuThemeIndex));
            } else {
                ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.10f, 0.10f, 0.12f, 0.92f));
            }
            float chipWidth = ImGui::CalcTextSize(sidebarLabel.c_str()).x + 44.0f;
            if (chipWidth < 130.0f) {
                chipWidth = 130.0f;
            }
            if (ImGui::Button(sidebarLabel.c_str(), ImVec2(chipWidth, 46.0f))) {
                sectionIndex = sidebarLabel;
                CVarSetString(mobileSidebarCvar, sidebarLabel.c_str());
                menuSearch.Clear();
                CVarSave();
            }
            ImGui::PopStyleColor();
        }
        ImGui::EndChild();

        ImGui::Spacing();
        ImGui::PushFont(GameEngine::Instance->fontStandardLargest);
        ImGui::TextUnformatted(sectionIndex.c_str());
        ImGui::PopFont();
        ImGui::Separator();
        ImGui::Spacing();

        // Full-width vertical settings feed. No desktop columns or left sidebar.
        ImGui::BeginChild(
            "AndroidPageContent", ImVec2(0.0f, 0.0f), ImGuiChildFlags_None,
            ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_AlwaysVerticalScrollbar
        );
        if (mobileEntry.sidebars.contains(sectionIndex)) {
            std::string menuLabel = mobileEntry.label;
            if (MenuInit::GetUpdateFuncs().contains(menuLabel)
                && MenuInit::GetUpdateFuncs()[menuLabel].contains(sectionIndex)) {
                for (auto& updateFunc : MenuInit::GetUpdateFuncs()[menuLabel][sectionIndex]) {
                    updateFunc();
                }
            }

            auto& activeSidebar = mobileEntry.sidebars.at(sectionIndex);
            for (size_t column = 0; column < activeSidebar.columnWidgets.size(); ++column) {
                if (column != 0) {
                    ImGui::Spacing();
                    ImGui::Separator();
                    ImGui::Spacing();
                }
                for (auto& widget : activeSidebar.columnWidgets.at(column)) {
                    MenuDrawItem(widget, 100, menuThemeIndex);
                    ImGui::Spacing();
                }
            }
        }
        ImGui::EndChild();
    }

    ImGui::PopStyleVar(2);
#else
'''

patch_file(
    "src/port/ui/Menu.cpp",
    [
        (
            '''    windowHeight = window->WorkRect.GetHeight();\n    windowWidth = window->WorkRect.GetWidth();\n\n    ImGui::PushFont(GameEngine::Instance->fontStandardLargest);''',
            '''    windowHeight = window->WorkRect.GetHeight();\n    windowWidth = window->WorkRect.GetWidth();\n\n''' + mobile_menu + '''    ImGui::PushFont(GameEngine::Instance->fontStandardLargest);''',
            "insert dedicated Android menu",
        ),
        (
            '''    if (!popout) {\n        ImGui::PopStyleVar();\n    }\n    ImGui::EndChild();\n    if (popout) {\n        poppedSize = ImGui::GetWindowSize();\n        poppedPos = ImGui::GetWindowPos();\n    }\n    if (freshOpen) {\n        freshOpen = false;\n    }\n    ImGui::End();\n}\n} // namespace Ship''',
            '''    if (!popout) {\n        ImGui::PopStyleVar();\n    }\n    ImGui::EndChild();\n    if (popout) {\n        poppedSize = ImGui::GetWindowSize();\n        poppedPos = ImGui::GetWindowPos();\n    }\n    if (freshOpen) {\n        freshOpen = false;\n    }\n    ImGui::End();\n#endif\n#ifdef __ANDROID__\n    if (!popout) {\n        ImGui::PopStyleVar();\n    }\n    if (popout) {\n        poppedSize = ImGui::GetWindowSize();\n        poppedPos = ImGui::GetWindowPos();\n    }\n    if (freshOpen) {\n        freshOpen = false;\n    }\n    ImGui::End();\n#endif\n}\n} // namespace Ship''',
            "close Android/desktop menu branches",
        ),
    ],
    "Android mobile menu v2 patch",
)


patch_file(
    "src/port/ui/PaperboatMenuSettings.cpp",
    [
        (
            '''    // Mod Menu\n    path.sidebarName = "Mod Menu";\n    path.column = SECTION_COLUMN_1;\n    AddSidebarEntry("Settings", path.sidebarName, 1);\n    AddWidget(path, "Popout Mod Menu Window", WIDGET_WINDOW_BUTTON)\n        .CVar(CVAR_WINDOW("ModMenu"))\n        .RaceDisable(false)\n        .WindowName("Mod Menu")\n        .HideInSearch(true)\n        .Options(WindowButtonOptions().Tooltip("Enables the separate Mod Menu Window."));''',
            '''    // Mod Menu\n#ifdef __ANDROID__\n    path.sidebarName = "Mods";\n    path.column = SECTION_COLUMN_1;\n    AddSidebarEntry("Settings", path.sidebarName, 1);\n    WindowButtonOptions androidModOptions;\n    androidModOptions.tooltip = "Manage installed mods.";\n    androidModOptions.showButton = false;\n    androidModOptions.embedWindow = true;\n    AddWidget(path, "Mods", WIDGET_WINDOW_BUTTON)\n        .CVar(CVAR_WINDOW("ModMenu"))\n        .RaceDisable(false)\n        .WindowName("Mod Menu")\n        .HideInSearch(true)\n        .Options(androidModOptions);\n#else\n    path.sidebarName = "Mod Menu";\n    path.column = SECTION_COLUMN_1;\n    AddSidebarEntry("Settings", path.sidebarName, 1);\n    AddWidget(path, "Popout Mod Menu Window", WIDGET_WINDOW_BUTTON)\n        .CVar(CVAR_WINDOW("ModMenu"))\n        .RaceDisable(false)\n        .WindowName("Mod Menu")\n        .HideInSearch(true)\n        .Options(WindowButtonOptions().Tooltip("Enables the separate Mod Menu Window."));\n#endif''',
            "embed Mods in Android settings",
        ),
    ],
    "Android embedded mods v2 patch",
)
