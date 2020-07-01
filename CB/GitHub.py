import os
import io
import zipfile
import requests
from . import retry, HEADERS


class GitHubAddon:
    @retry()
    def __init__(self, url):
        project = url.replace('https://github.com/', '')
        self.payload = requests.get(f'https://api.github.com/repos/{project}/releases/latest', headers=HEADERS)
        if self.payload.status_code == 404:
            raise RuntimeError(url)
        else:
            self.payload = self.payload.json()
        if 'assets' not in self.payload or len(self.payload['assets']) == 0 \
                or self.payload['assets'][0]['content_type'] not in ['application/x-zip-compressed', 'application/zip']:
            raise RuntimeError(url + '\nThis integration supports only the projects that provide packaged releases.')
        self.name = project.split('/')[1]
        self.downloadUrl = self.payload['assets'][0]['browser_download_url']
        self.currentVersion = self.payload['tag_name'] or self.payload['name']
        self.archive = None
        self.directories = []

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS).content))
        for file in self.archive.namelist():
            if file.lower().endswith('.toc') and '/' not in file:
                raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(filter(None, set(self.directories)))
        if len(self.directories) == 0:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.archive.extractall(path)
