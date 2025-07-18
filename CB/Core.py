import os
import re
import io
import sys
import json
import gzip
import glob
import httpx
import shutil
import zipfile
import hashlib
import datetime
import concurrent.futures
from pathlib import Path
from collections import Counter
from checksumdir import dirhash
from urllib.parse import quote_plus
from rich.progress import Progress, BarColumn
from . import retry, APIAuth, __version__
from .Tukui import TukuiAddon
from .GitHub import GitHubAddon, GitHubAddonRaw
from .WagoAddons import WagoAddonsAddon
from .WoWInterface import WoWInterfaceAddon


class Core:
    def __init__(self):
        self.http = httpx.Client(headers={'User-Agent': f'CurseBreaker/{__version__}'},
                                 timeout=10, http2=True, follow_redirects=True)
        self.path = Path('Interface/AddOns')
        self.configPath = Path('WTF/CurseBreaker.json')
        self.clientType = None
        self.config = None
        self.masterConfig = None
        self.dirIndex = None
        self.wowiCache = {}
        self.wagoCache = {}
        self.githubCache = {}
        self.wagoIdCache = None
        self.tukuiCache = None
        self.checksumCache = {}

    def init_master_config(self):
        try:
            self.masterConfig = json.load(gzip.open(io.BytesIO(
                self.http.get('https://cursebreaker.acidweb.dev/config-v2.json.gz').content)))
        except (StopIteration, UnicodeDecodeError, json.JSONDecodeError, httpx.RequestError) as e:
            raise RuntimeError('Failed to fetch the master config file. '
                               'Check your connectivity to Google Cloud.') from e

    def init_config(self):
        if os.path.isfile('CurseBreaker.json'):
            shutil.move('CurseBreaker.json', 'WTF')
        if os.path.isfile(Path('WTF/CurseBreaker.cache')):
            os.remove(Path('WTF/CurseBreaker.cache'))
        if os.path.isfile(self.configPath):
            with open(self.configPath) as f:
                try:
                    self.config = json.load(f)
                except (StopIteration, UnicodeDecodeError, json.JSONDecodeError) as e:
                    raise RuntimeError from e
        else:
            self.config = {'Addons': [],
                           'WAStash': [],
                           'IgnoreClientVersion': {},
                           'Backup': {'Enabled': True, 'Number': 7},
                           'Version': __version__,
                           'WAUsername': '',
                           'WAAccountName': '',
                           'WAAPIKey': '',
                           'GHAPIKey': '',
                           'WAAAPIKey': '',
                           'CBCompanionVersion': 0,
                           'CompactMode': False,
                           'AutoUpdate': True,
                           'ShowAuthors': True,
                           'ShowSources': False,
                           'AutoUpdateDelay': True}
            self.save_config()
        if not os.path.isdir('WTF-Backup') and self.config['Backup']['Enabled']:
            os.mkdir('WTF-Backup')
        self.update_config()

    def save_config(self):
        with open(self.configPath, 'w') as outfile:
            json.dump(self.config, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def update_config(self):
        if 'Version' in self.config.keys() and self.config['Version'] == __version__:
            return
        urlupdate = {'elvui-classic': 'elvui', 'elvui-classic:dev': 'elvui:dev', 'tukui-classic': 'tukui',
                     'sle:dev': 'shadow&light:dev', 'elvui:beta': 'elvui:dev'}
        # 4.0.0
        if 'WACompanionVersion' in self.config and os.path.isdir(Path('Interface/AddOns/WeakAurasCompanion')):
            shutil.rmtree(Path('Interface/AddOns/WeakAurasCompanion'), ignore_errors=True)
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
            # 2.2.0, 3.9.4, 3.12.0
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
            # 4.3.0
            if addon['URL'].startswith('https://www.tukui.org/classic-tbc-addons.php?id='):
                addon['URL'] = addon['URL'].replace('https://www.tukui.org/classic-tbc-addons.php?id=',
                                                    'https://www.tukui.org/classic-wotlk-addons.php?id=')
        for add in [['2.1.0', 'WAUsername', ''],
                    ['2.2.0', 'WAAccountName', ''],
                    ['2.2.0', 'WAAPIKey', ''],
                    ['2.2.0', 'WACompanionVersion', 0],
                    ['2.8.0', 'IgnoreClientVersion', {}],
                    ['3.0.1', 'CFCacheTimestamp', 0],
                    ['3.1.10', 'CFCacheCloudFlare', {}],
                    ['3.7.0', 'CompactMode', False],
                    ['3.10.0', 'AutoUpdate', True],
                    ['3.12.0', 'ShowAuthors', True],
                    ['3.16.0', 'IgnoreDependencies', {}],
                    ['3.18.0', 'WAStash', []],
                    ['3.20.0', 'GHAPIKey', ''],
                    ['4.0.0', 'WAAAPIKey', ''],
                    ['4.0.0', 'CBCompanionVersion', 0],
                    ['4.2.0', 'ShowSources', False],
                    ['4.7.0', 'AutoUpdateDelay', True]]:
            if add[1] not in self.config.keys():
                self.config[add[1]] = add[2]
        for delete in [['1.3.0', 'URLCache'],
                       ['3.0.1', 'CurseCache'],
                       ['4.0.0', 'CFCacheCloudFlare'],
                       ['4.0.0', 'CFCacheTimestamp'],
                       ['4.0.0', 'IgnoreDependencies'],
                       ['4.0.0', 'WACompanionVersion']]:
            if delete[1] in self.config.keys():
                self.config.pop(delete[1], None)
        self.config['Version'] = __version__
        self.save_config()

    def check_if_installed(self, url):
        for addon in self.config['Addons']:
            if url in (addon['URL'], addon['Name']):
                return addon

    def check_if_installed_dirs(self, directories):
        for addon in self.config['Addons']:
            if Counter(directories) == Counter(addon['Directories']):
                return addon

    def check_if_dev(self, url):
        if addon := self.check_if_installed(url):
            return addon['Development'] if 'Development' in addon.keys() else 0
        else:
            return 0

    def check_if_overlap(self):
        directories = []
        found = set()
        for addon in self.config['Addons']:
            directories = directories + addon['Directories']
        if dupes := [x for x in directories if x in found or found.add(x)]:
            addons = []
            for addon in self.config['Addons']:
                if set(addon['Directories']).intersection(dupes):
                    addons.append(addon['Name'])
            addons.sort()
            return '\n'.join(addons)
        else:
            return False

    def check_if_blocked(self, addon):
        return bool(addon and 'Block' in addon.keys())

    def check_if_dev_global(self):
        for addon in self.config['Addons']:
            if addon['URL'].startswith('https://addons.wago.io/addons/') and 'Development' in addon.keys():
                return addon['Development']
        return 0

    def check_if_from_gh(self):
        if self.config['GHAPIKey'] != '':
            return False
        count = 0
        for addon in self.config['Addons']:
            if addon['URL'].startswith('https://github.com/'):
                count += 1
        return count > 4

    def cleanup(self, directories):
        if len(directories) > 0:
            for directory in directories:
                shutil.rmtree(self.path / directory, ignore_errors=True)

    def parse_url(self, url):
        if url.startswith('https://addons.wago.io/addons/'):
            return WagoAddonsAddon(url, self.wagoCache,
                                   'retail' if url in self.config['IgnoreClientVersion'].keys() else self.clientType,
                                   self.masterConfig['ClientTypes'][self.clientType]['CurrentVersion'],
                                   self.check_if_dev(url), self.config['WAAAPIKey'], self.http)
        elif url.startswith('https://www.wowinterface.com/downloads/'):
            return WoWInterfaceAddon(url, self.wowiCache, self.http)
        elif url.startswith('https://github.com/'):
            return GitHubAddon(url, self.githubCache, self.clientType, self.config['GHAPIKey'], self.http)
        elif url.lower() == 'elvui':
            self.bulk_tukui_check()
            return TukuiAddon('elvui', self.tukuiCache,
                              self.masterConfig['ClientTypes'][self.clientType]['CurrentVersion'], self.http)
        elif url.lower() == 'tukui':
            self.bulk_tukui_check()
            return TukuiAddon('tukui', self.tukuiCache,
                              self.masterConfig['ClientTypes'][self.clientType]['CurrentVersion'], self.http)
        elif url.lower() in self.masterConfig['CustomRepository'].keys():
            return GitHubAddonRaw(self.masterConfig['CustomRepository'][url.lower()], self.config['GHAPIKey'],
                                  self.http)
        elif url.startswith('https://www.townlong-yak.com/addons/'):
            raise RuntimeError(f'{url}\nTownlong Yak is no longer supported by this application.')
        elif url.startswith('https://www.curseforge.com/wow/addons/'):
            raise RuntimeError(f'{url}\nCurseForge is no longer supported by this application.')
        elif url.startswith('https://www.tukui.org/'):
            raise RuntimeError(f'{url}\nTukui.org is no longer supported by this application.')
        else:
            raise NotImplementedError('Provided URL is not supported.')

    def parse_url_source(self, url):
        if url.startswith('https://addons.wago.io/addons/'):
            return 'Wago', url
        elif url.startswith('https://www.wowinterface.com/downloads/'):
            return 'WoWI', url
        elif url.startswith('https://github.com/'):
            return 'GitHub', url
        elif url.lower().endswith(':dev'):
            return 'GitHub', f'https://github.com/{self.masterConfig["CustomRepository"][url.lower()]["Repository"]}'
        elif url.lower().startswith('elvui'):
            return 'Tukui', 'https://www.tukui.org/download.php?ui=elvui'
        elif url.lower().startswith('tukui'):
            return 'Tukui', 'https://www.tukui.org/download.php?ui=tukui'
        else:
            return '?', None

    def parse_new_addon(self, ignore, url):
        if ignore:
            self.config['IgnoreClientVersion'][url] = True
        new = self.parse_url(url)
        new.get_addon()
        if addon := self.check_if_installed_dirs(new.directories):
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
                                      'Checksums': checksums})
        self.save_config()
        return True, new.name, new.currentVersion

    def add_addon(self, url, ignore):
        if url.endswith(':'):
            raise NotImplementedError('Provided URL is not supported.')
        elif 'wago-app://' in url:
            url = self.parse_wagoapp_payload(url)
        elif url.startswith('wa:'):
            url = f'https://addons.wago.io/addons/{url[3:]}'
        elif url.startswith('wowi:'):
            url = f'https://www.wowinterface.com/downloads/info{url[5:]}.html'
        elif url.startswith('gh:'):
            url = f'https://github.com/{url[3:]}'
        if url.endswith('/'):
            url = url[:-1]
        if addon := self.check_if_installed(url):
            return False, addon['Name'], addon['Version']
        else:
            return self.parse_new_addon(ignore, url)

    def del_addon(self, url, keep):
        if old := self.check_if_installed(url):
            if not keep:
                self.cleanup(old['Directories'])
            self.config['IgnoreClientVersion'].pop(old['URL'], None)
            self.config['Addons'][:] = [d for d in self.config['Addons'] if d.get('URL') != url
                                        and d.get('Name') != url]
            self.save_config()
            return old['Name'], old['Version']
        return False, False

    def update_addon(self, url, update, force):
        if not (old := self.check_if_installed(url)):
            return url, [], False, False, None, False, False, '?', None, None, None
        dev = self.check_if_dev(old['URL'])
        blocked = self.check_if_blocked(old)
        oldversion = old['Version']
        modified = self.checksumCache[old['URL']] if old['URL'] in self.checksumCache else self.check_checksum(old)[1]
        if old['URL'].startswith(('https://www.townlong-yak.com/addons/',
                                  'https://www.curseforge.com/wow/addons/',
                                  'https://www.tukui.org/')):
            return old['Name'], [], oldversion, oldversion, None, modified, blocked, 'Unsupported', old['URL'], \
                       None, dev
        source, sourceurl = self.parse_url_source(old['URL'])
        new = self.parse_url(old['URL'])
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
        return new.name, new.author, new.currentVersion, oldversion, new.uiVersion, modified, blocked, source, \
            sourceurl, new.changelogUrl, dev

    def check_checksum(self, addon, pbar=None):
        checksums = {}
        for directory in addon['Directories']:
            if os.path.isdir(self.path / directory):
                checksums[directory] = dirhash(self.path / directory)
        if pbar:
            pbar.update(0, advance=0.5, refresh=True)
        return addon['URL'], len(checksums.items() & addon['Checksums'].items()) != len(addon['Checksums'])

    def bulk_check_checksum(self, addons, pbar):
        self.checksumCache = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            workers = []
            for addon in addons:
                workers.append(executor.submit(self.check_checksum, addon, pbar))
            for future in concurrent.futures.as_completed(workers):
                output = future.result()
                self.checksumCache[output[0]] = output[1]

    def dev_toggle(self, url):
        if url == 'global':
            state = self.check_if_dev_global()
            for addon in self.config['Addons']:
                if addon['URL'].startswith('https://addons.wago.io/addons/'):
                    if state == 0:
                        addon['Development'] = 1
                    elif state == 1:
                        addon['Development'] = 2
                    elif state == 2:
                        addon.pop('Development', None)
            self.save_config()
            return state
        else:
            if addon := self.check_if_installed(url):
                if addon['URL'].startswith('https://addons.wago.io/addons/'):
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
        if addon := self.check_if_installed(url):
            state = self.check_if_blocked(addon)
            if state:
                addon.pop('Block', None)
            else:
                addon['Block'] = True
            self.save_config()
            return not state
        return None

    def backup_check(self):
        if not self.config['Backup']['Enabled']:
            return False
        if os.path.isfile(Path('WTF-Backup', f'{datetime.datetime.now().strftime("%d%m%y")}.zip')):
            return False
        listofbackups = [Path(x) for x in glob.glob('WTF-Backup/*.zip')]
        if len(listofbackups) >= self.config['Backup']['Number']:
            oldest_file = min(listofbackups, key=os.path.getctime)
            os.remove(oldest_file)
        return True

    def backup_wtf(self, console):
        archive = Path('WTF-Backup', f'{datetime.datetime.now().strftime("%d%m%y")}.zip')
        if os.path.isfile(archive):
            suffix = 1
            while True:
                archive = Path('WTF-Backup', f'{datetime.datetime.now().strftime("%d%m%y")}-{suffix}.zip')
                if not os.path.isfile(archive):
                    break
                suffix += 1
        zipf = zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED)
        filecount = 0
        for _, _, files in os.walk('WTF/', topdown=True, followlinks=True):
            files = [f for f in files if f[0] != '.']
            filecount += len(files)
        if filecount > 0:
            with Progress('{task.completed}/{task.total}', '|', BarColumn(bar_width=None), '|', auto_refresh=False,
                          console=console) as progress:
                task = progress.add_task('', total=filecount)
                while not progress.finished:
                    for root, _, files in os.walk('WTF/', topdown=True, followlinks=True):
                        files = [f for f in files if f[0] != '.']
                        for f in files:
                            zipf.write(Path(root, f))
                            progress.update(task, advance=1, refresh=True)
        zipf.close()

    def find_orphans(self):
        orphanedaddon = []
        orphaneconfig = []
        directories = []
        directoriesspecial = []
        ignored = ['.DS_Store', '.git']
        special = ['+Wowhead_Looter', 'CurseBreakerCompanion', 'SharedMedia_MyMedia', 'TradeSkillMaster_AppHelper']
        for addon in self.config['Addons']:
            for directory in addon['Directories']:
                directories.append(directory)
        for directory in os.listdir(self.path):
            if os.path.isdir(self.path / directory) and directory not in directories:
                if os.path.isdir(self.path / directory / '.git'):
                    orphanedaddon.append(f'{directory} [GIT]')
                    directoriesspecial.append(directory)
                elif directory in special:
                    orphanedaddon.append(f'{directory} [Special]')
                    directoriesspecial.append(directory)
                elif directory not in ignored:
                    orphanedaddon.append(directory)
        directories += directoriesspecial + orphanedaddon
        for root, _, files in os.walk('WTF/', followlinks=True):
            for f in files:
                if 'Blizzard_' not in f and f.endswith('.lua'):
                    name = os.path.splitext(f)[0]
                    if name not in directories:
                        orphaneconfig.append(str(Path(root, f))[4:])
        return orphanedaddon, orphaneconfig

    def search(self, query):
        if self.config['WAAAPIKey'] == '':
            raise RuntimeError('This feature only searches the database of the Wago Addons. '
                               'So their API key is required.\n'
                               'It can be obtained here: https://addons.wago.io/patreon')
        payload = self.http.get(f'https://addons.wago.io/api/external/addons/_search?query={quote_plus(query.strip())}&'
                                f'game_version={self.clientType}', auth=APIAuth('Bearer', self.config['WAAAPIKey']))
        self.parse_wagoaddons_error(payload.status_code)
        payload = payload.json()
        return [result['website_url'] for result in payload['data']]

    def create_reg(self):
        with open('CurseBreaker.reg', 'w') as outfile:
            outfile.write('Windows Registry Editor Version 5.00\n\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\wago-app]\n'
                          '"URL Protocol"="\\"\\""\n'
                          '@="\\"URL:CurseBreaker Protocol\\""\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\wago-app\\DefaultIcon]\n'
                          '@="\\"CurseBreaker.exe,1\\""\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\wago-app\\shell]\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\wago-app\\shell\\open]\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\wago-app\\shell\\open\\command]\n'
                          '@="\\"' + os.path.abspath(sys.executable).replace('\\', '\\\\') + '\\" \\"%1\\""\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\weakauras-companion]\n'
                          '"URL Protocol"="\\"\\""\n'
                          '@="\\"URL:CurseBreaker Protocol\\""\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\weakauras-companion\\DefaultIcon]\n'
                          '@="\\"CurseBreaker.exe,1\\""\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\weakauras-companion\\shell]\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\weakauras-companion\\shell\\open]\n'
                          '[HKEY_CURRENT_USER\\Software\\Classes\\weakauras-companion\\shell\\open\\command]\n'
                          '@="\\"' + os.path.abspath(sys.executable).replace('\\', '\\\\') + '\\" \\"%1\\""')

    def parse_wagoapp_payload(self, url):
        if self.config['WAAAPIKey'] == '':
            raise RuntimeError('This feature requires the Wago Addons API key.\n'
                               'It can be obtained here: https://addons.wago.io/patreon')
        projectid = url.replace('wago-app://addons/', '')
        payload = self.http.get(f'https://addons.wago.io/api/external/addons/{projectid}?game_version='
                                f'{self.clientType}', auth=APIAuth('Bearer', self.config['WAAAPIKey']))
        self.parse_wagoaddons_error(payload.status_code)
        payload = payload.json()
        return f'https://addons.wago.io/addons/{payload["slug"]}'

    def bulk_check(self, addons):
        ids_wowi = []
        ids_wago = []
        ids_gh = []
        for addon in addons:
            if addon['URL'].startswith('https://www.wowinterface.com/downloads/'):
                ids_wowi.append(re.findall(r'\d+', addon['URL'])[0].strip())
            elif addon['URL'].startswith('https://addons.wago.io/addons/') and \
                    addon['URL'] not in self.config['IgnoreClientVersion'].keys():
                ids_wago.append({'slug': addon['URL'].replace('https://addons.wago.io/addons/', ''), 'id': ''})
            elif addon['URL'].startswith('https://github.com/'):
                ids_gh.append(addon['URL'].replace('https://github.com/', ''))
        if ids_wowi:
            self.bulk_wowi_check(ids_wowi)
        if ids_wago and self.config['WAAAPIKey'] != '':
            self.bulk_wago_check(ids_wago)
        if ids_gh and self.config['GHAPIKey'] != '':
            self.bulk_gh_check(ids_gh)

    def bulk_wowi_check(self, ids):
        payload = self.http.get(f'https://api.mmoui.com/v3/game/WOW/filedetails/{",".join(ids)}.json',
                                timeout=15).json()
        if 'ERROR' not in payload:
            for addon in payload:
                self.wowiCache[str(addon['UID'])] = addon

    def bulk_wago_check(self, ids):
        if not self.wagoIdCache:
            self.wagoIdCache = self.http.get(f'https://addons.wago.io/api/data/slugs?game_version={self.clientType}',
                                             timeout=15)
            self.parse_wagoaddons_error(self.wagoIdCache.status_code)
            self.wagoIdCache = self.wagoIdCache.json()
        for addon in ids:
            if addon['slug'] in self.wagoIdCache['addons']:
                addon['id'] = self.wagoIdCache['addons'][addon['slug']]['id']
        payload = self.http.post(f'https://addons.wago.io/api/external/addons/_recents?game_version={self.clientType}',
                                 json={'addons': [addon["id"] for addon in ids if addon["id"] != ""]},
                                 auth=APIAuth('Bearer', self.config['WAAAPIKey']), timeout=15)
        self.parse_wagoaddons_error(payload.status_code)
        payload = payload.json()
        for addonid in payload['addons']:
            for addon in ids:
                if addon['id'] == addonid:
                    self.wagoCache[addon['slug']] = payload['addons'][addonid]
                    break

    def bulk_gh_check(self, ids):
        query = ('{\n  "query": "{ search( type: REPOSITORY query: \\"' + f'repo:{" repo:".join(ids)}' + ' fork:true\\"'
                 ' first: 100 ) { nodes { ... on Repository { nameWithOwner releases(first: 15) { nodes { tag_name: tag'
                 'Name name html_url: url draft: isDraft prerelease: isPrerelease assets: releaseAssets(first: 100) { n'
                 'odes { node_id: id name content_type: contentType url } } } } } } }}"\n}')
        payload = self.http.post('https://api.github.com/graphql', json=json.loads(query),
                                 auth=APIAuth('bearer', self.config['GHAPIKey']), timeout=15)
        if payload.status_code != 200:
            return
        payload = payload.json()
        for addon in payload['data']['search']['nodes']:
            self.githubCache[addon['nameWithOwner']] = addon['releases']['nodes']
        for addon in self.githubCache:
            for i in range(len(self.githubCache[addon])):
                self.githubCache[addon][i]['assets'] = self.githubCache[addon][i]['assets']['nodes']

    @retry(custom_error='Failed to parse Tukui API data')
    def bulk_tukui_check(self):
        if not self.tukuiCache:
            self.tukuiCache = self.http.get('https://api.tukui.org/v1/addons').json()

    def detect_accounts(self):
        if not os.path.isdir(Path('WTF/Account')):
            return []
        accounts = os.listdir(Path('WTF/Account'))
        accounts_processed = []
        for account in accounts:
            if os.path.isfile(Path(f'WTF/Account/{account}/SavedVariables/WeakAuras.lua')) or \
                        os.path.isfile(Path(f'WTF/Account/{account}/SavedVariables/Plater.lua')):
                accounts_processed.append(account)
        return accounts_processed

    # TODO: Refactor to be smarter
    def detect_addons(self):
        if self.config['WAAAPIKey'] == '':
            raise RuntimeError('This feature only matches addons that are in the database of the Wago Addons. Other sou'
                               'rces don\'t provide means to make a reasonable match. So Wago Addons API key is require'
                               'd. This application still can be used without it. Already installed addons can be added'
                               ' to CurseBreaker with the install command.\n'
                               'API key can be obtained here: https://addons.wago.io/patreon')
        names = []
        namesinstalled = []
        slugs = []
        output = []
        ignored = ['ElvUI_OptionsUI', 'ElvUI_Options', 'ElvUI_Libraries', 'Tukui_Config', '+Wowhead_Looter',
                   'WeakAurasCompanion', 'CurseBreakerCompanion', 'SharedMedia_MyMedia', 'TradeSkillMaster_AppHelper',
                   'WagoAnalytics', 'WagoAppCompanion', 'Details_Streamer', 'Details_Vanguard', '.DS_Store', '.git']
        specialcases = ['ElvUI', 'Tukui']

        addon_dirs = os.listdir(self.path)
        for directory in addon_dirs:
            if os.path.isdir(self.path / directory) and not os.path.islink(self.path / directory) and \
                    not os.path.isdir(self.path / directory / '.git') and not directory.startswith('Blizzard_') and \
                    directory not in ignored + specialcases:
                directoryhash = WagoAddonsHasher(self.path / directory)
                output.append({'name': directory, 'hash': directoryhash.get_hash()})

        payload = self.http.post(f'https://addons.wago.io/api/external/addons/_match?game_version={self.clientType}',
                                 json={'addons': output}, auth=APIAuth('Bearer', self.config['WAAAPIKey']))
        self.parse_wagoaddons_error(payload.status_code)
        payload = payload.json()
        for addon in payload['addons']:
            if self.check_if_installed(addon['website_url']):
                namesinstalled.append(addon['name'])
            else:
                names.append(addon['name'])
                slugs.append(f'wa:{addon["website_url"].split("/")[-1]}')
        for special in specialcases:
            if os.path.isdir(self.path / special):
                if self.check_if_installed(special):
                    namesinstalled.append(special)
                else:
                    names.append(special)
                    slugs.append(special)
        names.sort()
        namesinstalled.sort()
        slugs.sort()

        return names, slugs, namesinstalled

    def export_addons(self):
        addons = []
        for addon in self.config['Addons']:
            if addon['URL'].startswith('https://addons.wago.io/addons/'):
                url = f'wa:{addon["URL"].replace("https://addons.wago.io/addons/", "")}'
            elif addon['URL'].startswith('https://www.wowinterface.com/downloads/info'):
                url = f'wowi:{addon["URL"].split("/info")[-1].replace(".html", "")}'
            elif addon['URL'].startswith('https://github.com/'):
                url = f'gh:{addon["URL"].replace("https://github.com/", "")}'
            else:
                url = addon['URL'].lower()
            addons.append(url)
        return f'install {",".join(sorted(addons))}'

    def parse_wagoaddons_error(self, code):
        if code == 401:
            raise RuntimeError('Wago Addons API key is missing or incorrect.')
        elif code == 403:
            raise RuntimeError('Provided Wago Addons API key is expired. Please acquire a new one.')
        elif code == 423:
            raise RuntimeError('Provided Wago Addons API key is blocked. Please acquire a new one.')
        elif code in [429, 500, 502, 504]:
            raise RuntimeError('Temporary Wago Addons API issue. Please try later.')


