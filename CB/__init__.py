import string
import random

__version__ = '3.0.1'
__license__ = 'GPLv3'
__copyright__ = '2019, Paweł Jastrzębski <pawelj@iosphe.re>'
__docformat__ = 'restructuredtext en'


def retry(custom_error=False):
    def wraps(func):
        def inner(*args, **kwargs):
            description = None
            for i in range(2):
                try:
                    result = func(*args, **kwargs)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    description = str(e).replace('Failed to parse addon data: ', '')
                    continue
                else:
                    return result
            else:
                if custom_error:
                    raise RuntimeError(custom_error)
                else:
                    if description:
                        raise RuntimeError(f'Failed to parse addon data: {description}')
                    else:
                        raise RuntimeError('Unknown error during parsing addon data. '
                                           'There may be some issue with the website.')
        return inner
    return wraps


class AnsiCodes(object):
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37
    LIGHTBLACK_EX = 90
    LIGHTRED_EX = 91
    LIGHTGREEN_EX = 92
    LIGHTYELLOW_EX = 93
    LIGHTBLUE_EX = 94
    LIGHTMAGENTA_EX = 95
    LIGHTCYAN_EX = 96
    LIGHTWHITE_EX = 97
    RESET = 0

    def __init__(self):
        for name in dir(self):
            if not name.startswith('_'):
                setattr(self, name, '\x1b[' + str(getattr(self, name)) + 'm')


AC = AnsiCodes()
HEADERS = {'User-Agent': f'CB-{"".join(random.choices(string.ascii_uppercase + string.digits, k=10))}/{__version__}'}
