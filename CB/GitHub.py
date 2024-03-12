import os
import io
import shutil
import zipfile
import requests
from . import retry, HEADERS, APIAuth


# noinspection PyTypeChecker
class GitHubAddon:
    @retry()
    def __init__(self, url, clienttype, apikey):
        project = url.replace('https://github.com/', '')
        self.apiKey = apikey
        self.payloads = []
        try:
            self.payload = requests.get(f'https://api.github.com/repos/{project}/releases', headers=HEADERS,
                                        auth=APIAuth('token', self.apiKey), timeout=10)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise RuntimeError(f'{project}\nGitHub API failed to respond.')
        if self.payload.status_code == 401:
            raise RuntimeError(f'{project}\nIncorrect or expired GitHub API personal access token.')
        elif self.payload.status_code == 403:
            raise RuntimeError(f'{project}\nGitHub API rate limit exceeded. Try later or provide personal access '
                               f'token.')
        elif self.payload.status_code == 404:
            raise RuntimeError(url)
        else:
            self.payload = self.payload.json()
            for release in self.payload:
                if release['assets'] and len(release['assets']) > 0 \
                        and not release['draft'] and not release['prerelease']:
                    self.payloads.append(release)
                    if len(self.payloads) > 14:
                        break
            if len(self.payloads) == 0:
                raise RuntimeError(f'{url}\nThis integration supports only the projects that provide packaged'
                                   f' releases.')
        self.name = project.split('/')[1]
        self.clientType = clienttype
        self.currentVersion = None
        self.uiVersion = None
        self.downloadUrl = None
        self.changelogUrl = None
        self.archive = None
        self.metadata = None
        self.directories = []
        self.author = [project.split('/')[0]]
        self.releaseDepth = 0
        self.parse()

    def parse(self):
        if self.releaseDepth >= len(self.payloads):
            raise RuntimeError(f'{self.name}.\nFailed to find release for your client version.')
        self.currentVersion = self.payloads[self.releaseDepth]['tag_name'] or self.payloads[self.releaseDepth]['name']
        self.changelogUrl = self.payloads[self.releaseDepth]['html_url']
        self.parse_metadata()
        self.get_latest_package()

    def parse_metadata(self):
        for release in self.payloads[self.releaseDepth]['assets']:
            if release['name'] and release['name'] == 'release.json':
                self.metadata = requests.get(release['url'],
                                             headers=dict({'Accept': 'application/octet-stream'}, **HEADERS),
                                             auth=APIAuth('token', self.apiKey), timeout=10).json()
                break
        else:
            self.metadata = None

    def get_latest_package(self):
        if self.metadata:
            targetfile = None
            if self.clientType == 'classic':
                targetflavor = 'classic'
            elif self.clientType == 'wotlk':
                targetflavor = 'wrath'
            else:
                targetflavor = 'mainline'
            for release in self.metadata['releases']:
                if not release['nolib']:
                    for flavor in release['metadata']:
                        if flavor['flavor'] == targetflavor:
                            targetfile = release['filename']
                            if 'name' in release:
                                self.name = release['name']
                                self.currentVersion = release['version']
                            break
                    if targetfile:
                        break
            if not targetfile:
                self.releaseDepth += 1
                self.parse()
            for release in self.payloads[self.releaseDepth]['assets']:
                if release['name'] and release['name'] == targetfile:
                    self.downloadUrl = release['url']
                    break
            if not self.downloadUrl:
                self.releaseDepth += 1
                self.parse()
        else:
            latest = None
            latestclassic = None
            latestwrath = None
            for release in self.payloads[self.releaseDepth]['assets']:
                if release['name'] and release['name'].endswith('.zip') and '-nolib' not in release['name'] \
                        and release['content_type'] in ['application/x-zip-compressed', 'application/zip', 'raw']:
                    if not latest and not release['name'].endswith(('-classic.zip', '-bc.zip', '-bcc.zip',
                                                                    '-wrath.zip')):
                        latest = release['url']
                    elif not latestclassic and release['name'].endswith('-classic.zip'):
                        latestclassic = release['url']
                    elif not latestwrath and release['name'].endswith('-wrath.zip'):
                        latestwrath = release['url']
            if (self.clientType == 'retail' and latest) \
                    or (self.clientType == 'classic' and latest and not latestclassic) \
                    or (self.clientType == 'wotlk' and latest and not latestwrath):
                self.downloadUrl = latest
            elif self.clientType == 'classic' and latestclassic:
                self.downloadUrl = latestclassic
            elif self.clientType == 'wotlk' and latestwrath:
                self.downloadUrl = latestwrath
            else:
                self.releaseDepth += 1
                self.parse()

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(
            requests.get(self.downloadUrl, headers=dict({'Accept': 'application/octet-stream'}, **HEADERS),
                         auth=APIAuth('token', self.apiKey), timeout=10).content))
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
    def __init__(self, addon, apikey):
        repository = addon["Repository"]
        self.apiKey = apikey
        self.branch = addon["Branch"]
        self.name = addon["Name"]
        try:
            self.payload = requests.get(f'https://api.github.com/repos/{repository}/branches/{self.branch}',
                                        headers=HEADERS, auth=APIAuth('token', self.apiKey), timeout=10)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise RuntimeError(f'{self.name}\nGitHub API failed to respond.')
        if self.payload.status_code == 401:
            raise RuntimeError(f'{self.name}\nIncorrect or expired GitHub API personal access token.')
        elif self.payload.status_code == 403:
            raise RuntimeError(f'{self.name}\nGitHub API rate limit exceeded. Try later or provide personal access '
                               f'token.')
        elif self.payload.status_code == 404:
            raise RuntimeError(f'{self.name}\nTarget branch don\'t exist.')
        else:
            self.payload = self.payload.json()
        self.shorthPath = repository.split('/')[1]
        self.downloadUrl = f'https://github.com/{repository}/archive/refs/heads/{self.branch}.zip'
        self.changelogUrl = f'https://github.com/{repository}/commits/{self.branch}'
        self.currentVersion = self.payload['commit']['sha'][:7]
        self.uiVersion = None
        self.archive = None
        self.directories = addon["Directories"]
        self.author = addon["Authors"]

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS, timeout=10).content))

    def install(self, path):
        for directory in self.directories:
            shutil.rmtree(path / directory, ignore_errors=True)
        for file in self.archive.infolist():
            file.filename = file.filename.replace(f'{self.shorthPath}-{self.branch}/', '')
            if any(f in file.filename for f in self.directories):
                self.archive.extract(file, path)
