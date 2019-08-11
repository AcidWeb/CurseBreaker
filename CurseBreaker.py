import os
import sys
import time
import msvcrt
import shutil
import requests
import traceback
from tqdm import tqdm
from colorama import init, Fore
from terminaltables import SingleTable
from prompt_toolkit import PromptSession, HTML, print_formatted_text as printft
from prompt_toolkit.completion import WordCompleter
from ctypes import windll, wintypes, byref
from distutils.version import StrictVersion
from CB import __version__
from CB.Core import Core


class TUI:
    def __init__(self):
        self.core = Core()
        self.session = PromptSession()
        self.table_data = None
        self.table = None
        self.completer = None
        self.chandle = windll.kernel32.GetStdHandle(-11)
        sys.tracebacklimit = 0
        init()

    def start(self):
        self.setup_console()
        self.print_header()
        # Check if executable is in good location
        if not os.path.isfile('Wow.exe') or not os.path.isdir(os.path.join('Interface', 'AddOns')) or \
                not os.path.isdir('WTF'):
            printft(HTML('<ansibrightred>This executable should be placed in the same directory where Wow.exe is locate'
                         'd.</ansibrightred>\n'))
            os.system('pause')
            sys.exit(1)
        # Check if client have write access
        try:
            with open('PermissionTest', 'w') as _:
                pass
            os.remove('PermissionTest')
        except IOError:
            printft(HTML('<ansibrightred>CurseBreaker doesn\'t have write rights for the current directory.\n'
                         'Try starting it with administrative privileges.</ansibrightred>\n'))
            os.system('pause')
            sys.exit(1)
        self.auto_update()
        self.core.init_config()
        self.setup_completer()
        self.setup_table()
        # Curse URI Support
        if len(sys.argv) == 2 and 'twitch://' in sys.argv[1]:
            try:
                self.c_install(sys.argv[1].strip())
            except Exception as e:
                self.handle_exception(e)
            os.system('timeout /t 5')
            sys.exit(0)
        if len(sys.argv) == 2 and '.ccip' in sys.argv[1]:
            try:
                path = sys.argv[1].strip()
                self.c_install(self.core.parse_cf_xml(path))
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                self.handle_exception(e)
            os.system('timeout /t 5')
            sys.exit(0)
        # CLI command
        if len(sys.argv) >= 2:
            command = ' '.join(sys.argv[1:]).split(' ', 1)
            if getattr(self, f'c_{command[0].lower()}', False):
                try:
                    getattr(self, f'c_{command[0].lower()}')(command[1].strip() if len(command) > 1 else False)
                except Exception as e:
                    self.handle_exception(e)
            else:
                printft('Command not found.')
            sys.exit(0)
        # Addons auto update
        if len(self.core.config['Addons']) > 0:
            printft('Automatic update of all addons will start in 5 seconds.\n'
                    'Press any button to enter interactive mode.')
            starttime = time.time()
            keypress = None
            while True:
                if msvcrt.kbhit():
                    keypress = msvcrt.getch()
                    break
                elif time.time() - starttime > 5:
                    break
            if not keypress:
                if len(self.core.config['Addons']) > 37:
                    self.setup_console(True)
                self.print_header()
                try:
                    self.c_update(False, True)
                    if self.core.backup_check():
                        self.setup_table()
                        printft(HTML('\n<ansigreen>Backing up WTF directory:</ansigreen>'))
                        self.core.backup_wtf()
                except Exception as e:
                    self.handle_exception(e)
                printft('')
                os.system('pause')
                sys.exit(0)
        self.setup_console(True)
        self.print_header()
        printft(HTML('Use command <ansigreen>help</ansigreen> or press <ansigreen>TAB</ansigreen> to see a list of avai'
                     'lable commands.\nCommand <ansigreen>exit</ansigreen> or pressing <ansigreen>CTRL+D</ansigreen> wi'
                     'll close the application.\n'))
        # Prompt session
        while True:
            try:
                command = self.session.prompt(HTML('<ansibrightgreen>CB></ansibrightgreen> '), completer=self.completer)
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            else:
                command = command.split(' ', 1)
                if getattr(self, f'c_{command[0].lower()}', False):
                    try:
                        self.setup_table()
                        getattr(self, f'c_{command[0].lower()}')(command[1].strip() if len(command) > 1 else False)
                        self.setup_completer()
                    except Exception as e:
                        self.handle_exception(e)
                else:
                    printft('Command not found.')

    def auto_update(self):
        if getattr(sys, 'frozen', False):
            try:
                payload = requests.get('https://api.github.com/repos/AcidWeb/CurseBreaker/releases/latest').json()
                remoteversion = payload['name']
                changelog = payload['body']
                url = payload['assets'][0]['browser_download_url']
                if StrictVersion(remoteversion[1:]) > StrictVersion(__version__):
                    printft(HTML('<ansigreen>Updating CurseBreaker...</ansigreen>'))
                    if os.path.isfile(sys.executable + '.old'):
                        os.remove(sys.executable + '.old')
                    shutil.move(sys.executable, sys.executable + '.old')
                    payload = requests.get(url)
                    with open(sys.executable, 'wb') as f:
                        f.write(payload.content)
                    printft(HTML(f'<ansibrightgreen>Update complete! Please restart the application.</ansibrightgreen'
                                 f'>\n\n<ansigreen>Changelog:</ansigreen>\n{changelog}\n'))
                    os.system('pause')
                    sys.exit(0)
            except Exception as e:
                printft(HTML(f'<ansibrightred>Update failed!\n\nReason: {str(e)}</ansibrightred>\n'))
                os.system('pause')
                sys.exit(1)

    def handle_exception(self, e):
        if len(self.table_data) > 1:
            print(self.table.table)
        if getattr(sys, 'frozen', False):
            printft(HTML(f'\n<ansibrightred>{str(e)}</ansibrightred>'))
        else:
            sys.tracebacklimit = 1000
            traceback.print_exc()

    def print_header(self):
        os.system('cls')
        printft(HTML(f'<ansibrightblack>~~~ <ansibrightgreen>CurseBreaker</ansibrightgreen> <ansibrightred>v'
                     f'{__version__}</ansibrightred> ~~~</ansibrightblack>\n'))

    def setup_console(self, buffer=False):
        if getattr(sys, 'frozen', False):
            if buffer:
                windll.kernel32.SetConsoleScreenBufferSize(self.chandle, wintypes._COORD(100, 100))
            else:
                windll.kernel32.SetConsoleWindowInfo(self.chandle, True, byref(wintypes.SMALL_RECT(0, 0, 99, 49)))
                windll.kernel32.SetConsoleScreenBufferSize(self.chandle, wintypes._COORD(100, 50))
        else:
            os.system('mode con: cols=100 lines=50')

    def setup_completer(self):
        commands = ['install', 'uninstall', 'update', 'force_update', 'status', 'orphans', 'search', 'toggle_backup',
                    'toggle_dev', 'uri_integration', 'help', 'exit']
        addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
        for addon in addons:
            commands.extend([f'uninstall {addon["Name"]}', f'update {addon["Name"]}', f'force_update {addon["Name"]}',
                             f'toggle_dev {addon["Name"]}', f'status {addon["Name"]}'])
        self.completer = WordCompleter(commands, ignore_case=True, sentence=True)

    def setup_table(self):
        self.table_data = [[f'{Fore.LIGHTWHITE_EX}Status{Fore.RESET}', f'{Fore.LIGHTWHITE_EX}Name{Fore.RESET}',
                            f'{Fore.LIGHTWHITE_EX}Version{Fore.RESET}']]
        self.table = SingleTable(self.table_data)
        self.table.justify_columns[0] = 'center'

    def c_install(self, args):
        if args:
            addons = args.split(',')
            with tqdm(total=len(addons), bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
                for addon in addons:
                    installed, name, version = self.core.add_addon(addon)
                    if installed:
                        self.table_data.append([f'{Fore.GREEN}Installed{Fore.RESET}', name, version])
                    else:
                        self.table_data.append([f'{Fore.LIGHTBLACK_EX}Already installed{Fore.RESET}', name, version])
                    pbar.update(1)
            print(self.table.table)
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts a comma-separated list of links as an a'
                         'rgument.\n<ansigreen>Supported URLs:</ansigreen>\n\thttps://www.curseforge.com/wow/addons/[ad'
                         'don_name]\n\thttps://www.wowinterface.com/downloads/[addon_name]\n\tElvUI\n\tElvUI:Dev\n\tTuk'
                         'UI'))

    def c_uninstall(self, args):
        if args:
            addons = args.split(',')
            with tqdm(total=len(addons), bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
                for addon in addons:
                    name, version = self.core.del_addon(addon)
                    if name:
                        self.table_data.append([f'{Fore.LIGHTRED_EX}Uninstalled{Fore.RESET}', name, version])
                    else:
                        self.table_data.append([f'{Fore.LIGHTBLACK_EX}Not installed{Fore.RESET}', addon, ''])
                    pbar.update(1)
            print(self.table.table)
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts a comma-separated list of links or addo'
                         'n names as an argument.\n<ansigreen>Supported URLs:</ansigreen>\n\thttps://www.curseforge.com'
                         '/wow/addons/[addon_name]\n\thttps://www.wowinterface.com/downloads/[addon_name]\n\tElvUI\n\tE'
                         'lvUI:Dev\n\tTukUI'))

    def c_update(self, args, addline=False, update=True, force=False):
        if args:
            addons = args.split(',')
        else:
            addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
        with tqdm(total=len(addons), bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
            for addon in addons:
                name, versionnew, versionold, modified = self.core.\
                    update_addon(addon if isinstance(addon, str) else addon['URL'], update, force)
                if versionold:
                    if versionold == versionnew:
                        if modified:
                            self.table_data.append([f'{Fore.LIGHTRED_EX}Modified{Fore.RESET}', name, versionold])
                        else:
                            self.table_data.append([f'{Fore.GREEN}Up-to-date{Fore.RESET}', name, versionold])
                    else:
                        if modified:
                            self.table_data.append([f'{Fore.LIGHTRED_EX}Update suppressed{Fore.RESET}', name,
                                                    versionold])
                        else:
                            self.table_data.append([f'{Fore.YELLOW}{"Updated" if update else "Update available"}'
                                                    f'{Fore.RESET}', name, f'{Fore.YELLOW}{versionnew}{Fore.RESET}'])
                else:
                    self.table_data.append([f'{Fore.LIGHTBLACK_EX}Not installed{Fore.RESET}', addon, ''])
                pbar.update(1)
        print('\n' + self.table.table if addline else self.table.table)

    def c_force_update(self, args):
        if args:
            self.c_update(args, False, True, True)
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts a comma-separated list of links or addo'
                         'n names as an argument.'))

    def c_status(self, args):
        self.c_update(args, False, False)

    def c_orphans(self, _):
        orphansd, orphansf = self.core.find_orphans()
        printft(HTML('<ansigreen>Directories that are not part of any installed addon:</ansigreen>'))
        for orphan in sorted(orphansd):
            printft(HTML(orphan.replace('[GIT]', '<ansiyellow>[GIT]</ansiyellow>')))
        printft(HTML('\n<ansigreen>Files that are leftovers after no longer installed addons:</ansigreen>'))
        for orphan in sorted(orphansf):
            printft(orphan)

    def c_uri_integration(self, _):
        self.core.create_reg()
        printft('CurseBreaker.reg file was created. Attempting to import...')
        out = os.system('"' + os.path.join(os.path.dirname(sys.executable), 'CurseBreaker.reg') + '"')
        if out != 0:
            printft('Import failed. Please try to import REG file manually.')
        else:
            os.remove('CurseBreaker.reg')

    def c_toggle_dev(self, args):
        if args:
            status = self.core.dev_toggle(args)
            if status is None:
                printft(HTML('<ansibrightred>This addon does not exist or it is not installed yet.</ansibrightred>'))
            elif status:
                printft('This addon will now prioritize alpha/beta versions.')
            else:
                printft('This addon will not longer prioritize alpha/beta versions.')
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts an addon name as an argument.'))

    def c_toggle_backup(self, _):
        status = self.core.backup_toggle()
        printft('Backup of WTF directory is now:',
                HTML('<ansigreen>ENABLED</ansigreen>') if status else HTML('<ansired>DISABLED</ansired>'))

    def c_search(self, args):
        if args:
            results = self.core.search(args)
            printft(HTML('<ansigreen>Top results of your search:</ansigreen>'))
            for url in results:
                if self.core.check_if_installed(url):
                    printft(HTML(f'{url} <ansiyellow>[Installed]</ansiyellow>'))
                else:
                    printft(url)
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts a search query as an argument.'))

    def c_help(self, _):
        printft(HTML('<ansigreen>install [URL]</ansigreen>\n\tCommand accepts a comma-separated list of links.'))
        printft(HTML('<ansigreen>uninstall [URL/Name]</ansigreen>\n\tCommand accepts a comma-separated list of links or'
                     ' addon names.'))
        printft(HTML('<ansigreen>update [URL/Name]</ansigreen>\n\tCommand accepts a comma-separated list of links or ad'
                     'don names.\n\tIf no argument is provided all non-modified addons will be updated.'))
        printft(HTML('<ansigreen>force_update [URL/Name]</ansigreen>\n\tCommand accepts a comma-separated list of links'
                     ' or addon names.\n\tSelected addons will be reinstalled or updated regardless of their current st'
                     'ate.'))
        printft(HTML('<ansigreen>status</ansigreen>\n\tPrints the current state of all installed addons.'))
        printft(HTML('<ansigreen>orphans</ansigreen>\n\tPrints list of orphaned directories and files.'))
        printft(HTML('<ansigreen>search [Keyword]</ansigreen>\n\tExecute addon search on CurseForge.'))
        printft(HTML('<ansigreen>toggle_backup</ansigreen>\n\tEnable/disable automatic daily backup of WTF directory.'))
        printft(HTML('<ansigreen>toggle_dev</ansigreen>\n\tThis command accepts an addon name as an argument.\n\tPriori'
                     'tize alpha/beta versions for the provided addon.'))
        printft(HTML('<ansigreen>uri_integration</ansigreen>\n\tEnable integration with CurseForge page. "Install" butt'
                     'on will now start this application.'))
        printft(HTML('\n<ansibrightgreen>Supported URLs:</ansibrightgreen>\n\thttps://www.curseforge.com/wow/addons/[ad'
                     'don_name]\n\thttps://www.wowinterface.com/downloads/[addon_name]\n\tElvUI\n\tElvUI:Dev\n\tTukUI'))

    def c_exit(self, _):
        sys.exit(0)


if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
    os.system(f'title CurseBreaker v{__version__}')
    app = TUI()
    app.start()
