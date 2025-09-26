# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

# Get the current working directory (should be project root when script is run)
project_root = Path(os.getcwd())

# The deployment directory is where this spec file is located
deployment_root = project_root / "deployment"

# Define data files to include
datas = [
    # Frontend templates and static files
    (str(project_root / "front_end" / "templates"), "front_end/templates"),
    (str(project_root / "front_end" / "static"), "front_end/static"),
    # Configuration files if they exist
]

# NOTE: .env file is intentionally NOT included for security reasons
# Users should create their own .env file in the same directory as the executable

# Hidden imports for dynamic imports and playwright
hiddenimports = [
    # Playwright and browser automation
    "playwright",
    "playwright._impl",
    "playwright._impl._api_structures",
    "playwright._impl._connection",
    "playwright.async_api",
    "playwright.sync_api",
    # Web framework
    "quart",
    "quart.cors",
    "quart_cors",
    "hypercorn",
    # Image processing
    "PIL",
    "PIL.Image",
    "numpy",
    # PDF processing
    "pdfplumber",
    # Data processing
    "pandas",
    "openpyxl",
    # OpenAI
    "openai",
    # Other utilities
    "requests",
    "pydantic",
    "dotenv",
    "python_dotenv",
    # Async support
    "asyncio",
    "threading",
    "concurrent.futures",
    # Additional Windows-specific imports
    "multiprocessing",
    "multiprocessing.spawn",
    "multiprocessing.pool",
    "subprocess",
    "socket",
    "ssl",
    "certifi",
    "charset_normalizer",
    "urllib3",
    # Quart/Hypercorn dependencies that might be missed
    "h11",
    "wsproto",
    "trio",
    "sniffio",
    # Additional Playwright dependencies
    "greenlet",
    "pyee",
]

# Exclude unnecessary modules to reduce size
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "IPython",
    "jupyter",
    "notebook",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
]

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(deployment_root / "hooks")],
    hooksconfig={},
    runtime_hooks=[str(deployment_root / "hooks" / "hook-playwright.py")],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ez-expense",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX compression which can cause compatibility issues
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for windowed app on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # Let PyInstaller auto-detect architecture to avoid conflicts
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have one
)

# Optional: Create a .app bundle on macOS
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="EZ-Expense.app",
        icon=None,  # Add path to .icns file if you have one
        bundle_identifier="com.ez-expense.app",
        info_plist={
            "NSHighResolutionCapable": "True",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "CFBundleDisplayName": "EZ Expense",
            "NSHumanReadableCopyright": "Copyright © 2025",
            "LSBackgroundOnly": False,
        },
    )
