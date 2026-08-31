import io
import zipfile
from . import clean_name, parse_directories, retry


class TukuiAddon:
    @retry()
    def __init__(self, slug, checkcache, clientversion, http):
        for addon in checkcache:
            if addon['slug'] == slug:
                self.payload = addon
                break
        else:
            raise RuntimeError(f'{slug}\nProject not found.')
        self.http = http
        self.name = clean_name(self.payload['name'])
        self.downloadUrl = self.payload['url']
        self.currentVersion = self.payload['version']
        self.uiVersion = clientversion if clientversion in self.payload['patch'] else self.payload['patch'][0]
        self.archive = None
        self.directories = self.payload['directories']
        self.author = [self.payload['author']]
        self.ignoreUpdate = False
        self.changelogUrl = self.payload['changelog_url']

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(self.http.get(self.downloadUrl).content))
        self.directories = parse_directories(self.archive.namelist(), self.directories)
        if not self.directories:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.archive.extractall(path)
