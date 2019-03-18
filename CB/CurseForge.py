import os
import io
import re
import zipfile
import requests
from bs4 import BeautifulSoup
from . import retry


class CurseForgeAddon:
    @retry()
    def __init__(self, url, cache):
        if url in cache:
            project = cache[url]
        else:
            soup = BeautifulSoup(requests.get(url).content, 'html.parser')
            project = re.findall(r'\d+', soup.find('a', attrs={'class': 'button button--icon button--twitch '
                                                                        'download-button'})["data-nurture-data"])[0]
            self.cacheID = project
        self.payload = requests.get(f'https://addons-ecs.forgesvc.net/api/addon/{project}').json()
        self.name = self.payload['name']
        self.downloadUrl = None
        self.currentVersion = None
        self.archive = None
        self.directories = []
        self.get_current_version()

    def get_current_version(self):
        for f in self.payload['latestFiles']:
            if f['releaseType'] == 1:
                self.downloadUrl = f['downloadUrl']
                self.currentVersion = f['fileName']
                break
        if not self.downloadUrl and not self.currentVersion:
            for f in self.payload['latestFiles']:
                if f['releaseType'] == 2:
                    self.downloadUrl = f['downloadUrl']
                    self.currentVersion = f['fileName']
                    break
        if not self.downloadUrl or not self.currentVersion:
            raise RuntimeError

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl).content))
        for file in self.archive.namelist():
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(set(self.directories))

    def install(self, path):
        self.get_addon()
        self.archive.extractall(path)
