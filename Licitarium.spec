# PyInstaller spec — gera dist/Licitarium.exe (onefile, sem console)
# Uso: pyinstaller --clean Licitarium.spec
a = Analysis(
    ['licitarium.py'],
    datas=[('ui', 'ui')],
    hiddenimports=[],
    excludes=[],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='Licitarium',
    icon='design/licitarium.ico',
    console=False,
    upx=False,
)
