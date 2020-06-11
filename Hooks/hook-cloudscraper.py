from PyInstaller.utils.hooks import collect_data_files

hiddenimports = ['pyparsing']
datas = collect_data_files("cloudscraper", True)
