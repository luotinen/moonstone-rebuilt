# Moonstone Rebuilt

An unofficial, fan-made enhancement of **Moonstone: A Hard Days Knight** (Mindscape, 1991; DOS version 1992) that
runs the original DOS game in DOSBox-X with bug fixes, automatic saves and better sound.

**This release contains no game files.** You need your own copy of the DOS version from GOG.com. The setup copies
your game files into this folder and patches the copies; your GOG installation is not changed.

## Requirements

### Mandatory
| What | Notes |
|---|---|
| **Moonstone: A Hard Days Knight, DOS version, from GOG.com** | The unchanged GOG release. The setup checks all 280 game files by checksum and stops if any is missing or different. Other releases (CD, floppy, other stores) are not supported yet. |
| **Windows 10 or 11** | The scripts are Windows batch and PowerShell files. |
| **DOSBox-X** | Tested with version 2026.10.01. `Start.bat` looks for `C:\DOSBox-X\dosbox-x.exe`, then `%ProgramFiles%\DOSBox-X`, then the `PATH`. Download: <https://dosbox-x.com/> |
| **Python 3** | Only for the setup. On first run the setup installs the Python package `unicorn` with pip (needs an internet connection once). Download: <https://www.python.org/downloads/> and tick *Add python.exe to PATH*. |

