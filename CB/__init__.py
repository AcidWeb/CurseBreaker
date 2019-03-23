__version__ = '1.4.0'
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
                    raise RuntimeError('Failed to parse addon page. URL is wrong or your source has some issues.')
        return inner
    return wraps

