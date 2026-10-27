# Build on the target OS. Playwright's Node driver is bundled; browser/model weights are not.
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import sys

datas, binaries, hiddenimports = collect_all('playwright')
datas += [('applylocal/resources', 'applylocal/resources')]
# Some custom Python distributions link Tcl/Tk from a nonstandard prefix.
# Standard Windows Python is handled by PyInstaller's normal Tk hooks.
if sys.platform.startswith('linux'):
    for lib in (Path(sys.base_prefix) / 'lib').glob('libtcl*.so*'):
        if lib.is_file():
            binaries.append((str(lib), '.'))
a = Analysis(['launch.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='ApplyLocal',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
