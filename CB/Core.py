import os
import sys
import json
import shutil
import zipfile
import datetime
from tqdm import tqdm
from checksumdir import dirhash
from . import __version__
from .ElvUI import ElvUIAddon
from .CurseForge import CurseForgeAddon
from .WoWInterface import WoWInterfaceAddon


class Core:
    def __init__(self):
        self.path = 'Interface\\AddOns'
        self.config = None

    def init_config(self):
        if os.path.isfile('CurseBreaker.json'):
            with open('CurseBreaker.json', 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {'Addons': [],
                           'URLCache': {},
                           'Backup': {'Enabled': True, 'Number': 7},
                           'Version': __version__}
            self.save_config()
        if not os.path.isdir('WTF-Backup'):
            os.mkdir('WTF-Backup')
        self.update_config()

    def save_config(self):
        with open('CurseBreaker.json', 'w') as outfile:
            json.dump(self.config, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def update_config(self):
        if 'Version' not in self.config.keys():
            # 1.1.0
            for addon in self.config['Addons']:
                if 'Checksums' not in addon.keys():
                    checksums = {}
                    for directory in addon['Directories']:
                        checksums[directory] = dirhash(os.path.join(self.path, directory))
                    addon['Checksums'] = checksums
            self.config['Version'] = __version__
            self.save_config()

    def check_if_installed(self, url):
        for addon in self.config['Addons']:
            if addon['URL'] == url or addon['Name'] == url:
                return addon

    def cleanup(self, directories):
        if len(directories) > 0:
            for directory in directories:
                shutil.rmtree(os.path.join(self.path, directory), ignore_errors=True)

    def parse_url(self, url):
        if url.startswith('https://www.curseforge.com/wow/addons/'):
            if url in self.config['URLCache']:
                url = self.config['URLCache'][url]
            parser = CurseForgeAddon(url)
            if hasattr(parser, 'redirectUrl'):
                self.config['URLCache'][url] = parser.redirectUrl
            return parser
        if url.startswith('https://www.wowinterface.com/downloads/'):
            return WoWInterfaceAddon(url)
        elif url.lower() == 'elvui':
            return ElvUIAddon('master')
        elif url.lower() == 'elvui:dev':
            return ElvUIAddon('development')
        else:
            raise NotImplementedError('Provided URL is not supported.')

    def add_addon(self, url):
        if 'curse://' in url:
            url = url.split('/download-client')[0].replace('curse://', 'https://').strip()
        addon = self.check_if_installed(url)
        if not addon:
            new = self.parse_url(url)
            new.get_current_version()
            new.install(self.path)
            checksums = {}
            for directory in new.directories:
                checksums[directory] = dirhash(os.path.join(self.path, directory))
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

    def update_addon(self, url, update):
        old = self.check_if_installed(url)
        if old:
            new = self.parse_url(old['URL'])
            new.get_current_version()
            oldversion = old['Version']
            modified = self.check_checksum(url)
            if new.currentVersion != old['Version'] and not modified and update:
                self.cleanup(old['Directories'])
                new.install(self.path)
                checksums = {}
                for directory in new.directories:
                    checksums[directory] = dirhash(os.path.join(self.path, directory))
                old['Version'] = new.currentVersion
                old['Directories'] = new.directories
                old['Checksums'] = checksums
                self.save_config()
            return new.name, new.currentVersion, oldversion, modified
        return url, False, False, False

    def check_checksum(self, url):
        old = self.check_if_installed(url)
        if old:
            checksums = {}
            for directory in old['Directories']:
                checksums[directory] = dirhash(os.path.join(self.path, directory))
            return len(checksums.items() & old['Checksums'].items()) != len(old['Checksums'])
        return False

    def backup_toggle(self):
        self.config['Backup']['Enabled'] = not self.config['Backup']['Enabled']
        self.save_config()
        return self.config['Backup']['Enabled']

    def backup_check(self):
        if self.config['Backup']['Enabled']:
            if not os.path.isfile(f'WTF-Backup\\{datetime.datetime.now().strftime("%d%m%y")}.zip'):
                listofbackups = os.listdir('WTF-Backup')
                fullpath = [f'WTF-Backup\\{x}' for x in listofbackups]
                if len([name for name in listofbackups]) == self.config['Backup']['Number']:
                    oldest_file = min(fullpath, key=os.path.getctime)
                    os.remove(oldest_file)
                return True
            else:
                return False
        else:
            return False

    def backup_wtf(self):
        zipf = zipfile.ZipFile(f'WTF-Backup\\{datetime.datetime.now().strftime("%d%m%y")}.zip', 'w',
                               zipfile.ZIP_DEFLATED)
        filecount = sum([len(files) for r, d, files in os.walk('WTF/')])
        with tqdm(total=filecount, bar_format='{n_fmt}/{total_fmt} |{bar}|') as pbar:
            for root, dirs, files in os.walk('WTF/'):
                for f in files:
                    zipf.write(os.path.join(root, f))
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
                if os.path.isdir(os.path.join(self.path, directory, '.git')):
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
                        orphaneconfig.append(os.path.join(root, f)[4:])
        return orphanedaddon, orphaneconfig

    def create_reg(self):
        with open('CurseBreaker.reg', 'w') as outfile:
            outfile.write('Windows Registry Editor Version 5.00\n[HKEY_CURRENT_USER\Software\Classes\curse]\n"URL Proto'
                          'col"="\\"\\""\n@="\\"URL:CurseBreaker Protocol\\""\n[HKEY_CURRENT_USER\Software\Classes\curs'
                          'e\DefaultIcon]\n@="\\"CurseBreaker.exe,1\\""\n[HKEY_CURRENT_USER\Software\Classes\curse\shel'
                          'l]\n[HKEY_CURRENT_USER\Software\Classes\curse\shell\open]\n[HKEY_CURRENT_USER\Software\Class'
                          'es\curse\shell\open\command]\n@="\\"' + os.path.abspath(sys.executable).replace('\\', '\\\\')
                          + '\\" \\"%1\\""')

