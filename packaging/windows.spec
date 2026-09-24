# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: GameROBOT Windows one-file EXE.
# Builds a single self-contained GameROBOT.exe (GUI, no console).

import os

ROOT = os.path.join(SPECPATH, "..")

a = Analysis(
    [os.path.join(ROOT, "roadmind", "__main__.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "version.json"), "."),
           (os.path.join(ROOT, "yolo11n.pt"), ".")],
    hiddenimports=[
        'mss',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'pynput._util.win32',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'pandas',
        # macOS-only frameworks (must never be pulled into a Windows build)
        'Quartz', 'AppKit', 'Foundation', 'Vision', 'ApplicationServices',
        'pyobjc', 'pyobjc-core',
        'pyobjc_framework_Quartz', 'pyobjc_framework_Cocoa',
        'pyobjc_framework_Vision', 'pyobjc_framework_CoreMedia',
    ],
    cipher=None,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GameROBOT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)