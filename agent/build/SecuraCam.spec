# SecuraCam.spec — PyInstaller packaging config for the Security Camera Agent
#
# Usage (from the agent/ directory):
#   pip install pyinstaller
#   pyinstaller build/SecuraCam.spec --clean --distpath dist/
#
# Output:
#   Windows  → dist/SecuraCam.exe        (single-file portable executable)
#   macOS    → dist/SecuraCam.app        (zip it: zip -r SecuraCam-macOS.zip dist/SecuraCam.app)
#   Linux    → dist/SecuraCam/           (wrap with appimagetool in CI)

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['../src/main.py'],
    pathex=['../src'],
    binaries=[],
    datas=[
        # Bundle the YOLO model — must be present at build time
        ('../yolov8n.pt', '.'),
        # CustomTkinter needs its theme/asset files
        *collect_data_files('customtkinter'),
        # Ultralytics config files
        *collect_data_files('ultralytics'),
    ],
    hiddenimports=[
        *collect_submodules('ultralytics'),   # dynamic internal imports
        'customtkinter',
        'pystray',
        'PIL', 'PIL._imagingtk', 'PIL.Image', 'PIL.ImageDraw',
        'tkinter', '_tkinter',                # required by CustomTkinter
    ],
    excludes=['matplotlib', 'notebook', 'IPython'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Windows: single-file portable .exe ───────────────────────────────────────
if sys.platform == 'win32':
    exe = EXE(
        pyz, a.scripts,
        a.binaries, a.zipfiles, a.datas, [],
        name='SecuraCam',
        debug=False,
        strip=False,
        upx=True,
        console=False,              # no terminal window for end users
        icon='icons/icon.ico',
    )

# ── macOS: .app bundle (LSUIElement = tray-only, no Dock icon) ───────────────
elif sys.platform == 'darwin':
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='SecuraCam',
        debug=False,
        strip=False,
        upx=False,                  # UPX unreliable on Apple Silicon
        console=False,
        icon='icons/icon.png', # Using PNG as fallback for macOS since no icns yet
    )
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
                   strip=False, upx=False, name='SecuraCam')
    app = BUNDLE(
        coll,
        name='SecuraCam.app',
        icon='icons/icon.png',
        bundle_identifier='com.securacam.agent',
        info_plist={
            'CFBundleShortVersionString': '1.1.0',
            'NSCameraUsageDescription':
                'SecuraCam needs camera access to detect people.',
            'NSHighResolutionCapable': True,
            'LSUIElement': True,    # hides from Dock; lives in menu bar only
        },
    )

# ── Linux: directory output — CI wraps it into an AppImage ───────────────────
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='SecuraCam',
        debug=False,
        strip=True,
        upx=True,
        console=False,
        icon='icons/icon.png',
    )
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
                   strip=True, upx=True, name='SecuraCam')
