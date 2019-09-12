import os
import io
import zipfile
import requests
from . import retry, HEADERS
from operator import itemgetter
from xml.dom.minidom import parseString


class CurseForgeAddon:
    @retry()
    def __init__(self, url, idcache, checkcache, clienttype, allowdev):
        if url in idcache:
            project = idcache[url]
        else:
            xml = parseString(requests.get(url + '/download-client', headers=HEADERS).text)
            project = xml.childNodes[0].getElementsByTagName('project')[0].getAttribute('id')
            self.cacheID = project
        if project in checkcache:
            self.payload = checkcache[project]
        else:
            self.payload = requests.get(f'https://addons-ecs.forgesvc.net/api/v2/addon/{project}',
                                        headers=HEADERS).json()
        if not len(self.payload['latestFiles']) > 0:
            raise RuntimeError
        self.name = self.payload['name'].strip().strip('\u200b')
        self.clientType = clienttype
        self.allowDev = allowdev
        self.downloadUrl = None
        self.currentVersion = None
        self.archive = None
        self.directories = []
        self.get_current_version()

    def get_current_version(self):
        files = sorted(self.payload['latestFiles'], key=itemgetter('id'), reverse=True)
        for status in [[3, 2, 1]] if self.allowDev else [[1], [2], [3]]:
            for f in files:
                if f['gameVersionFlavor'] == self.clientType and f['releaseType'] in status \
                        and '-nolib' not in f['displayName'] and not f['isAlternate']:
                    self.downloadUrl = f['downloadUrl']
                    self.currentVersion = f['displayName']
                    break
            if self.downloadUrl and self.currentVersion:
                break
        else:
            raise RuntimeError

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS).content))
        for file in self.archive.namelist():
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(set(self.directories))

    def install(self, path):
        self.get_addon()
        self.archive.extractall(path)
