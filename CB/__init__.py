import string
import random
from rich.terminal_theme import TerminalTheme

__version__ = '3.13.0'
__license__ = 'GPLv3'
__copyright__ = '2019-2020, Paweł Jastrzębski <pawelj@iosphe.re>'
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


HEADERS = {'User-Agent': f'CB-{"".join(random.choices(string.ascii_uppercase + string.digits, k=10))}/{__version__}'}
HEADLESS_TERMINAL_THEME = TerminalTheme(
    (0, 0, 0),
    (255, 255, 255),
    [
        (0, 0, 0),
        (128, 0, 0),
        (0, 128, 0),
        (128, 128, 0),
        (0, 0, 128),
        (128, 0, 128),
        (0, 128, 128),
        (192, 192, 192),
    ],
    [
        (128, 128, 128),
        (255, 0, 0),
        (0, 255, 0),
        (255, 255, 0),
        (0, 0, 255),
        (255, 0, 255),
        (0, 255, 255),
        (255, 255, 255),
    ],
)
