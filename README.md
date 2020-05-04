# CurseBreaker

![GitHub release](https://img.shields.io/github/release/AcidWeb/CurseBreaker) ![GitHub Releases](https://img.shields.io/github/downloads/AcidWeb/CurseBreaker/latest/total) ![GitHub All Releases](https://img.shields.io/github/downloads/AcidWeb/CurseBreaker/total) ![GitHub Actions](https://github.com/AcidWeb/CurseBreaker/workflows/Binary%20builder/badge.svg)

CLI addon updater for World of Warcraft. (Asynchronous Updates)

![Screenshot](https://i.imgur.com/RQBNS4y.png)

## DOWNLOAD
The latest release can be found [here](https://github.com/AcidWeb/CurseBreaker/releases/latest).\
Please be aware that Linux and macOS versions are not thoroughly tested.

## USAGE
Place **CurseBreaker** binary inside directory containing `Wow.exe`, `WowClassic.exe` or `World of Warcraft.app` and start it up.\
Read the instructions on the top of the screen.

Already installed addons will not be recognized by **CurseBreaker** and they need to be reinstalled.\
This process can be partially automated by using the `import` command.

Both _Retail_ and _Classic_ clients are supported. The client version is detected automatically.\
By default **CurseBreaker** will create backups of entire `WTF` directory.

## TIPS & TRICKS
- On Windows command `uri_integration` can be used to enable integration with the CurseForge page.
- Most of the commands support the comma-separated list of addons.
- `install` command have optional `-i` flag that can be used to disable client version check.
- Environment variable `CURSEBREAKER_PATH` can be used to set the custom location of WoW client.
- Undocumented `symlink_protection` command will protect your symlinks against endless hunger of Battle.NET client.

## SUPPORTED URL
- CurseForge: `https://www.curseforge.com/wow/addons/[addon_name]`, `cf:[addon_name]`
- WoWInterface: `https://www.wowinterface.com/downloads/[addon_name]`, `wowi:[addon_id]`
- Tukui: `https://www.tukui.org/addons.php?id=[addon_id]`, `https://www.tukui.org/classic-addons.php?id=[addon_id]`, `tu:[addon_id]`, `tuc:[addon_id]`
- Tukui GitLab: `ElvUI`, `ElvUI:Dev`, `Tukui`
- Wago: **CurseBreaker** can update auras like WeakAuras Companion.

## WEAKAURAS SUPPORT
**CurseBreaker** by default will try to update all detected WeakAuras. Process work the same as WeakAuras Companion.\
Command `toggle_wa` can be used to set a single author name that will be ignored during the update.\
Additionally Wago API key can be set with `set_wa_api` command so non-public auras will also be upgradeable.

## KNOWN ISSUES
- Using "double" WoWInterface projects ([example](https://www.wowinterface.com/downloads/info5086-BigWigsBossmods)) will always install a retail version of the addon. It can't be fixed as WoWInterface API doesn't support this type of project.

## COPYRIGHT
**CurseBreaker** is free software/open source, and is distributed under the GNU General Public License v3.

Icon made by [Nikita Golubev](https://www.flaticon.com/authors/nikita-golubev) is licensed by [CC 3.0 BY](http://creativecommons.org/licenses/by/3.0/).
