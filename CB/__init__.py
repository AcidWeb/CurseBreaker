import os
import httpx
import string

__version__ = '5.0.0'
__license__ = 'GPLv3'
__copyright__ = '2019-2026, Paweł Jastrzębski <pawelj@iosphe.re>'
__docformat__ = 'restructuredtext en'

FLAVORS = {
    '_retail_': ('retail', 'Retail', False),
    '_ptr_': ('retail', 'Retail PTR', True),
    '_ptr2_': ('retail', 'Retail PTR 2', True),
    '_beta_': ('retail', 'Retail Beta', True),
    '_xptr_': ('retail', 'Retail XPTR', True),
    '_classic_': ('mop', 'Mists of Pandaria Classic', False),
    '_classic_ptr_': ('mop', 'Mists of Pandaria Classic PTR', True),
    '_classic_beta_': ('mop', 'Mists of Pandaria Classic Beta', True),
    '_classic_era_': ('classic', 'Classic', False),
    '_classic_era_ptr_': ('classic', 'Classic PTR', True),
    '_anniversary_': ('bc', 'Anniversary', False),
    '_forever_': ('forever', 'Forever', False),
}
SHARED_KEYS = ('WAAAPIKey', 'WAAPIKey', 'GHAPIKey', 'WAUsername', 'Backup', 'AutoUpdate', 'AutoUpdateDelay',
               'CompactMode', 'ShowAuthors', 'ShowSources')
API_KEYS = ('WAAAPIKey', 'WAAPIKey', 'GHAPIKey')


def clean_name(name):
    return name.strip(f'{string.whitespace}​')


def is_addon_directory(name):
    return bool(name) and name not in ('.', '..') and os.path.basename(name) == name


def parse_directories(names, known=()):
    directories = {name for name in known if is_addon_directory(name)}
    for name in names:
        directory = os.path.dirname(name)
        if is_addon_directory(directory):
            directories.add(directory)
    return sorted(directories)


def retry(custom_error=False):
    def wraps(func):
        def inner(*args, **kwargs):
            description = None
            for _ in range(2):
                try:
                    result = func(*args, **kwargs)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    description = str(e).replace('Failed to parse addon data: ', '')
                    continue
                else:
                    return result
            if custom_error:
                raise RuntimeError(custom_error) from None
            elif description:
                raise RuntimeError(f'Failed to parse addon data: {description}') from None
            else:
                raise RuntimeError('Unknown error during parsing addon data. '
                                   'There may be some issue with the website.') from None
        return inner
    return wraps


class APIAuth(httpx.Auth):
    def __init__(self, header, token):
        self.header = header
        self.token = token

    def auth_flow(self, request):
        if self.token != '':
            request.headers['Authorization'] = f'{self.header} {self.token}'
        yield request
