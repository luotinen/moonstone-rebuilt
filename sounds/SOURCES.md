# Substitute sounds: where each file comes from

These sounds stand in for samples that the Amiga version of Moonstone has and the DOS version lacks. None of them is
taken from, or modelled on, the original samples: each was made from a description of the sound, its length and the
rate the game plays it at. See `docs/amiga-audio-plan-2026-11-11.md`, section 5.2.

Format: mono, 8 bits, as many samples as the sample it stands in for, at the rate the game plays that sample.

## Synthesized

Made by `tools/make_substitute_sounds.py` (`python -I tools/make_substitute_sounds.py sounds chosen` writes exactly
these files; the random numbers are seeded, so the files come out the same every time). Three candidates of each were
made; the user chose these by ear on 12 Nov 2026.

Licence: **CC0 1.0** (public domain dedication, <https://creativecommons.org/publicdomain/zero/1.0/>): the nine
synthesized files may be used for anything, without credit. (The tool that makes them is under the project's
licence, like the other tools.)

| File | Stands in for | What it is | Candidate | Length |
|---|---|---|---|---|
| `beast_gallop.wav` | `BEASTGALLOP.SND` | one hoof beat of the war beast: a low, soft thud | a: one soft beat | 672 samples at 2,934 Hz (0.23 s) |
| `dragon_thud.wav` | `dragthud1c` | the dragon hits the ground: a heavy, deep thud | a: one deep thud | 4,008 at 4,655 Hz (0.86 s) |
| `trogg_bang.wav` | `bang2` | a dull bang | b: boomier | 1,832 at 4,395 Hz (0.42 s) |
| `troll_bash.wav` | `bash` | the troll's club lands: a thump with a crunch | b: heavier, less crunch | 6,670 at 11,084 Hz (0.60 s) |
| `balok_swish.wav` | `BALSWISH2b` | a big paw cuts the air: a short, heavy swish | b: heavier and lower | 1,872 at 9,852 Hz (0.19 s) |
| `guardian_sparks.wav` | `sparx2b` | sparks crackling, a steady texture | c: electric, buzzing hiss | 8,770 at 9,309 Hz (0.94 s), loops |
| `wind.wav` | `wind2` | wind over open ground | a: steady moor wind | 20,108 at 6,581 Hz (3.06 s), loops |
| `menu_click.wav` | `clik2` | a short click | b: a lower tock | 318 at 6,982 Hz (0.05 s) |
| `dice.wav` | `dice2c` | dice rattle on a table | b: wooden, fewer knocks | 2,226 at 5,533 Hz (0.40 s) |

## Recordings

Made by `tools/make_recorded_sounds.py` from recordings in the public domain: four that their authors released
under CC0 1.0 (public domain dedication) on Freesound, and one by the U.S. Fish and Wildlife Service, a work of the
U.S. federal government. The licence of each was read on its own page on 12 Nov 2026. Each file is a piece of the
recording, cut to length, turned to mono, played slower where said, band-limited to the new rate, brought to full
scale and reduced to 8 bits. The source recordings themselves are not part of Moonstone Rebuilt.

Three candidates of each were made (`python -I tools/make_recorded_sounds.py sounds candidates`, with the sources in
`sounds/sources`); the user chose these by ear on 12 Nov 2026.

Licence of these five files: **CC0 1.0**, as the synthesized ones.

| File | Stands in for | Source | Author | Licence | Processing | Length |
|---|---|---|---|---|---|---|
| `dragon_grunt.wav` | `chimpgruntloB`, the dragon's low grunt | [Alligatorbellow1.ogg](https://commons.wikimedia.org/wiki/File:Alligatorbellow1.ogg) on Wikimedia Commons: an alligator bellowing, from the Service's sound page (`fws.gov/video/sound.htm`), uploaded there by Borisblue in 2007 | U.S. Fish and Wildlife Service | Public domain (work of the U.S. federal government, `PD-USGov-FWS`) | 1.27 s from 14.88 s | 8,332 samples at 6,581 Hz (1.27 s) |
| `lion_den.wav` | `lionatmos1`, the lions' den (the game plays eight parts of it in turn) | [Lion lament](https://freesound.org/people/roman_cgr/sounds/223978/) | roman_cgr | CC0 1.0 | 1.06 s from 4.26 s | 8,273 at 7,830 Hz (1.06 s) |
| `long_scream.wav` | `rolandscreamB`, the Guardian's long scream | [human male scream 5](https://freesound.org/people/JohnsonBrandEditing/sounds/243382/) | JohnsonBrandEditing | CC0 1.0 | 1.12 s from 0.12 s, faded out | 13,924 at 12,445 Hz (1.12 s) |
| `rat_bite.wav` | `ratbite1`, a ratman's bite | [ratty squeaks.wav](https://freesound.org/people/Reitanna/sounds/217767/) | Reitanna | CC0 1.0 | 0.60 s from 3.62 s | 8,396 at 13,982 Hz (0.60 s) |
| `strain.wav` | `Strain1d`, a grunt of effort | [strenuous_grunts](https://freesound.org/people/takareads/sounds/841313/) | takareads | CC0 1.0 | 0.40 s from 6.27 s | 5,132 at 12,855 Hz (0.40 s) |

The other candidates (in `tools/make_recorded_sounds.py`, `PICKS`; all CC0 1.0 on Freesound): for the grunt a
pig's grunt by JarredGibb (233170) and a pig's growling grunt by TheKingOfGeeks360 (842313); for the den a tiger by schots (439280) and a tom
cat's purr by PostProdDog (503755); for the scream HenKonen (682177) and gtrempe (542128); for the rat Zabuhailo
(143125) and a guinea pig by TheKingOfGeeks360 (815837); for the strain salemaudio (803168) and BranndyBottle
(464677).

## Sounds with no file here

Nine samples the DOS game lacks are played with another take of the same sound that it has (the beast's second and
third roar with the first, two of the dragon's muffled cries with the third, three of the Guardian's screams with
the fourth, the troll's second grunt and the mudmen's third voice with their others). The eleven instruments of the
Amiga's location music have no substitute: the pieces are compositions.
