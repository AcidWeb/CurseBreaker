import os
import re
import shutil
import bbcode
import requests
from io import StringIO
from lupa import LuaRuntime
from base64 import b64decode
from pathlib import Path
from markdown import Markdown
from urllib.parse import quote_plus
from . import retry, HEADERS


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


class BaseParser:
    def __init__(self):
        self.lua = LuaRuntime()
        self.urlParser = re.compile('/([a-zA-Z0-9_-]+)/(\d+)')
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
        with open(Path(f'WTF/Account/{self.accountName}/SavedVariables/WeakAuras.lua'), 'r', encoding='utf-8',
                  errors='ignore') as file:
            data = file.read().replace('WeakAurasSaved = {', '{')
        wadata = self.lua.eval(data)
        for wa in wadata['displays']:
            if wadata['displays'][wa]['url']:
                search = self.urlParser.search(wadata['displays'][wa]['url'])
                if search is not None and search.group(1) and search.group(2):
                    if not wadata['displays'][wa]['parent'] and not wadata['displays'][wa]['ignoreWagoUpdate']:
                        if wadata['displays'][wa]['skipWagoUpdate']:
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
            if data[script]['url']:
                search = self.urlParser.search(data[script]['url'])
                if search is not None and search.group(1) and search.group(2):
                    if not data[script]['ignoreWagoUpdate']:
                        if data[script]['skipWagoUpdate']:
                            self.ignored[search.group(1)] = int(data[script]['skipWagoUpdate'])
                        self.list[search.group(1)] = int(search.group(2))

    def parse_storage(self):
        with open(Path(f'WTF/Account/{self.accountName}/SavedVariables/Plater.lua'), 'r', encoding='utf-8',
                  errors='ignore') as file:
            data = file.read().replace('PlaterDB = {', '{')
        platerdata = self.lua.eval(data)
        for profile in platerdata['profiles']:
            data = platerdata['profiles'][profile]['script_data']
            if data:
                self.parse_storage_internal(data)
            data = platerdata['profiles'][profile]['hook_data']
            if data:
                self.parse_storage_internal(data)
            data = platerdata['profiles'][profile]['url']
            if data:
                search = self.urlParser.search(data)
                if search is not None and search.group(1) and search.group(2):
                    if not platerdata['profiles'][profile]['ignoreWagoUpdate']:
                        if platerdata['profiles'][profile]['skipWagoUpdate']:
                            self.ignored[search.group(1)] = int(platerdata['profiles'][profile]['skipWagoUpdate'])
                        self.list[search.group(1)] = int(search.group(2))


