import os
import io
import zipfile
import requests
from . import retry, HEADERS
from operator import itemgetter
from json import JSONDecodeError


class CurseForgeAddon:
    @retry()
    def __init__(self, url, project, checkcache, clienttype, allowdev):
        if project in checkcache:
            self.payload = checkcache[project]
        else:
            try:
                self.payload = requests.get(f'https://addons-ecs.forgesvc.net/api/v2/addon/{project}',
                                            headers=HEADERS, timeout=5)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                raise RuntimeError(f'{url}\nCurseForge API failed to respond.')
            if self.payload.status_code == 404 or self.payload.status_code == 500:
                raise RuntimeError(f'{url}\nThis might be a temporary issue with CurseForge API or the project was '
                                   f'removed/renamed. In this case, uninstall it (and reinstall if it still exists) '
                                   f'to fix this issue.')
            elif self.payload.status_code == 403:
                raise RuntimeError(f'{url}\nAccess to CurseForge API was blocked. It is most likely caused by your'
                                   f' ISP or internet filter implemented by your government.')
            else:
                try:
                    self.payload = self.payload.json()
                except (StopIteration, JSONDecodeError):
                    raise RuntimeError(f'{url}\nThis might be a temporary issue with CurseForge API.')
        self.name = self.payload['name'].strip().strip('\u200b')
        if not len(self.payload['latestFiles']) > 0:
            raise RuntimeError(f'{self.name}.\nThe project doesn\'t have any releases.')
        self.clientType = clienttype
        self.allowDev = allowdev
        self.downloadUrl = None
        self.changelogUrl = None
        self.currentVersion = None
        self.uiVersion = None
        self.archive = None
        self.dependencies = None
        self.directories = []
        self.author = []
        self.get_current_version()

        for author in self.payload['authors']:
            if '_ForgeUser' not in author['name']:
                self.author.append(author['name'])

    def get_current_version(self):
        files = sorted(self.payload['latestFiles'], key=itemgetter('id'), reverse=True)
        release = [[1], [2], [3]]
        if self.allowDev == 1:
            release = [[2, 1]]
        elif self.allowDev == 2:
            release = [[3, 2, 1]]
        for status in release:
            for f in files:
                if (self.clientType == 'wow' or f['gameVersionFlavor'] == self.clientType) and \
                        f['releaseType'] in status and '-nolib' not in f['displayName'] and not f['isAlternate']:
                    self.downloadUrl = f['downloadUrl']
                    self.changelogUrl = f'{self.payload["websiteUrl"]}/files/{f["id"]}'
                    self.currentVersion = f['displayName']
                    if len(f['gameVersion']) > 0:
                        self.uiVersion = max(f['gameVersion'])
                    if len(f['dependencies']) > 0:
                        self.dependencies = []
                        for d in f['dependencies']:
                            if d['type'] == 3:
                                self.dependencies.append(d['addonId'])
                        if len(self.dependencies) == 0:
                            self.dependencies = None
                    break
            if self.downloadUrl and self.currentVersion:
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
