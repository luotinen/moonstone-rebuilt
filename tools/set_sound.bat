@echo off
rem Sets the music and the sound effects together (D82). Used by the Music_*.bat and AmigaSound_*.bat switches and by
rem Start.bat:   call tools\set_sound.bat MUSIC EFFECTS
rem MUSIC: adlib, gm, mt32 or keep; EFFECTS: amiga, dos or keep (keep = as now). The music in use is read from
rem music.conf, the effects from effects.cfg ("amiga" or "dos"; without the file, from music.conf as before D82).
rem It writes music.conf from the profile of the pair (_music\profiles: adlib, gm, mt32, amiga = Amiga effects with
rem AdLib music, amiga_gm = with GM music) and effects.cfg, and copies the music's tune files to DISKA and DISKB.
rem * MT-32 music and the Amiga effects cannot play together (both need the MIDI device; the MT-32 has no SoundFont).
rem   Asking for MT-32 music turns the Amiga effects off; asking for the Amiga effects with MT-32 music gives AdLib.
rem * General MIDI uses soundfonts\default.sf2, your own, if it is there, else soundfonts\GeneralUser-GS.sf2 (shipped).
rem   With the Amiga effects it plays from _music\amiga\amiga_gm.sf2, that font merged with the effects' own
rem   (tools\merge_soundfont.py, made again here when either changed; needs Python), and the tune files of
rem   _music\gm_amiga, whose player suits the effects (D82).
rem * Missing files fall back: no MT-32 ROMs or no GM font -> AdLib music; the Amiga effects not built -> DOS effects.
rem * The Amiga intro and ending music (D87, AMIGA.FLG: AmigaMusic_On.bat) plays from the SoundFont of the Amiga
rem   effects when that has the tunes (amiga.tunes, amiga_gm.tunes beside it) and the fixed game is in use, also with
rem   the DOS effects: AdLib music then uses the amiga profile (DOSBox-X loads amiga.sf2; SAVEHOOK sends no effects to
rem   it without AMIGASND.FLG), General MIDI the amiga_gm one with the tune files of _music\gm_amiga, as with the Amiga
rem   effects. MT-32 music keeps its Roland intro and ending tunes. Start.bat puts the tune modules in DISKA.
rem Sets SOUND_MUSIC, SOUND_EFFECTS, SOUND_TUNES (the set in DISKA/DISKB), SOUND_PROFILE, SOUND_AMIGA_TUNES (1 when the
rem Amiga intro and ending music plays from the SoundFont), SOUND_SAID ("Music: ... Sound effects: ...") and SOUND_NOTE
rem (what fell back, or empty). errorlevel 1 if the files could not be set up (SOUND_NOTE says why).
set "SOUND_MUSIC=%~1"
set "SOUND_EFFECTS=%~2"
set "SOUND_NOTE="
if /i not "%SOUND_MUSIC%"=="keep" goto effects
set "SOUND_MUSIC=adlib"
if not exist music.conf goto effects
findstr /c:"= mt32" music.conf >nul && set "SOUND_MUSIC=mt32"
findstr /c:"= fluidsynth" music.conf >nul && set "SOUND_MUSIC=gm"
findstr /c:"amiga_gm.sf2" music.conf >nul && set "SOUND_MUSIC=gm"
:effects
if /i not "%SOUND_EFFECTS%"=="keep" goto chosen
set "SOUND_EFFECTS=dos"
if exist effects.cfg goto effects_file
if not exist music.conf goto chosen
findstr /c:"amiga.sf2" music.conf >nul && set "SOUND_EFFECTS=amiga"
findstr /c:"amiga_gm.sf2" music.conf >nul && set "SOUND_EFFECTS=amiga"
goto chosen
:effects_file
findstr /b /c:"amiga" effects.cfg >nul && set "SOUND_EFFECTS=amiga"
:chosen
if /i not "%SOUND_MUSIC%"=="mt32" goto no_clash
if /i not "%SOUND_EFFECTS%"=="amiga" goto no_clash
if /i "%~1"=="mt32" (
  set "SOUND_EFFECTS=dos"
  set "SOUND_NOTE=MT-32 music cannot play with the Amiga sound effects: the effects are now the DOS game's."
) else (
  set "SOUND_MUSIC=adlib"
  set "SOUND_NOTE=The Amiga sound effects cannot play with MT-32 music: the music is now AdLib (original)."
)
:no_clash
if /i "%SOUND_MUSIC%"=="mt32" if not exist "mt32-roms\*CONTROL.ROM" (
  set "SOUND_MUSIC=adlib"
  set "SOUND_NOTE=No MT-32 ROMs found in mt32-roms - using AdLib music."
)
set "SOUND_FONT=soundfonts\default.sf2"
if not exist "%SOUND_FONT%" set "SOUND_FONT=soundfonts\GeneralUser-GS.sf2"
if /i "%SOUND_MUSIC%"=="gm" if not exist "%SOUND_FONT%" (
  set "SOUND_MUSIC=adlib"
  set "SOUND_NOTE=No SoundFont in soundfonts - using AdLib music."
)
if /i "%SOUND_EFFECTS%"=="amiga" if not exist "_music\amiga\amiga.sf2" (
  set "SOUND_EFFECTS=dos"
  set "SOUND_NOTE=The Amiga sound effects are not set up - run AmigaSound_Setup.bat. Using the DOS effects."
)
set "SOUND_PROFILE=%SOUND_MUSIC%"
set "SOUND_TUNES=%SOUND_MUSIC%"
if /i "%SOUND_EFFECTS%"=="amiga" if /i "%SOUND_MUSIC%"=="adlib" set "SOUND_PROFILE=amiga"
if /i "%SOUND_EFFECTS%"=="amiga" if /i "%SOUND_MUSIC%"=="gm" call :gm_amiga
call :amiga_tunes
rem Start.bat (keep keep) with nothing to fall back: music.conf and the tune files stay as the switches left them; only
rem a GM music.conf is written again, so that it names the GM SoundFont there is now. A change of the profile (the
rem Amiga intro and ending music turned on or off, the SoundFont built or removed, original mode) writes them all.
if /i not "%~1%~2"=="keepkeep" goto write
if defined SOUND_NOTE goto write
if not exist music.conf goto write
set "SOUND_WAS=adlib"
findstr /c:"= mt32" music.conf >nul && set "SOUND_WAS=mt32"
findstr /c:"= fluidsynth" music.conf >nul && set "SOUND_WAS=gm"
findstr /c:"amiga.sf2" music.conf >nul && set "SOUND_WAS=amiga"
findstr /c:"amiga_gm.sf2" music.conf >nul && set "SOUND_WAS=amiga_gm"
if /i not "%SOUND_WAS%"=="%SOUND_PROFILE%" goto write
if /i "%SOUND_PROFILE%"=="gm" if exist "_music\profiles\gm.conf" (
  copy /y "_music\profiles\gm.conf" music.conf >nul || goto failed
  if not exist "soundfonts\default.sf2" (>> music.conf echo fluid.soundfont = soundfonts\GeneralUser-GS.sf2)
)
if not exist effects.cfg (> effects.cfg echo %SOUND_EFFECTS%)
goto said
:write
for %%F in ("_music\%SOUND_TUNES%\DISKA\*.BIN" "_music\%SOUND_TUNES%\DISKB\*.BIN" "_music\profiles\%SOUND_PROFILE%.conf") do if not exist %%F goto missing
copy /y "_music\%SOUND_TUNES%\DISKA\*.BIN" DISKA >nul || goto failed
copy /y "_music\%SOUND_TUNES%\DISKB\*.BIN" DISKB >nul || goto failed
copy /y "_music\profiles\%SOUND_PROFILE%.conf" music.conf >nul || goto failed
if /i "%SOUND_PROFILE%"=="gm" if not exist "soundfonts\default.sf2" (>> music.conf echo fluid.soundfont = soundfonts\GeneralUser-GS.sf2)
(> effects.cfg echo %SOUND_EFFECTS%) || goto failed
:said
set "SOUND_SAID=Music: AdLib (original)"
if /i "%SOUND_MUSIC%"=="gm" set "SOUND_SAID=Music: General MIDI (SoundFont)"
if /i "%SOUND_MUSIC%"=="mt32" set "SOUND_SAID=Music: Roland MT-32"
if /i "%SOUND_EFFECTS%"=="amiga" set "SOUND_SAID=%SOUND_SAID%. Sound effects: Amiga"
if /i "%SOUND_EFFECTS%"=="dos" set "SOUND_SAID=%SOUND_SAID%. Sound effects: DOS"
if defined SOUND_AMIGA_TUNES set "SOUND_SAID=%SOUND_SAID%. Intro and ending music: Amiga"
exit /b 0
:amiga_tunes
rem D87: the Amiga intro and ending music from the SoundFont, with either effects (not with MT-32 music)
set "SOUND_AMIGA_TUNES="
if not exist AMIGA.FLG exit /b 0
if exist ORIGINAL.FLG exit /b 0
if not exist "_music\amiga\font\ATUNE1.BIN" exit /b 0
if not exist "_music\amiga\font\ATUNE6.BIN" exit /b 0
if /i "%SOUND_PROFILE%"=="adlib" if exist "_music\amiga\amiga.sf2" if exist "_music\amiga\amiga.tunes" set "SOUND_PROFILE=amiga"
if /i "%SOUND_PROFILE%"=="gm" if exist "_music\amiga\amiga.tunes" call :gm_tunes
if /i "%SOUND_PROFILE%"=="amiga" if exist "_music\amiga\amiga.tunes" set "SOUND_AMIGA_TUNES=1"
if /i "%SOUND_PROFILE%"=="amiga_gm" if exist "_music\amiga\amiga_gm.tunes" set "SOUND_AMIGA_TUNES=1"
exit /b 0
:gm_tunes
rem GM music with the DOS effects and the Amiga intro and ending music: the merged SoundFont, as with the Amiga effects;
rem if it cannot be made (no Python), GM music as before with its own intro and ending tunes
if not exist "_music\gm_amiga\DISKA\ATUNE1.BIN" exit /b 0
if not exist "_music\amiga\amiga.sf2" exit /b 0
set "PY="
call tools\find_python.bat >nul 2>nul
if defined PY %PY% -I tools\merge_soundfont.py --install . >nul 2>nul
if not exist "_music\amiga\amiga_gm.sf2" exit /b 0
if not exist "_music\amiga\amiga_gm.tunes" exit /b 0
set "SOUND_PROFILE=amiga_gm"
set "SOUND_TUNES=gm_amiga"
exit /b 0
:gm_amiga
rem GM music with the Amiga effects: the merged SoundFont, made or brought up to date, and the UART tune set
if not exist "_music\gm_amiga\DISKA\ATUNE1.BIN" (
  set "SOUND_MUSIC=adlib"
  set "SOUND_PROFILE=amiga"
  set "SOUND_TUNES=adlib"
  set "SOUND_NOTE=GM music with the Amiga effects needs the files Setup.bat makes - run Setup.bat. Using AdLib music."
  exit /b 0
)
set "PY="
call tools\find_python.bat >nul 2>nul
if defined PY %PY% -I tools\merge_soundfont.py --install . >nul 2>nul
if exist "_music\amiga\amiga_gm.sf2" (
  set "SOUND_PROFILE=amiga_gm"
  set "SOUND_TUNES=gm_amiga"
  exit /b 0
)
set "SOUND_MUSIC=adlib"
set "SOUND_PROFILE=amiga"
set "SOUND_NOTE=GM music with the Amiga effects needs _music\amiga\amiga_gm.sf2, which needs Python 3 to make - using AdLib music."
exit /b 0
:missing
set "SOUND_NOTE=The music files are missing (_music). Run Setup.bat first. Nothing was changed."
exit /b 1
:failed
set "SOUND_NOTE=Copying failed: the game may be half switched. Close DOSBox-X and run the switch again."
exit /b 1
