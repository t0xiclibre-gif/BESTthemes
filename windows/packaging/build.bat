@echo off
rem Construit BESTthemes-Setup.exe et BESTthemes-Portable.exe sur un PC Windows
rem (Python 3.11+ et Inno Setup 6 requis).
cd /d "%~dp0\..\.."
python -m pip install -r windows\requirements.txt pyinstaller || exit /b 1
python -m unittest discover -s windows\tests -t windows || exit /b 1
python -m PyInstaller windows\packaging\bestthemes_win.spec --noconfirm --distpath dist --workpath build || exit /b 1
dist\BESTthemes\BESTthemes.exe --selftest || exit /b 1
python -m PyInstaller windows\packaging\bestthemes_win_portable.spec --noconfirm --distpath dist --workpath build\portable || exit /b 1
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" windows\packaging\installer.iss || exit /b 1
echo.
echo Installateur et version portable prets dans le dossier dist\
