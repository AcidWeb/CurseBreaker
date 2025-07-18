# CurseBreaker

[<img src="https://img.shields.io/github/release/AcidWeb/CurseBreaker">](https://github.com/AcidWeb/CurseBreaker/releases/latest) [<img src="https://img.shields.io/github/downloads/AcidWeb/CurseBreaker/latest/total">](https://github.com/AcidWeb/CurseBreaker/releases/latest) [<img src="https://img.shields.io/github/downloads/AcidWeb/CurseBreaker/total">](https://github.com/AcidWeb/CurseBreaker/releases/latest) [<img src="https://img.shields.io/github/actions/workflow/status/AcidWeb/CurseBreaker/build.yml">](https://github.com/AcidWeb/CurseBreaker/actions) [<img src="https://img.shields.io/discord/362155557488164874?logo=discord">](https://discord.gg/G2SXFGb)

TUI/CLI addon updater for World of Warcraft.

![Screenshot](https://i.imgur.com/XI7vORk.png)

## DOWNLOAD
The latest release can be found [here](https://github.com/AcidWeb/CurseBreaker/releases/latest).\
Please be aware that Linux (.gz) and macOS (.zip) versions are not thoroughly tested.\
Windows 10+, Ubuntu 20.04+, Debian 11+ and macOS 11+ are supported.

## USAGE
Place **CurseBreaker** binary inside the directory containing `Wow.exe`, `WowClassic.exe` or `World of Warcraft.app`.\
Read the instructions at the top of the screen.

Already installed addons will not be recognized by **CurseBreaker**, and they need to be reinstalled.\
This process can be partially automated by using the `import` command.

_Retail_, _Mists of Pandaria Classic_ and _Classic_ clients are supported. The client version is detected automatically.\
By default **CurseBreaker** will create backups of the entire `WTF` directory.

## TIPS & TRICKS
- TUI will look a lot better if the application is started by something else than the default Windows command prompt. [Windows Terminal](https://aka.ms/terminal) is recommended.
- Many of the fields are links if used terminal emulator supports them. 
- On Windows command `uri_integration` can be used to enable integration with the Wago Addons and Wago page.
- Most of the commands support the space-separated list of addons.
- `install` command has an optional `-i` flag that can be used to disable the client version check.
- Environment variable `CURSEBREAKER_PATH` can be used to set the custom location of WoW client.
- The application can be run in non-interactive mode by providing commands directly as a parameter.
- When the application is started with a `headless` parameter entire addon and Wago upgrade process plus WTF backup should be executed in the background. Log file _CurseBreaker.html_ will be created in the same directory as the application.

## SUPPORTED URL
- Wago Addons: `https://addons.wago.io/addons/[addon_name]`, `wa:[addon_name]`
- WoWInterface: `https://www.wowinterface.com/downloads/[addon_name]`, `wowi:[addon_id]`
- Tukui: `ElvUI`, `Tukui`
- GitHub: Development versions of multiple addons. Slugs are suffixed with `:Dev`.
- GitHub Releases: `https://github.com/[username]/[repository_name]`, `gh:[username]/[repository_name]`
- Wago: **CurseBreaker** can update auras and Plater profiles/scripts like WeakAuras Companion.

## WAGO ADDONS SUPPORT
To use Wago Addons as addon source user needs to provide a personal API key. It is a paid feature.\
The key can be obtained [here](https://addons.wago.io/patreon) and needs to be added to the application configuration by using the `set wago_addons_api` command.

## GITHUB SUPPORT
Providing [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) **greatly** increase speed of bulk version check and solve possible issues with rate limiting.\
Both classic and fine-grained tokens are supported. No additional permissions are required.\
Token can be added to application by using the `set gh_api` command.

## WEAKAURAS SUPPORT
**CurseBreaker** by default will try to update all detected WeakAuras and Plater profiles/scripts. The process works the same as WeakAuras Companion.\
All updates will still need to be applied in-game in the WeakAuras/Plater option menu.\
Command `toggle wago` can be used to set a single author name that will be ignored during the update.\
Additionally Wago API key can be set with the `set wa_api` command so non-public entries will also be upgradeable.

## KNOWN ISSUES
- Using WoWInterface projects that provide multiple addon releases ([example](https://www.wowinterface.com/downloads/info5086-BigWigsBossmods)) will always install a retail version of the addon. It can't be fixed as WoWInterface API doesn't support this type of project.
- Some WoWInterface addon categories (e.g. Compilations, Optional) are not handled by their API. Addons in these categories can't be installed.
- WoWInterface projects that need to install files outside the `Interface\AddOns` directory are not supported.

## COPYRIGHT
**CurseBreaker** is a free software/open source and is distributed under the GNU General Public License v3.

Icon made by [Nikita Golubev](https://www.flaticon.com/authors/nikita-golubev) is licensed by [CC 3.0 BY](http://creativecommons.org/licenses/by/3.0/).
