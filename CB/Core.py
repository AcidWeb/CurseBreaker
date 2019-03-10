import os
import json
import shutil
import zipfile
import datetime
from tqdm import tqdm
from .CurseForge import CurseForgeAddon
from .ElvUI import ElvUIAddon
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
            self.config = {'Addons': [], 'URLCache': {}, 'Backup': {'Enabled': True, 'Number': 7}}
            self.save_config()
        if not os.path.isdir('WTF-Backup'):
            os.mkdir('WTF-Backup')

    def save_config(self):
        with open('CurseBreaker.json', 'w') as outfile:
            json.dump(self.config, outfile, sort_keys=True, indent=4, separators=(',', ': '))

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
        addon = self.check_if_installed(url)
        if not addon:
            new = self.parse_url(url)
            new.get_current_version()
            new.install(self.path)
            self.config['Addons'].append({'Name': new.name,
                                          'URL': url,
                                          'CurrentVersion': new.currentVersion,
                                          'InstalledVersion': new.currentVersion,
                                          'Directories': new.directories
                                          })
            self.save_config()
            return new.name, new.currentVersion
        return addon['Name'], False

    def del_addon(self, url):
        old = self.check_if_installed(url)
        if old:
            self.cleanup(old['Directories'])
            self.config['Addons'][:] = [d for d in self.config['Addons'] if d.get('URL') != url
                                        and d.get('Name') != url]
            self.save_config()
            return old['Name'], old['InstalledVersion']
        return False, False

    def update_addon(self, url):
        old = self.check_if_installed(url)
        if old:
            new = self.parse_url(old['URL'])
            new.get_current_version()
            oldversion = old['InstalledVersion']
            if new.currentVersion != old['InstalledVersion']:
                self.cleanup(old['Directories'])
                new.install(self.path)
                old['CurrentVersion'] = new.currentVersion
                old['InstalledVersion'] = new.currentVersion
                old['Directories'] = new.directories
            self.save_config()
            return new.name, old['InstalledVersion'], oldversion
        return url, False, False

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

    def backup_wtf(self, barwidth):
        zipf = zipfile.ZipFile(f'WTF-Backup\\{datetime.datetime.now().strftime("%d%m%y")}.zip', 'w',
                               zipfile.ZIP_DEFLATED)
        filecount = sum([len(files) for r, d, files in os.walk('WTF/')])
        with tqdm(total=filecount, bar_format='{n_fmt}/{total_fmt} |{bar}|', ncols=barwidth) as pbar:
            for root, dirs, files in os.walk('WTF/'):
                for f in files:
                    zipf.write(os.path.join(root, f))
                    pbar.update(1)
        zipf.close()

    def find_orphans(self):
        orphans = []
        directories = []
        for addon in self.config['Addons']:
            for directory in addon['Directories']:
                directories.append(directory)
        for directory in os.listdir(self.path):
            if directory not in directories:
                orphans.append(directory)
        return orphans
