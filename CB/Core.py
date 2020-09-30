import os
import re
import io
import sys
import json
import html
import gzip
import time
import glob
import pickle
import shutil
import zipfile
import datetime
import requests
import cloudscraper
from pathlib import Path
from collections import Counter
from checksumdir import dirhash
from multiprocessing import Pool
from rich.progress import Progress, BarColumn
from xml.dom.minidom import parse, parseString
from . import retry, HEADERS, __version__
from .Tukui import TukuiAddon
from .GitHub import GitHubAddon
from .GitLab import GitLabAddon
from .CurseForge import CurseForgeAddon
from .WoWInterface import WoWInterfaceAddon


class Core:
    def __init__(self):
        self.path = Path('Interface/AddOns')
        self.configPath = Path('WTF/CurseBreaker.json')
        self.cachePath = Path('WTF/CurseBreaker.cache')
        self.clientType = 'wow_retail'
        self.wagoCompanionVersion = 111
        self.config = None
        self.cfIDs = None
        self.cfDirs = None
        self.cfCache = {}
        self.wowiCache = {}
        self.checksumCache = {}
        self.scraper = cloudscraper.create_scraper()

    def init_config(self):
        if os.path.isfile('CurseBreaker.json'):
            shutil.move('CurseBreaker.json', 'WTF')
        if os.path.isfile(self.configPath):
            with open(self.configPath, 'r') as f:
                try:
                    self.config = json.load(f)
                except (StopIteration, UnicodeDecodeError, json.JSONDecodeError):
                    raise RuntimeError
        else:
            self.config = {'Addons': [],
                           'IgnoreClientVersion': {},
                           'Backup': {'Enabled': True, 'Number': 7},
                           'CFCacheCloudFlare': {},
                           'Version': __version__,
                           'WAUsername': '',
                           'WAAccountName': '',
                           'WAAPIKey': '',
                           'WACompanionVersion': 0,
                           'CFCacheTimestamp': 0,
                           'CompactMode': False,
                           'AutoUpdate': True}
            self.save_config()
        if not os.path.isdir('WTF-Backup') and self.config['Backup']['Enabled']:
            os.mkdir('WTF-Backup')
        self.update_config()

    def save_config(self):
        with open(self.configPath, 'w') as outfile:
            json.dump(self.config, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def update_config(self):
        if 'Version' not in self.config.keys() or self.config['Version'] != __version__:
            urlupdate = {'elvui-classic': 'elvui', 'elvui-classic:dev': 'elvui:dev', 'tukui-classic': 'tukui',
                         'sle:dev': 'shadow&light:dev'}
            for addon in self.config['Addons']:
                # 1.1.0
                if 'Checksums' not in addon.keys():
                    checksums = {}
                    for directory in addon['Directories']:
                        checksums[directory] = dirhash(self.path / directory)
                    addon['Checksums'] = checksums
                # 1.1.1
                if addon['Version'] is None:
                    addon['Version'] = '1'
                # 2.2.0, 3.9.4
                if addon['URL'].lower() in urlupdate:
                    addon['URL'] = urlupdate[addon['URL'].lower()]
                # 2.4.0
                if addon['Name'] == 'TukUI':
                    addon['Name'] = 'Tukui'
                    addon['URL'] = 'Tukui'
                # 2.7.3
                addon['Directories'] = list(filter(None, set(addon['Directories'])))
                # 3.0.2
                if addon['URL'].endswith('/'):
                    addon['URL'] = addon['URL'][:-1]
                # 3.3.0
                if 'Development' in addon.keys() and isinstance(addon['Development'], bool):
                    addon['Development'] = 1
            for add in [['2.1.0', 'WAUsername', ''],
                        ['2.2.0', 'WAAccountName', ''],
                        ['2.2.0', 'WAAPIKey', ''],
                        ['2.2.0', 'WACompanionVersion', 0],
                        ['2.8.0', 'IgnoreClientVersion', {}],
                        ['3.0.1', 'CFCacheTimestamp', 0],
                        ['3.1.10', 'CFCacheCloudFlare', {}],
                        ['3.7.0', 'CompactMode', False],
                        ['3.10.0', 'AutoUpdate', True]]:
                if add[1] not in self.config.keys():
                    self.config[add[1]] = add[2]
            for delete in [['1.3.0', 'URLCache'],
                           ['3.0.1', 'CurseCache']]:
                if delete[1] in self.config.keys():
                    self.config.pop(delete[1], None)
            self.config['Version'] = __version__
            self.save_config()

    def check_if_installed(self, url):
        for addon in self.config['Addons']:
            if addon['URL'] == url or addon['Name'] == url:
                return addon

    def check_if_installed_dirs(self, directories):
        for addon in self.config['Addons']:
            if Counter(directories) == Counter(addon['Directories']):
                return addon

    def check_if_dev(self, url):
        addon = self.check_if_installed(url)
        if addon:
            if 'Development' in addon.keys():
                return addon['Development']
            else:
                return 0
        else:
            return 0

    def check_if_blocked(self, addon):
        if addon:
            if 'Block' in addon.keys():
                return True
            else:
                return False
        else:
            return False

    def check_if_dev_global(self):
        for addon in self.config['Addons']:
            if addon['URL'].startswith('https://www.curseforge.com/wow/addons/') and 'Development' in addon.keys():
                return addon['Development']
        else:
            return 0

    def cleanup(self, directories):
        if len(directories) > 0:
            for directory in directories:
                shutil.rmtree(self.path / directory, ignore_errors=True)

    def parse_url(self, url):
        if url.startswith('https://www.curseforge.com/wow/addons/'):
            return CurseForgeAddon(url, self.parse_cf_id(url), self.cfCache,
                                   'wow' if url in self.config['IgnoreClientVersion'].keys() else self.clientType,
                                   self.check_if_dev(url))
        elif url.startswith('https://www.wowinterface.com/downloads/'):
            return WoWInterfaceAddon(url, self.wowiCache)
        elif url.startswith('https://www.tukui.org/addons.php?id='):
            if self.clientType == 'wow_classic':
                raise RuntimeError('Incorrect client version.')
            return TukuiAddon(url, False)
        elif url.startswith('https://www.tukui.org/classic-addons.php?id='):
            if self.clientType == 'wow_retail':
                raise RuntimeError('Incorrect client version.')
            elif url.endswith('1') or url.endswith('2'):
                raise RuntimeError('ElvUI and Tukui cannot be installed this way.')
            return TukuiAddon(url, True)
        elif url.startswith('https://github.com/'):
            return GitHubAddon(url, self.clientType)
        elif url.lower() == 'elvui':
            if self.clientType == 'wow_retail':
                return GitLabAddon('ElvUI', '60', 'elvui/elvui', 'master')
            else:
                return GitLabAddon('ElvUI', '492', 'elvui/elvui-classic', 'master')
        elif url.lower() == 'elvui:dev':
            if self.clientType == 'wow_retail':
                return GitLabAddon('ElvUI', '60', 'elvui/elvui', 'development')
            else:
                return GitLabAddon('ElvUI', '492', 'elvui/elvui-classic', 'development')
        # TODO Remove after 9.0 release
        elif url.lower() == 'elvui:beta':
            return GitLabAddon('ElvUI', '60', 'elvui/elvui', 'beta')
        elif url.lower() == 'tukui':
            if self.clientType == 'wow_retail':
                return GitLabAddon('Tukui', '77', 'Tukz/Tukui', 'master')
            else:
                return GitLabAddon('Tukui', '77', 'Tukz/Tukui', 'Classic')
        elif url.lower() == 'shadow&light:dev':
            if self.clientType == 'wow_retail':
                return GitLabAddon('ElvUI Shadow & Light', '45', 'shadow-and-light/shadow-and-light', 'dev')
            else:
                raise RuntimeError('Incorrect client version.')
        else:
            raise NotImplementedError('Provided URL is not supported.')

    def parse_url_source(self, url):
        if url.startswith('https://www.curseforge.com/wow/addons/'):
            return 'CF', url
        elif url.startswith('https://www.wowinterface.com/downloads/'):
            return 'WoWI', url
        elif url.startswith('https://www.tukui.org/addons.php?id=') or \
                url.startswith('https://www.tukui.org/classic-addons.php?id='):
            return 'Tukui', url
        elif url.lower().startswith('elvui'):
            return 'Tukui', 'https://www.tukui.org/download.php?ui=elvui'
        elif url.lower().startswith('tukui'):
            return 'Tukui', 'https://www.tukui.org/download.php?ui=tukui'
        elif url.lower() == 'shadow&light:dev':
            return 'Tukui', 'https://www.curseforge.com/wow/addons/elvui-shadow-light'
        elif url.startswith('https://github.com/'):
            return 'GitHub', url
        else:
            return '?', None

    def add_addon(self, url, ignore):
        if url.endswith(':'):
            raise NotImplementedError('Provided URL is not supported.')
        elif 'twitch://' in url:
            url = url.split('/download-client')[0].replace('twitch://', 'https://').strip()
        elif url.startswith('cf:'):
            url = f'https://www.curseforge.com/wow/addons/{url[3:]}'
        elif url.startswith('wowi:'):
            url = f'https://www.wowinterface.com/downloads/info{url[5:]}.html'
        elif url.startswith('tu:'):
            url = f'https://www.tukui.org/addons.php?id={url[3:]}'
        elif url.startswith('tuc:'):
            url = f'https://www.tukui.org/classic-addons.php?id={url[4:]}'
        elif url.startswith('gh:'):
            url = f'https://github.com/{url[3:]}'
        if url.endswith('/'):
            url = url[:-1]
        addon = self.check_if_installed(url)
        if not addon:
            if ignore:
                self.config['IgnoreClientVersion'][url] = True
            new = self.parse_url(url)
            new.get_addon()
            addon = self.check_if_installed_dirs(new.directories)
            if addon:
                return False, addon['Name'], addon['Version']
            self.cleanup(new.directories)
            new.install(self.path)
            checksums = {}
            for directory in new.directories:
                checksums[directory] = dirhash(self.path / directory)
            self.config['Addons'].append({'Name': new.name,
                                          'URL': url,
                                          'Version': new.currentVersion,
                                          'Directories': new.directories,
                                          'Checksums': checksums
                                          })
            self.save_config()
            return True, new.name, new.currentVersion
        return False, addon['Name'], addon['Version']

    def del_addon(self, url, keep):
        old = self.check_if_installed(url)
        if old:
            if not keep:
                self.cleanup(old['Directories'])
            self.config['IgnoreClientVersion'].pop(old['URL'], None)
            self.config['Addons'][:] = [d for d in self.config['Addons'] if d.get('URL') != url
                                        and d.get('Name') != url]
            self.save_config()
            return old['Name'], old['Version']
        return False, False

    def update_addon(self, url, update, force):
        old = self.check_if_installed(url)
        if old:
            source, sourceurl = self.parse_url_source(old['URL'])
            new = self.parse_url(old['URL'])
            oldversion = old['Version']
            if old['URL'] in self.checksumCache:
                modified = self.checksumCache[old['URL']]
            else:
                modified = self.check_checksum(old, False)
            blocked = self.check_if_blocked(old)
            if force or (new.currentVersion != old['Version'] and update and not modified and not blocked):
                new.get_addon()
                self.cleanup(old['Directories'])
                new.install(self.path)
                checksums = {}
                for directory in new.directories:
                    checksums[directory] = dirhash(self.path / directory)
                old['Name'] = new.name
                old['Version'] = new.currentVersion
                old['Directories'] = new.directories
                old['Checksums'] = checksums
                self.save_config()
            if force:
                modified = False
                blocked = False
            return new.name, new.currentVersion, oldversion, modified, blocked, source, sourceurl, new.changelogUrl
        return url, False, False, False, False, '?', None, None

    def check_checksum(self, addon, bulk=True):
        checksums = {}
        for directory in addon['Directories']:
            if os.path.isdir(self.path / directory):
                checksums[directory] = dirhash(self.path / directory)
        if bulk:
            return [addon['URL'], len(checksums.items() & addon['Checksums'].items()) != len(addon['Checksums'])]
        else:
            return len(checksums.items() & addon['Checksums'].items()) != len(addon['Checksums'])

    def bulk_check_checksum_callback(self, result):
        self.checksumCache[result[0]] = result[1]

    def bulk_check_checksum(self, addons, pbar):
        with Pool() as pool:
            workers = []
            for addon in addons:
                w = pool.apply_async(self.check_checksum, (addon, ), callback=self.bulk_check_checksum_callback)
                workers.append(w)
            for w in workers:
                w.wait()
                pbar.update(0, advance=0.5, refresh=True)

    def dev_toggle(self, url):
        if url == 'global':
            state = self.check_if_dev_global()
            for addon in self.config['Addons']:
                if addon['URL'].startswith('https://www.curseforge.com/wow/addons/'):
                    if state == 0:
                        addon['Development'] = 1
                    elif state == 1:
                        addon['Development'] = 2
                    elif state == 2:
                        addon.pop('Development', None)
            self.save_config()
            return state
        else:
            addon = self.check_if_installed(url)
            if addon:
                if addon['URL'].startswith('https://www.curseforge.com/wow/addons/'):
                    state = self.check_if_dev(url)
                    if state == 0:
                        addon['Development'] = 1
                    elif state == 1:
                        addon['Development'] = 2
                    elif state == 2:
                        addon.pop('Development', None)
                    self.save_config()
                    return state
                else:
                    return -1
            return None

    def block_toggle(self, url):
        addon = self.check_if_installed(url)
        if addon:
            state = self.check_if_blocked(addon)
            if state:
                addon.pop('Block', None)
            else:
                addon['Block'] = True
            self.save_config()
            return not state
        return None

    def generic_toggle(self, option, inside=None):
        if inside:
            self.config[option][inside] = not self.config[option][inside]
            self.save_config()
            return self.config[option][inside]
        else:
            self.config[option] = not self.config[option]
            self.save_config()
            return self.config[option]

    def backup_check(self):
        if self.config['Backup']['Enabled']:
            if not os.path.isfile(Path('WTF-Backup', f'{datetime.datetime.now().strftime("%d%m%y")}.zip')):
                listofbackups = [Path(x) for x in glob.glob('WTF-Backup/*.zip')]
                if len(listofbackups) == self.config['Backup']['Number']:
                    oldest_file = min(listofbackups, key=os.path.getctime)
                    os.remove(oldest_file)
                return True
            else:
                return False
        else:
            return False

    def backup_wtf(self, console):
        zipf = zipfile.ZipFile(Path('WTF-Backup', f'{datetime.datetime.now().strftime("%d%m%y")}.zip'), 'w',
                               zipfile.ZIP_DEFLATED)
        filecount = 0
        for _, _, files in os.walk('WTF/', topdown=True, followlinks=True):
            files = [f for f in files if not f[0] == '.']
            filecount += len(files)
        with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|', auto_refresh=False,
                      console=console) as progress:
            task = progress.add_task('', total=filecount)
            while not progress.finished:
                for root, _, files in os.walk('WTF/', topdown=True, followlinks=True):
                    files = [f for f in files if not f[0] == '.']
                    for f in files:
                        zipf.write(Path(root, f))
                        progress.update(task, advance=1, refresh=True)
        zipf.close()

    def find_orphans(self):
        orphanedaddon = []
        orphaneconfig = []
        directories = []
        directoriesgit = []
        ignored = ['.DS_Store']
        for addon in self.config['Addons']:
            for directory in addon['Directories']:
                directories.append(directory)
        for directory in os.listdir(self.path):
            if directory not in directories:
                if os.path.isdir(self.path / directory / '.git'):
                    orphanedaddon.append(f'{directory} [GIT]')
                    directoriesgit.append(directory)
                elif directory not in ignored:
                    orphanedaddon.append(directory)
        directories += directoriesgit + orphanedaddon
        for root, dirs, files in os.walk('WTF/', followlinks=True):
            for f in files:
                if 'Blizzard_' not in f and f.endswith('.lua'):
                    name = os.path.splitext(f)[0]
                    if name not in directories:
                        orphaneconfig.append(str(Path(root, f))[4:])
        return orphanedaddon, orphaneconfig

    @retry(custom_error='Failed to execute the search.')
    def search(self, query):
        results = []
        payload = requests.get(f'https://addons-ecs.forgesvc.net/api/v2/addon/search?gameId=1&pageSize=10&searchFilter='
                               f'{html.escape(query.strip())}', headers=HEADERS).json()
        for result in payload:
            results.append(result['websiteUrl'])
        return results

    def create_reg(self):
        with open('CurseBreaker.reg', 'w') as outfile:
            outfile.write('Windows Registry Editor Version 5.00\n\n[HKEY_CLASSES_ROOT\.ccip\Shell\Open\Command]\n@="\\"'
                          + os.path.abspath(sys.executable).replace('\\', '\\\\') + '\\\" \\"%1\\""\n[HKEY_CURRENT_USER'
                          '\Software\Classes\\twitch]\n"URL Protocol"="\\"\\""\n@="\\"URL:CurseBreaker Protocol\\""\n[H'
                          'KEY_CURRENT_USER\Software\Classes\\twitch\DefaultIcon]\n@="\\"CurseBreaker.exe,1\\""\n[HKEY_'
                          'CURRENT_USER\Software\Classes\\twitch\shell]\n[HKEY_CURRENT_USER\Software\Classes\\twitch\sh'
                          'ell\open]\n[HKEY_CURRENT_USER\Software\Classes\\twitch\shell\open\command]\n@="\\"'
                          + os.path.abspath(sys.executable).replace('\\', '\\\\') + '\\" \\"%1\\""')

    @retry()
    def parse_cf_id(self, url, bulk=False):
        if not self.cfIDs:
            # noinspection PyBroadException
            try:
                if not os.path.isfile(self.cachePath) or time.time() - self.config['CFCacheTimestamp'] > 86400:
                    with open(self.cachePath, 'wb') as f:
                        f.write(gzip.decompress(requests.get(
                            f'https://storage.googleapis.com/cursebreaker/cfid.pickle.gz', headers=HEADERS).content))
                    self.config['CFCacheTimestamp'] = int(time.time())
                    self.save_config()
                with open(self.cachePath, 'rb') as f:
                    self.cfIDs = pickle.load(f)
                self.cfIDs = {**self.config['CFCacheCloudFlare'], **self.cfIDs}
            except Exception:
                self.cfIDs = {}
        slug = url.split('/')[-1]
        if slug in self.cfIDs:
            project = self.cfIDs[slug]
        else:
            payload = self.scraper.get(url + '/download-client')
            if payload.status_code == 404:
                renamecheck = self.scraper.get(url, allow_redirects=False)
                if renamecheck.status_code == 303:
                    payload = self.scraper.get(f'https://www.curseforge.com{renamecheck.headers["location"]}'
                                               f'/download-client')
                if payload.status_code == 404:
                    if bulk:
                        return 0
                    else:
                        raise RuntimeError(f'{slug}\nThe project could be removed from CurseForge or renamed. Uninstall'
                                           f' it (and reinstall if it still exists) to fix this issue.')
            xml = parseString(payload.text)
            project = xml.childNodes[0].getElementsByTagName('project')[0].getAttribute('id')
            self.config['CFCacheCloudFlare'][slug] = project
            self.cfIDs = {**self.config['CFCacheCloudFlare'], **self.cfIDs}
            self.save_config()
        return project

    @retry(custom_error='Failed to parse the XML file.')
    def parse_cf_xml(self, path):
        xml = parse(path)
        project = xml.childNodes[0].getElementsByTagName('project')[0].getAttribute('id')
        payload = requests.get(f'https://addons-ecs.forgesvc.net/api/v2/addon/{project}', headers=HEADERS).json()
        url = payload['websiteUrl'].strip()
        return url

    @retry()
    def bulk_check(self, addons):
        ids_cf = []
        ids_wowi = []
        for addon in addons:
            if addon['URL'].startswith('https://www.curseforge.com/wow/addons/'):
                ids_cf.append(int(self.parse_cf_id(addon['URL'], True)))
            elif addon['URL'].startswith('https://www.wowinterface.com/downloads/'):
                ids_wowi.append(re.findall(r'\d+', addon['URL'])[0].strip())
        if len(ids_cf) > 0:
            payload = requests.post('https://addons-ecs.forgesvc.net/api/v2/addon', json=ids_cf, headers=HEADERS).json()
            for addon in payload:
                self.cfCache[str(addon['id'])] = addon
        if len(ids_wowi) > 0:
            payload = requests.get(f'https://api.mmoui.com/v4/game/WOW/filedetails/{",".join(ids_wowi)}.json',
                                   headers=HEADERS).json()
            for addon in payload:
                self.wowiCache[str(addon['id'])] = addon

    def detect_accounts(self):
        if os.path.isdir(Path('WTF/Account')):
            accounts = os.listdir(Path('WTF/Account'))
            accounts_processed = []
            for account in accounts:
                if os.path.isfile(Path(f'WTF/Account/{account}/SavedVariables/WeakAuras.lua')) or \
                        os.path.isfile(Path(f'WTF/Account/{account}/SavedVariables/Plater.lua')):
                    accounts_processed.append(account)
            return accounts_processed
        else:
            return []

    def detect_addons(self):
        if not self.cfDirs:
            self.cfDirs = pickle.load(gzip.open(io.BytesIO(
                requests.get(f'https://storage.googleapis.com/cursebreaker/cfdir{self.clientType}.pickle.gz',
                             headers=HEADERS).content)))
        addon_dirs = os.listdir(self.path)
        ignored = ['ElvUI_OptionsUI', 'Tukui_Config', '.DS_Store']
        hit = []
        partial_hit = []
        partial_hit_tmp = []
        partial_hit_raw = []
        miss = []
        for directory in addon_dirs:
            if os.path.isdir(self.path / directory) and not os.path.islink(self.path / directory) and \
                    not os.path.isdir(self.path / directory / '.git'):
                if directory in self.cfDirs:
                    if len(self.cfDirs[directory]) > 1:
                        partial_hit_raw.append(self.cfDirs[directory])
                    elif not self.check_if_installed(f'https://www.curseforge.com/wow/addons/'
                                                     f'{self.cfDirs[directory][0]}'):
                        hit.append(f'cf:{self.cfDirs[directory][0]}')
                else:
                    if directory == 'ElvUI' or directory == 'Tukui':
                        if not self.check_if_installed(directory):
                            hit.append(directory)
                    elif directory not in ignored:
                        miss.append(directory)
        for partial in partial_hit_raw:
            for slug in partial:
                if f'cf:{slug}' in hit or self.check_if_installed(f'https://www.curseforge.com/wow/addons/{slug}'):
                    break
            else:
                partial = [f'cf:{s}' for s in partial]
                partial_hit_tmp.append(sorted(partial))
        for partial in partial_hit_tmp:
            if partial not in partial_hit:
                partial_hit.append(partial)
        return sorted(list(set(hit))), partial_hit, sorted(list(set(miss)))

    def export_addons(self):
        addons = []
        for addon in self.config['Addons']:
            if addon['URL'].startswith('https://www.curseforge.com/wow/addons/'):
                url = f'cf:{addon["URL"].split("/")[-1]}'
            elif addon['URL'].startswith('https://www.wowinterface.com/downloads/info'):
                url = f'wowi:{addon["URL"].split("/info")[-1].replace(".html", "")}'
            elif addon['URL'].startswith('https://www.tukui.org/addons.php?id='):
                url = f'tu:{addon["URL"].split("?id=")[-1]}'
            elif addon['URL'].startswith('https://www.tukui.org/classic-addons.php?id='):
                url = f'tuc:{addon["URL"].split("?id=")[-1]}'
            elif addon['URL'].startswith('https://github.com/'):
                url = f'gh:{addon["URL"].replace("https://github.com/", "")}'
            else:
                url = addon['URL'].lower()
            addons.append(url)
        return f'install {",".join(sorted(addons))}'
