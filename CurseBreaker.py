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
from csv import reader
from pathlib import Path
from datetime import datetime
from rich import box
from rich.rule import Rule
from rich.table import Table
from rich.console import Console
from rich.progress import Progress, BarColumn
from rich.traceback import Traceback, install
from multiprocessing import freeze_support
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.completion import WordCompleter
from distutils.version import StrictVersion
from CB import HEADERS, HEADLESS_TERMINAL_THEME, __version__
from CB.Core import Core
from CB.Compat import pause, timeout, clear, set_terminal_title, set_terminal_size, getch, kbhit
from CB.Wago import WagoUpdater

if platform.system() == 'Windows':
    from ctypes import windll, wintypes


class TUI:
    def __init__(self):
        self.core = Core()
        self.session = PromptSession(reserve_space_for_menu=6)
        self.headless = False
        self.console = None
        self.table = None
        self.cfSlugs = None
        self.wowiSlugs = None
        self.completer = None
        self.os = platform.system()
        install()

    def start(self):
        # Check if headless mode was requested
        if len(sys.argv) == 2 and sys.argv[1].lower() == 'headless':
            self.headless = True
        self.setup_console()
        self.print_header()
        # Check if executable is in good location
        if not glob.glob('World*.app') and not glob.glob('Wow*.exe') or \
                not os.path.isdir(Path('Interface/AddOns')) or not os.path.isdir('WTF'):
            self.console.print('[bold red]This executable should be placed in the same directory where Wow.exe, '
                               'WowClassic.exe or World of Warcraft.app is located.[/bold red]\n\n')
            pause(self.headless)
            sys.exit(1)
        # Detect Classic client
        if os.path.basename(os.getcwd()) == '_classic_':
            self.core.clientType = 'wow_classic'
            set_terminal_title(f'CurseBreaker v{__version__} - Classic')
        # Check if client have write access
        try:
            with open('PermissionTest', 'w') as _:
                pass
            os.remove('PermissionTest')
        except IOError:
            self.console.print('[bold red]CurseBreaker doesn\'t have write rights for the current directory.\n'
                               'Try starting it with administrative privileges.[/bold red]\n\n')
            pause(self.headless)
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
            timeout(self.headless)
            sys.exit(0)
        if len(sys.argv) == 2 and '.ccip' in sys.argv[1]:
            try:
                path = sys.argv[1].strip()
                self.c_install(self.core.parse_cf_xml(path))
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                self.handle_exception(e)
            timeout(self.headless)
            sys.exit(0)
        # CLI command
        if len(sys.argv) >= 2:
            command = ' '.join(sys.argv[1:]).split(' ', 1)
            if command[0].lower() == 'headless':
                pass
            elif getattr(self, f'c_{command[0].lower()}', False):
                try:
                    getattr(self, f'c_{command[0].lower()}')(command[1].strip() if len(command) > 1 else False)
                except Exception as e:
                    self.handle_exception(e)
                sys.exit(0)
            else:
                self.console.print('Command not found.')
                sys.exit(0)
        # Addons auto update
        if len(self.core.config['Addons']) > 0:
            if not self.headless:
                self.console.print('Automatic update of all addons will start in 5 seconds.\n'
                                   'Press any button to enter interactive mode.', highlight=False)
            starttime = time.time()
            keypress = None
            while True:
                if self.headless:
                    break
                elif kbhit():
                    keypress = getch()
                    break
                elif time.time() - starttime > 5:
                    break
            if not keypress:
                if not self.headless:
                    self.print_header()
                try:
                    self.c_update(None, True)
                    if self.core.backup_check():
                        self.setup_table()
                        self.console.print(f'\n[green]Backing up WTF directory{"!" if self.headless else ":"}[/green]')
                        self.core.backup_wtf(None if self.headless else self.console)
                    if self.core.config['WAUsername'] != 'DISABLED':
                        self.setup_table()
                        self.c_wa_update(None, False)
                except Exception as e:
                    self.handle_exception(e)
                self.console.print('')
                self.print_log()
                pause(self.headless)
                sys.exit(0)
        if self.headless:
            sys.exit(1)
        self.setup_completer()
        self.print_header()
        self.console.print('Use command [green]help[/green] or press [green]TAB[/green] to see a list of available comm'
                           'ands.\nCommand [green]exit[/green] or pressing [green]CTRL+D[/green] will close the applica'
                           'tion.\n\n')
        if len(self.core.config['Addons']) == 0:
            self.console.print('Command [green]import[/green] might be used to detect already installed addons.\n\n')
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
                    self.console.print('Command not found.')

    def auto_update(self):
        if getattr(sys, 'frozen', False):
            try:
                if os.path.isfile(sys.executable + '.old'):
                    try:
                        os.remove(sys.executable + '.old')
                    except PermissionError:
                        pass
                payload = requests.get('https://api.github.com/repos/AcidWeb/CurseBreaker/releases/latest',
                                       headers=HEADERS).json()
                if 'name' in payload and 'body' in payload and 'assets' in payload:
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
                        self.console.print('[green]Updating CurseBreaker...[/green]')
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
                        os.chmod(sys.executable, 0o775)
                        self.console.print(f'[bold green]Update complete! Please restart the application.[/bold green]'
                                           f'\n\n[green]Changelog:[/green]\n{changelog}\n\n')
                        self.print_log()
                        pause(self.headless)
                        sys.exit(0)
            except Exception as e:
                self.console.print(f'[bold red]Update failed!\n\nReason: {str(e)}[/bold red]\n\n')
                self.print_log()
                pause(self.headless)
                sys.exit(1)

    def handle_exception(self, e, table=True):
        if self.table.row_count > 1 and table:
            self.console.print(self.table)
        if getattr(sys, 'frozen', False):
            sys.tracebacklimit = 0
        if isinstance(e, list):
            for es in e:
                self.console.print(Traceback.from_exception(exc_type=es.__class__, exc_value=es,
                                                            traceback=es.__traceback__))
        else:
            self.console.print(Traceback.from_exception(exc_type=e.__class__, exc_value=e, traceback=e.__traceback__))

    def print_header(self):
        clear()
        if self.headless:
            self.console.print(f'[bold green]CurseBreaker[/bold green] [bold red]v{__version__}[/bold red] | '
                               f'[yellow]{datetime.now()}[/yellow]', highlight=False)
        else:
            self.console.print(Rule(f'[bold green]CurseBreaker[/bold green] [bold red]v{__version__}[/bold red]'))
            self.console.print('\n')

    def print_log(self):
        if self.headless:
            html = self.console.export_html(inline_styles=True, theme=HEADLESS_TERMINAL_THEME)
            with open('CurseBreaker.html', 'a+', encoding='utf-8') as log:
                log.write(html)

    def setup_console(self):
        if self.headless:
            self.console = Console(record=True)
            if self.os == 'Windows':
                window = windll.kernel32.GetConsoleWindow()
                if window:
                    windll.user32.ShowWindow(window, 0)
        elif 'WINDIR' in os.environ and 'WT_SESSION' not in os.environ:
            set_terminal_size(100, 50)
            if platform.system() == 'Windows':
                windll.kernel32.SetConsoleScreenBufferSize(windll.kernel32.GetStdHandle(-11), wintypes._COORD(100, 200))
            self.console = Console(width=97)
        elif self.os == 'Darwin':
            set_terminal_size(100, 50)
            self.console = Console()
        else:
            self.console = Console()

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
            name = f'"{addon["Name"]}"' if ',' in addon["Name"] else addon["Name"]
            commands.extend([f'uninstall {name}', f'update {name}', f'force_update {name}', f'toggle_dev {name}',
                             f'status {name}'])
        for item in self.cfSlugs:
            commands.append(f'install cf:{item}')
        for item in self.wowiSlugs:
            commands.append(f'install wowi:{item}')
        commands.extend(['install ElvUI', 'install ElvUI:Dev', 'install Tukui', 'install SLE:Dev', 'toggle_dev global'])
        accounts = self.core.detect_accounts()
        for account in accounts:
            commands.append(f'set_wa_wow_account {account}')
        self.completer = WordCompleter(commands, ignore_case=True, sentence=True)

    def setup_table(self):
        self.table = Table(box=box.SQUARE)
        self.table.add_column('Status', header_style='bold white', no_wrap=True, justify='center')
        self.table.add_column('Name', header_style='bold white', no_wrap=True)
        self.table.add_column('Version', header_style='bold white', no_wrap=True)

    def c_install(self, args):
        if args:
            if args.startswith('-i '):
                args = args[3:]
                optignore = True
            else:
                optignore = False
            addons = [addon.strip() for addon in list(reader([args], skipinitialspace=True))[0]]
            with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|',
                          auto_refresh=False, console=self.console) as progress:
                task = progress.add_task('', total=len(addons))
                while not progress.finished:
                    for addon in addons:
                        installed, name, version = self.core.add_addon(addon, optignore)
                        if installed:
                            self.table.add_row('[green]Installed[/green]', name, version)
                        else:
                            self.table.add_row('[bold black]Already installed[/bold black]', name, version)
                        progress.update(task, advance=1, refresh=True)
            self.console.print(self.table)
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a comma-separated list of links as an arg'
                               'ument.\n\tOption [bold white]-i[/bold white] will disable the client version check.\n[b'
                               'old green]Supported URL:[/bold green]\n\thttps://www.curseforge.com/wow/addons/[[addon_'
                               'name]] [bold white]|[/bold white] cf:[[addon_name]]\n\thttps://www.wowinterface.com/dow'
                               'nloads/[[addon_name]] [bold white]|[/bold white] wowi:[[addon_id]]\n\thttps://www.tukui'
                               '.org/addons.php?id=[[addon_id]] [bold white]|[/bold white] tu:[[addon_id]]\n\thttps://w'
                               'ww.tukui.org/classic-addons.php?id=[[addon_id]] [bold white]|[/bold white] tuc:[[addon_'
                               'id]]\n\thttps://github.com/[[username]]/[[repository_name]] [bold white]|[/bold white] '
                               'gh:[[username]]/[[repository_name]]\n\tElvUI [bold white]|[/bold white] ElvUI:Dev\n\tTu'
                               'kui\n\tSLE:Dev', highlight=False)

    def c_uninstall(self, args):
        if args:
            addons = [addon.strip() for addon in list(reader([args], skipinitialspace=True))[0]]
            with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|',
                          auto_refresh=False, console=self.console) as progress:
                task = progress.add_task('', total=len(addons))
                while not progress.finished:
                    for addon in addons:
                        name, version = self.core.del_addon(addon)
                        if name:
                            self.table.add_row(f'[bold red]Uninstalled[/bold red]', name, version)
                        else:
                            self.table.add_row(f'[bold black]Not installed[/bold black]', addon, '')
                        progress.update(task, advance=1, refresh=True)
            self.console.print(self.table)
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a comma-separated list of addon names or '
                               'full links as an argument.\n[bold green]Supported URL:[/bold green]\n\thttps://www.curs'
                               'eforge.com/wow/addons/[[addon_name]]\n\thttps://www.wowinterface.com/downloads/[[addon_'
                               'name]]\n\thttps://www.tukui.org/addons.php?id=[[addon_id]]\n\thttps://www.tukui.org/cla'
                               'ssic-addons.php?id=[[addon_id]]\n\thttps://github.com/[[username]]/[[repository_name]]',
                               highlight=False)

    def c_update(self, args, addline=False, update=True, force=False):
        if len(self.core.cfCache) > 0 or len(self.core.wowiCache) > 0:
            self.core.cfCache = {}
            self.core.wowiCache = {}
            self.core.checksumCache = {}
        if args:
            addons = [addon.strip() for addon in list(reader([args], skipinitialspace=True))[0]]
        else:
            addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
        exceptions = []
        with Progress('{task.completed:.0f}/{task.total}', '|', BarColumn(bar_width=None), '|',
                      auto_refresh=False, console=None if self.headless else self.console) as progress:
            task = progress.add_task('', total=len(addons))
            if not args:
                self.core.bulk_check(addons)
                self.core.bulk_check_checksum(addons, progress)
            while not progress.finished:
                for addon in addons:
                    try:
                        name, versionnew, versionold, modified = self.core.\
                            update_addon(addon if isinstance(addon, str) else addon['URL'], update, force)
                        if versionold:
                            if versionold == versionnew:
                                if modified:
                                    self.table.add_row('[bold red]Modified[/bold red]', name, versionold)
                                else:
                                    self.table.add_row('[green]Up-to-date[/green]', name, versionold)
                            else:
                                if modified:
                                    self.table.add_row('[bold red]Update suppressed[/bold red]', name, versionold)
                                else:
                                    self.table.add_row(f'[yellow]{"Updated" if update else "Update available"}'
                                                       f'[/yellow]', name, f'[yellow]{versionnew}[/yellow]')
                        else:
                            self.table.add_row(f'[bold black]Not installed[/bold black]', addon, '')
                    except Exception as e:
                        exceptions.append(e)
                    progress.update(task, advance=1 if args else 0.5, refresh=True)
        if addline:
            self.console.print('\n')
        self.console.print(self.table)
        if len(addons) == 0:
            self.console.print('Apparently there are no addons installed by CurseBreaker.\n'
                               'Command [green]import[/green] might be used to detect already installed addons.')
        if len(exceptions) > 0:
            self.handle_exception(exceptions, False)

    def c_force_update(self, args):
        if args:
            self.c_update(args, False, True, True)
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a comma-separated list of addon names or '
                               'full links as an argument.')

    def c_status(self, args):
        self.c_update(args, False, False)

    def c_orphans(self, _):
        orphansd, orphansf = self.core.find_orphans()
        self.console.print('[green]Directories that are not part of any installed addon:[/green]')
        for orphan in sorted(orphansd):
            self.console.print(orphan.replace('[GIT]', '[yellow][[GIT]][/yellow]'), highlight=False)
        self.console.print('\n[green]Files that are leftovers after no longer installed addons:[/green]')
        for orphan in sorted(orphansf):
            self.console.print(orphan, highlight=False)

    def c_uri_integration(self, _):
        if self.os == 'Windows':
            self.core.create_reg()
            self.console.print('CurseBreaker.reg file was created. Attempting to import...')
            out = os.system('"' + str(Path(os.path.dirname(sys.executable), 'CurseBreaker.reg')) + '"')
            if out != 0:
                self.console.print('Import failed. Please try to import REG file manually.')
            else:
                os.remove('CurseBreaker.reg')
        else:
            self.console.print('This feature is available only on Windows.')

    def c_toggle_dev(self, args):
        if args:
            status = self.core.dev_toggle(args)
            if status is None:
                self.console.print('[bold red]This addon doesn\'t exist or it is not installed yet.[/bold red]')
            elif status == -1:
                self.console.print('[bold red]This feature can be only used with CurseForge addons.[/bold red]')
            elif status == 0:
                self.console.print('All CurseForge addons are now switched' if args == 'global' else 'Addon switched',
                                   'to the [yellow]beta[/yellow] channel.')
            elif status == 1:
                self.console.print('All CurseForge addons are now switched' if args == 'global' else 'Addon switched',
                                   'to the [red]alpha[/red] channel.')
            elif status == 2:
                self.console.print('All CurseForge addons are now switched' if args == 'global' else 'Addon switched',
                                   'to the [green]stable[/green] channel.')
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts an addon name (or "global") as an'
                               ' argument.', highlight=False)

    def c_toggle_backup(self, _):
        status = self.core.backup_toggle()
        self.console.print('Backup of WTF directory is now:',
                           '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')

    def c_toggle_wa(self, args):
        if args:
            if args == self.core.config['WAUsername']:
                self.console.print(f'WeakAuras version check is now: [green]ENABLED[/green]\nAuras created by '
                                   f'[bold white]{self.core.config["WAUsername"]}[/bold white] are now included.')
                self.core.config['WAUsername'] = ''
            else:
                self.core.config['WAUsername'] = args.strip()
                self.console.print(f'WeakAuras version check is now: [green]ENABLED[/green]\nAuras created by '
                                   f'[bold white]{self.core.config["WAUsername"]}[/bold white] are now ignored.')
        else:
            if self.core.config['WAUsername'] == 'DISABLED':
                self.core.config['WAUsername'] = ''
                self.console.print('WeakAuras version check is now: [green]ENABLED[/green]')
            else:
                self.core.config['WAUsername'] = 'DISABLED'
                shutil.rmtree(Path('Interface/AddOns/WeakAurasCompanion'), ignore_errors=True)
                self.console.print('WeakAuras version check is now: [red]DISABLED[/red]')
        self.core.save_config()

    def c_set_wa_api(self, args):
        if args:
            self.console.print('Wago API key is now set.')
            self.core.config['WAAPIKey'] = args.strip()
            self.core.save_config()
        elif self.core.config['WAAPIKey'] != '':
            self.console.print('Wago API key is now removed.')
            self.core.config['WAAPIKey'] = ''
            self.core.save_config()
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts API key as an argument.')

    def c_set_wa_wow_account(self, args):
        if args:
            args = args.strip()
            if os.path.isfile(Path(f'WTF/Account/{args}/SavedVariables/WeakAuras.lua')):
                self.console.print(f'WoW account name set to: [bold white]{args}[/bold white]')
                self.core.config['WAAccountName'] = args
                self.core.save_config()
            else:
                self.console.print('Incorrect WoW account name.')
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts the WoW account name as an argument.')

    def c_wa_update(self, _, verbose=True):
        if os.path.isdir(Path('Interface/AddOns/WeakAuras')):
            accounts = self.core.detect_accounts()
            if len(accounts) == 0:
                return
            elif len(accounts) > 1 and self.core.config['WAAccountName'] == '':
                if verbose:
                    self.console.print('More than one WoW account detected.\nPlease use [bold white]set_wa_wow_account['
                                       '/bold white] command to set the correct account name.')
                else:
                    self.console.print('\n[green]More than one WoW account detected.[/green]\nPlease use [bold white]se'
                                       't_wa_wow_account[/bold white] command to set the correct account name.')
                return
            elif len(accounts) == 1 and self.core.config['WAAccountName'] == '':
                self.core.config['WAAccountName'] = accounts[0]
                self.core.save_config()
            wa = WagoUpdater(self.core.config['WAUsername'], self.core.config['WAAccountName'],
                             self.core.config['WAAPIKey'])
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
                self.console.print('[green]Outdated WeakAuras:[/green]')
                for aura in status[0]:
                    self.console.print(aura, highlight=False)
                self.console.print('\n[green]Detected WeakAuras:[/green]')
                for aura in status[1]:
                    self.console.print(aura, highlight=False)
            else:
                self.console.print(f'\n[green]The number of outdated WeakAuras:[/green] {len(status[0])}',
                                   highlight=False)
        elif verbose:
            self.console.print('WeakAuras addon is not installed.')

    def c_search(self, args):
        if args:
            results = self.core.search(args)
            self.console.print('[green]Top results of your search:[/green]')
            for url in results:
                if self.core.check_if_installed(url):
                    self.console.print(f'{url} [yellow][[Installed]][/yellow]', highlight=False)
                else:
                    self.console.print(url, highlight=False)
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a search query as an argument.')

    def c_import(self, args):
        hit, partial_hit, miss = self.core.detect_addons()
        if args == 'install' and len(hit) > 0:
            self.c_install(','.join(hit))
        else:
            self.console.print(f'[green]Addons found:[/green]')
            for addon in hit:
                self.console.print(addon, highlight=False)
            self.console.print(f'\n[yellow]Possible matches:[/yellow]')
            for addon in partial_hit:
                self.console.print(' [bold white]or[/bold white] '.join(addon), highlight=False)
            self.console.print(f'\n[red]Unknown directories:[/red]')
            for addon in miss:
                self.console.print(f'{addon}', highlight=False)
            self.console.print(f'\nExecute [bold white]import install[/bold white] command to install all detected addo'
                               f'ns.\nPossible matches need to be installed manually with the [bold white]install[/bold'
                               f' white] command.\nAddons that are available only on WoWInterface and/or Tukui are not '
                               f'detected by this process.')

    def c_export(self, _):
        self.console.print(self.core.export_addons(), highlight=False)

    def c_help(self, _):
        self.console.print('[green]install [URL][/green]\n\tCommand accepts a comma-separated list of links.\n'
                           '[green]uninstall [URL/Name][/green]\n\tCommand accepts a comma-separated list of addon name'
                           's or full links.\n'
                           '[green]update [URL/Name][/green]\n\tCommand accepts a comma-separated list of addon names o'
                           'r full links.\n\tIf no argument is provided all non-modified addons will be updated.\n'
                           '[green]force_update [URL/Name][/green]\n\tCommand accepts a comma-separated list of addon n'
                           'ames or full links.\n\tSelected addons will be reinstalled or updated regardless of their c'
                           'urrent state.\n'
                           '[green]wa_update[/green]\n\tCommand detects all installed WeakAuras and generate WeakAura'
                           's Companion payload.\n'
                           '[green]status[/green]\n\tPrints the current state of all installed addons.\n'
                           '[green]orphans[/green]\n\tPrints list of orphaned directories and files.\n'
                           '[green]search [Keyword][/green]\n\tExecutes addon search on CurseForge.\n'
                           '[green]import[/green]\n\tCommand attempts to import already installed addons.\n'
                           '[green]export[/green]\n\tCommand prints list of all installed addons in a form suitable f'
                           'or sharing.\n'
                           '[green]toggle_backup[/green]\n\tEnables/disables automatic daily backup of WTF directory.'
                           '\n[green]toggle_dev [Name][/green]\n\tCommand accepts an addon name (or "global") as'
                           ' argument.\n\tPrioritizes alpha/beta versions for the provided addon.\n'
                           '[green]toggle_wa [Username][/green]\n\tEnables/disables automatic WeakAuras updates.\n\tI'
                           'f a username is provided check will start to ignore the specified author.\n'
                           '[green]set_wa_api [API key][/green]\n\tSets Wago API key required to access private auras'
                           '.\n\tIt can be procured here: [link=https://wago.io/account]https://wago.io/account[/link]'
                           '\n[green]set_wa_wow_account [Account name][/green]\n\tSets WoW account used by WeakAuras up'
                           'dater.\n\tNeeded only if WeakAuras are used on more than one WoW account.\n'
                           '[green]uri_integration[/green]\n\tEnables integration with CurseForge page.\n\t[i]"Install"'
                           '[/i] button will now start this application.\n'
                           '\n[bold green]Supported URL:[/bold green]\n\thttps://www.curseforge.com/wow/addons/[[addon_'
                           'name]] [bold white]|[/bold white] cf:[[addon_name]]\n\thttps://www.wowinterface.com/downloa'
                           'ds/[[addon_name]] [bold white]|[/bold white] wowi:[[addon_id]]\n\thttps://www.tukui.org/add'
                           'ons.php?id=[[addon_id]] [bold white]|[/bold white] tu:[[addon_id]]\n\thttps://www.tukui.org'
                           '/classic-addons.php?id=[[addon_id]] [bold white]|[/bold white] tuc:[[addon_id]]\n\thttps://'
                           'github.com/[[username]]/[[repository_name]] [bold white]|[/bold white] gh:[[username]]/[[re'
                           'pository_name]]\n\tElvUI [bold white]|[/bold white] ElvUI:Dev\n\tTukui\n\tSLE:Dev',
                           highlight=False)

    def c_exit(self, _):
        sys.exit(0)


if __name__ == '__main__':
    freeze_support()
    clientpath = os.environ.get('CURSEBREAKER_PATH')
    if clientpath:
        os.chdir(clientpath)
    elif getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
    set_terminal_title(f'CurseBreaker v{__version__}')
    app = TUI()
    app.start()
