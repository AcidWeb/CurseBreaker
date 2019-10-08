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
            self.payload = requests.get(f'https://api.mmoui.com/v3/game/WOW/filedetails/{project}.json',
                                        headers=HEADERS).json()[0]
        if not self.payload['UID'] == project:
            raise RuntimeError
        self.name = self.payload['UIName'].strip().strip('\u200b')
        self.downloadUrl = self.payload['UIDownload']
        self.currentVersion = self.payload['UIVersion']
        self.archive = None
        self.directories = []

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS).content))
        for file in self.archive.namelist():
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(filter(None, set(self.directories)))
        if len(self.directories) == 0:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.get_addon()
        self.archive.extractall(path)
