import os
import re
import requests
from lupa import LuaRuntime
from pathlib import Path
from . import retry, HEADERS


class WagoUpdater:
    def __init__(self, username, accountname, apikey):
        self.username = username
        self.accountName = accountname
        self.apiKey = apikey
        self.lua = LuaRuntime()
        self.urlParser = re.compile('/([a-zA-Z0-9_-]+)/(\d+)')
        self.waList = {}
        self.waIgnored = {}
        self.uidCache = {}
        self.idCache = {}
        self.dataCache = {'slugs': [], 'uids': [], 'ids': []}
        if self.username == 'DISABLED':
            self.username = ''
        if not os.path.isfile(Path(f'WTF/Account/{self.accountName}/SavedVariables/WeakAuras.lua')):
            raise RuntimeError('Incorrect WoW account name!')

    def parse_storage(self):
        with open(Path(f'WTF/Account/{self.accountName}/SavedVariables/WeakAuras.lua'), 'r', encoding='utf-8') as file:
            data = file.read().replace('WeakAurasSaved = {', '{')
        wadata = self.lua.eval(data)
        for wa in wadata['displays']:
            if wadata['displays'][wa]['url']:
                search = self.urlParser.search(wadata['displays'][wa]['url'])
                if search is not None and search.group(1) and search.group(2):
                    self.uidCache[wadata['displays'][wa]['uid']] = search.group(1)
                    self.idCache[wadata['displays'][wa]['id']] = search.group(1)
                    if not wadata['displays'][wa]['parent'] and not wadata['displays'][wa]['ignoreWagoUpdate']:
                        if wadata['displays'][wa]['skipWagoUpdate']:
                            self.waIgnored[search.group(1)] = int(wadata['displays'][wa]['skipWagoUpdate'])
                        self.waList[search.group(1)] = int(search.group(2))

    @retry('Failed to parse WeakAura data.')
    def check_updates(self):
        wa = [[], []]
        if len(self.waList) > 0:
            payload = requests.get(f'https://data.wago.io/api/check/weakauras?ids={",".join(self.waList.keys())}',
                                   headers={'api-key': self.apiKey, 'User-Agent': HEADERS['User-Agent']}).json()
            if 'error' in payload or 'msg' in payload:
                raise RuntimeError
            for aura in payload:
                if 'username' in aura and (not self.username or aura['username'] != self.username):
                    if not aura['slug'] in self.waList:
                        aura['slug'] = aura['_id']
                    if aura['version'] > self.waList[aura['slug']] and \
                       (not aura['slug'] in self.waIgnored or
                       (aura['slug'] in self.waIgnored and aura['version'] != self.waIgnored[aura['slug']])):
                        wa[0].append(aura['name'])
                        self.update_aura(aura)
                    else:
                        wa[1].append(aura['name'])
            wa[0].sort()
            wa[1].sort()
        return wa

    @retry('Failed to parse WeakAura data.')
    def update_aura(self, aura):
        raw = requests.get(f'https://data.wago.io/api/raw/encoded?id={aura["slug"]}',
                           headers={'api-key': self.apiKey, 'User-Agent': HEADERS['User-Agent']}).text
        slug = f'    ["{aura["slug"]}"] = {{\n      name = [=[{aura["name"]}]=],\n      author = [=[' \
               f'{aura["username"]}]=],\n      encoded = [=[{raw}]=],\n      wagoVersion = [=[' \
               f'{aura["version"]}]=],\n      wagoSemver = [=[{aura["versionString"]}]=],\n    }},\n'
        uids = ''
        ids = ''
        for u in self.uidCache:
            if self.uidCache[u] == aura["slug"]:
                uids = uids + f'    ["{u}"] = [=[{aura["slug"]}]=],\n'
        for i in self.idCache:
            if self.idCache[i] == aura["slug"]:
                ids = ids + f'    ["{i}"] = [=[{aura["slug"]}]=],\n'
        self.dataCache['slugs'].append(slug)
        self.dataCache['uids'].append(uids)
        self.dataCache['ids'].append(ids)

    def install_data(self):
        with open(Path('Interface/AddOns/WeakAurasCompanion/data.lua'), 'w', newline='\n', encoding='utf-8') as out:
            out.write('-- file generated automatically\nWeakAurasCompanion = {\n  slugs = {\n')
            for slug in self.dataCache['slugs']:
                out.write(slug)
            out.write('  },\n  uids = {\n')
            for uid in self.dataCache['uids']:
                out.write(uid)
            out.write('  },\n  ids = {\n')
            for ids in self.dataCache['ids']:
                out.write(ids)
            out.write('  },\n  stash = {\n  }\n}')

    def install_companion(self, client_type, force):
        if not os.path.isdir(Path('Interface/AddOns/WeakAurasCompanion')) or force:
            Path('Interface/AddOns/WeakAurasCompanion').mkdir(exist_ok=True)
            with open(Path('Interface/AddOns/WeakAurasCompanion/WeakAurasCompanion.toc'), 'w', newline='\n') as out:
                out.write(f'## Interface: {"11304" if client_type == "wow_classic" else "80300"}\n## Title: WeakAu'
                          f'ras Companion\n## Author: The WeakAuras Team\n## Version: 1.1.0\n## Notes: Keep your WeakAu'
                          f'ras updated!\n## X-Category: Interface Enhancements\n## DefaultState: Enabled\n## LoadOnDem'
                          f'and: 0\n## OptionalDeps: WeakAuras, Plater\n\ndata.lua\ninit.lua')
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
