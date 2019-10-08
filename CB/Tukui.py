import os
import io
import re
import zipfile
import requests
from . import retry, HEADERS


class TukuiAddon:
    @retry()
    def __init__(self, url, isclassic):
        project = re.findall(r'\d+', url)[0]
        self.payload = requests.get(f'https://www.tukui.org/api.php?{"classic-" if isclassic else ""}addon={project}',
                                    headers=HEADERS).json()
        if not self.payload['id'] == project:
            raise RuntimeError
        self.name = self.payload['name'].strip().strip('\u200b')
        self.downloadUrl = self.payload['url']
        self.currentVersion = self.payload['version']
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
