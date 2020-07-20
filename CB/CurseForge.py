import os
import io
import zipfile
import requests
from . import retry, HEADERS
from operator import itemgetter


class CurseForgeAddon:
    @retry()
    def __init__(self, project, checkcache, clienttype, allowdev):
        if project in checkcache:
            self.payload = checkcache[project]
        else:
            self.payload = requests.get(f'https://addons-ecs.forgesvc.net/api/v2/addon/{project}',
                                        headers=HEADERS)
            if self.payload.status_code == 404:
                raise RuntimeError(f'{project}\nThe project could be removed from CurseForge or renamed. Uninstall it '
                                   f'(and reinstall if it still exists) to fix this issue.')
            elif self.payload.status_code == 403:
                raise RuntimeError(f'{project}\nAccess to CurseForge API was blocked. It is most likely caused by your'
                                   f' ISP or internet filter implemented by your government.')
            else:
                self.payload = self.payload.json()
        self.name = self.payload['name'].strip().strip('\u200b')
        if not len(self.payload['latestFiles']) > 0:
            raise RuntimeError(f'{self.name}.\nThe project doesn\'t have any releases.')
        self.clientType = clienttype
        self.allowDev = allowdev
        self.downloadUrl = None
        self.currentVersion = None
        self.archive = None
        self.directories = []
        self.get_current_version()

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
                    self.currentVersion = f['displayName']
                    break
            if self.downloadUrl and self.currentVersion:
                break
        else:
            raise RuntimeError(f'{self.name}.\nFailed to find release for your client version.')

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
