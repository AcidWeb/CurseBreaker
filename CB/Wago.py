import os
import re
import httpx
import shutil
import bbcode
from io import StringIO, BytesIO
from pathlib import Path
from zipfile import ZipFile
from markdown import Markdown
from urllib.parse import quote_plus
from . import retry
from .SLPP import loads


def markdown_unmark_element(element, stream=None):
    if stream is None:
        stream = StringIO()
    if element.text:
        stream.write(element.text)
    for sub in element:
        markdown_unmark_element(sub, stream)
    if element.tail:
        stream.write(element.tail)
    return stream.getvalue()


class WagoAPIAuth(httpx.Auth):
    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        if self.token != '':
            request.headers['api-key'] = self.token
        yield request


class BaseParser:
    def __init__(self):
        self.urlParser = re.compile('/([a-zA-Z0-9_-]+)/(\\d+)')
        self.list = {}
        self.ignored = {}
        self.data = {'slugs': [], 'stash': []}


class WeakAuraParser(BaseParser):
    def __init__(self, accountname):
        super().__init__()
        self.accountName = accountname
        self.api = 'weakauras'
        self.parse_storage()

    def parse_storage(self):
        with open(Path(f'WTF/Account/{self.accountName}/SavedVariables/WeakAuras.lua'), encoding='utf-8',
                  errors='ignore') as file:
            data = file.read().replace('WeakAurasSaved = {', '{')
        wadata = loads(data)
        for wa in wadata['displays']:
            if 'url' in wadata['displays'][wa]:
                search = self.urlParser.search(wadata['displays'][wa]['url'])
                if (search is not None and search.group(1) and search.group(2) and search.group(1) not in self.list
                        and 'ignoreWagoUpdate' not in wadata['displays'][wa]):
                    if 'skipWagoUpdate' in wadata['displays'][wa]:
                        self.ignored[search.group(1)] = int(wadata['displays'][wa]['skipWagoUpdate'])
                    self.list[search.group(1)] = int(search.group(2))


class PlaterParser(BaseParser):
    def __init__(self, accountname):
        super().__init__()
        self.accountName = accountname
        self.api = 'plater'
        self.parse_storage()

    def parse_storage_internal(self, data):
        for script in data:
            if 'url' in script:
                search = self.urlParser.search(script['url'])
                if search is not None and search.group(1) and search.group(2) and 'ignoreWagoUpdate' not in script:
                    if 'skipWagoUpdate' in script:
                        self.ignored[search.group(1)] = int(script['skipWagoUpdate'])
                    self.list[search.group(1)] = int(search.group(2))

    def parse_storage(self):
        with open(Path(f'WTF/Account/{self.accountName}/SavedVariables/Plater.lua'), encoding='utf-8',
                  errors='ignore') as file:
            data = file.read()
        platerdata = loads(re.search(r'PlaterDB = {\n.*?}\n', data, re.DOTALL).group().replace('PlaterDB = {', '{', 1))
        for profile in platerdata['profiles']:
            if data := platerdata['profiles'][profile]['script_data']:
                self.parse_storage_internal(data)
            if data := platerdata['profiles'][profile]['hook_data']:
                self.parse_storage_internal(data)
            if 'url' in platerdata['profiles'][profile]:
                search = self.urlParser.search(platerdata['profiles'][profile]['url'])
                if (search is not None and search.group(1) and search.group(2) and
                        'ignoreWagoUpdate' not in platerdata['profiles'][profile]):
                    if 'skipWagoUpdate' in platerdata['profiles'][profile]:
                        self.ignored[search.group(1)] = int(platerdata['profiles'][profile]['skipWagoUpdate'])
                    self.list[search.group(1)] = int(search.group(2))


