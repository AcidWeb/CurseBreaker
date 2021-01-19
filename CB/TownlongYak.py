import os
import io
import re
import zipfile
import requests
from . import retry, HEADERS


class TownlongYakAddon:
    @retry()
    def __init__(self, url, clienttype):
        self.project = url.split('/')[-1]
        self.payload = requests.get(f'https://www.townlong-yak.com/addons/api/install-bundle/{self.project}',
                                    headers=HEADERS, timeout=5).json()
        self.name = self.payload['name'].strip().strip('\u200b')
        self.author = [self.payload['author']]
        self.clientType = clienttype
        self.uiVersion = None
        self.archive = None
        self.dependencies = None
        self.downloadUrl = None
        self.changelogUrl = None
        self.currentVersion = None
        self.directories = []
        self.get_current_version()

    def get_current_version(self):
        for release in self.payload['releases']:
            if release['ch'] == self.clientType:
                self.downloadUrl = release['dl']
                self.currentVersion = re.findall(r'.*-(.*)\.zip$', release['dl'])[0]
                self.changelogUrl = f'https://www.townlong-yak.com/addons/{self.project}/release/{self.currentVersion}'
                self.uiVersion = release['cv'][0]
                break
        else:
            raise RuntimeError(f'{self.name}.\nFailed to find release for your client version.')

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS, timeout=5).content))
        for file in self.archive.namelist():
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(filter(None, set(self.directories)))
        if len(self.directories) == 0:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.archive.extractall(path)
