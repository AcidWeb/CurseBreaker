import os
import re
import bbcode
import requests
from io import StringIO
from lupa import LuaRuntime
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
        self.uids = {}
        self.ids = {}
        self.data = {'slugs': [], 'uids': [], 'ids': [], 'stash': []}


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
                    self.uids[wadata['displays'][wa]['uid']] = search.group(1)
                    self.ids[wadata['displays'][wa]['id']] = search.group(1)
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
                    self.ids[data[script]['Name']] = search.group(1)
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
                    self.ids[profile] = search.group(1)
                    if not platerdata['profiles'][profile]['ignoreWagoUpdate']:
                        if platerdata['profiles'][profile]['skipWagoUpdate']:
                            self.ignored[search.group(1)] = int(platerdata['profiles'][profile]['skipWagoUpdate'])
                        self.list[search.group(1)] = int(search.group(2))


class WagoUpdater:
    # noinspection PyTypeChecker,PyUnresolvedReferences
    def __init__(self, config, masterconfig):
        self.username = config['WAUsername']
        self.accountName = config['WAAccountName']
        self.apiKey = config['WAAPIKey']
        self.stash = config['WAStash']
        self.masterConfig = masterconfig
        self.bbParser = bbcode.Parser()
        Markdown.output_formats['plain'] = markdown_unmark_element
        self.mdParser = Markdown(output_format='plain')
        self.mdParser.stripTopLevelTags = False
        if self.username == 'DISABLED':
            self.username = ''

    def clean_string(self, s):
        return s.replace('"', '\\"')

    @retry('Failed to parse Wago data.')
    def check_updates(self, addon):
        output = [[], []]
        if len(addon.list) > 0:
            payload = requests.get(f'https://data.wago.io/api/check/{addon.api}?ids='
                                   f'{",".join(quote_plus(item) for item in addon.list.keys())}',
                                   headers={'api-key': self.apiKey, 'User-Agent': HEADERS['User-Agent']},
                                   timeout=5).json()
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

    @retry('Failed to parse Wago data.')
    def check_stash(self, addon):
        output = []
        if len(self.stash) > 0:
            payload = requests.get(f'https://data.wago.io/api/check/{addon.api}?ids='
                                   f'{",".join(quote_plus(item) for item in self.stash)}',
                                   headers={'api-key': self.apiKey, 'User-Agent': HEADERS['User-Agent']},
                                   timeout=5).json()
            for entry in payload:
                output.append(entry['name'])
                raw = requests.get(f'https://data.wago.io/api/raw/encoded?id={quote_plus(entry["slug"])}',
                                   headers={'api-key': self.apiKey, 'User-Agent': HEADERS['User-Agent']},
                                   timeout=5).text
                stash = f'        ["{entry["slug"]}"] = {{\n          name = [=[{entry["name"]}]=],\n          ' \
                        f'author = [=[{entry["username"]}]=],\n          encoded = [=[{raw}]=],\n          ' \
                        f'wagoVersion = [=[{entry["version"]}]=],\n          ' \
                        f'wagoSemver = [=[{entry["versionString"]}]=],\n        }},\n'
                addon.data['stash'].append(stash)
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

    @retry('Failed to parse Wago data.')
    def update_entry(self, entry, addon):
        raw = requests.get(f'https://data.wago.io/api/raw/encoded?id={quote_plus(entry["slug"])}',
                           headers={'api-key': self.apiKey, 'User-Agent': HEADERS['User-Agent']}, timeout=5).text
        slug = f'        ["{entry["slug"]}"] = {{\n          name = [=[{entry["name"]}]=],\n          author = [=[' \
               f'{entry["username"]}]=],\n          encoded = [=[{raw}]=],\n          wagoVersion = [=[' \
               f'{entry["version"]}]=],\n          wagoSemver = [=[{entry["versionString"]}]=],\n          ' \
               f'versionNote = [=[{self.parse_changelog(entry)}]=],\n        }},\n'
        uids = ''
        ids = ''
        for u in addon.uids:
            if addon.uids[u] == entry["slug"]:
                uids = uids + f'        ["{self.clean_string(u)}"] = [=[{entry["slug"]}]=],\n'
        for i in addon.ids:
            if addon.ids[i] == entry["slug"]:
                ids = ids + f'        ["{self.clean_string(i)}"] = [=[{entry["slug"]}]=],\n'
        addon.data['slugs'].append(slug)
        addon.data['uids'].append(uids)
        addon.data['ids'].append(ids)

    def install_data(self, wadata, platerdata):
        with open(Path('Interface/AddOns/WeakAurasCompanion/data.lua'), 'w', newline='\n', encoding='utf-8') as out:
            out.write(('-- file generated automatically\n'
                       'WeakAurasCompanion = {\n'
                       '  WeakAuras = {\n'
                       '    slugs = {\n'
                       f'{"".join(str(x) for x in wadata["slugs"])}'
                       '    },\n'
                       '    uids = {\n'
                       f'{"".join(str(x) for x in wadata["uids"])}'
                       '    },\n'
                       '    ids = {\n'
                       f'{"".join(str(x) for x in wadata["ids"])}'
                       '    },\n'
                       '    stash = {\n'
                       f'{"".join(str(x) for x in wadata["stash"])}'
                       '    },\n'
                       '  },\n'
                       '  Plater = {\n'
                       '    slugs = {\n'
                       f'{"".join(str(x) for x in platerdata["slugs"])}'
                       '    },\n'
                       '    uids = {\n'
                       '    },\n'
                       '    ids = {\n'
                       f'{"".join(str(x) for x in platerdata["ids"])}'
                       '    },\n'
                       '    stash = {\n'
                       '    },\n'
                       '  },\n'
                       '}'))

    def install_companion(self, force):
        if not os.path.isdir(Path('Interface/AddOns/WeakAurasCompanion')) or force:
            Path('Interface/AddOns/WeakAurasCompanion').mkdir(exist_ok=True)
            tocmatrix = (('', self.masterConfig['RetailTOC']),
                         ('-Classic', self.masterConfig['ClassicTOC']),
                         ('-BCC', self.masterConfig['BurningCrusadeTOC']))
            for client in tocmatrix:
                with open(Path(f'Interface/AddOns/WeakAurasCompanion/WeakAurasCompanion{client[0]}.toc'),
                          'w', newline='\n') as out:
                    out.write((f'## Interface: {client[1]}\n'
                               '## Title: WeakAuras Companion\n'
                               '## Author: The WeakAuras Team\n'
                               '## Version: 1.1.0\n'
                               '## Notes: Keep your WeakAuras updated!\n'
                               '## X-Category: Interface Enhancements\n'
                               '## DefaultState: Enabled\n'
                               '## LoadOnDemand: 0\n'
                               '## OptionalDeps: WeakAuras, Plater\n'
                               '## SavedVariables: timestamp\n\n'                   
                               'data.lua\n'
                               'init.lua'))
            with open(Path('Interface/AddOns/WeakAurasCompanion/init.lua'), 'w', newline='\n') as out:
                out.write(('-- file generated automatically\n'
                           'local loadedFrame = CreateFrame("FRAME")\n'
                           'loadedFrame:RegisterEvent("ADDON_LOADED")\n'
                           'loadedFrame:SetScript("OnEvent", function(_, _, addonName)\n'
                           '  if addonName == "WeakAurasCompanion" then\n'
                           '    timestamp = GetTime()\n'
                           '    if WeakAuras then\n'
                           '      local WeakAurasData = WeakAurasCompanion.WeakAuras\n'
                           '      -- previous version compatibility\n'
                           '      WeakAurasCompanion.slugs = WeakAurasData.slugs\n'
                           '      WeakAurasCompanion.uids = WeakAurasData.uids\n'
                           '      WeakAurasCompanion.ids = WeakAurasData.ids\n'
                           '      WeakAurasCompanion.stash = WeakAurasData.stash\n'
                           '      local count = WeakAuras.CountWagoUpdates()\n'
                           '      if count and count > 0 then\n'
                           '        WeakAuras.prettyPrint(WeakAuras.L["There are %i updates to your auras ready to be i'
                           'nstalled!"]:format(count))\n'
                           '      end\n'
                           '      if WeakAuras.ImportHistory then\n'
                           '        for id, data in pairs(WeakAurasSaved.displays) do\n'
                           '          if data.uid and not WeakAurasSaved.history[data.uid] then\n'
                           '            local slug = WeakAurasData.uids[data.uid]\n'
                           '            if slug then\n'
                           '              local wagoData = WeakAurasData.slugs[slug]\n'
                           '              if wagoData and wagoData.encoded then\n'
                           '                WeakAuras.ImportHistory(wagoData.encoded)\n'
                           '              end\n'
                           '            end\n'
                           '          end\n'
                           '        end\n'
                           '      end\n'
                           '      if WeakAurasData.stash then\n'
                           '        local emptyStash = true\n'
                           '        for _ in pairs(WeakAurasData.stash) do\n'
                           '          emptyStash = false\n'
                           '        end\n'
                           '        if not emptyStash then\n'
                           '          WeakAuras.prettyPrint(WeakAuras.L["You have new auras ready to be installed!"])\n'
                           '        end\n'
                           '      end\n'
                           '    end\n'
                           '    if Plater and Plater.CheckWagoUpdates then\n'
                           '      Plater.CheckWagoUpdates()\n'
                           '    end\n'
                           '  end\n'
                           'end)'))
            with open(Path('Interface/AddOns/WeakAurasCompanion/data.lua'), 'w', newline='\n') as out:
                out.write(('-- file generated automatically\n'
                           'WeakAurasCompanion = {\n'
                           '  WeakAuras = {\n'
                           '    slugs = {},\n'
                           '    uids = {},\n'
                           '    ids = {},\n'
                           '    stash = {},\n'
                           '  },\n'
                           '  Plater = {\n'
                           '    slugs = {},\n'
                           '    uids = {},\n'
                           '    ids = {},\n'
                           '    stash = {},\n'
                           '  },\n'
                           '}'))

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
        statusstash = self.check_stash(wa)
        statusplater = self.check_updates(plater)
        self.install_data(wa.data, plater.data)
        return statuswa, statusplater, statusstash
