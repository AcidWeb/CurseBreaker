import os
import re
import bbcode
import requests
from io import StringIO
from lupa import LuaRuntime
from pathlib import Path
from markdown import Markdown
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
        self.data = {'slugs': [], 'uids': [], 'ids': []}


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
        self.retailTOC = masterconfig['RetailTOC']
        self.classicTOC = masterconfig['ClassicTOC']
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
            payload = requests.get(f'https://data.wago.io/api/check/{addon.api}?ids={",".join(addon.list.keys())}',
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
        raw = requests.get(f'https://data.wago.io/api/raw/encoded?id={entry["slug"]}',
                           headers={'api-key': self.apiKey, 'User-Agent': HEADERS['User-Agent']}, timeout=5).text
        slug = f'    ["{entry["slug"]}"] = {{\n      name = [=[{entry["name"]}]=],\n      author = [=[' \
               f'{entry["username"]}]=],\n      encoded = [=[{raw}]=],\n      wagoVersion = [=[' \
               f'{entry["version"]}]=],\n      wagoSemver = [=[{entry["versionString"]}]=],\n      ' \
               f'versionNote = [=[{self.parse_changelog(entry)}]=],\n'
        uids = ''
        ids = ''
        for u in addon.uids:
            if addon.uids[u] == entry["slug"]:
                uids = uids + f'    ["{self.clean_string(u)}"] = [=[{entry["slug"]}]=],\n'
        for i in addon.ids:
            if addon.ids[i] == entry["slug"]:
                ids = ids + f'    ["{self.clean_string(i)}"] = [=[{entry["slug"]}]=],\n'
        addon.data['slugs'].append(slug)
        addon.data['uids'].append(uids)
        addon.data['ids'].append(ids)

    def install_data(self, wadata, platerdata):
        with open(Path('Interface/AddOns/WeakAurasCompanion/data.lua'), 'w', newline='\n', encoding='utf-8') as out:
            out.write('-- file generated automatically\nWeakAurasCompanion = {\n  slugs = {\n')
            for slug in wadata['slugs']:
                out.write(slug + '    },\n')
            out.write('  },\n  uids = {\n')
            for uid in wadata['uids']:
                out.write(uid)
            out.write('  },\n  ids = {\n')
            for ids in wadata['ids']:
                out.write(ids)
            out.write('  },\n  stash = {\n  },\n  Plater = {\n    slugs = {\n')
            for slug in platerdata['slugs']:
                out.write('  ' + slug.replace('      ', '        ') + '      },\n')
            out.write('    },\n    uids = {\n    },\n    ids = {\n')
            for ids in platerdata['ids']:
                out.write('  ' + ids)
            out.write('    },\n    stash = {\n    }\n  }\n}')

    def install_companion(self, client_type, force):
        if not os.path.isdir(Path('Interface/AddOns/WeakAurasCompanion')) or force:
            Path('Interface/AddOns/WeakAurasCompanion').mkdir(exist_ok=True)
            with open(Path('Interface/AddOns/WeakAurasCompanion/WeakAurasCompanion.toc'), 'w', newline='\n') as out:
                out.write(f'## Interface: {self.classicTOC if client_type == "wow_classic" else self.retailTOC}\n## Tit'
                          f'le: WeakAuras Companion\n## Author: The WeakAuras Team\n## Version: 1.1.1\n## Notes: Keep y'
                          f'our WeakAuas updated!\n## X-Category: Interface Enhancements\n## DefaultState: Enabled\n## '
                          f'LoadOnDemand: 0\n## OptionalDeps: WeakAuras, Plater\n\ndata.lua\ninit.lua')
            with open(Path('Interface/AddOns/WeakAurasCompanion/init.lua'), 'w', newline='\n') as out:
                out.write('-- file generated automatically\nlocal buildTimeTarget = 20190123023201\nlocal waBuildTime ='
                          ' tonumber(WeakAuras and WeakAuras.buildTime or 0)\nif waBuildTime and waBuildTime > buildTim'
                          'eTarget then\n  local loadedFrame = CreateFrame("FRAME")\n  loadedFrame:RegisterEvent("ADDON'
                          '_LOADED")\n  loadedFrame:SetScript("OnEvent", function(_, _, addonName)\n    if addonName =='
                          ' "WeakAurasCompanion" then\n      local count = WeakAuras.CountWagoUpdates()\n      if count'
                          ' and count > 0 then\n        WeakAuras.prettyPrint(WeakAuras.L["There are %i updates to your'
                          ' auras ready to be installed!"]:format(count))\n      end\n      if WeakAuras.ImportHistory '
                          'then\n        for id, data in pairs(WeakAurasSaved.displays) do\n          if data.uid and n'
                          'ot WeakAurasSaved.history[data.uid] then\n            local slug = WeakAurasCompanion.uids[d'
                          'ata.uid]\n            if slug then\n              local wagoData = WeakAurasCompanion.slugs['
                          'slug]\n              if wagoData and wagoData.encoded then\n                WeakAuras.Import'
                          'History(wagoData.encoded)\n              end\n            end\n          end\n        end\n '
                          '     end\n      local emptyStash = true\n      for _ in pairs(WeakAurasCompanion.stash) do\n'
                          '        emptyStash = false\n      end\n      if not emptyStash and WeakAuras.StashShow then'
                          '\n        C_Timer.After(5, function() WeakAuras.StashShow() end)\n      end\n    end\n  end)'
                          '\nend\n\nif Plater and Plater.CheckWagoUpdates then\n    Plater.CheckWagoUpdates()\nend')
            with open(Path('Interface/AddOns/WeakAurasCompanion/data.lua'), 'w', newline='\n') as out:
                out.write('-- file generated automatically\nWeakAurasCompanion = {\n  slugs = {\n  },\n  uids = {\n  },'
                          '\n  ids = {\n  },\n  stash = {\n  },\n  Plater = {\n    slugs = {\n    },\n    uids = {\n   '
                          ' },\n    ids = {\n    },\n    stash = {\n    },\n  },\n}')

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
        self.install_data(wa.data, plater.data)
        return statuswa, statusplater
