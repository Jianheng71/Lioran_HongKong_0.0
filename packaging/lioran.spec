# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
datas = [(str(ROOT / "static"), "static")]
binaries = []
hiddenimports = ["app.main", "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto"]

for package in (
    "crawl4ai",
    "scrapling",
    "playwright",
    "patchright",
    "litellm",
    "pandas",
    "openpyxl",
    "uvicorn",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    if package == "litellm":
        package_datas = [
            item for item in package_datas if "/proxy/" not in item[0].replace("\\", "/")
        ]
        package_hiddenimports = [
            item for item in package_hiddenimports if not item.startswith("litellm.proxy")
        ]
    elif package == "pandas":
        package_datas = [
            item
            for item in package_datas
            if "/tests/" not in item[0].replace("\\", "/")
            and "/_testing/" not in item[0].replace("\\", "/")
        ]
        package_hiddenimports = [
            item for item in package_hiddenimports if not item.startswith("pandas.tests")
        ]
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

icon = ROOT / "packaging" / "generated-icons"
icon_file = icon / ("lioran.ico" if sys.platform == "win32" else "lioran.icns")

a = Analysis(
    [str(ROOT / "start.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lioran",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_file),
)
collect = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Lioran",
)

if sys.platform == "darwin":
    app = BUNDLE(
        collect,
        name="Lioran.app",
        icon=str(icon_file),
        bundle_identifier="com.jianheng71.lioran",
        info_plist={
            "CFBundleName": "Lioran",
            "CFBundleDisplayName": "Lioran",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
