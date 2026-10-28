@echo off
rem Switches the game to: fixed (unpacked EXEs, K1, K2, K4, K5, K6, K9, K10, K11, K16, K17, K18, K19, K20, K21, K22, K23, K24, D6, D7, D9, D11, D12, D13, D14, D15).
cd /d "%~dp0"
for %%F in ("_fixes\fixed\MAIN.EXE" "_fixes\fixed\INTR.EXE" "_fixes\fixed\DISKA\CAMEL4") do if not exist %%F goto missing
if not exist "_fixes\fixed\SAMPLES\*" goto missing
set "SRC_MAIN=_fixes\fixed\MAIN.EXE"
rem D10: the custom rules from custom_rules.ini, if they are on (Custom_rules_on.bat)
if exist CUSTOM_RULES.FLG if exist "_fixes\rules\MAIN.EXE" set "SRC_MAIN=_fixes\rules\MAIN.EXE"
copy /y "%SRC_MAIN%" MAIN.EXE >nul || goto failed
copy /y "_fixes\fixed\INTR.EXE" INTR.EXE >nul || goto failed
rem K10: the sound effects at their real sample rates
copy /y "_fixes\fixed\SAMPLES\*" SAMPLES >nul || goto failed
copy /y "_fixes\fixed\DISKA\CAMEL4" DISKA >nul || goto failed
if exist ORIGINAL.FLG del ORIGINAL.FLG
if "%SRC_MAIN%"=="_fixes\rules\MAIN.EXE" echo Custom rules from custom_rules.ini: on
echo Game: fixed (unpacked EXEs, K1, K2, K4, K5, K6, K9, K10, K11, K16, K17, K18, K19, K20, K21, K22, K23, K24, D6, D7, D9, D11, D12, D13, D14, D15)
pause
exit /b 0
:missing
echo The fixed programs are missing (_fixes\fixed). Run Setup.bat first. Nothing was changed.
pause
exit /b 1
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
