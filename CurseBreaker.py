import os
import io
import re
import sys
import math
import time
import gzip
import glob
import json
import httpx
import base64
import random
import shutil
import zipfile
import platform
import pyperclip
import subprocess
from io import BytesIO
from PIL import Image
from csv import reader
from shlex import split
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext, suppress
from rich_pixels import Pixels
from rich import box
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich.align import Align
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich.console import Console, detect_legacy_windows
from rich.control import Control
from rich.progress import Progress, BarColumn
from rich.traceback import Traceback, install
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.completion import WordCompleter, NestedCompleter
from packaging.version import Version
from CB import __version__
from CB.Core import Core
from CB.Wago import WagoUpdater
from CB.Compat import clear, set_terminal_title, set_terminal_size, KBHit
from CB.Resources import LOGO, HEADLESS_TERMINAL_THEME

if platform.system() == 'Windows':
    from ctypes import windll, wintypes


class TUI:
    def __init__(self):
        self.core = Core()
        self.session = PromptSession(reserve_space_for_menu=6, complete_in_thread=True)
        self.headless = False
        self.console = None
        self.table = None
        self.slugs = None
        self.completer = None
        self.os = platform.system()
        install()

    def start(self):  # sourcery skip: low-code-quality
        # Check if headless mode was requested
        if len(sys.argv) == 2 and sys.argv[1].lower() == 'headless':
            self.headless = True
        self.setup_console()
        self.print_header()
        self.core.init_master_config()
        # Check if executable is in good location
        if not glob.glob('World*.app') and not glob.glob('Wow*.exe') or \
                not os.path.isdir(Path('Interface/AddOns')) or not os.path.isdir('WTF'):
            self.handle_shutdown('[bold red]This executable should be placed in the same directory where Wow.exe, WowCl'
                                 'assic.exe or World of Warcraft.app is located. Additionally, make sure that this WoW '
                                 'installation was started at least once.[/bold red]\n')
        # Detect client flavor
        if 'CURSEBREAKER_FLAVOR' in os.environ:
            flavor = os.environ.get('CURSEBREAKER_FLAVOR')
        else:
            flavor = os.path.basename(os.getcwd())
        if flavor in {'_retail_', '_ptr_', '_ptr2_', '_beta_', '_xptr_'}:
            self.core.clientType = 'retail'
        elif flavor in {'_classic_', '_classic_ptr_', '_classic_beta_'}:
            self.core.clientType = 'cata'
            set_terminal_title(f'CurseBreaker v{__version__} - Cataclysm Classic')
        elif flavor in {'_classic_era_', '_classic_era_ptr_'}:
            self.core.clientType = 'classic'
            set_terminal_title(f'CurseBreaker v{__version__} - Classic')
        else:
            self.handle_shutdown('[bold red]This client release is currently unsupported by CurseBreaker.[/bold red]\n')
        # Check if client have write access
        try:
            with open('PermissionTest', 'w') as _:
                pass
            os.remove('PermissionTest')
        except OSError:
            self.handle_shutdown('[bold red]CurseBreaker doesn\'t have write rights for the current directory.\nTry sta'
                                 'rting it with administrative privileges.[/bold red]\n')
        # Application auto update and initialization
        self.auto_update()
        try:
            self.core.init_config()
        except RuntimeError:
            self.handle_shutdown('[bold red]The config file is corrupted. Restore the earlier version from backup.[/bol'
                                 'd red]\n')
        self.setup_table()
        # Wago Addons URI Support
        if len(sys.argv) == 2 and sys.argv[1].startswith('wago-app://addons/'):
            try:
                self.c_install(sys.argv[1].strip())
            except Exception as e:
                self.handle_exception(e)
            self.handle_shutdown()
        # Wago URI Support
        if len(sys.argv) == 2 and sys.argv[1].startswith('weakauras-companion://wago/push/'):
            try:
                self.core.config['WAStash'].append(sys.argv[1].strip().replace('weakauras-companion://wago/push/', ''))
                self.core.config['WAStash'] = list(set(self.core.config['WAStash']))
                self.core.save_config()
                self.c_wago_update(_, flush=False)
            except Exception as e:
                self.handle_exception(e)
            self.handle_shutdown()
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
                self.core.http.close()
                sys.exit(0)
            else:
                self.console.print('Command not found.')
                self.core.http.close()
                sys.exit(0)
        # Addons auto update
        if len(self.core.config['Addons']) > 0 and self.core.config['AutoUpdate']:
            if not self.headless and self.core.config['AutoUpdateDelay']:
                if self.console.color_system == 'truecolor':
                    with Image.open(BytesIO(base64.b64decode(LOGO))) as image:
                        logo = Pixels.from_image(image, resize=(40, 40))
                    self.console.print(Panel(Align.center(logo), border_style='yellow'))
                    self.console.print('')
                keypress = self.handle_keypress('Automatic update of all addons will start in {} seconds.\nPress any bu'
                                                'tton to enter interactive mode.', 5, True)
            else:
                keypress = False
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
                        self.console.print('')
                        with nullcontext() if self.headless else self.console.status('Processing Wago data'):
                            self.setup_table()
                            self.c_wago_update(None, False)
                except Exception as e:
                    self.handle_exception(e)
                self.console.print('')
                self.print_log()
                if self.headless:
                    self.core.http.close()
                    sys.exit(0)
                else:
                    self.print_author_reminder()
                    keypress = self.handle_keypress('Press [bold]I[/bold] to enter interactive mode or any other button'
                                                    ' to close the application.', 0, False)
                    if not keypress or keypress.lower() not in [b'i', 'i']:
                        self.core.http.close()
                        sys.exit(0)
        if self.headless:
            self.core.http.close()
            sys.exit(1)
        # Interactive mode initialization
        self.setup_completer()
        self.print_header()
        self.console.print('Use command [green]help[/green] or press [green]TAB[/green] to see a list of available comm'
                           'ands.\nCommand [green]exit[/green] or pressing [green]CTRL+D[/green] will close the applica'
                           'tion.\n')
        if len(self.core.config['Addons']) == 0:
            self.console.print('To enable Wago Addons support API key needs to be provided.\nIt can be obtained here: ['
                               'link=https://addons.wago.io/patreon]https://addons.wago.io/patreon[/link]\nAfter that i'
                               't needs to added to application configuration by using [green]set wago_addons_api[/gree'
                               'n] command.\nCommand [green]import[/green] might be used to detect already installed ad'
                               'dons.')
        self.motd_parser()
        if self.core.backup_check():
            self.console.print('[green]Backing up WTF directory:[/green]')
            self.core.backup_wtf(self.console)
            self.console.print('')
        # Prompt session
        while True:
            try:
                command = self.session.prompt(HTML('<ansibrightgreen>CB></ansibrightgreen> '), completer=self.completer)
            except KeyboardInterrupt:
                continue
            except EOFError:
                self.core.http.close()
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

    def _auto_update_cleanup(self):
        self.print_log()
        self.core.http.close()
        self.handle_keypress('Press any button to continue...', 0, False)

    def _auto_update_install(self, url, changelog):
        self.console.print('[green]Updating CurseBreaker...[/green]')
        shutil.move(sys.executable, f'{sys.executable}.old')
        payload = self.core.http.get(url)
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
        self.console.print(f'[bold green]Update complete! The application will be restarted now.[/bold green]\n\n'
                           f'[green]Changelog:[/green]\n{changelog}\n')
        self._auto_update_cleanup()
        subprocess.call([sys.executable] + sys.argv[1:])
        sys.exit(0)

    def auto_update(self):
        if not getattr(sys, 'frozen', False) or 'CURSEBREAKER_VARDEXMODE' in os.environ:
            return
        try:
            if os.path.isfile(f'{sys.executable}.old'):
                with suppress(PermissionError):
                    os.remove(f'{sys.executable}.old')
            try:
                payload = self.core.http.get('https://api.github.com/repos/AcidWeb/CurseBreaker/releases/latest').json()
            except httpx.RequestError:
                return
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
                if url and Version(remoteversion[1:]) > Version(__version__):
                    self._auto_update_install(url, changelog)
        except Exception as e:
            if os.path.isfile(f'{sys.executable}.old'):
                shutil.move(f'{sys.executable}.old', sys.executable)
            self.console.print(f'[bold red]Update failed!\n\nReason: {e!s}[/bold red]\n')
            self._auto_update_cleanup()
            sys.exit(1)

    def motd_parser(self):
        if detect_legacy_windows():
            self.console.print(Panel('The old Windows terminal was detected. Use of the new Windows Terminal is highly '
                                     'recommended. https://aka.ms/terminal', title='WARNING', border_style='red'))
            self.console.print('')
        else:
            payload = self.core.http.get('https://cursebreaker.acidweb.dev/motd')
            if payload.status_code == 200:
                self.console.print(Panel(payload.content.decode('UTF-8'), title=':megaphone: MOTD :megaphone:',
                                         border_style='red'))
                self.console.print('')

    def handle_exception(self, e, table=True):
        if self.table.row_count > 1 and table:
            self.console.print(self.table)
        if getattr(sys, 'frozen', False) and 'CURSEBREAKER_DEBUG' not in os.environ:
            sys.tracebacklimit = 0
            width = 0
        else:
            width = 100
        if isinstance(e, list):
            for es in e:
                self.console.print(Traceback.from_exception(exc_type=es.__class__, exc_value=es,
                                                            traceback=es.__traceback__, width=width))
        else:
            self.console.print(Traceback.from_exception(exc_type=e.__class__, exc_value=e,
                                                        traceback=e.__traceback__, width=width))

    def _handle_keypress_console(self, count, msg, countdown=None):
        kb = KBHit()
        starttime = time.time()
        keypress = False
        while True:
            if kb.kbhit():
                keypress = kb.getch()
                break
            elif count and time.time() - starttime > count:
                break
            if countdown:
                countdown.update(Text(msg.format(math.ceil(count - (time.time() - starttime)))))
            time.sleep(0.01)
        kb.set_normal_term()
        return keypress

    def handle_keypress(self, msg, count, live):
        if self.headless:
            return False
        if live:
            with Live(Text(msg.format(count)), console=self.console, refresh_per_second=2) as countdown:
                keypress = self._handle_keypress_console(count, msg, countdown)
        else:
            self.console.print(msg)
            keypress = self._handle_keypress_console(count, msg)
        return keypress

    def handle_shutdown(self, message=''):
        self.core.http.close()
        if not message:
            self.handle_keypress('\nWaiting for {} seconds, press any button to continue...', 5, True)
            sys.exit(0)
        else:
            self.console.print(message)
            self.handle_keypress('Press any button to continue...', 0, False)
            sys.exit(1)

    def print_header(self):
        if self.headless:
            self.console.print(f'[bold green]CurseBreaker[/bold green] [bold red]v{__version__}[/bold red] | '
                               f'[yellow]{datetime.now()}[/yellow]', highlight=False)
        else:
            if len(sys.argv) == 1:
                clear()
            self.console.print(Rule(f'[bold green]CurseBreaker[/bold green] [bold red]v{__version__}[/bold red]'))
            self.console.print('')

    def print_log(self):
        if self.headless:
            html = self.console.export_html(inline_styles=True, theme=HEADLESS_TERMINAL_THEME)
            with open('CurseBreaker.html', 'a+', encoding='utf-8') as log:
                log.write(html)

    def print_author_reminder(self):
        if random.randint(1, 10) != 1:
            return
        addon = random.choice(self.core.config['Addons'])
        project_url = addon['URL']
        if not project_url.startswith('https://'):
            project_url = project_url.lower()
            if not project_url.endswith(':dev'):
                project_url = f'{project_url}:dev'
            project_url = self.core.masterConfig['CustomRepository'][project_url]['SupportURL']
        self.console.print(Panel(f'Hey! You use [bold white]{addon["Name"]}[/bold white] quite often. Maybe it\'s t'
                                 f'ime to check out the project page how you can support the author(s)? [link='
                                 f'{project_url}]{project_url}[/link]', title=':sparkles: Support :sparkles:',
                                 border_style='yellow'))
        self.console.print('')

    def setup_console(self):
        if self.headless:
            self.console = Console(record=True)
            if self.os == 'Windows' and (window := windll.kernel32.GetConsoleWindow()):
                windll.user32.ShowWindow(window, 0)
        elif detect_legacy_windows():
            set_terminal_size(100, 50)
            windll.kernel32.SetConsoleScreenBufferSize(windll.kernel32.GetStdHandle(-11), wintypes._COORD(100, 200))
            self.console = Console(width=97)
        else:
            self.console = Console()

    def setup_completer(self):
        if not self.slugs:
            try:
                self.slugs = json.load(gzip.open(io.BytesIO(
                    self.core.http.get('https://cursebreaker.acidweb.dev/slugs-v2.json.gz').content)))
            except (StopIteration, UnicodeDecodeError, json.JSONDecodeError, httpx.RequestError):
                self.slugs = {'wa': [], 'wowi': [], 'gh': []}
        addons = []
        for addon in sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower()):
            addons.append(addon['Name'])
        slugs = ['ElvUI', 'Tukui']
        if self.core.config['WAAAPIKey'] != '':
            for item in self.slugs['wa']:
                slugs.append(f'wa:{item}')
        for item in self.slugs['wowi']:
            slugs.append(f'wowi:{item}')
        for item in self.slugs['gh']:
            slugs.append(f'gh:{item}')
        for item in self.slugs['custom']:
            slugs.append(f'{item}')
        accounts = list(self.core.detect_accounts())
        self.completer = NestedCompleter.from_nested_dict({
            'install': WordCompleter(slugs, ignore_case=True, match_middle=True, WORD=True),
            'uninstall': WordCompleter(addons, ignore_case=True),
            'update': WordCompleter(addons, ignore_case=True),
            'force_update': WordCompleter(addons, ignore_case=True),
            'wago_update': None,
            'status': WordCompleter(addons, ignore_case=True),
            'orphans': None,
            'search': None,
            'backup': None,
            'import': {'install': None},
            'export': None,
            'toggle': {'authors': None,
                       'autoupdate': None,
                       'autoupdate_delay': None,
                       'backup': None,
                       'channel': WordCompleter([*addons, 'global'], ignore_case=True, sentence=True),
                       'compact_mode': None,
                       'pinning': WordCompleter(addons, ignore_case=True, sentence=True),
                       'sources': None,
                       'wago': None},
            'set': {'wago_addons_api': None,
                    'wago_api': None,
                    'wago_wow_account': WordCompleter(accounts, ignore_case=True, sentence=True),
                    'gh_api': None},
            'uri_integration': None,
            'help': None,
            'exit': None
        })

    def setup_table(self, sources=False):
        self.table = Table(box=box.SQUARE)
        self.table.add_column('Status', header_style='bold white', no_wrap=True, justify='center')
        if sources:
            self.table.add_column('Source', header_style='bold white', no_wrap=True, justify='center')
        self.table.add_column('Name / Author' if self.core.config['ShowAuthors'] else 'Name', header_style='bold white')
        self.table.add_column('Version', header_style='bold white')

    def parse_args(self, args):
        parsed = []
        for addon in sorted(self.core.config['Addons'], key=lambda k: len(k['Name']), reverse=True):
            if addon['Name'] in args or addon['URL'] in args:
                parsed.append(addon['Name'])
                args = args.replace(addon['Name'], '', 1)
        return sorted(parsed)

    def parse_link(self, text, link, dev=None, authors=None, uiversion=None):
        if dev == 1:
            dev = ' [bold][B][/bold]'
        elif dev == 2:
            dev = ' [bold][A][/bold]'
        else:
            dev = ''
        if authors and self.core.config['ShowAuthors']:
            authors.sort()
            authors = f' [bold black]by {", ".join(authors)}[/bold black]'
        else:
            authors = ''
        if uiversion and uiversion not in \
                [v['CurrentVersion'] for _, v in self.core.masterConfig['ClientTypes'].items()]:
            uiversion = ' [bold yellow][!][/bold yellow]'
        else:
            uiversion = ''
        if link:
            obj = Text.from_markup(f'[link={link}]{text}[/link]{dev}{authors}{uiversion}')
        else:
            obj = Text.from_markup(f'{text}{dev}{authors}{uiversion}')
        obj.no_wrap = True
        return obj

    def parse_custom_addons(self):
        payload = []
        for addon in self.core.masterConfig['CustomRepository'].values():
            payload.append(addon['Slug'])
        return ' [bold white]|[/bold white] '.join(payload)

    def c_install(self, args):
        if not args:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a space-separated list of links as an arg'
                               'ument.[bold white]\n\tFlags:[/bold white]\n\t\t[bold white]-i[/bold white] - Disable th'
                               'e client version check.\n[bold green]Supported URL:[/bold green]\n\thttps://addons.wago'
                               '.io/addons/\\[addon_name] [bold white]|[/bold white] wa:\\[addon_name]\n\thttps://www.w'
                               'owinterface.com/downloads/\\[addon_name] [bold white]|[/bold white] wowi:\\[addon_id]\n'
                               '\thttps://github.com/\\[username]/\\[repository_name] [bold white]|[/bold white] gh:\\['
                               'username]/\\[repository_name]\n\tElvUI [bold white]|[/bold white] Tukui\n\t' +
                               self.parse_custom_addons(), highlight=False)
            return
        optignore = False
        pargs = split(args.replace("'", "\\'"))
        if '-i' in pargs:
            optignore = True
            args = args.replace('-i', '', 1)
        args = re.sub(r'([a-zA-Z0-9_:])( +)([a-zA-Z0-9_:])', r'\1,\3', args)
        addons = [re.sub(r'[\[\]]', '', addon).strip() for addon in next(iter(reader([args], skipinitialspace=True)))]
        exceptions = []
        if addons:
            if self.core.clientType != 'retail':
                for addon in addons:
                    if addon.startswith(('https://www.wowinterface.com/downloads/', 'wowi:')):
                        self.console.print('[yellow][WARNING][/yellow] WoWInterface support for non-retail clients is l'
                                           'imited. If the selected project offers multiple downloads this application '
                                           'will always install the retail version of the addon.')
                        break
            with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|', auto_refresh=False,
                          console=self.console) as progress:
                task = progress.add_task('', total=len(addons))
                while not progress.finished:
                    for addon in addons:
                        try:
                            installed, name, version = self.core.add_addon(addon, optignore)
                            if installed:
                                self.table.add_row('[green]Installed[/green]', Text(name, no_wrap=True),
                                                   Text(version, no_wrap=True))
                            else:
                                self.table.add_row('[bold black]Already installed[/bold black]',
                                                   Text(name, no_wrap=True), Text(version, no_wrap=True))
                        except Exception as e:
                            exceptions.append(e)
                        progress.update(task, advance=1, refresh=True)
            self.console.print(self.table)
        if exceptions:
            self.handle_exception(exceptions, False)

    def c_uninstall(self, args):
        if not args:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a space-separated list of addon names or '
                               'full links as an argument.\n\t[bold white]Flags:[/bold white]\n\t\t[bold white]-k[/bold'
                               ' white] - Keep the addon files after uninstalling.', highlight=False)
            return
        optkeep = False
        pargs = split(args.replace("'", "\\'"))
        if '-k' in pargs:
            optkeep = True
            args = args.replace('-k', '', 1)
        addons = self.parse_args(args)
        if len(addons) > 0:
            with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|', auto_refresh=False,
                          console=self.console) as progress:
                task = progress.add_task('', total=len(addons))
                while not progress.finished:
                    for addon in addons:
                        name, version = self.core.del_addon(addon, optkeep)
                        if name:
                            self.table.add_row('[bold red]Uninstalled[/bold red]', Text(name, no_wrap=True),
                                               Text(version, no_wrap=True))
                        else:
                            self.table.add_row('[bold black]Not installed[/bold black]', Text(addon, no_wrap=True),
                                               Text('', no_wrap=True))
                        progress.update(task, advance=1, refresh=True)
            self.console.print(self.table)

    def _c_update_process(self, addon, update, force, compact, compacted, provider):  # sourcery skip: low-code-quality
        name, authors, versionnew, versionold, uiversion, modified, blocked, source, sourceurl, changelog, dstate \
            = self.core.update_addon(addon if isinstance(addon, str) else addon['URL'], update, force)
        additionalstatus = f' [bold red]{source.upper()}[/bold red]' if source == 'Unsupported' and not provider else ''
        if versionold:
            payload = [self.parse_link(name, sourceurl, authors=authors),
                       self.parse_link(versionold, changelog, dstate, uiversion=uiversion)]
            if versionold == versionnew:
                if modified:
                    payload.insert(0, f'[bold red]Modified[/bold red]{additionalstatus}')
                elif compact and compacted > -1 and source != 'Unsupported':
                    payload = None
                    compacted += 1
                else:
                    payload.insert(0, f'[green]Up-to-date[/green]{additionalstatus}')
            elif modified or blocked:
                payload.insert(0, f'[bold red]Update suppressed[/bold red]{additionalstatus}')
            else:
                version = self.parse_link(versionnew, changelog, dstate, uiversion=uiversion)
                version.stylize('yellow')
                payload = [f'[yellow]{"Updated" if update else "Update available"}[/yellow]{additionalstatus}',
                           payload[0], version]
        else:
            payload = [f'[bold black]Not installed[/bold black]{additionalstatus}', Text(addon, no_wrap=True),
                       Text('', no_wrap=True)]
        if payload:
            if provider:
                if source == 'Unsupported':
                    payload.insert(1, f'[bold red]{source.upper()}[/bold red]')
                else:
                    payload.insert(1, source)
            self.table.add_row(*payload)
        return compacted

    def c_update(self, args, addline=False, update=True, force=False, reverseprovider=False, reversecompact=False):
        compact = not self.core.config['CompactMode'] if reversecompact else self.core.config['CompactMode']
        provider = not self.core.config['ShowSources'] if reverseprovider else self.core.config['ShowSources']
        self.setup_table(sources=provider)
        if args:
            addons = self.parse_args(args)
            compacted = -1
        else:
            addons = sorted(self.core.config['Addons'], key=lambda k: k['Name'].lower())
            compacted = 0
        if len(addons) == 0:
            self.console.print('Apparently there are no addons installed by CurseBreaker (or you provided incorrect add'
                               'on name).\nCommand [green]import[/green] might be used to detect already installed addo'
                               'ns.', highlight=False)
            return
        exceptions = []
        with Progress('{task.completed:.0f}/{task.total}', '|', BarColumn(bar_width=None), '|',
                      console=None if self.headless else self.console) as progress:
            task = progress.add_task('', total=len(addons), start=bool(args))
            if not args:
                with suppress(RuntimeError, httpx.RequestError):
                    self.core.bulk_check(addons)
                progress.start_task(task)
                self.core.bulk_check_checksum(addons, progress)
            while not progress.finished:
                for addon in addons:
                    try:
                        compacted = self._c_update_process(addon, update, force, compact, compacted, provider)
                    except Exception as e:
                        exceptions.append(e)
                    progress.update(task, advance=1 if args else 0.5, refresh=True)
        if addline:
            self.console.print('')
        self.console.print(self.table)
        if compacted > 0:
            self.console.print(f'Additionally [green]{compacted}[/green] addons are up-to-date.')
        if overlap := self.core.check_if_overlap():
            self.console.print(f'\n[bold red]Detected addon directory overlap. This will cause issues. Affected add'
                               f'ons:[/bold red]\n{overlap}')
        if self.core.check_if_from_gh():
            self.console.print('\n[bold red]Multiple addons acquired from GitHub have been detected. Providing a p'
                               'ersonal GitHub token is highly recommended.[/bold red]')
        if exceptions:
            self.handle_exception(exceptions, False)

    # noinspection PyTypeChecker
    def c_force_update(self, args):
        if args:
            self.c_update(args, False, True, True)
        elif Confirm.ask('[bold red]Execute a forced update of all addons and overwrite ALL local changes?[/bold red]'):
            self.c_update(False, False, True, True)

    def c_status(self, args):
        optsource = False
        optcompact = False
        if args:
            pargs = split(args.replace("'", "\\'"))
            if '-s' in pargs:
                optsource = True
                args = args.replace('-s', '', 1)
            if '-a' in pargs:
                optcompact = True
                args = args.replace('-a', '', 1)
            args = args.strip()
        self.c_update(args, False, False, False, optsource, optcompact)

    def c_orphans(self, _):
        orphansd, orphansf = self.core.find_orphans()
        self.console.print('[green]Directories that are not part of any installed addon:[/green]')
        for orphan in sorted(orphansd):
            self.console.print(orphan.replace('[GIT]', '[yellow][GIT][/yellow]')
                               .replace('[Special]', '[red][Special][/red]'), highlight=False)
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

    def _c_toggle_channel(self, args):
        if args := args[8:]:
            status = self.core.dev_toggle(args)
            if status is None:
                self.console.print('[bold red]This addon doesn\'t exist or it is not installed yet.[/bold red]')
            elif status == -1:
                self.console.print('[bold red]This feature can be only used with addons provided by Wago Addons.[/bold '
                                   'red]')
            elif status == 0:
                self.console.print(
                    'All Wago addons are now switched' if args == 'global' else 'Addon switched',
                    'to the [yellow]beta[/yellow] channel.')
            elif status == 1:
                self.console.print(
                    'All Wago addons are now switched' if args == 'global' else 'Addon switched',
                    'to the [red]alpha[/red] channel.')
            elif status == 2:
                self.console.print(
                    'All Wago addons are now switched' if args == 'global' else 'Addon switched',
                    'to the [green]stable[/green] channel.')
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts an addon name (or "global") as an argumen'
                               't.', highlight=False)

    def _c_toggle_pinning(self, args):
        if args := args[8:]:
            status = self.core.block_toggle(args)
            if status is None:
                self.console.print('[bold red]This addon does not exist or it is not installed yet.[/bold red]')
            elif status:
                self.console.print('Updates for this addon are now [red]suppressed[/red].')
            else:
                self.console.print('Updates for this addon are [green]no longer suppressed[/green].')
        else:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts an addon name as an argument.')

    def _c_toggle_wago(self, args):
        if args := args[5:]:
            if args == self.core.config['WAUsername']:
                self.console.print(f'Wago version check is now: [green]ENABLED[/green]\nEntries created by [bold white]'
                                   f'{self.core.config["WAUsername"]}[/bold white] are now included.')
                self.core.config['WAUsername'] = ''
            else:
                self.core.config['WAUsername'] = args.strip()
                self.console.print(f'Wago version check is now: [green]ENABLED[/green]\nEntries created by [bold white]'
                                   f'{self.core.config["WAUsername"]}[/bold white] are now ignored.')
        elif self.core.config['WAUsername'] == 'DISABLED':
            self.core.config['WAUsername'] = ''
            self.console.print('Wago version check is now: [green]ENABLED[/green]')
        else:
            self.core.config['WAUsername'] = 'DISABLED'
            shutil.rmtree(Path('Interface/AddOns/WeakAurasCompanion'), ignore_errors=True)
            self.console.print('Wago version check is now: [red]DISABLED[/red]')
        self.core.save_config()

    def _c_toggle_parse(self, option, inside=None):
        if inside:
            self.core.config[option][inside] = not self.core.config[option][inside]
            self.core.save_config()
            return self.core.config[option][inside]
        else:
            self.core.config[option] = not self.core.config[option]
            self.core.save_config()
            return self.core.config[option]

    def c_toggle(self, args):
        if not args:
            self.console.print('[green]Usage:[/green]\n\t[green]toggle authors[/green]\n\t\tEnables/disables the displa'
                               'y of addon author names in the table.\n\t[green]toggle autoupdate[/green]\n\t\tEnables/'
                               'disables the automatic addon update on startup.\n\t[green]toggle autoupdate_delay[/gree'
                               'n]\n\t\tEnables/disables the timeout before the automatic addon update.\n\t[green]toggl'
                               'e backup[/green]\n\t\tEnables/disables automatic daily backup of WTF directory.\n\t[gre'
                               'en]toggle channel [Name][/green]\n\t\tCommand accepts an addon name (or "global") as ar'
                               'gument.\n\t\tPrioritizes alpha/beta versions for the provided addon.\n\t[green]toggle c'
                               'ompact_mode [/green]\n\t\tEnables/disables compact table mode that hides entries of up-'
                               'to-date addons.\n\t[green]toggle pinning [Name][/green]\n\t\tCommand accepts an addon n'
                               'ame as argument.\n\t\tBlocks/unblocks updating of the provided addon.\n\t[green]toggle '
                               'sources[/green]\n\t\tEnables/disables the source column in the status table.\n\t[green]'
                               'toggle wago [Username][/green]\n\t\tEnables/disables automatic Wago updates.\n\t\tIf a '
                               'username is provided check will start to ignore the specified author.', highlight=False)
            return
        args = args.strip()
        if args.startswith('channel'):
            self._c_toggle_channel(args)
        elif args.startswith('pinning'):
            self._c_toggle_pinning(args)
        elif args.startswith('wago'):
            self._c_toggle_wago(args)
        elif args == 'authors':
            status = self._c_toggle_parse('ShowAuthors')
            self.console.print('The authors listing is on now:',
                               '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')
        elif args == 'autoupdate_delay':
            status = self._c_toggle_parse('AutoUpdateDelay')
            self.console.print('The timeout before the automatic addon update on startup is now:',
                               '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')
        elif args == 'autoupdate':
            status = self._c_toggle_parse('AutoUpdate')
            self.console.print('The automatic addon update on startup is now:',
                               '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')
        elif args == 'backup':
            status = self._c_toggle_parse('Backup', 'Enabled')
            self.console.print('Backup of WTF directory is now:',
                               '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')
        elif args == 'compact_mode':
            status = self._c_toggle_parse('CompactMode')
            self.console.print('Table compact mode is now:',
                               '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')
        elif args == 'sources':
            status = self._c_toggle_parse('ShowSources')
            self.console.print('The source column is now:',
                               '[green]ENABLED[/green]' if status else '[red]DISABLED[/red]')
        else:
            self.console.print('Unknown option.')

    def _c_set_parse(self, msg, key, value):
        self.console.print(msg)
        self.core.config[key] = value.strip()
        self.core.save_config()

    def c_set(self, args):
        if not args:
            self.console.print('[green]Usage:[/green]\n\t[green]set wago_addons_api [API key][/green]\n\t\tSets Wago Ad'
                               'dons API key required to use Wago Addons as addon source.\n\t\tIt can be obtained here:'
                               ' [link=https://addons.wago.io/patreon]https://addons.wago.io/patreon[/link]\n\t[green]s'
                               'et wago_api [API key][/green]\n\t\tSets Wago API key required to access private entries'
                               '.\n\t\tIt can be obtained here: [link=https://wago.io/account]https://wago.io/account[/'
                               'link]\n\t[green]set wago_wow_account [Account name][/green]\n\t\tSets WoW account used '
                               'by Wago updater.\n\t\tNeeded only if compatible addons are used on more than one WoW ac'
                               'count.\n\t[green]set gh_api [API key][/green]\n\t\tSets GitHub API key. Might be needed'
                               ' to get around API rate limits.', highlight=False)
            return
        args = args.strip()
        if args.startswith('wago_addons_api'):
            if args := args[16:]:
                self._c_set_parse('Wago Addons API key is now set.', 'WAAAPIKey', args)
            elif self.core.config['WAAAPIKey'] != '':
                self._c_set_parse('Wago Addons API key is now removed.', 'WAAAPIKey', '')
            else:
                self.console.print('[green]Usage:[/green]\n\tThis command accepts API key as an argument.')
        elif args.startswith('wago_api'):
            if args := args[9:]:
                self._c_set_parse('Wago API key is now set.', 'WAAPIKey', args)
            elif self.core.config['WAAPIKey'] != '':
                self._c_set_parse('Wago API key is now removed.', 'WAAPIKey', '')
            else:
                self.console.print('[green]Usage:[/green]\n\tThis command accepts API key as an argument.')
        elif args.startswith('gh_api'):
            if args := args[7:]:
                self._c_set_parse('GitHub API key is now set.', 'GHAPIKey', args)
            elif self.core.config['GHAPIKey'] != '':
                self._c_set_parse('GitHub API key is now removed.', 'GHAPIKey', '')
            else:
                self.console.print('[green]Usage:[/green]\n\tThis command accepts API key as an argument.')
        elif args.startswith('wago_wow_account'):
            if args := args[17:]:
                args = args.strip()
                if os.path.isfile(Path(f'WTF/Account/{args}/SavedVariables/WeakAuras.lua')) or \
                        os.path.isfile(Path(f'WTF/Account/{args}/SavedVariables/Plater.lua')):
                    self.console.print(f'WoW account name set to: [bold white]{args}[/bold white]')
                    self.core.config['WAAccountName'] = args
                    self.core.save_config()
                else:
                    self.console.print('Incorrect WoW account name.')
            else:
                self.console.print('[green]Usage:[/green]\n\tThis command accepts the WoW account name as an'
                                   ' argument.')
        else:
            self.console.print('Unknown option.')

    def _c_wago_update_init(self, flush, verbose):
        accounts = self.core.detect_accounts()
        if self.core.config['WAAccountName'] != '' and self.core.config['WAAccountName'] not in accounts:
            self.core.config['WAAccountName'] = ''
        if len(accounts) == 0:
            return
        elif len(accounts) > 1 and self.core.config['WAAccountName'] == '':
            if verbose:
                self.console.print('More than one WoW account detected.\nPlease use [bold white]set wago_wow_accoun'
                                   't[''/bold white] command to set the correct account name.')
            else:
                self.console.print('\n[green]More than one WoW account detected.[/green]\nPlease use [bold white]se'
                                   't wago_wow_account[/bold white] command to set the correct account name.')
            return
        elif len(accounts) == 1 and self.core.config['WAAccountName'] == '':
            self.core.config['WAAccountName'] = accounts[0]
            self.core.save_config()
        if flush and len(self.core.config['WAStash']) > 0:
            self.core.config['WAStash'] = []
            self.core.save_config()

    def _c_wago_update_status(self, addon, status):
        self.console.print(f'[green]Outdated {addon}:[/green]')
        for aura in status[0]:
            self.console.print(f'[link={aura[1]}]{aura[0]}[/link]', highlight=False)
        self.console.print(f'\n[green]Detected {addon}:[/green]')
        for aura in status[1]:
            self.console.print(f'[link={aura[1]}]{aura[0]}[/link]', highlight=False)

    def c_wago_update(self, _, verbose=True, flush=True):
        if not os.path.isdir(Path('Interface/AddOns/WeakAuras')) and not os.path.isdir(Path('Interface/AddOns/Plater')):
            if verbose:
                self.console.print('No compatible addon is installed.')
            return
        self._c_wago_update_init(flush, verbose)
        wago = WagoUpdater(self.core.config, self.core.http)
        if Version(__version__) >= Version(self.core.masterConfig['ConfigVersion']) and \
                self.core.masterConfig['CBCompanionVersion'] > self.core.config['CBCompanionVersion']:
            self.core.config['CBCompanionVersion'] = self.core.masterConfig['CBCompanionVersion']
            self.core.save_config()
            force = True
        else:
            force = False
        wago.install_companion(force)
        statuswa, statusplater, statusstash = wago.update()
        if verbose:
            if len(statusstash) > 0:
                self.console.print('[green]WeakAuras ready to install:[/green]')
                for aura in statusstash:
                    self.console.print(aura)
                self.console.print('\nReload the interface in the WoW client to access them.')
            elif len(statuswa[0]) > 0 or len(statuswa[1]) > 0:
                self._c_wago_update_status('WeakAuras', statuswa)
            if len(statusplater[0]) > 0 or len(statusplater[1]) > 0:
                if len(statuswa[0]) != 0 or len(statuswa[1]) != 0:
                    self.console.print('')
                self._c_wago_update_status('Plater', statusplater)
        else:
            if not self.headless:
                self.console.control(Control.move(x=0, y=-1))
            if len(statuswa[0]) > 0:
                self.console.print(f'\n[green]The number of outdated WeakAuras:[/green] '
                                   f'{len(statuswa[0])}', highlight=False)
            if len(statusplater[0]) > 0:
                self.console.print(f'\n[green]The number of outdated Plater profiles/scripts:[/green] '
                                   f'{len(statusplater[0])}', highlight=False)

    def c_search(self, args):
        if not args:
            self.console.print('[green]Usage:[/green]\n\tThis command accepts a search query as an argument.')
            return
        results = self.core.search(args)
        self.console.print('[green]Top results of your search:[/green]')
        for url in results:
            if self.core.check_if_installed(url):
                self.console.print(f'[link={url}]{url}[/link] [yellow][Installed][/yellow]', highlight=False)
            else:
                self.console.print(f'[link={url}]{url}[/link]', highlight=False)

    def c_backup(self, _):
        self.core.backup_wtf(None if self.headless else self.console)

    def c_import(self, args):
        names, slugs, installed = self.core.detect_addons()
        if args == 'install' and len(slugs) > 0:
            self.c_install(','.join(slugs))
        else:
            self.console.print('[green]New addons found:[/green]')
            for addon in names:
                self.console.print(addon, highlight=False)
            self.console.print('\n[yellow]Already installed addons:[/yellow]')
            for addon in installed:
                self.console.print(addon, highlight=False)
            self.console.print('\n[bold]This process detects only addons available on Wago Addons and ElvUI/Tukui.[/bol'
                               'd]\nExecute [bold white]import install[/bold white] command to install all new detected'
                               ' addons.\nAfter installation run the [bold white]orphans[/bold white] command and [bold'
                               ' white]install[/bold white] missing addons.')

    def c_export(self, _):
        payload = self.core.export_addons()
        pyperclip.copy(payload)
        self.console.print(f'{payload}\n\nThe command above was copied to the clipboard.', highlight=False)

    def c_help(self, _):
        self.console.print('[green]install [URL][/green]\n\tCommand accepts a space-separated list of links.\n\t[bold w'
                           'hite]Flags:[/bold white]\n\t'
                           '\t[bold white]-i[/bold white] - Disable the client version check.\n'
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
                           '[green]status[/green]\n\tPrints the current state of all installed addons.\n\t[bold yellow]'
                           '[!][/bold yellow] mark means that the latest release is not updated yet for the current WoW'
                           ' version.\n\t[bold white]Flags:[/bold white]\n\t\t[bold white]-a[/bold white] - Temporary r'
                           'everse the table compacting option.\n\t\t[bold white]-s[/bold white] - Temporary reverse th'
                           'e source display option.\n'
                           '[green]orphans[/green]\n\tPrints list of orphaned directories and files.\n'
                           '[green]search [Keyword][/green]\n\tExecutes addon search on Wago Addons.\n'
                           '[green]backup[/green]\n\tCommand creates a backup of WTF directory.\n'
                           '[green]import[/green]\n\tCommand attempts to import already installed addons.\n'
                           '[green]export[/green]\n\tCommand prints list of all installed addons in a form suitable f'
                           'or sharing.\n'
                           '[green]toggle authors[/green]\n\tEnables/disables the display of addon author names in the '
                           'table.\n'
                           '[green]toggle autoupdate[/green]\n\tEnables/disables the automatic addon update on startup'
                           '.\n'
                           '[green]toggle autoupdate_delay[/green]\n\tEnables/disables the timeout before the automatic'
                           ' addon update.\n'
                           '[green]toggle backup[/green]\n\tEnables/disables automatic daily backup of WTF directory.\n'
                           '[green]toggle channel [Name][/green]\n\tCommand accepts an addon name (or "global") as argu'
                           'ment.\n\tPrioritizes alpha/beta versions for the provided addon.\n'
                           '[green]toggle compact_mode [/green]\n\tEnables/disables compact table mode that hides entri'
                           'es of up-to-date addons.\n'
                           '[green]toggle pinning [Name][/green]\n\tCommand accepts an addon name as argument.\n\tBlock'
                           's/unblocks updating of the provided addon.\n'
                           '[green]toggle sources[/green]\n\tEnables/disables the source column in the status table.\n'
                           '[green]toggle wago [Username][/green]\n\tEnables/disables automatic Wago updates.\n\tIf a u'
                           'sername is provided check will start to ignore the specified author.\n'
                           '[green]set wago_addons_api [API key][/green]\n\tSets Wago Addons API key required to use Wa'
                           'go Addons as addon source.\n\tIt can be obtained here: [link=https://addons.wago.io/patreon'
                           ']https://addons.wago.io/patreon[/link]\n'
                           '[green]set wago_api [API key][/green]\n\tSets Wago API key required to access private entri'
                           'es.\n\tIt can be obtained here: [link=https://wago.io/account]https://wago.io/account[/link'
                           ']\n'
                           '[green]set wago_wow_account [Account name][/green]\n\tSets WoW account used by Wago updater'
                           '.\n\tNeeded only if compatible addons are used on more than one WoW account.\n[green]set gh'
                           '_api [API key][/green]\n\tSets GitHub API key. Might be needed to get around API rate limit'
                           's.\n'
                           '[green]uri_integration[/green]\n\tEnables integration with Wago Addons and Wago page.\n\t"D'
                           'ownload with Wago App" and "Send to WeakAura Companion App" buttons.\n\n[bold green]Support'
                           'ed URL:[/bold green]\n\thttps://addons.wago.io/addons/\\[addon_name] [bold white]|[/bold wh'
                           'ite] wa:\\[addon_name]\n\thttps://www.wowinterface.com/downloads/\\[addon_name] [bold white'
                           ']|[/bold white] wowi:\\[addon_id]\n\thttps://github.com/\\[username]/\\[repository_name] [b'
                           'old white]|[/bold white] gh:\\[username]/\\[repository_name]\n\tElvUI [bold white]|[/bold w'
                           'hite] Tukui\n\t' + self.parse_custom_addons(), highlight=False)

    def c_exit(self, _):
        self.core.http.close()
        sys.exit(0)


if __name__ == '__main__':
    if clientpath := os.environ.get('CURSEBREAKER_PATH'):
        os.chdir(clientpath)
    elif getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
    set_terminal_title(f'CurseBreaker v{__version__}')
    app = TUI()
    app.start()
