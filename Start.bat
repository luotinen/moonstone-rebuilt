@echo off
rem Starts Moonstone with DOSBox-X using the settings in this folder.
cd /d "%~dp0"
set "DBX="
set "AMIGA="
if exist "C:\DOSBox-X\dosbox-x.exe" set "DBX=C:\DOSBox-X\dosbox-x.exe"
if not defined DBX if exist "%ProgramFiles%\DOSBox-X\dosbox-x.exe" set "DBX=%ProgramFiles%\DOSBox-X\dosbox-x.exe"
if not defined DBX for %%P in (dosbox-x.exe) do if not "%%~$PATH:P"=="" set "DBX=%%~$PATH:P"
if not defined DBX (
  echo DOSBox-X was not found. Install it: https://dosbox-x.com/
  pause
  exit /b 1
)
if not exist music.conf call :adlib
rem If the extra files for the chosen music are missing, AdLib music is used (otherwise the music would be silent).
findstr /c:"= mt32" music.conf >nul && if not exist "mt32-roms\*CONTROL.ROM" (
  echo No MT-32 ROMs found in mt32-roms - using AdLib music.
  call :adlib
)
findstr /c:"= fluidsynth" music.conf >nul && if not exist "soundfonts\default.sf2" (
  echo SoundFont soundfonts\default.sf2 not found - using AdLib music.
  call :adlib
)
if exist AMIGA.FLG call :amiga
if "%MOONSTONE_NOLAUNCH%"=="1" exit /b 0
rem The Amiga music player starts first (it waits for the DOSBox-X window), so that DOSBox-X, started last, gets the
rem keyboard focus; otherwise Enter and Space would not reach the game until its window is clicked.
if defined AMIGA start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0amiga_music.ps1"
start "" "%DBX%" -conf "%~dp0moonstone-dosbox-x.conf" -conf "%~dp0music.conf"
exit /b 0
:adlib
copy /y "_music\adlib\DISKA\*.BIN" DISKA >nul
copy /y "_music\adlib\DISKB\*.BIN" DISKB >nul
copy /y "_music\profiles\adlib.conf" music.conf >nul
exit /b 0
:amiga
rem Amiga intro and ending music (D8): muted DOS intro and ending tunes, amiga_music.ps1 plays the Amiga modules.
if not exist "_music\amiga\intro.wav" (
  echo Amiga music is not set up - run AmigaMusic_Setup.bat. Using the DOS music.
  exit /b 0
)
set "SET=adlib"
findstr /c:"= mt32" music.conf >nul && set "SET=mt32"
findstr /c:"= fluidsynth" music.conf >nul && set "SET=gm"
copy /y "_music\amiga\%SET%\*.BIN" DISKA >nul
set "AMIGA=1"
exit /b 0