class WagoUpdater:
    # noinspection PyTypeChecker
    def __init__(self, config, http):
        self.http = http
        self.auth = WagoAPIAuth(config['WAAPIKey'])
        self.username = config['WAUsername']
        self.accountName = config['WAAccountName']
        self.stash = config['WAStash']
        self.bbParser = bbcode.Parser()
        Markdown.output_formats['plain'] = markdown_unmark_element
        self.mdParser = Markdown(output_format='plain')
        self.mdParser.stripTopLevelTags = False
        if self.username == 'DISABLED':
            self.username = ''

    def clean_string(self, s):
        return s.replace('"', '\\"')

    @retry('Failed to parse Wago data. Wago might be down or provided API key is incorrect.')
    def check_updates(self, addon):
        output = [[], []]
        if len(addon.list) > 0:
            payload = self.http.post(f'https://data.wago.io/api/check/{addon.api}',
                                     json={'ids': list(addon.list.keys())}, auth=self.auth, timeout=15).json()
            if 'error' in payload or 'msg' in payload:
                raise RuntimeError
            for entry in payload:
                if 'username' in entry and (not self.username or entry['username'] != self.username):
                    if entry['slug'] not in addon.list:
                        entry['slug'] = entry['_id']
                    if (entry['version'] > addon.list[entry['slug']] and
                            (entry['slug'] not in addon.ignored or entry['version'] != addon.ignored[entry['slug']])):
                        output[0].append([entry['name'], entry['url']])
                        self.update_entry(entry, addon)
                    elif 'name' in entry:
                        output[1].append([entry['name'], entry['url']])
            output[0] = sorted(output[0], key=lambda v: v[0])
            output[1] = sorted(output[1], key=lambda v: v[0])
        return output

    @retry('Failed to parse Wago data. Wago might be down or provided API key is incorrect.')
    def check_stash(self, wa, plater):
        output = []
        if len(self.stash) > 0:
            payload = self.http.post('https://data.wago.io/api/check/',
                                     json={'ids': self.stash}, auth=self.auth, timeout=15).json()
            for entry in payload:
                output.append(entry['name'])
                raw = self.http.get(f'https://data.wago.io/api/raw/encoded?id={quote_plus(entry["slug"])}',
                                    auth=self.auth, timeout=15).text
                stash = f'        ["{entry["slug"]}"] = {{\n          name = [=[{entry["name"]}]=],\n          author' \
                        f' = [=[{entry["username"]}]=],\n          encoded = [=[{raw}]=],\n          wagoVersion = [=' \
                        f'[{entry["version"]}]=],\n          wagoSemver = [=[{entry["versionString"]}]=],\n          ' \
                        f'source = [=[Wago]=],\n          logo = [=[Interface\\AddOns\\CurseBreakerCompanion\\LogoWA.' \
                        f'tga]=],\n          versionNote = [=[]=],\n        }}' \
                        f',\n'
                if entry['type'] == 'WEAKAURA':
                    wa.data['stash'].append(stash)
                elif entry['type'] == 'PLATER':
                    plater.data['stash'].append(stash)
            output.sort()
        return output

    def parse_changelog(self, entry):
        if 'changelog' not in entry or 'text' not in entry['changelog']:
            return ''
        if entry['changelog']['format'] == 'bbcode':
            return self.bbParser.strip(entry['changelog']['text'])
        elif entry['changelog']['format'] == 'markdown':
            return self.mdParser.convert(entry['changelog']['text'])

    @retry('Failed to parse Wago data. Wago might be down or provided API key is incorrect.')
    def update_entry(self, entry, addon):
        raw = self.http.get(f'https://data.wago.io/api/raw/encoded?id={quote_plus(entry["slug"])}',
                            auth=self.auth, timeout=15).text
        slug = f'        ["{entry["slug"]}"] = {{\n          name = [=[{entry["name"]}]=],\n          author = [=[' \
               f'{entry["username"]}]=],\n          encoded = [=[{raw}]=],\n          wagoVersion = [=[' \
               f'{entry["version"]}]=],\n          wagoSemver = [=[{entry["versionString"]}]=],\n          source = [' \
               f'=[Wago]=],\n          logo = [=[Interface\\AddOns\\CurseBreakerCompanion\\LogoWA.tga]=],\n          ' \
               f'versionNote = [=[{self.parse_changelog(entry)}]=],\n' \
               f'        }},\n'
        addon.data['slugs'].append(slug)

    def install_data(self, wadata, platerdata):
        with open(Path('Interface/AddOns/CurseBreakerCompanion/Data.lua'), 'w', newline='\n', encoding='utf-8') as out:
            out.write('CurseBreakerCompanion = {\n'
                      '  WeakAuras = {\n'
                      '    slugs = {\n'
                      f'{"".join(str(x) for x in wadata["slugs"])}'
                      '    },\n'
                      '    stash = {\n'
                      f'{"".join(str(x) for x in wadata["stash"])}'
                      '    },\n'
                      '  },\n'
                      '  Plater = {\n'
                      '    slugs = {\n'
                      f'{"".join(str(x) for x in platerdata["slugs"])}'
                      '    },\n'
                      '    stash = {\n'
                      f'{"".join(str(x) for x in platerdata["stash"])}'
                      '    },\n'
                      '  },\n'
                      '}')

    def install_companion(self, force):
        target_path = Path('Interface/AddOns/CurseBreakerCompanion')
        if not os.path.isdir(target_path) or force:
            shutil.rmtree(target_path, ignore_errors=True)
            ZipFile(BytesIO(self.http.get('https://cursebreaker.acidweb.dev/CurseBreakerCompanion.zip')
                            .content)).extractall(target_path / '..')

    def update(self):
        if os.path.isdir(Path('Interface/AddOns/WeakAuras')) and os.path.isfile(
                Path(f'WTF/Account/{self.accountName}/SavedVariables/WeakAuras.lua')):
            wa = WeakAuraParser(self.accountName)
        else:
            wa = BaseParser()
        if os.path.isdir(Path('Interface/AddOns/Plater')) and os.path.isfile(
                Path(f'WTF/Account/{self.accountName}/SavedVariables/Plater.lua')):
            plater = PlaterParser(self.accountName)
        else:
            plater = BaseParser()
        statuswa = self.check_updates(wa)
        statusplater = self.check_updates(plater)
        statusstash = self.check_stash(wa, plater)
        self.install_data(wa.data, plater.data)
        return statuswa, statusplater, statusstash
