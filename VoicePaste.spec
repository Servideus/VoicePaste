# Build from either working directory; all inputs are relative to this spec.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_submodules
root = Path(SPECPATH)
app = root / 'voicepaste'
a = Analysis(
    [str(app / 'src/voicepaste/app.py')],
    pathex=[str(app / 'src')],
    datas=[(str(app / 'assets/icon.ico'), 'assets'),
           (str(root / 'LICENSE'), '.'),
           (str(root / 'third_party_licenses'), 'third_party_licenses')],
    hiddenimports=collect_submodules('google.genai', filter=lambda name: '.tests' not in name) + ['keyring.backends.Windows', 'win32timezone'],
)
# Windows provides these DLLs. A different ICU on PATH may expose versioned
# symbols instead of the unversioned symbols required by Qt.
system_dlls = {'ucrtbase.dll', 'icuuc.dll', 'icuin.dll', 'icudt.dll', 'icu.dll'}
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in system_dlls]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas,
    name='VoicePaste', console=os.environ.get('VOICEPASTE_DEBUG_CONSOLE') == '1', upx=False,
    icon=str(app / 'assets/icon.ico'), version=str(app / 'version_info.txt'))
