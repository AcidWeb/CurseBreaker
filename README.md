# CurseBreaker

[<img src="https://img.shields.io/github/release/AcidWeb/CurseBreaker">](https://github.com/AcidWeb/CurseBreaker/releases/latest) [<img src="https://img.shields.io/github/downloads/AcidWeb/CurseBreaker/latest/total">](https://github.com/AcidWeb/CurseBreaker/releases/latest) [<img src="https://img.shields.io/github/downloads/AcidWeb/CurseBreaker/total">](https://github.com/AcidWeb/CurseBreaker/releases/latest) [<img src="https://img.shields.io/github/workflow/status/AcidWeb/CurseBreaker/Binary%20builder">](https://github.com/AcidWeb/CurseBreaker/actions) [<img src="https://img.shields.io/discord/362155557488164874?logo=discord">](https://discord.gg/G2SXFGb)

TUI/CLI addon updater for World of Warcraft.

![Screenshot](https://i.imgur.com/A3DH1xf.png)

## DOWNLOAD
The latest release can be found [here](https://github.com/AcidWeb/CurseBreaker/releases/latest).\
Please be aware that Linux (.gz) and macOS (.zip) versions are not thoroughly tested.

## USAGE
Place **CurseBreaker** binary inside directory containing `Wow.exe`, `WowClassic.exe` or `World of Warcraft.app`.\
Read the instructions on the top of the screen.

Already installed addons will not be recognized by **CurseBreaker** and they need to be reinstalled.\
This process can be partially automated by using the `import` command.

Both _Retail_ and _Classic_ clients are supported. The client version is detected automatically.\
By default **CurseBreaker** will create backups of entire `WTF` directory.

## TIPS & TRICKS
- On Windows command `uri_integration` can be used to enable integration with the CurseForge page.
- Most of the commands support the space-separated list of addons.
- `install` command have optional `-i` flag that can be used to disable client version check.
- TUI will look a little better if the application is started by something else than the default Windows command prompt. Preview version of [Windows Terminal](https://aka.ms/terminal-preview) is recommended.
- Environment variable `CURSEBREAKER_PATH` can be used to set the custom location of WoW client.
- When the application is started with a `headless` parameter entire addon and Wago upgrade process plus WTF backup should be executed in the background. Log file _CurseBreaker.html_ will be created in the same directory as the application.

## SUPPORTED URL
- CurseForge: `https://www.curseforge.com/wow/addons/[addon_name]`, `cf:[addon_name]`
- WoWInterface: `https://www.wowinterface.com/downloads/[addon_name]`, `wowi:[addon_id]`
- Tukui: `https://www.tukui.org/addons.php?id=[addon_id]`, `https://www.tukui.org/classic-addons.php?id=[addon_id]`, `tu:[addon_id]`, `tuc:[addon_id]`
- Tukui GitLab: `ElvUI`, `ElvUI:Dev`, `Tukui`, `Shadow&Light:Dev`
- GitHub Releases: `https://github.com/[username]/[repository_name]`, `gh:[username]/[repository_name]`
- Wago: **CurseBreaker** can update auras and Plater profiles/scripts like WeakAuras Companion.

## WEAKAURAS SUPPORT
**CurseBreaker** by default will try to update all detected WeakAuras and Plater profiles/scripts. Process work the same as WeakAuras Companion.\
All updates will still need to be applied in-game in the WeakAuras/Plater option menu.\
Command `toggle_wa` can be used to set a single author name that will be ignored during the update.\
Additionally Wago API key can be set with `set_wa_api` command so non-public entries will also be upgradeable.

## KNOWN ISSUES
- Using "double" WoWInterface projects ([example](https://www.wowinterface.com/downloads/info5086-BigWigsBossmods)) will always install a retail version of the addon. It can't be fixed as WoWInterface API doesn't support this type of project.
- WoWInterface projects that need to install files outside the `Interface\AddOns` directory are not supported.

## COPYRIGHT
**CurseBreaker** is free software/open source, and is distributed under the GNU General Public License v3.

Icon made by [Nikita Golubev](https://www.flaticon.com/authors/nikita-golubev) is licensed by [CC 3.0 BY](http://creativecommons.org/licenses/by/3.0/).
