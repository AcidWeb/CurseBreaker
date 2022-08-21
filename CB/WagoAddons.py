import os
import io
import zipfile
import requests
from datetime import datetime
from dateutil import parser
from dateutil.tz import tzutc
from json import JSONDecodeError
from . import retry, HEADERS, APIAuth


class WagoAddonsAddon:
    @retry()
    def __init__(self, url, checkcache, clienttype, allowdev, apikey):
        project = url.replace('https://addons.wago.io/addons/', '')
        self.apiKey = apikey
        self.clientType = clienttype
        if project in checkcache:
            self.payload = checkcache[project]
            self.payload['display_name'] = self.payload['name']
            self.payload['recent_release'] = self.payload['recent_releases']
        else:
            if self.apiKey == '':
                raise RuntimeError(f'{url}\nThe Wago Addons API key is missing. '
                                   f'It can be obtained here: https://addons.wago.io/patreon')
            try:
                self.payload = requests.get(f'https://addons.wago.io/api/external/addons/{project}?game_version='
                                            f'{self.clientType}', headers=HEADERS, auth=APIAuth('Bearer', self.apiKey),
                                            timeout=5)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                raise RuntimeError(f'{url}\nWago Addons API failed to respond.')
            if self.payload.status_code == 401:
                raise RuntimeError(f'{url}\nWago Addons API key is missing or incorrect.')
            elif self.payload.status_code == 403:
                raise RuntimeError(f'{url}\nProvided Wago Addons API key is expired. Please acquire a new one.')
            elif self.payload.status_code == 423:
                raise RuntimeError(f'{url}\nProvided Wago Addons API key is blocked. Please acquire a new one.')
            elif self.payload.status_code == 404 or self.payload.status_code == 429 or self.payload.status_code == 500:
                raise RuntimeError(f'{url}\nThis might be a temporary issue with Wago Addons API or the project was '
                                   f'removed/renamed. In this case, uninstall it (and reinstall if it still exists) '
                                   f'to fix this issue.')
            else:
                try:
                    self.payload = self.payload.json()
                except (StopIteration, JSONDecodeError):
                    raise RuntimeError(f'{url}\nThis might be a temporary issue with Wago Addons API.')
        self.name = self.payload['display_name'].strip().strip('\u200b')
        self.allowDev = allowdev
        self.downloadUrl = None
        self.changelogUrl = None
        self.currentVersion = None
        self.uiVersion = None
        self.archive = None
        self.directories = []
        self.author = self.payload['authors']
        self.get_current_version()

    def get_current_version(self):
        if len(self.payload['recent_release']) == 0:
            raise RuntimeError(f'{self.name}.\nFailed to find release for your client version.')

        empty = datetime(1, 1, 1, 0, 1, tzinfo=tzutc())
        release = {'stable': datetime(1, 1, 1, 0, 0, tzinfo=tzutc()),
                   'beta': datetime(1, 1, 1, 0, 0, tzinfo=tzutc()),
                   'alpha': datetime(1, 1, 1, 0, 0, tzinfo=tzutc())}
        for channel in ['stable', 'beta', 'alpha']:
            if channel in self.payload['recent_release']:
                release[channel] = parser.isoparse(self.payload['recent_release'][channel]['created_at'])
        if self.allowDev == 1:
            release.pop('alpha', None)
        elif self.allowDev == 0:
            if release['stable'] == empty:
                release.pop('stable', None)
                if release['beta'] != empty:
                    release.pop('alpha', None)
                elif release['alpha'] != empty:
                    release.pop('beta', None)
                else:
                    release.pop('alpha', None)
                    release.pop('beta', None)
            else:
                release.pop('alpha', None)
                release.pop('beta', None)
        if len(release) == 0:
            raise RuntimeError(f'{self.name}.\nFailed to find release for your client version.')
        release = self.payload['recent_release'][max(release, key=release.get)]

        self.downloadUrl = release['download_link'] if 'download_link' in release else release['link']
        self.uiVersion = release['patch'] if 'patch' in release else release[f'supported_{self.clientType}_patch']
        self.changelogUrl = f'{self.payload["website_url"]}/versions'
        self.currentVersion = release['label']

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS,
                                                               auth=APIAuth('Bearer', self.apiKey), timeout=5).content))
        for file in self.archive.namelist():
            if '/' not in os.path.dirname(file):
                self.directories.append(os.path.dirname(file))
        self.directories = list(filter(None, set(self.directories)))
        if len(self.directories) == 0:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.archive.extractall(path)
