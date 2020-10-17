import io
import shutil
import zipfile
import requests
from . import retry, HEADERS


class GitLabAddon:
    @retry()
    def __init__(self, name, projectid, path, branch):
        self.payload = requests.get(f'https://git.tukui.org/api/v4/projects/{projectid}/repository/branches/{branch}',
                                    headers=HEADERS, timeout=5)
        if self.payload.status_code == 404:
            raise RuntimeError(name)
        else:
            self.payload = self.payload.json()
        self.name = name
        self.shorthPath = path.split('/')[1]
        self.downloadUrl = f'https://git.tukui.org/{path}/-/archive/{branch}/{self.shorthPath}-{branch}.zip'
        self.changelogUrl = None
        self.currentVersion = self.payload['commit']['short_id']
        self.uiVersion = None
        self.branch = branch
        self.archive = None
        self.dependencies = None
        self.directories = []
        self.author = []

        if name == 'ElvUI':
            self.author = ['Elv', 'Blazeflack']
            if projectid == '60':
                self.changelogUrl = 'https://www.tukui.org/download.php?ui=elvui&changelog'
            elif projectid == '492':
                self.changelogUrl = 'https://www.tukui.org/classic-addons.php?id=2&changelog'
        elif name == 'Tukui':
            self.author = ['Tukz']
            if branch == 'master':
                self.changelogUrl = 'https://www.tukui.org/download.php?ui=tukui&changelog'
            elif branch == 'Classic':
                self.changelogUrl = 'https://www.tukui.org/classic-addons.php?id=1&changelog'
        elif name == 'ElvUI Shadow & Light':
            self.author = ['Repooc', 'DarthPredator']
            self.changelogUrl = 'https://git.tukui.org/shadow-and-light/shadow-and-light/-/commits/dev'

    @retry()
    def get_addon(self):
        self.archive = zipfile.ZipFile(io.BytesIO(requests.get(self.downloadUrl, headers=HEADERS, timeout=5).content))
        for file in self.archive.namelist():
            file_info = self.archive.getinfo(file)
            if file_info.is_dir() and file_info.filename.count('/') == 2 and '.gitlab' not in file_info.filename:
                self.directories.append(file_info.filename.split('/')[1])
        self.directories = list(filter(None, set(self.directories)))
        if len(self.directories) == 0:
            raise RuntimeError(f'{self.name}.\nProject package is corrupted or incorrectly packaged.')

    def install(self, path):
        self.archive.extractall(path)
        for directory in self.directories:
            shutil.rmtree(path / directory, ignore_errors=True)
            # FIXME - Python bug #32689 - Fixed in 3.9
            shutil.move(str(path / f'{self.shorthPath}-{self.branch}' / directory), str(path))
        shutil.rmtree(path / f'{self.shorthPath}-{self.branch}')
