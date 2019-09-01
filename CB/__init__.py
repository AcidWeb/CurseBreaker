__version__ = '2.2.0'
__license__ = 'GPLv3'
__copyright__ = '2019, Paweł Jastrzębski <pawelj@iosphe.re>'
__docformat__ = 'restructuredtext en'


def retry(custom_error=False):
    def wraps(func):
        def inner(*args, **kwargs):
            for i in range(3):
                # noinspection PyBroadException
                try:
                    result = func(*args, **kwargs)
                except KeyboardInterrupt:
                    raise
                except Exception:
                    continue
                else:
                    return result
            else:
                if custom_error:
                    raise RuntimeError(custom_error)
                else:
                    raise RuntimeError('Failed to parse addon data. There is some issue with the website or this addon '
                                       'don\'t have release for your client version.')
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
    RESET = 39
    LIGHTBLACK_EX = 90
    LIGHTRED_EX = 91
    LIGHTGREEN_EX = 92
    LIGHTYELLOW_EX = 93
    LIGHTBLUE_EX = 94
    LIGHTMAGENTA_EX = 95
    LIGHTCYAN_EX = 96
    LIGHTWHITE_EX = 97

    def __init__(self):
        for name in dir(self):
            if not name.startswith('_'):
                setattr(self, name, '\033[' + str(getattr(self, name)) + 'm')


AC = AnsiCodes()
