@echo off
rem Switches the game to: fixed (unpacked EXEs, K1, K2, K4, K5, K9, K10, K11, K16, K17, K18, K19, D6, D7, D9, D11, D12, D13, D14, D15).
cd /d "%~dp0"
copy /y "_fixes\fixed\MAIN.EXE" MAIN.EXE >nul
copy /y "_fixes\fixed\INTR.EXE" INTR.EXE >nul
rem K10: the sound effects at their real sample rates
copy /y "_fixes\fixed\SAMPLES\*" SAMPLES >nul
copy /y "_fixes\fixed\DISKA\CAMEL4" DISKA >nul
if exist ORIGINAL.FLG del ORIGINAL.FLG
rem D10: the custom rules from custom_rules.ini, if they are on (Custom_rules_on.bat)
if exist CUSTOM_RULES.FLG if exist "_fixes\rules\MAIN.EXE" copy /y "_fixes\rules\MAIN.EXE" MAIN.EXE >nul
if exist CUSTOM_RULES.FLG echo Custom rules from custom_rules.ini: on
echo Game: fixed (unpacked EXEs, K1, K2, K4, K5, K9, K10, K11, K16, K17, K18, K19, D6, D7, D9, D11, D12, D13, D14, D15)
pause