### Optional
| What | What it adds |
|---|---|
| **Your own Amiga Moonstone disk 1** as an ADF image | Richard Joseph's Amiga intro and ending music instead of the DOS tunes. See [Amiga music](#amiga-music-optional). |
| **VLC media player** | Needed once, to turn the Amiga music into WAV files. Not needed for playing. <https://www.videolan.org/> |
| **Roland MT-32 ROMs** (`MT32_CONTROL.ROM`, `MT32_PCM.ROM`, or the CM-32L ones) | The best DOS music. Put them in `mt32-roms`, then run `Music_MT32.bat`. Tested with MT-32 v1.07 (SHA-1 of `MT32_CONTROL.ROM`: `b083518fffb7f66b03c23b7eb4f868e62dc5a987`). They are Roland's copyright; obtain them legally. |
| **A General MIDI SoundFont** (e.g. the freely distributable *GeneralUser GS*, from <https://www.schristiancollins.com/generaluser.php>) | General MIDI music. Save it as `soundfonts\default.sf2`, then run `Music_GM.bat`. Tested with GeneralUser GS 2.0.3 (rename `GeneralUser-GS.sf2` to `default.sf2`); the GM profile uses the reverb and chorus settings its author recommends for DOSBox-X. |

The setup picks the music for you: MT-32 if the ROMs are there (the music was written for it), else General MIDI if
a SoundFont is there, else the original AdLib music. Put the files in place before running `Setup.bat`, or switch later with the `Music_*.bat` files.

## Installation

1. Install the game from GOG.com, DOSBox-X and Python 3.
2. Download this release and unpack it to a folder of its own, e.g. `C:\Games\Moonstone Rebuilt`.
3. Optional: put your Amiga disk image in the `amiga` folder (see below).
4. Run **`Setup.bat`**. It finds the GOG installation by itself (GOG Galaxy or the usual folders). If it does not,
   give the folder: `Setup.bat "D:\Games\GOG\Moonstone"`.
5. Start the game with **`Start.bat`**.

`Setup.bat` can be run again at any time, e.g. after adding the Amiga disk image. It leaves your saves (`save`),
ROMs and SoundFont alone.

## Amiga music (optional)

The Amiga version has two pieces of music, the intro and the ending, both on **disk 1**. They replace the DOS intro
and ending tunes; the music inside the game stays as chosen (the Amiga version has no in-game music).

* **File name and place:** save the image of your Amiga Moonstone **disk 1** as

  ```
  amiga\Moonstone_Disk1.adf
  ```

  inside this folder (the `amiga` folder is already there). Disks 2 and 3 are not needed.
* **Format:** a standard 880 KB AmigaDOS disk image (`.adf`), made from your own original disk, e.g. with a
  Greaseweazle or KryoFlux. The setup finds the music on the disk and reports if it differs from the known version.
* **Setup:** run `Setup.bat` (or `AmigaMusic_Setup.bat` if the game is already set up). It needs VLC once.
* **On and off:** `AmigaMusic_On.bat` / `AmigaMusic_Off.bat`.

While the Amiga music is on, the DOS intro and ending tunes are silent copies, and a small helper
(`amiga_music.ps1`) plays the Amiga music beside DOSBox-X while the intro or the ending runs. It stops when you
skip the intro.

## Playing

* **Start:** `Start.bat`.
* **Skip the intro or the ending:** Enter, Space or Esc.
* **Gold:** a knight can carry at most 150 gold. Anything above that is lost, and the game does not warn you.
* **Controls:** the arrow keys move; Enter + a direction attacks (when the knight faces right):

  | Direction + Enter | Move |
  |---|---|
  | up | overhead chop |
  | forward + up | upward thrust |
  | forward | swing |
  | forward + down | lunge |
  | down | sidestep (dodges thrusts and overhead chops) |
  | back + down | block |
  | back | backward thrust |
  | back + up | dagger throw |

  Second player: W, A, S and D (up, left, down, right) plus Tab. The original used X for down; Moonstone Rebuilt
  changes it to S (D9).
* **Give up (Game Over):** Esc on the map. In the original game this was Q, next to the second player's keys, so a
  game could end by accident; Moonstone Rebuilt moves it to Esc (fix K5). It does not ask first.
* **Quit DOSBox-X:** Ctrl+F9 (asks first) or close the window.

### Saving and loading
* **Your own saves:** F11+S saves and F11+L loads, using the slot chosen under *Capture → Select save slot*
  (slot 1 by default; there are 100).
* **Automatic saves:** the game pauses for about a second and saves
  * at the start of every human player's turn on the map: slots **91–95**, shown as `PRETURN`
  * at the start of every fight: slots **96–100**, shown as `PREFIGHT`.

  Computer knights' turns are not saved. Both ranges rotate; one turn or fight often fills two slots with the same
  moment, so each range holds roughly the last two or three.
* **Loading an automatic save:** *Capture → Select save slot* → go to the last page (slots 91–100) → pick the newest
  slot by its time → *Capture → Load state* (or F11+L). Before saving by hand again, select slot 1 (or another slot
  below 91), or the next automatic save will overwrite yours.

## Options

| File | Does |
|---|---|
| `Music_AdLib.bat` / `Music_GM.bat` / `Music_MT32.bat` | Music version. If the ROMs or the SoundFont are missing, `Start.bat` falls back to AdLib. |
| `SoundCard_SoundBlaster.bat` / `SoundCard_AdLib.bat` | Sound effects as digitised samples (Sound Blaster, default) or on the AdLib synthesiser. |
| `Fixes_On.bat` / `Fixes_Off.bat` | All fixes (default) or the original game: the original programs (only unpacked, so that they run in DOSBox-X) and sound files. Saves do not carry over between the two. In original mode there are no automatic saves. |
| `AmigaMusic_On.bat` / `AmigaMusic_Off.bat` | Amiga intro and ending music on or off (after it has been set up). |
| `moonstone-dosbox-x.conf` | DOSBox-X settings: window size, shader, speed, saves. |

## What is changed

All changes are listed with details in **[FIXES.md](FIXES.md)**. In short:

* **Bug fixes:** the hidden ratmen disease that took a life point every four days is gone; duel loot no longer
  duplicates the Sword of Sharpness; the game no longer ends
  when Q is pressed by accident (Game Over is now on Esc); Math the Wizard
  and Mythral raise the right stats and say the right thing; fights can no longer run
  out of object slots; the sound effects play at their real speed; a sound that never played now
  plays; ratmen grow stronger with the moon as the manual says.
* **Improvements:** automatic saves before every fight and turn; the intro and ending can be skipped; the intro
  works in DOSBox-X; MT-32, General MIDI or AdLib music; optional Amiga intro and ending music; DOSBox-X settings
  from the GOG community (speed, joystick, black screen); 4:3 picture with crisp pixels.

The original difficulty and rules are kept.

## Known limitations

* Some fixes are worked out from the game code and not yet confirmed in play; [FIXES.md](FIXES.md) says which.
* The Amiga music starts with the intro program, so it is not in step with the DOS intro's pictures, and DOSBox-X's
  volume setting does not affect it.
* An automatic save often takes two slots (DOSBox-X's save pauses the game's wait).
* The mouse is turned off: the game does not use it, and a captured mouse disturbed the intro's keyboard handling.

## Troubleshooting

| Problem | What to do |
|---|---|
| *The GOG installation of Moonstone was not found* | Give the folder: `Setup.bat "path\to\Moonstone"`. |
| *game files are missing or different* | Verify or reinstall the game in GOG Galaxy. Only the unchanged GOG DOS release works. |
| *Python 3 is needed* | Install Python 3 with *Add python.exe to PATH* ticked, then run `Setup.bat` again. |
| *DOSBox-X was not found* | Install DOSBox-X to `C:\DOSBox-X` or add it to the `PATH`. |
| No music | Normal on the map and in fights: the game only has music in the intro, the ending and five places. If it is silent there too, run `Music_AdLib.bat`. |
| No sound effects as samples | Run `SoundCard_SoundBlaster.bat`. |
| The game freezes at the first fight or turn, or when taking a weapon after a duel | `SAVEHOOK.COM` is not running; run `Setup.bat` again. As a workaround, `Fixes_Off.bat`. |

## Credits and legal

*Moonstone: A Hard Days Knight* was designed by Rob Anderson and Todd Prescott, with music by Richard Joseph,
published by Mindscape; the DOS version is sold by GOG.com. Moonstone Rebuilt is an unofficial fan project and is
not affiliated with or endorsed by the rights holders. It contains only its own scripts, settings and tools; all game
files come from your own copy, and the Amiga music only from your own disk image. Do not share the game folder after
setup: it then contains the game's files.

## License

Copyright (C) 2026 Lauri Uotinen.

Moonstone Rebuilt's own files (scripts, settings, tools and documentation) are free software under the
**GNU General Public License v3.0**; see [LICENSE](LICENSE). The license does not cover the game itself or any file
that the setup copies or builds from your copy of the game.
