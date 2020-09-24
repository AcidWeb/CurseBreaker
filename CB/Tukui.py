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
                                    headers=HEADERS)
        if self.payload.text == '':
            raise RuntimeError(url)
        else:
            self.payload = self.payload.json()
        self.name = self.payload['name'].strip().strip('\u200b')
        self.downloadUrl = self.payload['url']
        self.changelogUrl = self.payload['changelog']
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
        self.archive.extractall(path)
