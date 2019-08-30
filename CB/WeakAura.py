import os
import re
import requests
from lupa import LuaRuntime
from pathlib import Path
from . import retry

# TODO: Update Companion

class WeakAuraUpdater:
    def __init__(self, username, apikey, clienttype):
        self.username = username
        self.api_key = apikey
        self.client_type = clienttype
        self.lua = LuaRuntime()
        self.url_parser = re.compile('(\w+)/(\d+)')
        self.storage_location = []
        self.wa_detected = [[], []]
        self.wa_list = {}
        self.wa_ignored = {}
        self.uid_cache = {}
        self.id_cache = {}
        self.data_cache = {'slugs': [], 'uids': [], 'ids': []}
        self.locate_storage()
        self.parse_storage()
        self.install_companion()

    def locate_storage(self):
        account_list = os.listdir(os.path.join('WTF', 'Account'))
        for account in account_list:
            storage_path = Path(f'WTF/Account/{account}/SavedVariables/WeakAuras.lua')
            if os.path.isfile(storage_path):
                self.storage_location.append(storage_path)

    def parse_storage(self):
        for storage in self.storage_location:
            with open(storage, 'r') as file:
                data = file.read().replace('WeakAurasSaved = {', '{')
            wadata = self.lua.eval(data)
            for wa in wadata['displays']:
                if wadata['displays'][wa]['url']:
                    search = self.url_parser.search(wadata['displays'][wa]['url'])
                    if search.group(1) and search.group(2):
                        self.uid_cache[wadata['displays'][wa]['uid']] = search.group(1)
                        self.id_cache[wadata['displays'][wa]['id']] = search.group(1)
                        if not wadata['displays'][wa]['parent'] and not wadata['displays'][wa]['ignoreWagoUpdate']:
                            if wadata['displays'][wa]['skipWagoUpdate']:
                                self.wa_ignored[search.group(1)] = int(wadata['displays'][wa]['skipWagoUpdate'])
                            self.wa_list[search.group(1)] = int(search.group(2))

    @retry('Failed to parse WeakAura data.')
    def check_updates(self):
        payload = requests.get(f'https://data.wago.io/api/check/weakauras?ids={",".join(self.wa_list.keys())}',
                               headers={'api-key': self.api_key}).json()
        if 'error' in payload or 'msg' in payload:
            raise RuntimeError
        for aura in payload:
            if 'username' in aura and (not self.username or aura['username'] != self.username):
                if aura['version'] > self.wa_list[aura['slug']] and\
                        (not aura['slug'] in self.wa_ignored or
                         (aura['slug'] in self.wa_ignored and aura['version'] != self.wa_ignored[aura['slug']])):
                    print(aura['version'], self.wa_list[aura['slug']])
                    self.wa_detected[0].append(aura['name'])
                    self.update_aura(aura)
                else:
                    self.wa_detected[1].append(aura['name'])
        self.wa_detected[0].sort()
        self.wa_detected[1].sort()
        self.install_data()
        return self.wa_detected

    @retry('Failed to parse WeakAura data.')
    def update_aura(self, aura):
        raw = requests.get(f'https://data.wago.io/api/raw/encoded?id={aura["slug"]}',
                           headers={'api-key': self.api_key}).text
        slug = f'    ["{aura["slug"]}"] = {{\n      name = [=[{aura["name"]}]=],\n      author = [=[' \
               f'{aura["username"]}]=],\n      encoded = [=[{raw}]=],\n      wagoVersion = [=[' \
               f'{aura["version"]}]=],\n      wagoSemver = [=[{aura["versionString"]}]=],\n    }},\n'
        uids = ''
        ids = ''
        for u in self.uid_cache:
            if self.uid_cache[u] == aura["slug"]:
                uids = uids + f'    ["{u}"] = [=[{aura["slug"]}]=],\n'
        for i in self.id_cache:
            if self.id_cache[i] == aura["slug"]:
                ids = ids + f'    ["{i}"] = [=[{aura["slug"]}]=],\n'
        self.data_cache['slugs'].append(slug)
        self.data_cache['uids'].append(uids)
        self.data_cache['ids'].append(ids)

    def install_data(self):
        with open(Path('Interface\AddOns\WeakAurasCompanion\data.lua'), 'w', newline='\n') as out:
            out.write('-- file generated automatically\nWeakAurasCompanion = {\n  slugs = {\n')
            for slug in self.data_cache['slugs']:
                out.write(slug)
            out.write('  },\n  uids = {\n')
            for uid in self.data_cache['uids']:
                out.write(uid)
            out.write('  },\n  ids = {\n')
            for ids in self.data_cache['ids']:
                out.write(ids)
            out.write('  },\n  stash = {\n  }\n}')

    def install_companion(self):
        if not os.path.isdir(Path('Interface\AddOns\WeakAurasCompanion')):
            os.mkdir(Path('Interface\AddOns\WeakAurasCompanion'))
            with open(Path('Interface\AddOns\WeakAurasCompanion\WeakAurasCompanion.toc'), 'w', newline='\n') as out:
                out.write(f'## Interface: {"11302" if self.client_type == "wow_classic" else "80200"}\n## Title: WeakAu'
                          f'ras Companion\n## Author: The WeakAuras Team\n## Version: 1.0.0\n## Notes: Keep your WeakAu'
                          f'ras updated!\n## X-Category: Interface Enhancements\n## DefaultState: Enabled\n## LoadOnDem'
                          f'and: 0\n## Dependencies: WeakAuras\n\ndata.lua\ninit.lua')
            with open(Path('Interface\AddOns\WeakAurasCompanion\init.lua'), 'w', newline='\n') as out:
                out.write('-- file generated automatically\nlocal buildTimeTarget = 20190123023201\nlocal waBuildTime ='
                          ' tonumber(WeakAuras.buildTime)\n\nif waBuildTime and waBuildTime < buildTimeTarget then\n  W'
                          'eakAurasCompanion = nil\nelse\n  local loadedFrame = CreateFrame("FRAME")\n  loadedFrame:Reg'
                          'isterEvent("ADDON_LOADED")\n  loadedFrame:SetScript("OnEvent", function(_, _, addonName)\n  '
                          '  if addonName == "WeakAurasCompanion" then\n      local count = WeakAuras.CountWagoUpdates('
                          ')\n      if count and count > 0 then\n        WeakAuras.prettyPrint(WeakAuras.L["There are %'
                          'i updates to your auras ready to be installed!"]:format(count))\n      end\n    end\n  end)'
                          '\nend')
            with open(Path('Interface\AddOns\WeakAurasCompanion\data.lua'), 'w', newline='\n') as out:
                out.write('-- file generated automatically\nWeakAurasCompanion = {\n  slugs = {\n  },\n  uids = {\n  },'
                          '\n  ids = {\n  },\n  stash = {\n  }\n}')

