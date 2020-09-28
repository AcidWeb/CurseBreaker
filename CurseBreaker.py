import os
import io
import re
import sys
import time
import gzip
import glob
import shutil
import pickle
import zipfile
import requests
import platform
import pyperclip
import subprocess
from csv import reader
from pathlib import Path
from datetime import datetime
from rich import box
from rich.text import Text
from rich.rule import Rule
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from rich.progress import Progress, BarColumn
from rich.traceback import Traceback, install
from multiprocessing import freeze_support
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.shortcuts import confirm
from prompt_toolkit.completion import WordCompleter, NestedCompleter
from distutils.version import StrictVersion
from CB import HEADERS, HEADLESS_TERMINAL_THEME, __version__
from CB.Core import Core
from CB.Compat import pause, timeout, clear, set_terminal_title, set_terminal_size, getch, kbhit
from CB.Wago import WagoUpdater

if platform.system() == 'Windows':
    from ctypes import windll, wintypes

# FIXME - Python bug #39010 - Fixed in 3.8.6/3.9
import asyncio
import selectors
asyncio.set_event_loop(asyncio.SelectorEventLoop(selectors.SelectSelector()))


class TUI:
    def __init__(self):
        self.core = Core()
        self.session = PromptSession(reserve_space_for_menu=6, complete_in_thread=True)
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
                               'WowClassic.exe or World of Warcraft.app is located. Additionally, make sure that '
                               'this WoW installation was started at least once.[/bold red]\n')
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
                               'Try starting it with administrative privileges.[/bold red]\n')
            pause(self.headless)
            sys.exit(1)
        self.auto_update()
        try:
            self.core.init_config()
        except RuntimeError:
            self.console.print('[bold red]The config file is corrupted. Restore the earlier version from backup.'
                               '[/bold red]\n')
            pause(self.headless)
            sys.exit(1)
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
        if len(self.core.config['Addons']) > 0 and self.core.config['AutoUpdate']:
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
                    self.motd_parser()
                    self.c_update(None, True)
                    if self.core.backup_check():
                        self.setup_table()
                        self.console.print(f'\n[green]Backing up WTF directory{"!" if self.headless else ":"}[/green]')
                        self.core.backup_wtf(None if self.headless else self.console)
                    if self.core.config['WAUsername'] != 'DISABLED':
                        self.setup_table()
                        self.c_wago_update(None, False)
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
                           'tion.\n')
        if len(self.core.config['Addons']) == 0:
            self.console.print('Command [green]import[/green] might be used to detect already installed addons.\n')
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
        if getattr(sys, 'frozen', False) and 'CURSEBREAKER_VARDEXMODE' not in os.environ:
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
                            zipfile.ZipFile(io.BytesIO(payload.content)).extractall(path=os.path.dirname(
                                os.path.abspath(sys.executable)))
                        else:
                            with open(sys.executable, 'wb') as f:
                                if self.os == 'Windows':
                                    f.write(payload.content)
                                elif self.os == 'Linux':
                                    f.write(gzip.decompress(payload.content))
                        os.chmod(sys.executable, 0o775)
                        self.console.print(f'[bold green]Update complete! The application will be restarted now.'
                                           f'[/bold green]\n\n[green]Changelog:[/green]\n{changelog}\n')
                        self.print_log()
                        pause(self.headless)
                        subprocess.call([sys.executable] + sys.argv[1:])
                        sys.exit(0)
            except Exception as e:
                self.console.print(f'[bold red]Update failed!\n\nReason: {str(e)}[/bold red]\n')
                self.print_log()
                pause(self.headless)
                sys.exit(1)

    def motd_parser(self):
        payload = requests.get('https://storage.googleapis.com/cursebreaker/motd', headers=HEADERS)
        if payload.status_code == 200:
            self.console.print(Panel(payload.content.decode('UTF-8'), title='MOTD', border_style='red'))
            self.console.print('')

    def handle_exception(self, e, table=True):
        if self.table.row_count > 1 and table:
            self.console.print(self.table)
        if getattr(sys, 'frozen', False) and 'CURSEBREAKER_DEBUG' not in os.environ:
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
            self.console.print('')

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
        addons = []
        for addon in sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower()):
            addons.append(addon['Name'])
        slugs = ['ElvUI', 'Tukui']
        for item in self.cfSlugs:
            slugs.append(f'cf:{item}')
        for item in self.wowiSlugs:
            slugs.append(f'wowi:{item}')
        slugs.extend(['ElvUI:Dev', 'Shadow&Light:Dev'])
        accounts = []
        for account in self.core.detect_accounts():
            accounts.append(account)
        self.completer = NestedCompleter.from_nested_dict({
            'install': WordCompleter(slugs, ignore_case=True, match_middle=True, WORD=True),
            'uninstall': WordCompleter(addons, ignore_case=True),
            'update': WordCompleter(addons, ignore_case=True),
            'force_update': WordCompleter(addons, ignore_case=True),
            'wago_update': None,
            'status': WordCompleter(addons, ignore_case=True),
            'orphans': None,
            'search': None,
            'import': {'install': None},
            'export': None,
            'toggle_backup': None,
            'toggle_dev': WordCompleter(addons + ['global'], ignore_case=True, sentence=True),
            'toggle_block': WordCompleter(addons, ignore_case=True, sentence=True),
            'toggle_compact_mode': None,
            'toggle_autoupdate': None,
            'toggle_wago': None,
            'set_wago_api': None,
            'set_wago_wow_account': WordCompleter(accounts, ignore_case=True, sentence=True),
            'uri_integration': None,
            'help': None,
            'exit': None
        })

    def setup_table(self):
        self.table = Table(box=box.SQUARE)
        self.table.add_column('Status', header_style='bold white', no_wrap=True, justify='center')
        self.table.add_column('Name', header_style='bold white')
        self.table.add_column('Version', header_style='bold white')

    def parse_args(self, args):
        parsed = []
        for addon in sorted(self.core.config['Addons'], key=lambda k: len(k['Name']), reverse=True):
            if addon['Name'] in args or addon['URL'] in args:
                parsed.append(addon['Name'])
                args = args.replace(addon['Name'], '', 1)
        return sorted(parsed)

    def c_install(self, args):
        if args:
            if args.startswith('-i '):
                args = args[3:]
                optignore = True
            else:
                optignore = False
            args = re.sub(r'([a-zA-Z0-9_:])([ ]+)([a-zA-Z0-9_:])', r'\1,\3', args)
            addons = [addon.strip() for addon in list(reader([args], skipinitialspace=True))[0]]
            with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|',
                          auto_refresh=False, console=self.console) as progress:
                task = progress.add_task('', total=len(addons))
                while not progress.finished:
                    for addon in addons:
                        installed, name, version = self.core.add_addon(addon, optignore)
                        if installed:
                            self.table.add_row('[green]Installed[/green]', Text(name, no_wrap=True),
                                               Text(version, no_wrap=True))
                        else:
                            self.table.add_row('[bold black]Already installed[/bold black]',
                                               Text(name, no_wrap=True), Text(version, no_wrap=True))
                        progress.update(task, advance=1, refresh=True)
            self.console.print(self.table)
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a space-separated list of links as an arg'
                               'ument.[bold white]\n\tFlags:[/bold white]\n\t\t[bold white]-i[/bold white] - Disable th'
                               'e client version check.\n[bold green]Supported URL:[/bold green]\n\thttps://www.cursefo'
                               'rge.com/wow/addons/\[addon_name] [bold white]|[/bold white] cf:\[addon_name]\n\thttps:/'
                               '/www.wowinterface.com/downloads/\[addon_name] [bold white]|[/bold white] wowi:\[addon_i'
                               'd]\n\thttps://www.tukui.org/addons.php?id=\[addon_id] [bold white]|[/bold white] tu:\[a'
                               'ddon_id]\n\thttps://www.tukui.org/classic-addons.php?id=\[addon_id] [bold white]|[/bold'
                               ' white] tuc:\[addon_id]\n\thttps://github.com/\[username]/\[repository_name] [bold whit'
                               'e]|[/bold white] gh:\[username]/\[repository_name]\n\tElvUI [bold white]|[/bold white] '
                               'ElvUI:Dev\n\tTukui\n\tShadow&Light:Dev', highlight=False)

    def c_uninstall(self, args):
        if args:
            if args.startswith('-k '):
                args = args[3:]
                optkeep = True
            else:
                optkeep = False
            addons = self.parse_args(args)
            with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|',
                          auto_refresh=False, console=self.console) as progress:
                task = progress.add_task('', total=len(addons))
                while not progress.finished:
                    for addon in addons:
                        name, version = self.core.del_addon(addon, optkeep)
                        if name:
                            self.table.add_row(f'[bold red]Uninstalled[/bold red]',
                                               Text(name, no_wrap=True), Text(version, no_wrap=True))
                        else:
                            self.table.add_row(f'[bold black]Not installed[/bold black]',
                                               Text(addon, no_wrap=True), Text('', no_wrap=True))
                        progress.update(task, advance=1, refresh=True)
            self.console.print(self.table)
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a space-separated list of addon names or '
                               'full links as an argument.\n\t[bold white]Flags:[/bold white]\n\t\t[bold white]-k[/bold'
                               ' white] - Keep the addon files after uninstalling.', highlight=False)

    def c_update(self, args, addline=False, update=True, force=False, provider=False):
        if len(self.core.cfCache) > 0 or len(self.core.wowiCache) > 0:
            self.core.cfCache = {}
            self.core.wowiCache = {}
            self.core.checksumCache = {}
        if args:
            addons = self.parse_args(args)
            compacted = -1
        else:
            addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
            compacted = 0
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
                        # noinspection PyTypeChecker
                        name, versionnew, versionold, modified, blocked, source, changelog = self.core.\
                            update_addon(addon if isinstance(addon, str) else addon['URL'], update, force)
                        if provider:
                            source = f' [bold white]{source}[/bold white]'
                        else:
                            source = ''
                        if versionold:
                            if versionold == versionnew:
                                if changelog:
                                    versionold = Text.from_markup(f'[link={changelog}]{versionold}[/link]')
                                    versionold.no_wrap = True
                                else:
                                    versionold = Text(versionold, no_wrap=True)
                                if modified:
                                    self.table.add_row(f'[bold red]Modified[/bold red]{source}',
                                                       Text(name, no_wrap=True), versionold)
                                else:
                                    if self.core.config['CompactMode'] and compacted > -1:
                                        compacted += 1
                                    else:
                                        self.table.add_row(f'[green]Up-to-date[/green]{source}',
                                                           Text(name, no_wrap=True), versionold)
                            else:
                                if modified or blocked:
                                    if changelog:
                                        versionold = Text.from_markup(f'[link={changelog}]{versionold}[/link]')
                                        versionold.no_wrap = True
                                    else:
                                        versionold = Text(versionold, no_wrap=True)
                                    self.table.add_row(f'[bold red]Update suppressed[/bold red]{source}',
                                                       Text(name, no_wrap=True), versionold)
                                else:
                                    if changelog:
                                        versionnew = Text.from_markup(f'[yellow][link={changelog}]{versionnew}'
                                                                      f'[/link][/yellow]')
                                        versionnew.no_wrap = True
                                    else:
                                        versionnew = Text(versionnew, style='yellow', no_wrap=True)
                                    self.table.add_row(f'[yellow]{"Updated" if update else "Update available"}'
                                                       f'[/yellow]{source}', Text(name, no_wrap=True), versionnew)
                        else:
                            self.table.add_row(f'[bold black]Not installed[/bold black]{source}',
                                               Text(addon, no_wrap=True), Text('', no_wrap=True))
                    except Exception as e:
                        exceptions.append(e)
                    progress.update(task, advance=1 if args else 0.5, refresh=True)
        if addline:
            self.console.print('')
        self.console.print(self.table)
        if compacted > 0:
            self.console.print(f'Additionally [green]{compacted}[/green] addons are up-to-date.')
        if len(addons) == 0:
            self.console.print('Apparently there are no addons installed by CurseBreaker.\n'
                               'Command [green]import[/green] might be used to detect already installed addons.')
        if len(exceptions) > 0:
            self.handle_exception(exceptions, False)

    def c_force_update(self, args):
        if args:
            self.c_update(args, False, True, True)
        else:
            # noinspection PyTypeChecker
            answer = confirm(HTML('<ansibrightred>Execute a forced update of all addons and overwrite ALL local '
                                  'changes?</ansibrightred>'))
            if answer:
                self.c_update(False, False, True, True)

    def c_status(self, args):
        if args and args.startswith('-s'):
            args = args[2:]
            optsource = True
        else:
            optsource = False
        self.c_update(args, False, False, False, optsource)

    def c_orphans(self, _):
        orphansd, orphansf = self.core.find_orphans()
        self.console.print('[green]Directories that are not part of any installed addon:[/green]')
        for orphan in sorted(orphansd):
            self.console.print(orphan.replace('[GIT]', '[yellow]\[GIT][/yellow]'), highlight=False)
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

    def c_toggle_block(self, args):
        if args:
            status = self.core.block_toggle(args)
            if status is None:
                self.console.print('[bold red]This addon does not exist or it is not installed yet.[/bold red]')
            elif status:
                self.console.print('Updates for this addon are now [red]suppressed[/red].')
            else:
                self.console.print('Updates for this addon are [green]no longer suppressed[/green].')
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts an addon name as an argument.')

    def c_toggle_backup(self, _):
        status = self.core.generic_toggle('Backup', 'Enabled')
        self.console.print('Backup of WTF directory is now:',
                           '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')

    def c_toggle_compact_mode(self, _):
        status = self.core.generic_toggle('CompactMode')
        self.console.print('Table compact mode is now:',
                           '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')

    def c_toggle_autoupdate(self, _):
        status = self.core.generic_toggle('AutoUpdate')
        self.console.print('The automatic addon update on startup is now:',
                           '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')

    def c_toggle_wago(self, args):
        if args:
            if args == self.core.config['WAUsername']:
                self.console.print(f'Wago version check is now: [green]ENABLED[/green]\nEntries created by '
                                   f'[bold white]{self.core.config["WAUsername"]}[/bold white] are now included.')
                self.core.config['WAUsername'] = ''
            else:
                self.core.config['WAUsername'] = args.strip()
                self.console.print(f'Wago version check is now: [green]ENABLED[/green]\nEntries created by '
                                   f'[bold white]{self.core.config["WAUsername"]}[/bold white] are now ignored.')
        else:
            if self.core.config['WAUsername'] == 'DISABLED':
                self.core.config['WAUsername'] = ''
                self.console.print('Wago version check is now: [green]ENABLED[/green]')
            else:
                self.core.config['WAUsername'] = 'DISABLED'
                shutil.rmtree(Path('Interface/AddOns/WeakAurasCompanion'), ignore_errors=True)
                self.console.print('Wago version check is now: [red]DISABLED[/red]')
        self.core.save_config()

    def c_set_wago_api(self, args):
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

    def c_set_wago_wow_account(self, args):
        if args:
            args = args.strip()
            if os.path.isfile(Path(f'WTF/Account/{args}/SavedVariables/WeakAuras.lua')) or \
                    os.path.isfile(Path(f'WTF/Account/{args}/SavedVariables/Plater.lua')):
                self.console.print(f'WoW account name set to: [bold white]{args}[/bold white]')
                self.core.config['WAAccountName'] = args
                self.core.save_config()
            else:
                self.console.print('Incorrect WoW account name.')
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts the WoW account name as an argument.')

    def c_wago_update(self, _, verbose=True):
        if os.path.isdir(Path('Interface/AddOns/WeakAuras')) or os.path.isdir(Path('Interface/AddOns/Plater')):
            accounts = self.core.detect_accounts()
            if len(accounts) == 0:
                return
            elif len(accounts) > 1 and self.core.config['WAAccountName'] == '':
                if verbose:
                    self.console.print('More than one WoW account detected.\nPlease use [bold white]set_wago_wow_accoun'
                                       't[''/bold white] command to set the correct account name.')
                else:
                    self.console.print('\n[green]More than one WoW account detected.[/green]\nPlease use [bold white]se'
                                       't_wago_wow_account[/bold white] command to set the correct account name.')
                return
            elif len(accounts) == 1 and self.core.config['WAAccountName'] == '':
                self.core.config['WAAccountName'] = accounts[0]
                self.core.save_config()
            wago = WagoUpdater(self.core.config['WAUsername'], self.core.config['WAAccountName'],
                               self.core.config['WAAPIKey'])
            if self.core.wagoCompanionVersion != self.core.config['WACompanionVersion']:
                self.core.config['WACompanionVersion'] = self.core.wagoCompanionVersion
                self.core.save_config()
                force = True
            else:
                force = False
            wago.install_companion(self.core.clientType, force)
            statuswa, statusplater = wago.update()
            if verbose:
                if len(statuswa[0]) > 0 or len(statuswa[1]) > 0:
                    self.console.print('[green]Outdated WeakAuras:[/green]')
                    for aura in statuswa[0]:
                        self.console.print(aura, highlight=False)
                    self.console.print('\n[green]Detected WeakAuras:[/green]')
                    for aura in statuswa[1]:
                        self.console.print(aura, highlight=False)
                if len(statusplater[0]) > 0 or len(statusplater[1]) > 0:
                    if len(statuswa[0]) != 0 or len(statuswa[1]) != 0:
                        self.console.print('')
                    self.console.print('[green]Outdated Plater profiles/scripts:[/green]')
                    for aura in statusplater[0]:
                        self.console.print(aura, highlight=False)
                    self.console.print('\n[green]Detected Plater profiles/scripts:[/green]')
                    for aura in statusplater[1]:
                        self.console.print(aura, highlight=False)
            else:
                if len(statuswa[0]) > 0:
                    self.console.print(f'\n[green]The number of outdated WeakAuras:[/green] '
                                       f'{len(statuswa[0])}', highlight=False)
                if len(statusplater[0]) > 0:
                    self.console.print(f'\n[green]The number of outdated Plater profiles/scripts:[/green] '
                                       f'{len(statusplater[0])}', highlight=False)
        elif verbose:
            self.console.print('No compatible addon is installed.')

    def c_search(self, args):
        if args:
            results = self.core.search(args)
            self.console.print('[green]Top results of your search:[/green]')
            for url in results:
                if self.core.check_if_installed(url):
                    self.console.print(f'[link={url}]{url}[/link] [yellow]\[Installed][/yellow]', highlight=False)
                else:
                    self.console.print(f'[link={url}]{url}[/link]', highlight=False)
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
        payload = self.core.export_addons()
        pyperclip.copy(payload)
        self.console.print(f'{payload}\n\nThe command above was copied to the clipboard.', highlight=False)

    def c_help(self, _):
        self.console.print('[green]install [URL][/green]\n\tCommand accepts a space-separated list of links.\n\t[bold w'
                           'hite]Flags:[/bold white]\n\t\t[bold white]-i[/bold white] - Disable the client version chec'
                           'k.\n'
                           '[green]uninstall [URL/Name][/green]\n\tCommand accepts a space-separated list of addon name'
                           's or full links.\n\t[bold white]Flags:[/bold white]\n\t\t[bold white]-k[/bold white] - Keep'
                           ' the addon files after uninstalling.\n'
                           '[green]update [URL/Name][/green]\n\tCommand accepts a space-separated list of addon names o'
                           'r full links.\n\tIf no argument is provided all non-modified addons will be updated.\n'
                           '[green]force_update [URL/Name][/green]\n\tCommand accepts a space-separated list of addon n'
                           'ames or full links.\n\tSelected addons will be reinstalled or updated regardless of their c'
                           'urrent state.\n\tIf no argument is provided all addons will be forcefully updated.\n'
                           '[green]wago_update[/green]\n\tCommand detects all installed WeakAuras and Plater profiles/s'
                           'cripts.\n\tAnd then generate WeakAuras Companion payload.\n'
                           '[green]status[/green]\n\tPrints the current state of all installed addons.\n\t[bold white]F'
                           'lags:[/bold white]\n\t\t[bold white]-s[/bold white] - Display the source of the addons.\n'
                           '[green]orphans[/green]\n\tPrints list of orphaned directories and files.\n'
                           '[green]search [Keyword][/green]\n\tExecutes addon search on CurseForge.\n'
                           '[green]import[/green]\n\tCommand attempts to import already installed addons.\n'
                           '[green]export[/green]\n\tCommand prints list of all installed addons in a form suitable f'
                           'or sharing.\n'
                           '[green]toggle_backup[/green]\n\tEnables/disables automatic daily backup of WTF directory.\n'
                           '[green]toggle_dev [Name][/green]\n\tCommand accepts an addon name (or "global") as argument'
                           '.\n\tPrioritizes alpha/beta versions for the provided addon.\n'
                           '[green]toggle_block [Name][/green]\n\tCommand accepts an addon name as argument.\n\tBlocks/'
                           'unblocks updating of the provided addon.\n'
                           '[green]toggle_compact_mode [/green]\n\tEnables/disables compact table mode that hides entri'
                           'es of up-to-date addons.\n'
                           '[green]toggle_autoupdate [/green]\n\tEnables/disables the automatic addon update on startup'
                           '.\n'
                           '[green]toggle_wago [Username][/green]\n\tEnables/disables automatic Wago updates.\n\tIf a u'
                           'sername is provided check will start to ignore the specified author.\n'
                           '[green]set_wago_api [API key][/green]\n\tSets Wago API key required to access private entri'
                           'es.\n\tIt can be procured here:'
                           ' [link=https://wago.io/account]https://wago.io/account[/link]\n'
                           '[green]set_wago_wow_account [Account name][/green]\n\tSets WoW account used by Wago updater'
                           '.\n\tNeeded only if compatibile addons are used on more than one WoW account.\n'
                           '[green]uri_integration[/green]\n\tEnables integration with CurseForge page.\n\t[i]"Install"'
                           '[/i] button will now start this application.\n'
                           '\n[bold green]Supported URL:[/bold green]\n\thttps://www.curseforge.com/wow/addons/\[addon_'
                           'name] [bold white]|[/bold white] cf:\[addon_name]\n\thttps://www.wowinterface.com/downloads'
                           '/\[addon_name] [bold white]|[/bold white] wowi:\[addon_id]\n\thttps://www.tukui.org/addons.'
                           'php?id=\[addon_id] [bold white]|[/bold white] tu:\[addon_id]\n\thttps://www.tukui.org/class'
                           'ic-addons.php?id=\[addon_id] [bold white]|[/bold white] tuc:\[addon_id]\n\thttps://github.c'
                           'om/\[username]/\[repository_name] [bold white]|[/bold white] gh:\[username]/\[repository_na'
                           'me]\n\tElvUI [bold white]|[/bold white] ElvUI:Dev\n\tTukui\n\tShadow&Light:Dev',
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
