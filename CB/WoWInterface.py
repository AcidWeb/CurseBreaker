import os
import io
import re
import zipfile
import requests
from . import retry, HEADERS


class WoWInterfaceAddon:
    @retry()
    def __init__(self, url, checkcache):
        project = re.findall(r'\d+', url)[0]
        if project in checkcache:
            self.payload = checkcache[project]
        else:
            try:
                self.payload = requests.get(f'https://api.mmoui.com/v3/game/WOW/filedetails/{project}.json',
                                            headers=HEADERS, timeout=5).json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                raise RuntimeError(f'{url}\nWoWInterface API failed to respond.')
            if 'ERROR' in self.payload:
                raise RuntimeError(f'{url}\nThis might be a temporary error or this project is not supported '
                                   f'by WoWInterface API.')
            else:
                self.payload = self.payload[0]
        self.name = self.payload['UIName'].strip().strip('\u200b')
        self.downloadUrl = self.payload['UIDownload']
        self.changelogUrl = f'{url}#changelog'
        self.currentVersion = self.payload['UIVersion']
        self.uiVersion = None
        self.archive = None
        self.dependencies = None
        self.directories = []
        self.author = [self.payload['UIAuthorName']]

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
