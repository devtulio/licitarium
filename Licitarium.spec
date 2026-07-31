# PyInstaller spec — gera dist/Licitarium.exe (onefile, sem console)
# Uso: pyinstaller --clean Licitarium.spec
a = Analysis(
    ['licitarium.py'],
    datas=[('ui', 'ui')],
    hiddenimports=[],
    excludes=[],
)
pyz = PYZ(a.pure)
# imagem mostrada enquanto o onefile extrai a runtime (antes do Python subir);
# o app a fecha em main() via pyi_splash
splash = Splash(
    'design/splash.png',
    binaries=a.binaries,
    datas=a.datas,
    always_on_top=False,
)
exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.datas,
    name='Licitarium',
    icon='design/licitarium.ico',
    console=False,
    upx=False,
)
