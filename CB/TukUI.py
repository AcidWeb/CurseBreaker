import os
import io
import shutil
import zipfile
import requests
from bs4 import BeautifulSoup
from . import retry


class TukUIAddon:
    @retry
    def __init__(self):
        self.soup = BeautifulSoup(requests.get('https://git.tukui.org/Tukz/Tukui/tree/master').content, 'html.parser')
        self.name = 'TukUI'
        self.downloadUrl = 'https://git.tukui.org/Tukz/Tukui/-/archive/master/Tukui-master.zip'
        self.currentVersion = None
        self.archive = None
        self.directories = []

    def get_current_version(self):
        try:
            self.currentVersion = self.soup.find('div', attrs={'class': 'label label-monospace'}).contents[0].strip()
        except Exception:
            raise RuntimeError('Failed to parse addon page. URL is wrong or your source has some issues.')

    @retry
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl).content))
        for file in self.archive.namelist():
            file_info = self.archive.getinfo(file)
            if file_info.is_dir() and file_info.filename.count('/') == 2 and '.gitlab' not in file_info.filename:
                self.directories.append(file_info.filename.split('/')[1])

    def install(self, path):
        self.get_addon()
        self.archive.extractall(path)
        for directory in self.directories:
            shutil.move(os.path.join(path, 'Tukui-master', directory), path)
        shutil.rmtree(os.path.join(path, 'Tukui-master'))
