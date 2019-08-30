import os
import re
import requests
from lupa import LuaRuntime
from pathlib import Path
from . import retry


class WeakAuraUpdater:
    def __init__(self, username):
        self.username = username
        self.lua = LuaRuntime()
        self.url_parser = re.compile('(\w+)/(\d+)')
        self.storage_location = []
        self.wa_outdated = []
        self.wa_list = {}
        self.locate_storage()
        self.parse_storage()

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
                if not wadata['displays'][wa]['parent'] and wadata['displays'][wa]['url']:
                    search = self.url_parser.search(wadata['displays'][wa]['url'])
                    if search.group(1) and search.group(2):
                        self.wa_list[search.group(1)] = int(search.group(2))

    @retry()
    def check_updates(self):
        payload = requests.get(f'https://data.wago.io/api/check/weakauras?ids={",".join(self.wa_list.keys())}').json()
        for aura in payload:
            if 'username' in aura and (not self.username or aura['username'] != self.username):
                if aura['version'] > self.wa_list[aura['slug']]:
                    self.wa_outdated.append(aura['name'])
        self.wa_outdated.sort()
        return self.wa_outdated

