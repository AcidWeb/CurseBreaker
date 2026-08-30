import io
import re
import httpx
import zipfile
from . import clean_name, parse_directories, retry


class WoWInterfaceAddon:
    @retry()
    def __init__(self, url, checkcache, http):
        project = re.findall(r'\d+', url)[0]
        self.http = http
        if project in checkcache:
            self.payload = checkcache[project]
        else:
            try:
                self.payload = self.http.get(f'https://api.mmoui.com/v3/game/WOW/filedetails/{project}.json').json()
            except httpx.RequestError as e:
                raise RuntimeError(f'{url}\nWoWInterface API failed to respond.') from e
            if 'ERROR' in self.payload:
                raise RuntimeError(f'{url}\nThis might be a temporary error or this project is not supported '
                                   f'by WoWInterface API.')
            else:
                self.payload = self.payload[0]
        self.name = clean_name(self.payload['UIName'])
        self.downloadUrl = self.payload['UIDownload']
        self.changelogUrl = f'{url}#changelog'
        self.currentVersion = self.payload['UIVersion']
        self.uiVersion = None
        self.archive = None
        self.directories = []
        self.author = [self.payload['UIAuthorName']]

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(self.http.get(self.downloadUrl).content))
        self.directories = parse_directories(self.archive.namelist())
        if not self.directories:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.archive.extractall(path)
