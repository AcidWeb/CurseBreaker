import os
import json
import shutil
from .CurseForge import CurseForgeAddon
from .ElvUI import ElvUIAddon


class Core:
    def __init__(self):
        self.path = 'Interface\\AddOns'
        if os.path.isfile('CurseBreaker.json'):
            with open('CurseBreaker.json', 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {'Addons': [], 'URLCache': {}}
            self.save()

    def save(self):
        with open('CurseBreaker.json', 'w') as outfile:
            json.dump(self.config, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def check_if_installed(self, url):
        for addon in self.config['Addons']:
            if addon['URL'] == url:
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
            self.save()
            return new.name, new.currentVersion
        return addon['Name'], False

    def del_addon(self, url):
        old = self.check_if_installed(url)
        if old:
            self.cleanup(old['Directories'])
            self.config['Addons'][:] = [d for d in self.config['Addons'] if d.get('URL') != url]
            self.save()
            return old['Name'], old['InstalledVersion']
        return False, False

    def update_addon(self, url):
        old = self.check_if_installed(url)
        if old:
            new = self.parse_url(url)
            new.get_current_version()
            oldversion = old['InstalledVersion']
            if new.currentVersion != old['InstalledVersion']:
                self.cleanup(old['Directories'])
                new.install(self.path)
                old['CurrentVersion'] = new.currentVersion
                old['InstalledVersion'] = new.currentVersion
                old['Directories'] = new.directories
            self.save()
            return new.name, old['InstalledVersion'], oldversion
        return url, False, False