class WagoUpdater:
    # noinspection PyTypeChecker
    def __init__(self, config, clienttoc):
        self.username = config['WAUsername']
        self.accountName = config['WAAccountName']
        self.stash = config['WAStash']
        self.clientTOC = clienttoc
        self.bbParser = bbcode.Parser()
        Markdown.output_formats['plain'] = markdown_unmark_element
        self.mdParser = Markdown(output_format='plain')
        self.mdParser.stripTopLevelTags = False
        self.headers = HEADERS
        if self.username == 'DISABLED':
            self.username = ''
        if config['WAAPIKey'] != '':
            self.headers = dict({'api-key': config['WAAPIKey']}, **HEADERS)

    def clean_string(self, s):
        return s.replace('"', '\\"')

    @retry('Failed to parse Wago data. Wago might be down or provided API key is incorrect.')
    def check_updates(self, addon):
        output = [[], []]
        if len(addon.list) > 0:
            payload = requests.get(f'https://data.wago.io/api/check/{addon.api}?ids='
                                   f'{",".join(quote_plus(item) for item in addon.list.keys())}', headers=self.headers,
                                   timeout=15).json()
            if 'error' in payload or 'msg' in payload:
                raise RuntimeError
            for entry in payload:
                if 'username' in entry and (not self.username or entry['username'] != self.username):
                    if not entry['slug'] in addon.list:
                        entry['slug'] = entry['_id']
                    if entry['version'] > addon.list[entry['slug']] and (not entry['slug'] in addon.ignored or
                       (entry['slug'] in addon.ignored and entry['version'] != addon.ignored[entry['slug']])):
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
            payload = requests.get(f'https://data.wago.io/api/check/?ids='
                                   f'{",".join(quote_plus(item) for item in self.stash)}',
                                   headers=self.headers, timeout=15).json()
            for entry in payload:
                output.append(entry['name'])
                raw = requests.get(f'https://data.wago.io/api/raw/encoded?id={quote_plus(entry["slug"])}',
                                   headers=self.headers, timeout=15).text
                stash = f'        ["{entry["slug"]}"] = {{\n          name = [=[{entry["name"]}]=],\n          author' \
                        f' = [=[{entry["username"]}]=],\n          encoded = [=[{raw}]=],\n          wagoVersion = [=' \
                        f'[{entry["version"]}]=],\n          wagoSemver = [=[{entry["versionString"]}]=],\n          ' \
                        f'source = [=[Wago]=],\n          logo = [=[Interface\AddOns\CurseBreakerCompanion\Logo.tga]=' \
                        f'],\n          versionNote = [=[]=],\n        }}' \
                        f',\n'
                if entry['type'] == 'WEAKAURA':
                    wa.data['stash'].append(stash)
                elif entry['type'] == 'PLATER':
                    plater.data['stash'].append(stash)
            output.sort()
        return output

    def parse_changelog(self, entry):
        if 'changelog' in entry and 'text' in entry['changelog']:
            if entry['changelog']['format'] == 'bbcode':
                return self.bbParser.strip(entry['changelog']['text'])
            elif entry['changelog']['format'] == 'markdown':
                return self.mdParser.convert(entry['changelog']['text'])
        else:
            return ''

    @retry('Failed to parse Wago data. Wago might be down or provided API key is incorrect.')
    def update_entry(self, entry, addon):
        raw = requests.get(f'https://data.wago.io/api/raw/encoded?id={quote_plus(entry["slug"])}', headers=self.headers,
                           timeout=15).text
        slug = f'        ["{entry["slug"]}"] = {{\n          name = [=[{entry["name"]}]=],\n          author = [=[' \
               f'{entry["username"]}]=],\n          encoded = [=[{raw}]=],\n          wagoVersion = [=[' \
               f'{entry["version"]}]=],\n          wagoSemver = [=[{entry["versionString"]}]=],\n          source = [' \
               f'=[Wago]=],\n          logo = [=[Interface\AddOns\CurseBreakerCompanion\Logo.tga]=],\n          versi' \
               f'onNote = [=[{self.parse_changelog(entry)}]=],\n' \
               f'        }},\n'
        addon.data['slugs'].append(slug)

    def install_data(self, wadata, platerdata):
        with open(Path('Interface/AddOns/CurseBreakerCompanion/Data.lua'), 'w', newline='\n', encoding='utf-8') as out:
            out.write(('CurseBreakerCompanion = {\n'
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
                       '}'))

    def install_companion(self, force):
        if not os.path.isdir(Path('Interface/AddOns/CurseBreakerCompanion')) or force:
            shutil.rmtree(Path('Interface/AddOns/CurseBreakerCompanion'), ignore_errors=True)
            Path('Interface/AddOns/CurseBreakerCompanion').mkdir(exist_ok=True)
            with open(Path(f'Interface/AddOns/CurseBreakerCompanion/CurseBreakerCompanion.toc'),
                      'w', newline='\n') as out:
                out.write((f'## Interface: {self.clientTOC}\n'
                           '## Title: CurseBreaker Companion\n'
                           '## Notes: CurseBreaker -> WoW integration.\n'
                           '## Version: 1.1.0\n'
                           '## Author: AcidWeb\n'
                           '## OptionalDeps: WeakAuras, Plater\n\n'                  
                           'Data.lua\n'
                           'Init.lua'))
            with open(Path('Interface/AddOns/CurseBreakerCompanion/Init.lua'), 'w', newline='\n') as out:
                out.write(('local loadedFrame = CreateFrame("FRAME")\n'
                           'loadedFrame:RegisterEvent("ADDON_LOADED")\n'
                           'loadedFrame:SetScript("OnEvent", function(self, _, addonName)\n'
                           '  if addonName == "CurseBreakerCompanion" then\n'
                           '    if WeakAuras and WeakAuras.AddCompanionData then\n'
                           '      WeakAuras.AddCompanionData(CurseBreakerCompanion.WeakAuras)\n'
                           '    end\n'
                           '    if Plater and Plater.AddCompanionData then\n'
                           '      Plater.AddCompanionData(CurseBreakerCompanion.Plater)\n'
                           '    end\n'
                           '    self:UnregisterEvent("ADDON_LOADED")\n'
                           '  end\n'
                           'end)'))
            with open(Path('Interface/AddOns/CurseBreakerCompanion/Data.lua'), 'w', newline='\n') as out:
                out.write(('CurseBreakerCompanion = {\n'
                           '  WeakAuras = {\n'
                           '    slugs = {},\n'
                           '    stash = {},\n'
                           '  },\n'
                           '  Plater = {\n'
                           '    slugs = {},\n'
                           '    stash = {},\n'
                           '  },\n'
                           '}'))
            with open(Path('Interface/AddOns/CurseBreakerCompanion/Logo.tga'), 'wb') as out:
                out.write(b64decode(b'AAAKAAAAAAAAAAAAIAAgACAInwAAAACfAAAAAJ8AAAAAnwAAAACfAAAAAJ8AAAAAnwAAAACfAAAAAJEAA'
                                    b'AAAAwAAABkAAAA1AAAALwAAAAGJAAAAAIcAAAAAAAAAAAqEAAAACwAAAAAMgQAAADwGAAAADAICC14nIW'
                                    b'P1CAYhpwAAAA4AAAALAAAACocAAAAAhwAAAAABEREk7iQkRfSCJSVG9AElJUX0Ghoz9YEEBgv5BhoaM/U'
                                    b'bGjX4SD2t/xkXP/skJEX1JCRF9BERJO6HAAAAAIcAAAAABiQkQ/8YNkj/KmiD/ypphP8jWG//I1lw/zJ/'
                                    b'nv+BLnSR/wYyf57/IFBm/0g+rv8bNVP/HUhc/xcyQ/8kJEP/hwAAAACHAAAAAAQkJET/KmmD/1HG9v9Sy'
                                    b'fn/Ucj3/4FSyvr/gT+dw/8GU839/z+bwf9JP6//LWmK/1HG9f8qaYT/JCRE/4cAAAAAhwAAAAAPJCRE/y'
                                    b'diev8gVGr/M4Gg/x1NYP9CpMv/Km2H/zWDo/8/ncP/VM7//z+dw/9JP6//LmuM/1LJ+f8ra4X/JCRE/4c'
                                    b'AAAAAhwAAAAAPJCRE/ydiev8nZH7/O5K1/ylpgv82iKr/KmuF/zWDo/8/ncP/VM7//z+dw/9JP6//LmuM'
                                    b'/1LJ+f8ra4X/JCRE/4cAAAAAhwAAAAAPJCRE/ytqhP9QxfT/Usr6/1LJ+f9Ty/v/Ucj4/z+dwv8/ncP/V'
                                    b'M7//z+dw/9JP6//LmuM/1LJ+f8ra4X/JCRE/4cAAAAAhwAAAAAPJCRE/ydie/8kWnD/M4Cg/yxxjf8/nM'
                                    b'L/KWiB/zSBof8/ncP/VM7//z+dw/9JP6//LmuM/1LJ+f8ra4X/JCRE/4cAAAAAhwAAAAAPJCRE/yhkff8'
                                    b'nY3v/PJa6/xxLXv86kLL/G0ZX/y1viv8/ncP/VM7//z+dw/9JP6//LmuM/1LJ+f8ra4X/JCRE/4cAAAAA'
                                    b'hwAAAAAPJCRE/ytqhf9Rx/b/U8r7/1HG9v9Syvr/Ucf3/z6av/8/ncP/VM7//z+dw/9JP6//LmuM/1LJ+'
                                    b'f8ra4X/JCRE/4cAAAAAhwAAAAAPJCRE/ypngf82hqf/OpCz/ydje/81h6j/KWmD/yhkff8/ncP/VM7//z'
                                    b'+dw/9JP6//LmuM/1LJ+f8ra4X/JCRE/4cAAAAAhwAAAAAPIyND/yhjfP8iV2z/Mn+e/yhlff9Co8r/Hk9'
                                    b'j/zqPsv8/ncP/VM7//z+dw/9JP6//LmuM/1LJ+f8ra4X/IyND/4cAAAAAhwAAAAAPDw8g7ylogv9QxPP/'
                                    b'R7Db/1DF9f9RyPj/TLrm/zJ/nfwudpP8SbPe/z6Yvv9JP6//LWmJ/1DG9f8paIL/Dw8g74cAAAAAhwAAA'
                                    b'AAPAAAAEQUZIpsRN0amCiYyphE3RqYROEemDzJAmAUZIWICCA1jCyk1mAokMcM2LoX6Dhgz3hA2RagFGS'
                                    b'KbAAAAEIcAAAAAiAAAAAAAAAAAA4IAAAAEAQAAAAMAAAACgQAAAAAFAAAAAgAAARsDAw9XAAACNQAAAAQ'
                                    b'AAAADiAAAAACfAAAAAJ8AAAAAnwAAAACfAAAAAJ8AAAAAnwAAAACfAAAAAJ8AAAAAAAAAAAAAAABUUlVF'
                                    b'VklTSU9OLVhGSUxFLgA='))

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
