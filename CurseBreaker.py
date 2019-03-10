import os
import sys
import argparse
import traceback
from colorama import init, Fore
from terminaltables import SingleTable
from CB import __version__
from CB.Core import Core


class GUI:
    def __init__(self):
        parser = argparse.ArgumentParser(description='All options support comma separated lists. '
                                                     'When started without arguments program will update all add-ons.',
                                         epilog='Supported URLs: https://www.curseforge.com/wow/addons/<addon_name>, '
                                                'https://www.wowinterface.com/downloads/<addon_name>, ElvUI, ElvUI:Dev')
        parser.add_argument('-a', '--add', help='Install add-ons', metavar='URL')
        parser.add_argument('-r', '--remove', help='Remove add-ons', metavar='URL/Name')
        parser.add_argument('-u', '--update', help='Update add-ons', metavar='URL/Name')
        parser.add_argument('-l', '--list', help='Show installed add-ons', action='store_true')
        parser.add_argument('-b', '--backup', help='Enable/disable WTF backup', action='store_true')
        parser.add_argument('-d', '--debug', help='Display more verbose errors', action='store_true')

        self.args = parser.parse_args()
        self.core = Core()
        self.table = [['Status', 'Name', 'Version']]
        self.gui = SingleTable(self.table)
        self.gui.title = f'{Fore.LIGHTGREEN_EX}CurseBreaker {Fore.LIGHTBLACK_EX}v{__version__}{Fore.RESET}'
        self.gui.justify_columns[0] = 'center'
        sys.tracebacklimit = 0
        init()

    def start(self):
        os.system('cls')
        print(f'{Fore.LIGHTBLACK_EX}~~~ {Fore.LIGHTGREEN_EX}CurseBreaker '
              f'{Fore.LIGHTBLACK_EX}v{__version__} ~~~{Fore.RESET}\n')
        if not os.path.isfile('Wow.exe') or not os.path.isdir('Interface\\AddOns') or not os.path.isdir('WTF'):
            print(f'{Fore.LIGHTRED_EX}This executable should be placed in WoW directory!{Fore.RESET}')
            os.system('pause')
            sys.exit(1)
        else:
            self.core.init_config()

        if self.args.add:
            addons = self.args.add.split(',')
            for addon in addons:
                name, version = self.core.add_addon(addon)
                if version:
                    self.table.append([f'{Fore.GREEN}Installed{Fore.RESET}', name, version])
                else:
                    self.table.append([f'{Fore.LIGHTBLACK_EX}Already installed{Fore.RESET}', name, ''])
                os.system('cls')
                print(self.gui.table)
        elif self.args.remove:
            addons = self.args.remove.split(',')
            for addon in addons:
                name, version = self.core.del_addon(addon)
                if name:
                    self.table.append([f'{Fore.RED}Uninstalled{Fore.RESET}', name, version])
                else:
                    self.table.append([f'{Fore.LIGHTBLACK_EX}Not installed{Fore.RESET}', addon, ''])
                os.system('cls')
                print(self.gui.table)
        elif self.args.list:
            addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
            for addon in addons:
                self.table.append([f'{Fore.GREEN}Up-to-date{Fore.RESET}', addon['Name'], addon['InstalledVersion']])
            os.system('cls')
            print(self.gui.table)
        elif self.args.backup:
            status = self.core.backup_toggle()
            print(f'{Fore.LIGHTGREEN_EX}Backup of WTF directory is now: '
                  f'{f"{Fore.GREEN}ENABLED{Fore.RESET}" if status else f"{Fore.LIGHTRED_EX}DISABLED{Fore.RESET}"}')
        else:
            if self.args.update:
                addons = self.args.update.split(',')
            else:
                addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
            if len(addons) == 0:
                raise RuntimeError('No add-ons installed. '
                                   'Start this application with -h parameter to see available options.')
            else:
                for addon in addons:
                    name, versionnew, versionold = self.core.update_addon(addon if isinstance(addon, str) else
                                                                          addon['URL'])
                    if versionold:
                        if versionold == versionnew:
                            self.table.append([f'{Fore.GREEN}Up-to-date{Fore.RESET}', name, versionold])
                        else:
                            self.table.append([f'{Fore.YELLOW}Updated{Fore.RESET}', name,
                                               f'{versionold} {Fore.LIGHTBLACK_EX}>>>{Fore.RESET} {versionnew}'])
                    else:
                        self.table.append([f'{Fore.LIGHTBLACK_EX}Not installed{Fore.RESET}', addon, ''])
                    os.system('cls')
                    print(self.gui.table)
        if self.core.backup_check():
            print(f'\n{Fore.LIGHTGREEN_EX}Backing up WTF directory:{Fore.RESET}')
            self.core.backup_wtf(self.gui.table_width)
        os.system('pause')


if __name__ == '__main__':
    try:
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
        app = GUI()
        app.start()
    except Exception as e:
        # noinspection PyUnboundLocalVariable
        if app.args.debug:
            sys.tracebacklimit = 1000
            traceback.print_exc()
            sys.exit(1)
        else:
            print(f'{Fore.LIGHTRED_EX}{str(e)}{Fore.RESET}')
            os.system('pause')
            sys.exit(1)

