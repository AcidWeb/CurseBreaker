import os
import io
import shutil
import zipfile
import requests
from . import retry, HEADERS


class GitHubAddon:
    @retry()
    def __init__(self, url, clienttype):
        project = url.replace('https://github.com/', '')
        try:
            self.payload = requests.get(f'https://api.github.com/repos/{project}/releases', headers=HEADERS, timeout=5)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise RuntimeError(f'{project}\nGitHub API failed to respond.')
        if self.payload.status_code == 404:
            raise RuntimeError(url)
        else:
            self.payload = self.payload.json()
            for release in self.payload:
                if release['assets'] and len(release['assets']) > 0\
                        and not release['draft'] and not release['prerelease']:
                    self.payload = release
                    break
            else:
                raise RuntimeError(f'{url}\nThis integration supports only the projects that provide packaged '
                                   f'releases.')
        self.name = project.split('/')[1]
        self.clientType = clienttype
        self.currentVersion = self.payload['tag_name'] or self.payload['name']
        self.uiVersion = None
        self.downloadUrl = None
        self.changelogUrl = self.payload['html_url']
        self.archive = None
        self.dependencies = None
        self.directories = []
        self.author = [project.split('/')[0]]
        self.get_latest_package()

    def get_latest_package(self):
        latest = None
        latestclassic = None
        for release in self.payload['assets']:
            if release['name'] and '-nolib' not in release['name'] \
                    and release['content_type'] in {'application/x-zip-compressed', 'application/zip'}:
                if not latest and not release['name'].endswith('-classic.zip') and \
                        not release['name'].endswith('-bc.zip'):
                    latest = release['browser_download_url']
                elif not latestclassic and release['name'].endswith('-classic.zip') and \
                        not release['name'].endswith('-bc.zip'):
                    latestclassic = release['browser_download_url']
        if (self.clientType == 'wow_retail' and latest) or (self.clientType == 'wow_classic' and latest
                                                            and not latestclassic):
            self.downloadUrl = latest
        elif self.clientType == 'wow_classic' and latestclassic:
            self.downloadUrl = latestclassic
        else:
            raise RuntimeError(f'{self.name}.\nFailed to find release for your client version.')

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS, timeout=5).content))
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


class GitHubAddonRaw:
    @retry()
    def __init__(self, project, branch, targetdirs):
        try:
            self.payload = requests.get(f'https://api.github.com/repos/{project}/branches/{branch}',
                                        headers=HEADERS, timeout=5)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise RuntimeError(f'{project}\nGitHub API failed to respond.')
        if self.payload.status_code == 404:
            raise RuntimeError(f'{project}\nTarget branch don\'t exist.')
        else:
            self.payload = self.payload.json()
        self.name = None
        self.shorthPath = project.split('/')[1]
        self.downloadUrl = f'https://github.com/{project}/archive/refs/heads/{branch}.zip'
        self.changelogUrl = f'https://github.com/{project}/commits/{branch}'
        self.currentVersion = self.payload['commit']['sha'][:7]
        self.branch = branch
        self.uiVersion = None
        self.archive = None
        self.dependencies = None
        self.directories = targetdirs
        self.author = []

        if project == 'Shadow-and-Light/shadow-and-light':
            self.name = 'ElvUI Shadow & Light'
            self.author = ['Repooc', 'DarthPredator']
        else:
            raise RuntimeError(f'{project}\nThis source is unsupported.')

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS, timeout=5).content))

    def install(self, path):
        self.archive.extractall(path)
        for directory in self.directories:
            shutil.rmtree(path / directory, ignore_errors=True)
            # FIXME - Python bug #32689 - Fixed in 3.9
            shutil.move(str(path / f'{self.shorthPath}-{self.branch}' / directory), str(path))
        shutil.rmtree(path / f'{self.shorthPath}-{self.branch}')
