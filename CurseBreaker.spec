import platform
from CB import __version__ as version

block_cipher = None

if platform.system() == 'Windows':
    from PyInstaller.utils.win32 import versioninfo as vi

    tuple_version = tuple(int(i) for i in version.split('.')) + (0,)
    raw_version = vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(
            filevers=tuple_version,
            prodvers=tuple_version,
            mask=0x3f,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0)
        ),
        kids=[
            vi.StringFileInfo(
                [
                    vi.StringTable(
                        '000004B0',
                        [vi.StringStruct('FileVersion', f'{version}.0'),
                         vi.StringStruct('ProductVersion', f'{version}.0'),
                         vi.StringStruct('OriginalFilename', 'CurseBreaker.exe'),
                         vi.StringStruct('InternalName', 'CurseBreaker.exe'),
                         vi.StringStruct('FileDescription', 'CurseBreaker'),
                         vi.StringStruct('CompanyName', ' '),
                         vi.StringStruct('LegalCopyright', 'Copyright (C) 2019-2023 Paweł Jastrzębski'),
                         vi.StringStruct('ProductName', 'CurseBreaker')])
                ]),
            vi.VarFileInfo([vi.VarStruct('Translation', [0, 1200])])
        ]
    )
else:
    raw_version = None

a = Analysis(
    ['CurseBreaker.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CurseBreaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False if platform.system() == 'Windows' else True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['CurseBreaker.ico'] if platform.system() == 'Windows' else None,
    version=raw_version
)
