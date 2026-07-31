# PyInstaller spec — gera dist/Licitarium.exe (onefile, sem console)
# Uso: pyinstaller --clean Licitarium.spec
a = Analysis(
    ['licitarium.py'],
    datas=[('ui', 'ui')],
    hiddenimports=[],
    excludes=[],
)
pyz = PYZ(a.pure)
# sem Splash() do PyInstaller de propósito: a imagem estática é fixa (não
# acompanha o tema) e aparecia antes da tela de abertura do app, dando a
# impressão de duas aberturas em sequência. Só a splash temática ficou.
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
