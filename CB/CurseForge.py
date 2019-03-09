import os
import io
import zipfile
import requests
from bs4 import BeautifulSoup


class CurseForgeAddon:
    def __init__(self, url):
        try:
            if url.startswith('https://www.curseforge.com/wow/addons/'):
                soup = BeautifulSoup(requests.get(url).content, 'html.parser')
                for link in soup.findAll('a', href=True, text='Visit Project Page'):
                    url = link['href'] + '/files'
                    break
                self.redirectUrl = url
            self.soup = BeautifulSoup(requests.get(url).content, 'html.parser')
            self.name = self.soup.title.string.split(' - ')[1].strip()
            self.downloadUrl = url + '/latest'
            self.currentVersion = None
            self.archive = None
            self.directories = []
        except Exception:
            raise RuntimeError('Failed to parse CurseForge page. Check if URL is correct.')

    def get_current_version(self):
        try:
            table = self.soup.find('table', attrs={'class': 'listing listing-project-file project-file-listing'
                                                            ' b-table b-table-a'}).find('tbody')
            for row in table.find_all('tr', attrs={'class': 'project-file-list-item'}):
                if 'Release' in str(row.find('td', attrs={'class': 'project-file-release-type'})):
                    self.currentVersion = row.find('a', attrs={'class': 'overflow-tip twitch-link'}).contents[0].strip()
                    break
            if not self.currentVersion:
                for row in table.find_all('tr', attrs={'class': 'project-file-list-item'}):
                    if 'Beta' in str(row.find('td', attrs={'class': 'project-file-release-type'})):
                        self.currentVersion = row.find('a', attrs={'class': 'overflow-tip twitch-link'}).contents[0]\
                            .strip()
                        break
        except Exception:
            raise RuntimeError('Failed to parse CurseForge page. Check if URL is correct.')

    def get_addon(self):
        try:
            self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl).content))
            for file in self.archive.namelist():
                if '/' not in os.path.dirname(file):
                    self.directories.append(os.path.dirname(file))
            self.directories = list(set(self.directories))
        except Exception:
            raise RuntimeError('Failed to download the archive.')

    def install(self, path):
        self.get_addon()
        self.archive.extractall(path)
