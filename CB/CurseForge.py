import os
import io
import zipfile
import requests
from bs4 import BeautifulSoup
from . import retry


class CurseForgeAddon:
    @retry()
    def __init__(self, url):
        if url.startswith('https://www.curseforge.com/wow/addons/'):
            soup = BeautifulSoup(requests.get(url).content, 'html.parser')
            for link in soup.findAll('a', href=True, text='Visit Project Page'):
                url = link['href'] + '/files'
                break
            self.redirectUrl = url
        self.url = url
        self.soup = BeautifulSoup(requests.get(self.url).content, 'html.parser')
        self.name = self.soup.title.string.split(' - ')[1].strip()
        self.downloadUrl = url + '/latest'
        self.currentVersion = None
        self.archive = None
        self.directories = []

    def version_search(self, tag):
        version = None
        table = self.soup.find('table', attrs={'class': 'listing listing-project-file project-file-listing '
                                                        'b-table b-table-a'}).find('tbody')
        for row in table.find_all('tr', attrs={'class': 'project-file-list-item'}):
            if tag in str(row.find('td', attrs={'class': 'project-file-release-type'})):
                version = row.find('a', attrs={'class': 'overflow-tip twitch-link'}).contents[0].strip()
                break
        return version

    @retry()
    def get_current_version(self):
        self.currentVersion = self.version_search('Release')
        if self.currentVersion is None:
            self.currentVersion = self.version_search('Beta')
        if self.currentVersion:
            return
        for page in range(2, 6):
            self.soup = BeautifulSoup(requests.get(f'{self.url}?page={page}').content, 'html.parser')
            self.currentVersion = self.version_search('Release')
            if self.currentVersion is None:
                self.currentVersion = self.version_search('Beta')
            if self.currentVersion:
                break
        if self.currentVersion is None:
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
