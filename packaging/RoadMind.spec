# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: RoadMind.app
# Paths are relative to this spec file so the same spec builds locally and on CI.

import os

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")
ROOT = os.path.join(SPECPATH, "..")

a = Analysis(
    [os.path.join(ROOT, "roadmind", "__main__.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "version.json"), "."),
           (os.path.join(ROOT, "yolo11n.pt"), ".")],
    hiddenimports=[
        'pynput.keyboard._darwin', 'pynput.mouse._darwin',
        'mss', 'pyobjc_framework_Quartz', 'pyobjc_framework_Vision',
        'pyobjc_framework_Cocoa', 'pyobjc_framework_CoreMedia',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas'],
    cipher=None,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='RoadMind',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name='RoadMind',
)

app = BUNDLE(
    coll,
    name='RoadMind.app',
    icon=None,
    bundle_identifier='dev.roadmind.app',
    info_plist={
        'CFBundleName': 'RoadMind',
        'CFBundleDisplayName': 'RoadMind AI Autopilot',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '12.0',
        'NSRequiresAquaSystemAppearance': False,
    },
)