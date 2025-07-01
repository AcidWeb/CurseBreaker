import httpx

__version__ = '4.8.0'
__license__ = 'GPLv3'
__copyright__ = '2019-2025, Paweł Jastrzębski <pawelj@iosphe.re>'
__docformat__ = 'restructuredtext en'


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
