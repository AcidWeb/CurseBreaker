import os
import io
import sys
import time
import gzip
import glob
import shutil
import pickle
import zipfile
import requests
import platform
import traceback
from tqdm import tqdm
from pathlib import Path
from terminaltables import SingleTable
from prompt_toolkit import PromptSession, HTML, ANSI, print_formatted_text as printft
from prompt_toolkit.completion import WordCompleter
from distutils.version import StrictVersion
from CB import AC, HEADERS, __version__
from CB.Core import Core
from CB.Compat import pause, timeout, clear, set_terminal_title, set_terminal_size, getch, kbhit, UnicodeSingleTable
from CB.WeakAura import WeakAuraUpdater

if platform.system() == 'Windows':
    from ctypes import windll, wintypes, byref


class TUI:
    def __init__(self):
        self.core = Core()
        self.session = PromptSession(reserve_space_for_menu=7)
        self.tableData = None
        self.table = None
        self.cfSlugs = None
        self.wowiSlugs = None
        self.completer = None
        self.os = platform.system()
        if self.os == 'Windows':
            self.chandle = windll.kernel32.GetStdHandle(-11)
        sys.tracebacklimit = 0

    def start(self):
        self.setup_console()
        self.print_header()
        # Check if executable is in good location
        if not glob.glob('World*.app') and not os.path.isfile('Wow.exe') or \
                not os.path.isdir(Path('Interface/AddOns')) or not os.path.isdir('WTF'):
            printft(HTML('<ansibrightred>This executable should be placed in the same directory where Wow.exe or World '
                         'of Warcraft.app is located.</ansibrightred>\n'))
            pause()
            sys.exit(1)
        # Detect Classic client
        if os.path.basename(os.path.dirname(sys.executable)) == '_classic_':
            self.core.clientType = 'wow_classic'
            set_terminal_title(f'CurseBreaker v{__version__} - Classic')
        # Check if client have write access
        try:
            with open('PermissionTest', 'w') as _:
                pass
            os.remove('PermissionTest')
        except IOError:
            printft(HTML('<ansibrightred>CurseBreaker doesn\'t have write rights for the current directory.\n'
                         'Try starting it with administrative privileges.</ansibrightred>\n'))
            pause()
            sys.exit(1)
        self.auto_update()
        self.core.init_config()
        self.setup_table()
        # Curse URI Support
        if len(sys.argv) == 2 and 'twitch://' in sys.argv[1]:
            try:
                self.c_install(sys.argv[1].strip())
            except Exception as e:
                self.handle_exception(e)
            timeout()
            sys.exit(0)
        if len(sys.argv) == 2 and '.ccip' in sys.argv[1]:
            try:
                path = sys.argv[1].strip()
                self.c_install(self.core.parse_cf_xml(path))
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                self.handle_exception(e)
            timeout()
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
                if kbhit():
                    keypress = getch()
                    break
                elif time.time() - starttime > 5:
                    break
            if not keypress:
                if len(self.core.config['Addons']) > 35:
                    self.setup_console(len(self.core.config['Addons']))
                self.print_header()
                try:
                    self.c_update(None, True)
                    if self.core.backup_check():
                        self.setup_table()
                        printft(HTML('\n<ansigreen>Backing up WTF directory:</ansigreen>'))
                        self.core.backup_wtf()
                    if self.core.config['WAUsername'] != 'DISABLED':
                        self.setup_table()
                        self.c_wa_update(None, False)
                except Exception as e:
                    self.handle_exception(e)
                printft('')
                pause()
                sys.exit(0)
        self.setup_completer()
        self.setup_console(len(self.core.config['Addons']))
        self.print_header()
        printft(HTML('Use command <ansigreen>help</ansigreen> or press <ansigreen>TAB</ansigreen> to see a list of avai'
                     'lable commands.\nCommand <ansigreen>exit</ansigreen> or pressing <ansigreen>CTRL+D</ansigreen> wi'
                     'll close the application.\n'))
        if len(self.core.config['Addons']) == 0:
            printft(HTML('Command <ansigreen>import</ansigreen> might be used to detect already installed addons.\n'))
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
                if os.path.isfile(sys.executable + '.old'):
                    os.remove(sys.executable + '.old')
                payload = requests.get('https://api.github.com/repos/AcidWeb/CurseBreaker/releases/latest',
                                       headers=HEADERS).json()
                remoteversion = payload['name']
                changelog = payload['body']
                url = None
                for binary in payload['assets']:
                    if (self.os == 'Windows' and '.exe' in binary['name'])\
                            or (self.os == 'Darwin' and '.zip' in binary['name'])\
                            or (self.os == 'Linux' and '.gz' in binary['name']):
                        url = binary['browser_download_url']
                        break
                if url and StrictVersion(remoteversion[1:]) > StrictVersion(__version__):
                    printft(HTML('<ansigreen>Updating CurseBreaker...</ansigreen>'))
                    shutil.move(sys.executable, sys.executable + '.old')
                    payload = requests.get(url, headers=HEADERS)
                    if self.os == 'Darwin':
                        zipfile.ZipFile(io.BytesIO(payload.content)).extractall()
                    else:
                        with open(sys.executable, 'wb') as f:
                            if self.os == 'Windows':
                                f.write(payload.content)
                            elif self.os == 'Linux':
                                f.write(gzip.decompress(payload.content))
                    printft(HTML(f'<ansibrightgreen>Update complete! Please restart the application.</ansibrightgreen'
                                 f'>\n\n<ansigreen>Changelog:</ansigreen>\n{changelog}\n'))
                    pause()
                    sys.exit(0)
            except Exception as e:
                printft(HTML(f'<ansibrightred>Update failed!\n\nReason: {str(e)}</ansibrightred>\n'))
                pause()
                sys.exit(1)

    def handle_exception(self, e, table=True):
        if len(self.tableData) > 1 and table:
            self.sanitize_table()
            printft(ANSI(self.table.table))
        if getattr(sys, 'frozen', False):
            if isinstance(e, list):
                for es in e:
                    printft(HTML(f'\n<ansibrightred>{str(es)}</ansibrightred>'))
            else:
                printft(HTML(f'\n<ansibrightred>{str(e)}</ansibrightred>'))
        else:
            if isinstance(e, list):
                for es in e:
                    traceback.print_exception(es, es, es.__traceback__, limit=1000)
            else:
                traceback.print_exc(limit=1000)

    def print_header(self):
        clear()
        printft(HTML(f'<ansibrightblack>~~~ <ansibrightgreen>CurseBreaker</ansibrightgreen> <ansibrightred>v'
                     f'{__version__}</ansibrightred> ~~~</ansibrightblack>\n'))

    def setup_console(self, buffer=0):
        if getattr(sys, 'frozen', False) and self.os == 'Windows':
            if buffer > 0:
                windll.kernel32.SetConsoleScreenBufferSize(self.chandle, wintypes._COORD(100, 100 + round(buffer, -2)))
            else:
                windll.kernel32.SetConsoleWindowInfo(self.chandle, True, byref(wintypes.SMALL_RECT(0, 0, 99, 49)))
                windll.kernel32.SetConsoleScreenBufferSize(self.chandle, wintypes._COORD(100, 50))
        else:
            set_terminal_size(100, 50)

    def setup_completer(self):
        if not self.cfSlugs or not self.wowiSlugs:
            # noinspection PyBroadException
            try:
                self.cfSlugs = pickle.load(gzip.open(io.BytesIO(
                    requests.get('https://storage.googleapis.com/cursebreaker/cfslugs.pickle.gz',
                                 headers=HEADERS).content)))
                self.wowiSlugs = pickle.load(gzip.open(io.BytesIO(
                    requests.get('https://storage.googleapis.com/cursebreaker/wowislugs.pickle.gz',
                                 headers=HEADERS).content)))
            except Exception:
                self.cfSlugs = []
                self.wowiSlugs = []
        commands = ['install', 'uninstall', 'update', 'force_update', 'wa_update', 'status', 'orphans', 'search',
                    'import', 'export', 'toggle_backup', 'toggle_dev', 'toggle_wa', 'set_wa_api', 'set_wa_wow_account',
                    'uri_integration', 'help', 'exit']
        addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
        for addon in addons:
            commands.extend([f'uninstall {addon["Name"]}', f'update {addon["Name"]}', f'force_update {addon["Name"]}',
                             f'toggle_dev {addon["Name"]}', f'status {addon["Name"]}'])
        for item in self.cfSlugs:
            commands.append(f'install cf:{item}')
        for item in self.wowiSlugs:
            commands.append(f'install wowi:{item}')
        commands.extend(['install ElvUI', 'install ElvUI:Dev', 'install Tukui'])
        wa = WeakAuraUpdater('', '', '')
        accounts = wa.get_accounts()
        for account in accounts:
            commands.append(f'set_wa_wow_account {account}')
        self.completer = WordCompleter(commands, ignore_case=True, sentence=True)

    def setup_table(self):
        self.tableData = [[f'{AC.LIGHTWHITE_EX}Status{AC.RESET}', f'{AC.LIGHTWHITE_EX}Name{AC.RESET}',
                           f'{AC.LIGHTWHITE_EX}Version{AC.RESET}']]
        self.table = SingleTable(self.tableData) if self.os == 'Windows' else UnicodeSingleTable(self.tableData)
        self.table.justify_columns[0] = 'center'

    def sanitize_table(self):
        if not self.table.ok:
            mwidth = self.table.column_max_width(1)
            for row in self.table.table_data[1:]:
                if len(row[1]) > mwidth:
                    row[1] = row[1][:mwidth - 3] + '...'

    def c_install(self, args):
        if args:
            if args.startswith('-i '):
                args = args[3:]
                optignore = True
            else:
                optignore = False
            addons = [addon.strip() for addon in args.split(',')]
            with tqdm(total=len(addons), bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
                for addon in addons:
                    installed, name, version = self.core.add_addon(addon, optignore)
                    if installed:
                        self.tableData.append([f'{AC.GREEN}Installed{AC.RESET}', name, version])
                    else:
                        self.tableData.append([f'{AC.LIGHTBLACK_EX}Already installed{AC.RESET}', name, version])
                    pbar.update(1)
            self.sanitize_table()
            printft(ANSI(self.table.table))
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts a comma-separated list of links as an a'
                         'rgument.\n\tOption <ansiwhite>-i</ansiwhite> will disable the client version check.\n<ansigre'
                         'en>Supported URLs:</ansigreen>\n\thttps://www.curseforge.com/wow/addons/[addon_name] <ansiwhi'
                         'te>|</ansiwhite> cf:[addon_name]\n\thttps://www.wowinterface.com/downloads/[addon_name] <ansi'
                         'white>|</ansiwhite> wowi:[addon_id]\n\thttps://www.tukui.org/addons.php?id=[addon_id] <ansiwh'
                         'ite>|</ansiwhite> tu:[addon_id]\n\thttps://www.tukui.org/classic-addons.php?id=[addon_id] <an'
                         'siwhite>|</ansiwhite> tuc:[addon_id]\n\tElvUI <ansiwhite>|</ansiwhite> ElvU'
                         'I:Dev\n\tTukui'))

    def c_uninstall(self, args):
        if args:
            addons = [addon.strip() for addon in args.split(',')]
            with tqdm(total=len(addons), bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
                for addon in addons:
                    name, version = self.core.del_addon(addon)
                    if name:
                        self.tableData.append([f'{AC.LIGHTRED_EX}Uninstalled{AC.RESET}', name, version])
                    else:
                        self.tableData.append([f'{AC.LIGHTBLACK_EX}Not installed{AC.RESET}', addon, ''])
                    pbar.update(1)
            self.sanitize_table()
            printft(ANSI(self.table.table))
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts a comma-separated list of links as an a'
                         'rgument.\n<ansigreen>Supported URLs:</ansigreen>\n\thttps://www.curseforge.com/wow/addons/[ad'
                         'don_name] <ansiwhite>|</ansiwhite> cf:[addon_name]\n\thttps://www.wowinterface.com/downloads/'
                         '[addon_name] <ansiwhite>|</ansiwhite> wowi:[addon_id]\n\thttps://www.tukui.org/addons.php?id='
                         '[addon_id] <ansiwhite>|</ansiwhite> tu:[addon_id]\n\thttps://www.tukui.org/classic-addons.php'
                         '?id=[addon_id] <ansiwhite>|</ansiwhite> tuc:[addon_id]\n\tElvUI <ansiwhite>|</ansiwhite> ElvU'
                         'I:Dev\n\tTukui'))

    def c_update(self, args, addline=False, update=True, force=False):
        if len(self.core.cfCache) > 0 or len(self.core.wowiCache) > 0:
            self.core.cfCache = {}
            self.core.wowiCache = {}
        if args:
            addons = [addon.strip() for addon in args.split(',')]
        else:
            addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
            self.core.bulk_check(addons)
        with tqdm(total=len(addons), bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
            exceptions = []
            for addon in addons:
                try:
                    name, versionnew, versionold, modified = self.core.\
                        update_addon(addon if isinstance(addon, str) else addon['URL'], update, force)
                    if versionold:
                        if versionold == versionnew:
                            if modified:
                                self.tableData.append([f'{AC.LIGHTRED_EX}Modified{AC.RESET}', name, versionold])
                            else:
                                self.tableData.append([f'{AC.GREEN}Up-to-date{AC.RESET}', name, versionold])
                        else:
                            if modified:
                                self.tableData.append([f'{AC.LIGHTRED_EX}Update suppressed{AC.RESET}',
                                                       name, versionold])
                            else:
                                self.tableData.append([f'{AC.YELLOW}{"Updated " if update else "Update available"}'
                                                       f'{AC.RESET}', name, f'{AC.YELLOW}{versionnew}{AC.RESET}'])
                    else:
                        self.tableData.append([f'{AC.LIGHTBLACK_EX}Not installed{AC.RESET}', addon, ''])
                except Exception as e:
                    exceptions.append(e)
                pbar.update(1)
        self.sanitize_table()
        printft(ANSI('\n' + self.table.table if addline else self.table.table))
        if len(exceptions) > 0:
            self.handle_exception(exceptions, False)

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
        if self.os == 'Windows':
            self.core.create_reg()
            printft('CurseBreaker.reg file was created. Attempting to import...')
            out = os.system('"' + str(Path(os.path.dirname(sys.executable), 'CurseBreaker.reg')) + '"')
            if out != 0:
                printft('Import failed. Please try to import REG file manually.')
            else:
                os.remove('CurseBreaker.reg')
        else:
            printft('This feature is available only on Windows.')

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

    def c_toggle_wa(self, args):
        if args:
            if args == self.core.config['WAUsername']:
                printft(HTML(f'WeakAuras version check is now: <ansigreen>ENABLED</ansigreen>\n'
                             f'Auras created by <ansiwhite>{self.core.config["WAUsername"]}</ansiwhite>'
                             f' are now included.'))
                self.core.config['WAUsername'] = ''
            else:
                self.core.config['WAUsername'] = args.strip()
                printft(HTML(f'WeakAuras version check is now: <ansigreen>ENABLED</ansigreen>\n'
                             f'Auras created by <ansiwhite>{self.core.config["WAUsername"]}</ansiwhite>'
                             f' are now ignored.'))
        else:
            if self.core.config['WAUsername'] == 'DISABLED':
                self.core.config['WAUsername'] = ''
                printft(HTML('WeakAuras version check is now: <ansigreen>ENABLED</ansigreen>'))
            else:
                self.core.config['WAUsername'] = 'DISABLED'
                shutil.rmtree(Path('Interface/AddOns/WeakAurasCompanion'), ignore_errors=True)
                printft(HTML('WeakAuras version check is now: <ansired>DISABLED</ansired>'))
        self.core.save_config()

    def c_set_wa_api(self, args):
        if args:
            printft('Wago API key is now set.')
            self.core.config['WAAPIKey'] = args.strip()
            self.core.save_config()
        elif self.core.config['WAAPIKey'] != '':
            printft('Wago API key is now removed.')
            self.core.config['WAAPIKey'] = ''
            self.core.save_config()
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts API key as an argument.'))

    def c_set_wa_wow_account(self, args):
        if args:
            args = args.strip()
            if os.path.isfile(Path(f'WTF/Account/{args}/SavedVariables/WeakAuras.lua')):
                printft(HTML(f'WoW account name set to: <ansiwhite>{args}</ansiwhite>'))
                self.core.config['WAAccountName'] = args
                self.core.save_config()
            else:
                printft('Incorrect WoW account name.')
        else:
            printft(HTML('<ansigreen>Usage:</ansigreen>\n\tThis command accepts the WoW account name as an argument.'))

    def c_wa_update(self, _, verbose=True):
        if os.path.isdir(Path('Interface/AddOns/WeakAuras')):
            wa = WeakAuraUpdater('' if self.core.config['WAUsername'] == 'DISABLED' else self.core.config['WAUsername'],
                                 self.core.config['WAAccountName'], self.core.config['WAAPIKey'])
            accounts = wa.get_accounts()
            if len(accounts) > 1:
                if verbose:
                    printft(HTML('More than one WoW account detected.\nPlease use <ansiwhite>set_wa_wow_account</ansiwh'
                                 'ite> command to set the correct account name.'))
                else:
                    printft(HTML('\n<ansigreen>More than one WoW account detected.</ansigreen>\nPlease use <ansiwhite>s'
                                 'et_wa_wow_account</ansiwhite> command to set the correct account name.'))
                return
            if wa.accountName:
                if not self.core.config['WAAccountName']:
                    self.core.config['WAAccountName'] = wa.accountName
                    self.core.save_config()
                if self.core.waCompanionVersion != self.core.config['WACompanionVersion']:
                    self.core.config['WACompanionVersion'] = self.core.waCompanionVersion
                    self.core.save_config()
                    force = True
                else:
                    force = False
                wa.parse_storage()
                status = wa.check_updates()
                wa.install_companion(self.core.clientType, force)
                wa.install_data()
                if verbose:
                    printft(HTML('<ansigreen>Outdated WeakAuras:</ansigreen>'))
                    for aura in status[0]:
                        printft(aura)
                    printft(HTML('\n<ansigreen>Detected WeakAuras:</ansigreen>'))
                    for aura in status[1]:
                        printft(aura)
                else:
                    printft(HTML(f'\n<ansigreen>The number of outdated WeakAuras:</ansigreen> {len(status[0])}'))
        elif verbose:
            printft('WeakAuras addon is not installed.')

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

    def c_import(self, args):
        hit, partial_hit, miss = self.core.detect_addons()
        if args == 'install' and len(hit) > 0:
            self.c_install(','.join(hit))
        else:
            printft(HTML(f'<ansigreen>Addons found:</ansigreen>'))
            for addon in hit:
                printft(addon)
            printft(HTML(f'\n<ansiyellow>Possible matches:</ansiyellow>'))
            for addon in partial_hit:
                printft(HTML(' <ansiwhite>or</ansiwhite> '.join(addon)))
            printft(HTML(f'\n<ansired>Unknown directories:</ansired>'))
            for addon in miss:
                printft(f'{addon}')
            printft(HTML(f'\nExecute <ansiwhite>import install</ansiwhite> command to install all detected addons.\n'
                         f'Possible matches need to be installed manually with the <ansiwhite>install</ansiwhite>'
                         f' command.'))

    def c_export(self, _):
        printft(self.core.export_addons())

    def c_help(self, _):
        printft(HTML('<ansigreen>install [URL]</ansigreen>\n\tCommand accepts a comma-separated list of links.\n'
                     '<ansigreen>uninstall [URL/Name]</ansigreen>\n\tCommand accepts a comma-separated list of links or'
                     ' addon names.\n'
                     '<ansigreen>update [URL/Name]</ansigreen>\n\tCommand accepts a comma-separated list of links or ad'
                     'don names.\n\tIf no argument is provided all non-modified addons will be updated.\n'
                     '<ansigreen>force_update [URL/Name]</ansigreen>\n\tCommand accepts a comma-separated list of links'
                     ' or addon names.\n\tSelected addons will be reinstalled or updated regardless of their current st'
                     'ate.\n'
                     '<ansigreen>wa_update</ansigreen>\n\tCommand detects all installed WeakAuras and generate WeakAura'
                     's Companion payload.\n'
                     '<ansigreen>status</ansigreen>\n\tPrints the current state of all installed addons.\n'
                     '<ansigreen>orphans</ansigreen>\n\tPrints list of orphaned directories and files.\n'
                     '<ansigreen>search [Keyword]</ansigreen>\n\tExecutes addon search on CurseForge.\n'
                     '<ansigreen>import</ansigreen>\n\tCommand attempts to import already installed addons.\n'
                     '<ansigreen>export</ansigreen>\n\tCommand prints list of all installed addons in a form suitable f'
                     'or sharing.\n'
                     '<ansigreen>toggle_backup</ansigreen>\n\tEnables/disables automatic daily backup of WTF directory.'
                     '\n<ansigreen>toggle_dev [Name]</ansigreen>\n\tCommand accepts an addon name as argument.\n\tPrior'
                     'itizes alpha/beta versions for the provided addon.\n'
                     '<ansigreen>toggle_wa [Username]</ansigreen>\n\tEnables/disables automatic WeakAuras updates.\n\tI'
                     'f a username is provided check will start to ignore the specified author.\n'
                     '<ansigreen>set_wa_api [API key]</ansigreen>\n\tSets Wago API key required to access private auras'
                     '.\n\tIt can be procured here: https://wago.io/account\n'
                     '<ansigreen>set_wa_wow_account [Account name]</ansigreen>\n\tSets WoW account used by WeakAuras up'
                     'dater.\n\tNeeded only if WeakAuras are used on more than one WoW account.\n'
                     '<ansigreen>uri_integration</ansigreen>\n\tEnables integration with CurseForge page. "Install" but'
                     'ton will now start this application.\n'
                     '\n<ansibrightgreen>Supported URL:</ansibrightgreen>\n\thttps://www.curseforge.com/wow/addons/[add'
                     'on_name] <ansiwhite>|</ansiwhite> cf:[addon_name]\n\thttps://www.wowinterface.com/downloads/[addo'
                     'n_name] <ansiwhite>|</ansiwhite> wowi:[addon_id]\n\thttps://www.tukui.org/addons.php?id=[addon_id'
                     '] <ansiwhite>|</ansiwhite> tu:[addon_id]\n\thttps://www.tukui.org/classic-addons.php?id=[addon_id'
                     '] <ansiwhite>|</ansiwhite> tuc:[addon_id]\n\tElvUI <ansiwhite>|</ansiwhite> ElvUI:Dev\n\tTukui'))

    def c_exit(self, _):
        sys.exit(0)


if __name__ == '__main__':
    clientpath = os.environ.get('CURSEBREAKER_PATH')
    if clientpath:
        os.chdir(clientpath)
    elif getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
    set_terminal_title(f'CurseBreaker v{__version__}')
    app = TUI()
    app.start()
