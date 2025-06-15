# -*- mode: python ; coding: utf-8 -*-
# swift_main_win.spec

block_cipher = None

a = Analysis(
    ['swift_1.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets/logo.png', 'assets')], 
    hiddenimports=['swift_2', 'swift_connect', 'swift_shared'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AtomConnect',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                   # False = no terminal window
    icon='assets/atom.ico',         # Windows icon (.ico file)
)
