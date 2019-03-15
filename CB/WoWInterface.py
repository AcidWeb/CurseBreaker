import os
import io
import zipfile
import requests
from bs4 import BeautifulSoup
from . import retry


class WoWInterfaceAddon:
    @retry()
    def __init__(self, url):
        self.soup = BeautifulSoup(requests.get(url).content, 'html.parser')
        self.name = self.soup.find('meta', attrs={'property': 'og:title'})['content']
        self.downloadUrl = url.replace('/info', '/download')
        self.currentVersion = None
        self.archive = None
        self.directories = []

    def get_current_version(self):
        try:
            self.currentVersion = self.soup.find('div', attrs={'id': 'version'}).contents[0].split(': ')[1].strip()
        except Exception:
            raise RuntimeError('Failed to parse addon page. URL is wrong or your source has some issues.')

    @retry()
    def get_addon(self):
        dsoup = BeautifulSoup(requests.get(self.downloadUrl).content, 'html.parser')
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(dsoup.find('div', attrs={'class': 'manuallink'}).
                                                               find('a')['href'].strip()).content))
        for file in self.archive.namelist():
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(set(self.directories))

    def install(self, path):
        self.get_addon()
        self.archive.extractall(path)
