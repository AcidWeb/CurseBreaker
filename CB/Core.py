import os
import sys
import json
import html
import shutil
import zipfile
import datetime
import requests
from tqdm import tqdm
from pathlib import Path
from checksumdir import dirhash
from xml.dom.minidom import parse
from . import retry, __version__
from .GitLab import GitLabAddon
from .CurseForge import CurseForgeAddon
from .WoWInterface import WoWInterfaceAddon


class Core:
    def __init__(self):
        self.path = Path('Interface/AddOns')
        self.clientType = 'wow_retail'
        self.waCompanionVersion = 20190123023201
        self.config = None
        self.cfCache = {}

    def init_config(self):
        if os.path.isfile('CurseBreaker.json'):
            with open('CurseBreaker.json', 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {'Addons': [],
                           'CurseCache': {},
                           'Backup': {'Enabled': True, 'Number': 7},
                           'Version': __version__,
                           'WAUsername': '',
                           'WAAccountName': '',
                           'WAAPIKey': '',
                           'WACompanionVersion': 0}
            self.save_config()
        if not os.path.isdir('WTF-Backup') and self.config['Backup']['Enabled']:
            os.mkdir('WTF-Backup')
        self.update_config()

    def save_config(self):
        with open('CurseBreaker.json', 'w') as outfile:
            json.dump(self.config, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def update_config(self):
        if 'Version' not in self.config.keys() or self.config['Version'] != __version__:
            urlupdate = {'elvui-classic': 'elvui', 'elvui-classic:dev': 'elvui:dev', 'tukui-classic': 'tukui'}
            for addon in self.config['Addons']:
                # 1.1.0
                if 'Checksums' not in addon.keys():
                    checksums = {}
                    for directory in addon['Directories']:
                        checksums[directory] = dirhash(self.path / directory)
                    addon['Checksums'] = checksums
                # 1.1.1
                if addon['Version'] is None:
                    addon['Version'] = "1"
                # 2.2.0
                if addon['URL'].lower() in urlupdate:
                    addon['URL'] = urlupdate[addon['URL'].lower()]
            # 1.3.0
            if 'URLCache' in self.config.keys():
                self.config.pop('URLCache', None)
            if 'CurseCache' not in self.config.keys():
                self.config['CurseCache'] = {}
            # 2.1.0
            if 'WAUsername' not in self.config.keys():
                self.config['WAUsername'] = ''
            # 2.2.0
            if 'WAAccountName' not in self.config.keys():
                self.config['WAAccountName'] = ''
            if 'WAAPIKey' not in self.config.keys():
                self.config['WAAPIKey'] = ''
            if 'WACompanionVersion' not in self.config.keys():
                self.config['WACompanionVersion'] = 0
            self.config['Version'] = __version__
            self.save_config()

    def check_if_installed(self, url):
        for addon in self.config['Addons']:
            if addon['URL'] == url or addon['Name'] == url:
                return addon

    def check_if_dev(self, url):
        addon = self.check_if_installed(url)
        if addon:
            if 'Development' in addon.keys():
                return True
            else:
                return False
        else:
            return False

    def cleanup(self, directories):
        if len(directories) > 0:
            for directory in directories:
                shutil.rmtree(self.path / directory, ignore_errors=True)

    def parse_url(self, url):
        if url.startswith('https://www.curseforge.com/wow/addons/'):
            parser = CurseForgeAddon(url, self.config['CurseCache'], self.cfCache,
                                     self.clientType, self.check_if_dev(url))
            if hasattr(parser, 'cacheID'):
                self.config['CurseCache'][url] = parser.cacheID
                self.save_config()
            return parser
        if url.startswith('https://www.wowinterface.com/downloads/'):
            return WoWInterfaceAddon(url)
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
        elif url.lower() == 'tukui':
            if self.clientType == 'wow_retail':
                return GitLabAddon('TukUI', '77', 'Tukz/Tukui', 'master')
            else:
                return GitLabAddon('TukUI', '77', 'Tukz/Tukui', 'Classic')
        else:
            raise NotImplementedError('Provided URL is not supported.')

    def add_addon(self, url):
        if 'twitch://' in url:
            url = url.split('/download-client')[0].replace('twitch://', 'https://').strip()
        addon = self.check_if_installed(url)
        if not addon:
            new = self.parse_url(url)
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

    def del_addon(self, url):
        old = self.check_if_installed(url)
        if old:
            self.cleanup(old['Directories'])
            self.config['Addons'][:] = [d for d in self.config['Addons'] if d.get('URL') != url
                                        and d.get('Name') != url]
            self.save_config()
            return old['Name'], old['Version']
        return False, False

    def update_addon(self, url, update, force):
        old = self.check_if_installed(url)
        if old:
            new = self.parse_url(old['URL'])
            oldversion = old['Version']
            modified = self.check_checksum(url)
            if force or (new.currentVersion != old['Version'] and update and not modified):
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
            return new.name, new.currentVersion, oldversion, modified if not force else False
        return url, False, False, False

    def check_checksum(self, url):
        old = self.check_if_installed(url)
        if old:
            checksums = {}
            for directory in old['Directories']:
                if os.path.isdir(self.path / directory):
                    checksums[directory] = dirhash(self.path / directory)
            return len(checksums.items() & old['Checksums'].items()) != len(old['Checksums'])
        return False

    def dev_toggle(self, url):
        addon = self.check_if_installed(url)
        if addon:
            state = self.check_if_dev(url)
            if state:
                addon.pop('Development', None)
            else:
                addon['Development'] = True
            self.save_config()
            return not state
        return None

    def backup_toggle(self):
        self.config['Backup']['Enabled'] = not self.config['Backup']['Enabled']
        self.save_config()
        return self.config['Backup']['Enabled']

    def backup_check(self):
        if self.config['Backup']['Enabled']:
            if not os.path.isfile(Path('WTF-Backup', f'{datetime.datetime.now().strftime("%d%m%y")}.zip')):
                listofbackups = os.listdir('WTF-Backup')
                fullpath = [Path('WTF-Backup', x) for x in listofbackups]
                if len([name for name in listofbackups]) == self.config['Backup']['Number']:
                    oldest_file = min(fullpath, key=os.path.getctime)
                    os.remove(oldest_file)
                return True
            else:
                return False
        else:
            return False

    def backup_wtf(self):
        zipf = zipfile.ZipFile(Path('WTF-Backup', f'{datetime.datetime.now().strftime("%d%m%y")}.zip'), 'w',
                               zipfile.ZIP_DEFLATED)
        filecount = 0
        for root, dirs, files in os.walk('WTF/', topdown=True):
            files = [f for f in files if not f[0] == '.']
            dirs[:] = [d for d in dirs if not d[0] == '.']
            filecount += len(files)
        with tqdm(total=filecount, bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
            for root, dirs, files in os.walk('WTF/', topdown=True):
                files = [f for f in files if not f[0] == '.']
                dirs[:] = [d for d in dirs if not d[0] == '.']
                for f in files:
                    zipf.write(Path(root, f))
                    pbar.update(1)
        zipf.close()

    def find_orphans(self):
        orphanedaddon = []
        orphaneconfig = []
        directories = []
        directoriesgit = []
        for addon in self.config['Addons']:
            for directory in addon['Directories']:
                directories.append(directory)
        for directory in os.listdir(self.path):
            if directory not in directories:
                if os.path.isdir(self.path / directory / '.git'):
                    orphanedaddon.append(f'{directory} [GIT]')
                    directoriesgit.append(directory)
                else:
                    orphanedaddon.append(directory)
        directories += directoriesgit + orphanedaddon
        for root, dirs, files in os.walk('WTF/'):
            for f in files:
                if 'Blizzard_' not in f and f.endswith('.lua'):
                    name = f.split('.')[0]
                    if name not in directories:
                        orphaneconfig.append(str(Path(root, f))[4:])
        return orphanedaddon, orphaneconfig

    @retry(custom_error='Failed to execute the search.')
    def search(self, query):
        results = []
        payload = requests.get(f'https://addons-ecs.forgesvc.net/api/v2/addon/search?gameId=1&pageSize=10&searchFilter='
                               f'{html.escape(query.strip())}').json()
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

    @retry(custom_error='Failed to parse the XML file.')
    def parse_cf_xml(self, path):
        xml = parse(path)
        project = xml.childNodes[0].getElementsByTagName('project')[0].getAttribute('id')
        payload = requests.get(f'https://addons-ecs.forgesvc.net/api/v2/addon/{project}').json()
        url = payload['websiteUrl'].strip()
        self.config['CurseCache'][url] = project
        self.save_config()
        return url

    @retry(custom_error='Failed to execute bulk version check.')
    def bulk_cf_check(self, addons):
        ids = []
        for addon in addons:
            if addon['URL'] in self.config['CurseCache']:
                ids.append(int(self.config['CurseCache'][addon['URL']]))
        if len(ids) > 0:
            payload = requests.post('https://addons-ecs.forgesvc.net/api/v2/addon', json=ids).json()
            for addon in payload:
                self.cfCache[str(addon['id'])] = addon
