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
rem The music and the sound effects (D82, tools\set_sound.bat): music.conf and effects.cfg as the switches left them,
rem with their tune files; if the extra files for the choice are missing, AdLib music or the DOS effects are used
rem (otherwise the music would be silent). GM music with the Amiga effects plays from one SoundFont, made again here
rem when the GM SoundFont or the effects' changed.
call tools\set_sound.bat keep keep || goto musicfail
if defined SOUND_NOTE echo %SOUND_NOTE%
rem D65: SAVEHOOK.COM sends the effects to the SoundFont only while AMIGASND.FLG is there; it follows effects.cfg.
if exist AMIGASND.FLG del AMIGASND.FLG
if /i "%SOUND_EFFECTS%"=="amiga" > AMIGASND.FLG echo amiga
rem D73: and the location music while the SoundFont has it (amiga.music, written beside it when it is built
rem from the Amiga disk images).
if exist AMIGAMUS.FLG del AMIGAMUS.FLG
if exist AMIGASND.FLG if exist "_music\amiga\amiga.music" > AMIGAMUS.FLG echo music
rem D87: a tune module that plays from the SoundFont must not stay in DISKA when the SoundFont may not be there to
rem play it (AMIGA.FLG deleted by hand, the effects turned off): the DOS tunes of the set in use come back first.
if exist "_music\amiga\font\ATUNE1.BIN" call :dostunes || goto musicfail
if exist AMIGA.FLG call :amiga || goto musicfail
if "%MOONSTONE_NOLAUNCH%"=="1" exit /b 0
rem The Amiga music player (D8; not needed when the tunes play from the SoundFont, D87) starts first (it waits for
rem the DOSBox-X window), so that DOSBox-X, started last, gets the keyboard focus; otherwise Enter and Space would
rem not reach the game until its window is clicked.
if defined AMIGA start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0amiga_music.ps1"
start "" "%DBX%" -conf "%~dp0moonstone-dosbox-x.conf" -conf "%~dp0music.conf"
exit /b 0
:dostunes
fc /b DISKA\ATUNE1.BIN "_music\amiga\font\ATUNE1.BIN" >nul 2>&1 || exit /b 0
copy /y "_music\%SOUND_TUNES%\DISKA\ATUNE1.BIN" DISKA >nul || exit /b 1
copy /y "_music\%SOUND_TUNES%\DISKA\ATUNE6.BIN" DISKA >nul || exit /b 1
exit /b 0
:amiga
rem Amiga intro and ending music. D87: with the Amiga sound effects on, DOSBox-X has the SoundFont loaded, and if it
rem holds the two tunes (amiga.tunes beside amiga.sf2; amiga_gm.tunes beside the font merged with the GM one), tune
rem modules of our own play them from it, inside DOSBox-X. The fixed INTR.EXE slows the pictures to the Amiga's pace
rem for them, so not in original mode.
set "TUNES=_music\amiga\amiga.tunes"
if /i "%SOUND_PROFILE%"=="amiga_gm" set "TUNES=_music\amiga\amiga_gm.tunes"
if exist AMIGASND.FLG if not exist ORIGINAL.FLG if exist "%TUNES%" if exist "_music\amiga\font\ATUNE6.BIN" (
  copy /y "_music\amiga\font\*.BIN" DISKA >nul || exit /b 1
  exit /b 0
)
rem In every other case (D8): muted DOS intro and ending tunes, amiga_music.ps1 plays the Amiga modules.
if not exist "_music\amiga\intro.wav" (
  echo Amiga music is not set up - run AmigaMusic_Setup.bat. Using the DOS music.
  exit /b 0
)
rem The muted copies of the set in use (gm_amiga: GM music with the Amiga effects, D82)
set "SET=%SOUND_TUNES%"
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
