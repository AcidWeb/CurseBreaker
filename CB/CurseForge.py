import os
import io
import re
import zipfile
import requests
from bs4 import BeautifulSoup
from operator import itemgetter
from . import retry


class CurseForgeAddon:
    @retry()
    def __init__(self, url, cache, allowdev):
        if url in cache:
            project = cache[url]
        else:
            soup = BeautifulSoup(requests.get(url).content, 'html.parser')
            project = re.findall(r'\d+', soup.find('div', attrs={'class': 'w-full flex justify-between'}).text)[0]
            self.cacheID = project
        self.payload = requests.post('https://addons-ecs.forgesvc.net/api/v2/addon', json=[int(project)]).json()[0]
        self.name = self.payload['name']
        self.allowDev = allowdev
        self.downloadUrl = None
        self.currentVersion = None
        self.archive = None
        self.directories = []
        self.get_current_version()

    def get_current_version(self):
        files = sorted(self.payload['latestFiles'], key=itemgetter('id'), reverse=True)
        for status in [[3, 2], [1]] if self.allowDev else [[1], [2], [3]]:
            for f in files:
                if f['releaseType'] in status and '-nolib' not in f['displayName'] and not f['isAlternate']:
                    self.downloadUrl = f['downloadUrl']
                    self.currentVersion = f['displayName']
                    break
            if self.downloadUrl and self.currentVersion:
                break
        else:
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
