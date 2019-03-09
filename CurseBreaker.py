import os
import argparse
from colorama import init, Fore, Style
from CurseBreaker import __version__
from CurseBreaker.Core import Core

init()
parser = argparse.ArgumentParser()
parser.add_argument('-a', '--add', help='Install addon', metavar='URL')
parser.add_argument('-r', '--remove', help='Remove addon', metavar='URL')
parser.add_argument('-u', '--update', help='Update single addon', metavar='URL')
args = parser.parse_args()

if __name__ == '__main__':
    app = Core()
    print(f'{Fore.LIGHTBLACK_EX}~~~ {Fore.LIGHTGREEN_EX}CurseBreaker '
          f'{Fore.LIGHTBLACK_EX}v{__version__} ~~~{Style.RESET_ALL}\n')

    if not os.path.exists('Wow.exe') or not os.path.exists('Interface\\AddOns'):
        print(f'{Fore.RED}This executable should be placed in WoW directory!{Style.RESET_ALL}')
        exit(1)

    if args.add:
        addons = args.add.split(',')
        for addon in addons:
            name, version = app.add_addon(addon)
            if version:
                print(f'{Fore.GREEN}Installed{Style.RESET_ALL} | {version} | {name}')
            else:
                print(f'{Fore.LIGHTBLACK_EX}Already installed{Style.RESET_ALL} | {name}')
    elif args.remove:
        addons = args.remove.split(',')
        for addon in addons:
            name, version = app.del_addon(addon)
            if name:
                print(f'{Fore.RED}Uninstalled{Style.RESET_ALL} | {version} | {name}')
            else:
                print(f'{Fore.LIGHTBLACK_EX}Not installed{Style.RESET_ALL} | {addon}')
    else:
        if args.update:
            addons = args.update.split(',')
        else:
            addons = sorted(app.config['Addons'], key=lambda k: k['Name'].lower())
        for addon in addons:
            name, versionnew, versionold = app.update_addon(addon if isinstance(addon, str) else addon['URL'])
            if versionold:
                if versionold == versionnew:
                    print(f'{Fore.GREEN}Up-to-date{Style.RESET_ALL} | {versionold} | {name}')
                else:
                    print(f'{Fore.YELLOW}Updated{Style.RESET_ALL} | {versionold} >>> {versionnew} | {name}')
            else:
                print(f' {Fore.LIGHTBLACK_EX}Not installed{Style.RESET_ALL} | {addon}')
