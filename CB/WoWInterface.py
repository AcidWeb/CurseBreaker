import os
import io
import re
import zipfile
from . import retry


class WoWInterfaceAddon:
    @retry()
    def __init__(self, url, checkcache, scraper):
        project = re.findall(r'\d+', url)[0]
        self.scraper = scraper
        if project in checkcache:
            self.payload = checkcache[project]
        else:
            self.payload = self.scraper.get(f'https://api.mmoui.com/v4/game/WOW/filedetails/{project}.json').json()
            if 'ERROR' in self.payload:
                raise RuntimeError(url)
            else:
                self.payload = self.payload[0]
        self.name = self.payload['title'].strip().strip('\u200b')
        self.downloadUrl = self.payload['downloadUri']
        self.currentVersion = self.payload['version']
        self.archive = None
        self.directories = []

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(self.scraper.get(self.downloadUrl).content))
        for file in self.archive.namelist():
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(filter(None, set(self.directories)))
        if len(self.directories) == 0:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.get_addon()
        self.archive.extractall(path)
