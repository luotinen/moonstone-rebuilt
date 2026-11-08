@echo off
rem Starts Moonstone with DOSBox-X using the settings in this folder.
cd /d "%~dp0"
rem A setup that did not finish: its files cannot be vouched for, whatever the flags below say.
if exist SETUP.FLG goto setupfail
rem A missing lock requires rebuilding at K12; existing flags may belong to a higher rating.
if not exist PARENTAL.LCK goto locked
rem An age rating locked for good (PARENTAL.LCK below 18, or no PARENTAL.LCK: K12) needs the custom rules on.
set "AGELOCK=1"
if exist PARENTAL.LCK findstr /b /c:"18 " PARENTAL.LCK >nul && set "AGELOCK="
if defined AGELOCK (
  if exist ORIGINAL.FLG goto locked
  if not exist CUSTOM_RULES.FLG goto locked
)
rem A change of the programs that did not finish, or custom rules whose MAIN.EXE and SAVEHOOK.COM are not their own pair
if exist INSTALLING.FLG goto unfinished
if not exist CUSTOM_RULES.FLG goto paired
fc /b SAVEHOOK.COM "_fixes\rules\SAVEHOOK.COM" >nul 2>&1 || goto mismatch
if exist ORIGINAL.FLG goto paired
fc /b MAIN.EXE "_fixes\rules\MAIN.EXE" >nul 2>&1 || goto mismatch
:paired
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
if not exist music.conf call :adlib || goto musicfail
rem If the extra files for the chosen music are missing, AdLib music is used (otherwise the music would be silent).
findstr /c:"= mt32" music.conf >nul && if not exist "mt32-roms\*CONTROL.ROM" (
  echo No MT-32 ROMs found in mt32-roms - using AdLib music.
  call :adlib || goto musicfail
)
findstr /c:"= fluidsynth" music.conf >nul && if not exist "soundfonts\default.sf2" (
  echo SoundFont soundfonts\default.sf2 not found - using AdLib music.
  call :adlib || goto musicfail
)
if exist AMIGA.FLG call :amiga || goto musicfail
if "%MOONSTONE_NOLAUNCH%"=="1" exit /b 0
rem The Amiga music player starts first (it waits for the DOSBox-X window), so that DOSBox-X, started last, gets the
rem keyboard focus; otherwise Enter and Space would not reach the game until its window is clicked.
if defined AMIGA start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0amiga_music.ps1"
start "" "%DBX%" -conf "%~dp0moonstone-dosbox-x.conf" -conf "%~dp0music.conf"
exit /b 0
:adlib
for %%F in ("_music\adlib\DISKA\*.BIN" "_music\adlib\DISKB\*.BIN" "_music\profiles\adlib.conf") do if not exist %%F exit /b 1
copy /y "_music\adlib\DISKA\*.BIN" DISKA >nul || exit /b 1
copy /y "_music\adlib\DISKB\*.BIN" DISKB >nul || exit /b 1
copy /y "_music\profiles\adlib.conf" music.conf >nul || exit /b 1
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
if not exist "_music\amiga\%SET%\*.BIN" (
  echo Amiga music is not set up - run AmigaMusic_Setup.bat. Using the DOS music.
  exit /b 0
)
copy /y "_music\amiga\%SET%\*.BIN" DISKA >nul || exit /b 1
set "AMIGA=1"
exit /b 0
:musicfail
echo The music files could not be set up ^(_music^). Run Setup.bat. The game was not started.
pause
exit /b 1
:setupfail
echo The setup did not finish. Run Setup.bat. The game was not started.
pause
exit /b 1
:unfinished
echo A change of the game's programs did not finish. Close DOSBox-X and run Custom_rules_on.bat or Setup.bat. The game was not started.
pause
exit /b 1
:mismatch
echo The custom rules are on, but MAIN.EXE or SAVEHOOK.COM is not theirs. Run Custom_rules_on.bat. The game was not started.
pause
exit /b 1
:locked
echo This installation needs its age rating enforced before launch ^(no PARENTAL.LCK: K12^).
echo Set age_rating in custom_rules.ini, run Fixes_On.bat and Custom_rules_on.bat; then Start.bat starts the game.
pause
exit /b 1
