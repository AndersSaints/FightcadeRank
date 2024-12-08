# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/ui.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/config.py', '.'),  
        ('src/api.py', '.'),     
        ('src/cache.py', '.'),   
        ('src/logger.py', '.'),  
        ('flags/*', 'flags/'),  
        ('rank/*', 'rank/'),    
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'cloudscraper',
        'requests',
        'structlog',
        'pydantic',
        'pydantic_settings',
        'concurrent.futures',
        'threading',
        'pathlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],  
    exclude_binaries=True,  
    name='FightcadeRank',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FightcadeRank'
)
