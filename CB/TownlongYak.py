import os
import io
import zipfile
import requests
from . import retry, HEADERS


class TownlongYakAddon:
    @retry()
    def __init__(self, url, checkcache, clienttype):
        for addon in checkcache['addons']:
            if addon['repository'] == url:
                self.payload = addon
                break
        else:
            raise RuntimeError(url)
        self.project = url.split('/')[-1]
        self.name = self.payload['repository_name'].strip().strip('\u200b')
        self.author = [self.payload['owner_name']]
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
            if release['game_type'] == self.clientType and not release['prerelease']:
                self.downloadUrl = release['download_url']
                self.currentVersion = release['toc_version']
                self.changelogUrl = f'https://www.townlong-yak.com/addons/{self.project}/release/' \
                                    f'{self.currentVersion.replace(" ", "").lower()}'
                if self.changelogUrl[-1].isalpha():
                    self.changelogUrl = self.changelogUrl[:-1]
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
