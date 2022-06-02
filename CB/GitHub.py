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
                                        auth=APIAuth('token', self.apiKey), timeout=5)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise RuntimeError(f'{project}\nGitHub API failed to respond.')
        if self.payload.status_code == 403:
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
                    if len(self.payloads) > 4:
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
                self.metadata = requests.get(release['browser_download_url'], headers=HEADERS, timeout=5).json()
                break
        else:
            self.metadata = None

    def get_latest_package(self):
        if self.metadata:
            targetfile = None
            if self.clientType == 'classic':
                targetflavor = 'classic'
            elif self.clientType == 'bc':
                targetflavor = 'bcc'
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
                    self.downloadUrl = release['browser_download_url']
                    break
            if not self.downloadUrl:
                self.releaseDepth += 1
                self.parse()
        else:
            latest = None
            latestclassic = None
            latestbc = None
            for release in self.payloads[self.releaseDepth]['assets']:
                if release['name'] and '-nolib' not in release['name'] \
                        and release['content_type'] in {'application/x-zip-compressed', 'application/zip'}:
                    if not latest and not release['name'].endswith('-classic.zip') and \
                            not release['name'].endswith('-bc.zip') and not release['name'].endswith('-bcc.zip'):
                        latest = release['browser_download_url']
                    elif not latestclassic and release['name'].endswith('-classic.zip'):
                        latestclassic = release['browser_download_url']
                    elif not latestbc and (release['name'].endswith('-bc.zip') or release['name'].endswith('-bcc.zip')):
                        latestbc = release['browser_download_url']
            if (self.clientType == 'retail' and latest) \
                    or (self.clientType == 'classic' and latest and not latestclassic) \
                    or (self.clientType == 'bc' and latest and not latestbc):
                self.downloadUrl = latest
            elif self.clientType == 'classic' and latestclassic:
                self.downloadUrl = latestclassic
            elif self.clientType == 'bc' and latestbc:
                self.downloadUrl = latestbc
            else:
                self.releaseDepth += 1
                self.parse()

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
    def __init__(self, project, branch, targetdirs, apikey):
        self.apiKey = apikey
        try:
            self.payload = requests.get(f'https://api.github.com/repos/{project}/branches/{branch}',
                                        headers=HEADERS, auth=APIAuth('token', self.apiKey), timeout=5)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise RuntimeError(f'{project}\nGitHub API failed to respond.')
        if self.payload.status_code == 403:
            raise RuntimeError(f'{project}\nGitHub API rate limit exceeded. Try later or provide personal access '
                               f'token.')
        elif self.payload.status_code == 404:
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
        self.directories = targetdirs
        self.author = []

        if project == 'tukui-org/ElvUI':
            self.name = 'ElvUI'
            self.author = ['Elv']
        elif project == 'tukui-org/Tukui':
            self.name = 'TukUI'
            self.author = ['Tukz']
        elif project == 'Shadow-and-Light/shadow-and-light':
            self.name = 'ElvUI Shadow & Light'
            self.author = ['Repooc', 'DarthPredator']
        else:
            raise RuntimeError(f'{project}\nThis source is unsupported.')

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS, timeout=5).content))

    def install(self, path):
        for directory in self.directories:
            shutil.rmtree(path / directory, ignore_errors=True)
        for file in self.archive.infolist():
            file.filename = file.filename.replace(f'{self.shorthPath}-{self.branch}/', '')
            if any(f in file.filename for f in self.directories):
                self.archive.extract(file, path)
