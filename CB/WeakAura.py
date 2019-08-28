import os
import re
import requests
from pathlib import Path
from . import retry


class WeakAuraUpdater:
    def __init__(self, username):
        self.url = re.compile('(\w+)/(\d+)')
        self.username = username
        self.storage_location = []
        self.wa_outdated = []
        self.wa_ids = []
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
            with open(storage) as fp:
                for _, line in enumerate(fp):
                    if '["url"]' in line:
                        search = self.url.search(line)
                        if search.group(1) and search.group(2) and \
                                (search.group(1) not in self.wa_list.keys() or
                                 int(search.group(2)) > self.wa_list[search.group(1)]):
                            self.wa_list[search.group(1)] = int(search.group(2))
                            self.wa_ids.append(search.group(1))
        self.wa_ids = list(dict.fromkeys(self.wa_ids))

    @retry()
    def check_updates(self):
        payload = requests.get(f'https://data.wago.io/api/check/weakauras?ids={",".join(self.wa_ids)}').json()
        for aura in payload:
            if 'username' in aura and (not self.username or aura['username'] != self.username):
                if aura['version'] > self.wa_list[aura['slug']]:
                    self.wa_outdated.append(aura['name'])
        self.wa_outdated.sort()
        return self.wa_outdated