class WagoAddonsHasher:
    def __init__(self, directory):
        self.directory = directory
        self.filesToHash = []
        self.filesToParse = []
        self.hashes = []
        self.parse()

    def parse_file(self, target):
        for f in target:
            if f.is_file():
                self.filesToHash.append(f)
                if not f.name.lower().endswith('.lua'):
                    with open(f, encoding='utf-8', errors='ignore') as g:
                        newfilestoparse = None
                        data = g.read()
                        if f.name.lower().endswith('.toc'):
                            data = re.sub(r'\s*#.*$', '', data, flags=re.I | re.M)
                            newfilestoparse = re.findall(r'^\s*((?:(?<!\.\.).)+\.(?:xml|lua))\s*$', data,
                                                         flags=re.I | re.M)
                        elif f.name.lower().endswith('.xml'):
                            data = re.sub(r'<!--.*?-->', '', data, flags=re.I | re.S)
                            newfilestoparse = re.findall(r"<(?:Include|Script)\s+file=[\"']((?:(?<!\.\.).)+)[\"']\s*/>",
                                                         data, flags=re.I)
                        if newfilestoparse and len(newfilestoparse) > 0:
                            newfilestoparse = [Path(f.parent, element) for element in newfilestoparse]
                            self.parse_file(newfilestoparse)

    def parse(self):
        for f in list(self.directory.glob('*')):
            if f.name.lower().endswith('.toc'):
                self.filesToParse.append(f)
            elif f.name.lower() == 'bindings.xml':
                self.filesToHash.append(f)
        self.parse_file(self.filesToParse)
        self.filesToHash = list(dict.fromkeys(self.filesToHash))
        for f in self.filesToHash:
            with open(f, 'rb') as g:
                self.hashes.append(hashlib.md5(g.read()).hexdigest())
        self.hashes.sort()

    def get_hash(self):
        return hashlib.md5(''.join(self.hashes).encode('utf-8')).hexdigest()
