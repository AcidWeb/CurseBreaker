import os
import io
import zipfile
import requests
from . import retry, HEADERS
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
        if not len(self.payload['gameVersionLatestFiles']) > 0:
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
        latestfiles = {1: 0, 2: 0, 3: 0}
        for f in self.payload['gameVersionLatestFiles']:
            if 'gameVersionTypeId' in f and f['gameVersionTypeId'] == self.clientType and f['projectFileId'] > latestfiles[f['fileType']]:
                latestfiles[f['fileType']] = f['projectFileId']

        targetrelease = 0
        if self.allowDev == 1:
            latestfiles.pop(3, None)
            targetrelease = latestfiles[max(latestfiles, key=latestfiles.get)]
        elif self.allowDev == 2:
            targetrelease = latestfiles[max(latestfiles, key=latestfiles.get)]
        else:
            if latestfiles[1] > 0:
                targetrelease = latestfiles[1]
            elif latestfiles[2] > 0:
                targetrelease = latestfiles[2]
            elif latestfiles[3] > 0:
                targetrelease = latestfiles[3]
        if targetrelease == 0:
            raise RuntimeError(f'{self.name}.\nFailed to find release for your client version.')

        for f in self.payload['latestFiles']:
            if f['id'] == targetrelease:
                self.downloadUrl = f['downloadUrl']
                self.changelogUrl = f'{self.payload["websiteUrl"]}/files/{f["id"]}'
                self.currentVersion = f['displayName']
                if len(f['sortableGameVersion']) > 0:
                    for v in f['sortableGameVersion']:
                        if v['gameVersionTypeId'] == self.clientType:
                            self.uiVersion = v['gameVersion']
                            break
                if len(f['dependencies']) > 0:
                    self.dependencies = []
                    for d in f['dependencies']:
                        if d['type'] == 3:
                            self.dependencies.append(d['addonId'])
                    if len(self.dependencies) == 0:
                        self.dependencies = None
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
