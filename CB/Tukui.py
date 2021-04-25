import os
import io
import re
import zipfile
import requests
from . import retry, HEADERS


class TukuiAddon:
    @retry()
    def __init__(self, url, checkcache, special=None):
        if special:
            try:
                self.payload = requests.get(f'https://www.tukui.org/api.php?ui={special}',
                                            headers=HEADERS, timeout=5).json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                raise RuntimeError(f'{url}\nTukui API failed to respond.')
        else:
            project = re.findall(r'\d+', url)[0]
            for addon in checkcache:
                if addon['id'] == project:
                    self.payload = addon
                    break
            else:
                raise RuntimeError(f'{url}\nProject not found.')
        self.name = self.payload['name'].strip().strip('\u200b')
        self.downloadUrl = self.payload['url']
        self.currentVersion = self.payload['version']
        self.uiVersion = self.payload['patch']
        self.archive = None
        self.dependencies = None
        self.directories = []
        self.author = [self.payload['author']]

        if 'changelog' in self.payload:
            self.changelogUrl = self.payload['changelog']
        else:
            self.changelogUrl = None

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
