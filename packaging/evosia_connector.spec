# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for EVOSIA Connector — Windows packaging foundation.

This spec produces a directory-bundle (not single-file) containing the
EVOSIA Connector runtime. A directory bundle is preferred for:
- Better startup performance
- Easier updates (delta patches)
- Simpler debugging
- Signed-distribution compatibility

The bundle includes:
- evosia_connector package (wrapper)
- evosia_agent package (certified runtime)
- All Python dependencies
- Python runtime (embedded)
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Project root (one level up from packaging/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

# Collect all data files from evosia_agent (py.typed, etc.)
evosia_agent_datas = []
evosia_agent_pkg = os.path.join(ROOT, "evosia_agent")
if os.path.isdir(evosia_agent_pkg):
    for f in os.listdir(evosia_agent_pkg):
        if f.endswith((".pyi", ".typed")):
            evosia_agent_datas.append(
                (os.path.join(evosia_agent_pkg, f), "evosia_agent")
            )

a = Analysis(
    [os.path.join(ROOT, "evosia_connector", "__main__.py")],
    pathex=[ROOT],
    binaries=[],
    datas=evosia_agent_datas,
    hiddenimports=[
        "evosia_connector",
        "evosia_connector.version",
        "evosia_connector.config",
        "evosia_connector.launcher",
        "evosia_agent",
        "evosia_agent.agent",
        "evosia_agent.api_client",
        "evosia_agent.config",
        "evosia_agent.credential_store",
        "evosia_agent.device_identity",
        "evosia_agent.heartbeat",
        "evosia_agent.path_validation",
        "evosia_agent.project_api",
        "evosia_agent.project_registry",
        "evosia_agent.scanner",
        "evosia_agent.version",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "cv2",
        "pytest",
        "unittest",
    ],
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
    name="evosia-connector",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    name="evosia-connector",
)
