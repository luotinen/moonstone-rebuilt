"""Byte patches for the uncompressed MAIN.EXE (see make_main_exe.py). Each patch names its address in the
running program (segment:offset in the load-segment-1000h image, or DS:offset with DS = 223Bh), the original bytes
it expects and the new bytes, so a patch can never be applied to the wrong file. Fix ids match docs/remake.md (K1...)."""
import struct

LOAD_SEG, DS_SEG = 0x1000, 0x223b

PATCHES = {
    'K1': {
        'title': 'CHEAP1B sample: the sample name table lists "cheap2b" twice (DS:8721, entries 8 and 9); '
                 'entry 8 is meant to be cheap1b (the list is alphabetical), so CHEAP1B was never played',
        'bytes': [(('DS', 0x87c1), b'cheap2b\0', b'cheap1b\0')],
    },
    'K2': {
        'title': 'Ratmen grow stronger as the moon waxes (manual). The ratmen setup at 1000:23fe used its strong '
                 'stats (7 HP, bite 6, claw 3) at full moon (2Dh) and its strongest (12 HP, bite 8, claw 5) at new moon '
                 '(31h). Now: strongest at full moon, strong at three-quarter moon (2Fh), normal otherwise',
        'bytes': [((0x1000, 0x240c), b'\x83\x3e\x89\x89\x2d', b'\x83\x3e\x89\x89\x2f'),   # strong:    full -> 3/4
                  ((0x1000, 0x2427), b'\x83\x3e\x89\x89\x31', b'\x83\x3e\x89\x89\x2d')],  # strongest: new  -> full
    },
    'K4': {
        'title': 'Object slot leak in fights (a safeguard: in play a fight uses about 8-9 of the 10 animation slots). '
                 'New fight objects (fire, hit effects, daggers) are made at 1000:3E89: a game object slot (20 at DS:6F08) and '
                 'an animation slot (10 at DS:947E, call 981F). When the animation slots are full, 981F returns AX=1, which '
                 'was ignored: the game slot stayed taken for the rest of the fight, and with all 20 gone the next object '
                 'was written past the table (DS:76B0). Now the routine ends with [di] = AX xor 1, which frees the game slot '
                 'when the animation slot could not be had (2A1E has already set [di] to 1, so the old mov word [di],1 '
                 'was redundant)',
        'bytes': [((0x1000, 0x3ea5), bytes.fromhex('c7050100885535e87059c3'),      # mov word [di],1 / mov [di+35h],dl /
                                                                                    # call 981F / ret
                                     bytes.fromhex('885535e874593401' '8805c3'))],  # mov [di+35h],dl / call 981F /
    },                                                                              # xor al,1 / mov [di],al / ret
    'K5': {
        'title': 'Quit key moved from Q to Esc. On the map the turn loop (1000:A594) checks Q (scan code 10h) with the '
                 'key check at 8288 and goes straight to GAME OVER, without asking, during any knight\'s turn. Q is '
                 'next to W and A, the second player\'s movement keys, so the game could end by accident (the '
                 '"unexpected Game Over" reports). Esc (01h) is far from the movement keys; MAIN uses it only in the '
                 'menu before a game',
        'bytes': [((0x1000, 0xa594), b'\xb8\x10\x00', b'\xb8\x01\x00')],   # mov ax,10h (Q) -> mov ax,01h (Esc)
    },
    'K11': {
        'title': 'Math and Mythral read their stat tables wrongly (confirmed in play for Math: only strength ever rose, '
                 'and twice Math printed a long list of game data). Math (1000:B9C2, also used when the Guardian wins at '
                 '0FF8) steps through the 4-byte table at DS:E33B (stat field, message) 8 bytes per index, and the caller '
                 'reads the message at [si+ax+4]: strength 5/16, constitution 3/16, endurance never, 8/16 a field that is '
                 'not a stat, and never the right message. Mythral (1000:BBD5) searches only 2 of the 3 entries of '
                 'DS:DE04 / DE1C (stat field, message record) and takes [si+4] instead of [si+2]. Now Math gives strength '
                 '5/16, endurance 5/16, constitution 6/16 with the matching line, and Mythral the right message for every '
                 'stat, gain and loss',
        'bytes': [((0x1000, 0xb9e2), b'\xd1\xe0', b'\x90\x90'),                         # shl ax,1 -> nop nop (index *4)
                  ((0x1000, 0xb972), b'\x03\xf0\xff\x74\x04', b'\x90\x90\xff\x74\x02'),  # add si,ax / push [si+4]
                                                                                    #   -> nop nop / push [si+2]
                  ((0x1000, 0xbbd5), b'\xb9\x02\x00', b'\xb9\x03\x00'),               # mov cx,2 -> mov cx,3
                  ((0x1000, 0xbbe7), b'\x8b\x74\x04', b'\x8b\x74\x02')],              # mov si,[si+4] -> [si+2]
    },
    'K16': {
        'title': 'Duel looting. (1) The weapon pick on the loot screen (1000:ce91) moved only the weapon number, so a '
                 'knight who took the Sword of Sharpness got it without the sword item, and the loser kept the item '
                 'and was re-armed with it: two swords. The compare and store after the long-sword check become '
                 'int 62h, which SAVEHOOK.COM handles: it also moves the item when the weapon is 19h (needs '
                 'SAVEHOOK.COM resident, like D6). (2) The automatic loot of a computer winner (1000:0b8e) moved the '
                 'hit points of the old armour of the winner instead of the armour taken; push/pop ax go. (3) When '
                 'the loser has no lives left, the sword is now set as the weapon of the winner (1000:0c4b), not of '
                 'the loser. (4) The stat raise of a computer knight after a duel win (1000:04bd) had no cap; it now '
                 'stops at 5 like the human level-up (1000:d58b) and keeps the XP when the stat is already 5',
        'bytes': [((0x1000, 0xce99), b'\x3b\x6c\x40\x7c\x03', b'\xcd\x62\xeb\x04\x90'),   # int 62h / jmp cea1
                  ((0x1000, 0x0b96), b'\x50', b'\x90'),                                     # push ax -> nop
                  ((0x1000, 0x0b9d), b'\x58', b'\x90'),                                     # pop ax -> nop
                  ((0x1000, 0x0c4b), b'\xc7\x45\x40', b'\xc7\x44\x40'),                     # [di+40h] -> [si+40h]
                  ((0x1000, 0x04bd), bytes.fromhex('2503003d02007e03b802008bd8fe402e83fb0175048344380a'),
                                     bytes.fromhex('2503003c0314ff8bd880782e057d18fe402e4b75048344380a'))],
        # and ax,3 / cmp al,3 / adc al,-1 (3 -> 2) / mov bx,ax / cmp byte [bx+si+2Eh],5 / jge 04e6 (no raise, no XP
        # spent) / inc byte [bx+si+2Eh] / dec bx / jnz 04d6 / add word [si+38h],10 (CON: +10 HP)
    },
    'K17': {
        'title': 'Ratmen disease removed (user decision; widely taken for a bug). A ratman\'s bite set the disease '
                 '(knight +60h, 1000:42AD), and at every periodic update (each moon phase, four days; 1000:1229) a '
                 'diseased knight lost a life point, without any message. Now the bite does not infect, and the '
                 'update skips the loss also for a knight infected in an older save',
        'bytes': [((0x1000, 0x42ad), b'\xc6\x45\x60\x01', b'\xc6\x45\x60\x00'),   # mov byte [di+60h],1 -> 0
                  ((0x1000, 0x122d), b'\x74\x04', b'\xeb\x04')],                     # je -> jmp: no life lost
    },
    'K18': {
        'title': 'The dragon\'s hoard grew with every new game (B14 in the user\'s research list; confirmed in the emulator). '
                 'The new-game reset (1000:1C19, also run by every practice) rolls four magic items and gold into the '
                 'dragon\'s item table (DS:6EE8) and gold (6E26h+32h) on top of what is there; nothing else clears them, '
                 'so after five new games in one session the hoard held 25 items and 133 gold. Its mov dx,0 before the '
                 'rolls (1000:1DBE) becomes int 63h: SAVEHOOK.COM clears the table and the gold, then sets dx = 0. '
                 'User decision: instead the hoard grows with the dragon\'s victories. Every time it beats a knight '
                 '(1000:0D23, before it loots the loser: a lost fight, or a computer knight, frog or knight without '
                 'lives robbed) the hoard gets at a 50 % chance one more magic item (rolled as the game rolls them, '
                 'DS:E365) and always 0-9 gold. '
                 'custom_rules.ini can choose reset only, or keep the original (no reset). Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x1dbe), b'\xba\x00\x00', b'\xcd\x63\x90'),
                  ((0x1000, 0x0d23), b'\xbe\x26\x6e', b'\xcd\x63\x90')],
    },
    'K19': {
        'title': 'Moonstone names on the item screen (B10 in the user\'s research list, a speedrun report: "names a '
                 'half-moon new-moon"). The names follow the druids\' check, which ends the game (1000:1053): bit 1 '
                 'at new moon (31h), 2 at full moon (2Dh), 4 and 8 at half moon (2Eh); the icons agree (bits 4 and 8 '
                 'share a picture). The item screen (1000:C6F6) named bit 8 "New moon Moonstone"; its text number '
                 'becomes 20h, "Half Moonstone". (The first version followed the damage check 1000:2DB9 instead, '
                 'which swaps bits 1 and 4 against the druids, and renamed bits 1 and 4 too)',
        'bytes': [((0x1000, 0xc766), b'\x1c', b'\x20')],    # bit 8: half
    },
    'K6': {
        'title': 'Hit recovery for the dragon and the Guardian (F5; the speedrun guide\'s dragon combo and Guardian '
                 'stun-lock). Their update checks first whether they were hit (1000:3861 cmp word [di+0Eh],0; '
                 '1000:4F6A cmp word [si+0Eh],0), and every hit restarts the hit reaction, so quick blows kept them '
                 'from fighting back. Both become int 63h: a hit within the hit recovery time (custom rules '
                 'dragon_hit_recovery, guardian_hit_recovery; default 0.8 s; 0 = as the game) of the last counted one '
                 'is dropped. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x3861), b'\x83\x7d\x0e\x00', b'\xcd\x63\x90\x90'),
                  ((0x1000, 0x4f6a), b'\x83\x7c\x0e\x00', b'\xcd\x63\x90\x90')],
    },
    'K21': {
        'title': 'The dragon keeps its target (speedrun guide: "you can reroll the target of the dragon by entering '
                 'your item menu then exiting"). The map set-up 1000:A6E1 runs again whenever the map is drawn anew, '
                 'and calls the dragon\'s set-up 1000:A78C, which rolls a random target with lives each time '
                 '(A80D-A82E, target in dragon +46h). Its sub cx,cx at A80D becomes int 63h: called from the map set-up '
                 '(return A72Ch), the dragon keeps a target that still has lives. The Scroll of the Wyrm (1000:ADEE) '
                 'still rolls a new one. Off in speedrun mode. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0xa80d), b'\x2b\xc9', b'\xcd\x63')],
    },
    'K22': {
        'title': 'No extra action at the end of a turn (speedrun guide: "the extra turn glitch", spamming Enter as the '
                 'last action of a turn ends, e.g. to fight a lair or a Black Knight twice in one day). After a '
                 'place\'s action (1000:B000: a fight, the city, a lair) the map loop jumped back to its start '
                 '(A5B8 jmp A4B0) and read the input again before the end-of-turn check (A5FB), so a pressed Enter '
                 'started another action. The jmp becomes int 63h: when the action used up the turn ([CC98h] >= '
                 '[CCACh]), the loop goes on to its dragon and end-of-turn checks (A5BB). Off in speedrun mode. Needs '
                 'SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0xa5b8), b'\xe9\xf5\xfe', b'\xcd\x63\x90')],
    },
    'K23': {
        'title': 'No lives back from a potion after the Guardian (speedrun guide: "when you lose life to the guardian '
                 'you can restore your life back to 5"). A lost Guardian fight takes one life at the end of the fight '
                 'and two more in the Valley (1000:0FFF, sub byte [si+31h],2, no floor), so lives can go below 0, and '
                 'a lost fight restores full hit points. The healing potion at full hit points (1000:CCB6) adds a '
                 'life and turns 6 and above into 5 with an unsigned compare: -2 became -1 = FFh, and then 5. The '
                 'potion\'s life code (CCB6-CCC2) becomes int 63h: a knight without lives (0 or below) gets none, the '
                 'cap is max_lives (custom rules; 5). Off in speedrun mode (then as the game, cap 5). Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0xccb6), bytes.fromhex('fe4431807c31067204c6443105'), b'\xcd\x63' + b'\x90' * 11)],
    },
    'K24': {
        'title': 'Moonstone damage bonus at the right phase. In its phase a Moonstone doubles the knight\'s damage '
                 '(1000:2DAB), but the check took bit 1 at half moon (2Eh) and bit 4 at new moon (31h), the other way '
                 'round from Stonehenge (1000:1053), the names and the icons (K19): bit 1 is the new-moon stone, 4 a '
                 'half-moon one. The two phase numbers swap. Speedrun mode puts them back',
        'bytes': [((0x1000, 0x2dc1), b'\x2e', b'\x31'),     # bit 1: new moon
                  ((0x1000, 0x2de2), b'\x31', b'\x2e')],    # bit 4: half moon
    },
    'K20': {
        'title': 'Moon pictures in the right order (speedrun guide: "the half-moon is actually bigger than the 3/4"). '
                 'The phase is also the picture (KI.CEL frames 2Dh-31h: full, three-quarters, half, crescent, new), '
                 'and the cycle DS:05A9 goes 2Dh, 2Fh, 2Eh, 30h, 31h: the map showed full, half, three-quarters, '
                 'crescent, new. The half-moon Moonstones work at 2Eh. The draw (1000:9053, mov ax,[8989h]) becomes '
                 'int 63h, which swaps the pictures of 2Eh and 2Fh: the phases and their days stay, the half moon '
                 'is drawn when the half-moon stones work. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x9053), b'\xa1\x89\x89', b'\xcd\x63\x90')],
    },
    'D6': {
        'title': 'Save state before every fight (Moonstone Rebuilt only). Every fight (lairs, dragon, Guardian, knights) '
                 'starts in the routine at 1000:0307; its first instruction (mov word [7841h],0) becomes int 66h, '
                 'which SAVEHOOK.COM (make_savehook.py) handles: it does that instruction and has DOSBox-X autosave '
                 'the state. Needs SAVEHOOK.COM resident, otherwise the game crashes at the first fight',
        'bytes': [((0x1000, 0x0307), b'\xc7\x06\x41\x78\x00\x00', b'\xcd\x66\x90\x90\x90\x90')],
    },
    'D7': {
        'title': 'Save state at the start of every human turn on the map (Moonstone Rebuilt only). The turn change at '
                 '1000:a610 sets up the next knight (call 1000:a697) and then loads its record (1000:a63f, '
                 'mov si,[77e8h]); that instruction becomes int 65h, which SAVEHOOK.COM handles: it does the '
                 'instruction and, unless the knight is computer-controlled, has DOSBox-X autosave the state. '
                 'Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0xa63f), b'\x8b\x36\xe8\x77', b'\xcd\x65\x90\x90')],
    },
    'D9': {
        'title': 'Player 2 moves with W, A, S, D (Moonstone Rebuilt; user request). The keyboard routine at 1000:83C0 '
                 'reads player 2 as Tab (fire), W (up), X (down), A (left) and D (right); down becomes S (scan code '
                 '1Fh), which the game does not use for anything else',
        'bytes': [((0x1000, 0x8403), b'\xb8\x2d\x00', b'\xb8\x1f\x00')],   # mov ax,2Dh (X) -> mov ax,1Fh (S)
    },
    'D11': {
        'title': 'Practice against the computer with one player (Moonstone Rebuilt; user request). Practice '
                 '(1000:00E7) saves the chosen number of players in [0940h], forces two and always sets up two human '
                 'knights: 6C9Eh (controller 2, the first player\'s keys) and 6D00h (controller 1, the second '
                 'player\'s). The set-up of 6D00h (1000:011D: type 6, controller 1, +20h = 2) and InitPractice\'s '
                 'controller (1000:2031) become int 63h, which SAVEHOOK.COM handles: with one player chosen the '
                 'second knight is a computer knight as the game makes them at 1000:1C75 (type 8, controller 4, '
                 '+20h = 4: black), otherwise as before. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x011d), b'\xc6\x44\x35\x06\xc6\x44\x09\x01\xc7\x44\x20\x02\x00',
                   b'\xcd\x63' + b'\x90' * 11),
                  ((0x1000, 0x2031), b'\xc6\x45\x09\x01', b'\xcd\x63\x90\x90')],
    },
    'D12': {
        'title': 'Practice with 3 or 4 players: two teams (Moonstone Rebuilt; user request; a prototype). With 3 '
                 'players chosen and a controller on joystick A, or 4 and controllers on joysticks A and B, practice '
                 'adds knights 6D62h (joystick A) and 6DC4h (joystick B): team 1 = player 1 (arrows) + joystick A, '
                 'team 2 = player 2 (W A S D) + joystick B, in the colours of players 1 and 2; otherwise practice is '
                 'as before. In this mode the keys and the joysticks are four separate inputs (1000:83C0 otherwise '
                 'ORs joystick A into player 1 and B into player 2), teammates do not hurt each other, and the fight '
                 'ends when one team has no knight left. All sites become int 63h (SAVEHOOK.COM): InitPractice after '
                 'the second knight (2038, it adds the others through the game\'s own 1F76 and 2998), the fight loop\'s '
                 'end check (036F), a knight\'s hit (4273), the joystick ORs (83EE, 8420), the input pick (0A8F) and '
                 'the end of practice (014B). Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x203b), b'\xc7\x06\x1c\x09\x06\x00', b'\xcd\x63' + b'\x90' * 4),
                  ((0x1000, 0x036f), b'\x80\x3e\x7d\x89\x00', b'\xcd\x63\x90\x90\x90'),
                  ((0x1000, 0x4273), b'\x8b\x75\x0e\x33\xc0', b'\xcd\x63\x90\x90\x90'),
                  ((0x1000, 0x83ee), b'\x5b\x0b\xd8', b'\xcd\x63\x90'),
                  ((0x1000, 0x8420), b'\x5a\x5b\x0b\xc2', b'\xcd\x63\x90\x90'),
                  ((0x1000, 0x0a8f), b'\x80\x7d\x09\x01\x74\x02\x8b\xc3', b'\xcd\x63' + b'\x90' * 6),
                  ((0x1000, 0x014b), b'\x8b\x16\x40\x09', b'\xcd\x63\x90\x90')],
    },
    'D13': {
        'title': 'Four colours in the 3-4 player practice (Moonstone Rebuilt; user request; with D12). The game sets only '
                 'palette entries 0-31 of its 256-colour screen. The interpreter\'s two blitter calls (1000:9AFB, '
                 '9B07) note when knight 6D62h or 6DC4h is drawn; after the bitplanes are converted to bytes '
                 '(1000:5EDD) that frame\'s knight colours move up by 26: 6-8 to 32-34 (6D62h, drawn from KN*.OB) and '
                 '9-11 to 35-37 (6DC4h, HE*.OB). Entries 32-37 are written after the palette write (1000:5B3E) and '
                 'each fade step (5BAD in, 5C21 out), from the fight palette words of knights +20h = 1 and 3 '
                 '(1000:4838, 484E; custom rules colour them), scaled with the fade. Only while D12\'s mode is on. '
                 'Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x9afb), b'\xe8\xd6\xc2', b'\xcd\x63\x90'),
                  ((0x1000, 0x9b07), b'\xe8\xca\xc2', b'\xcd\x63\x90'),
                  ((0x1000, 0x5edd), b'\x5f\x5e\x1f', b'\xcd\x63\x90'),
                  ((0x1000, 0x5b3e), b'\xba\xc8\x03', b'\xcd\x63\x90'),
                  ((0x1000, 0x5bad), b'\x81\xc5\xc0\x00', b'\xcd\x63\x90\x90'),
                  ((0x1000, 0x5c21), b'\x81\xc5\xc0\x00', b'\xcd\x63\x90\x90')],
    },
    'D14': {
        'title': 'Practice choices (Moonstone Rebuilt; user request; with D11-D13). In the first menu, Space on Practice '
                 'starts the 3-4 player practice as two teams in their keyboard players\' colours; Enter starts it as '
                 'everyone against everyone, in four colours, until one knight is left. With 1 player chosen, the keys '
                 '1-9 start a practice against the monsters of one lair through the game\'s own lair fight (as many '
                 'at once as the lair sends): 1 ratmen x10, 2 ratmen x14, 3 wasteland troggs x10, 4 axe troggs x10, 5 '
                 'war beasts x9, 6 spear troggs x5, 7 Baloks x3, 8 mudmen x5, 9 trolls x6; 0 (or Enter) the Black '
                 'Knight. The menu stores its input at 1000:1299 and practice calls InitPractice at 1000:0142; both '
                 'become int 63h (SAVEHOOK.COM keeps the choice and calls 1000:055E and 1F2C with that lair\'s '
                 'record). Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x1299), b'\x89\x1e\xe2\x77', b'\xcd\x63\x90\x90'),
                  ((0x1000, 0x0142), b'\xe8\xb5\x1e', b'\xcd\x63\x90')],
    },
    'K25': {
        'title': 'Instant kills in co-op (found in the user\'s play test, 31 Oct 2026): the monsters\' instant kills '
                 '(troll, mudman, Balok, dragon...) call 1000:0AB2, which sets the HP of [8979h] to -1, the knight '
                 'of a one-to-one fight. In co-op that is the first knight standing: it fell without a blow while '
                 'the knight hit played its death, kept its HP and stood up again, and the monster went on '
                 'attacking it. mov si,[8979h] becomes int 63h: in co-op the knight the monster fights ([0978h]). '
                 'Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x0ab3), bytes.fromhex('8b367989'), bytes.fromhex('cd639090')),
                  # the knight's handler never looked at its HP: a knight killed so got up again; in co-op a knight
                  # down gets the death fall once and then stays (1000:3ED0)
                  ((0x1000, 0x3ed0), bytes.fromhex('c70634780000'), bytes.fromhex('cd6390909090')),
                  # the troll looked only at knight 1's HP and went idle once it was down (1000:55F9)
                  ((0x1000, 0x55f9), bytes.fromhex('be9e6c837c3800'), bytes.fromhex('cd639090909090')),
                  # the mudman held one knight and pulled another under or let another go: the knight it takes
                  # hold of stays its knight (1000:52FE, 559C, 54DB)
                  ((0x1000, 0x52fe), bytes.fromhex('a17809'), bytes.fromhex('cd6390')),
                  ((0x1000, 0x559c), bytes.fromhex('8b440c'), bytes.fromhex('cd6390')),
                  ((0x1000, 0x54db), bytes.fromhex('8bc7'), bytes.fromhex('cd63')),
                  # the dragon's bite takes a knight off and sets [77F0h]; the next knight's handler that runs kills
                  # itself (3EEA): in co-op another knight than the one eaten (1000:3AF3 notes the one eaten)
                  ((0x1000, 0x3af3), bytes.fromhex('8b450c'), bytes.fromhex('cd6390')),
                  # ... and in co-op without the flag (1000:3AF9): the eating script kills the one eaten
                  ((0x1000, 0x3af9), bytes.fromhex('c706f0770100'), bytes.fromhex('cd6390909090'))],
    },
    'K28': {
        'title': 'The Balok in co-op (found in the user\'s play test, 1 Nov 2026): its hold pauses the knight it '
                 'touched (1000:37A7) but lets go of the knight it fights then ([0978h], 37FC), so with 2-4 knights '
                 'the knight held could stay frozen and the fight stuck. mov ax,[0978h] at 1000:35AF and mov ax,di '
                 'at 37A7 become int 63h: the knight it takes hold of stays its knight while the hold lasts, and '
                 'its frames of the hold draw that knight in the knight\'s colours. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x35af), bytes.fromhex('a17809'), bytes.fromhex('cd6390')),
                  ((0x1000, 0x37a7), bytes.fromhex('8bc7'), bytes.fromhex('cd63')),
                  # the spear trogg's frames of a fallen knight on its spear (1000:2F90)
                  ((0x1000, 0x2f90), bytes.fromhex('8bc6'), bytes.fromhex('cd63'))],
    },
    'D25': {
        'title': 'Knights turn in place and walk up close (user report 4 Nov 2026). A turn (1000:3F83, 3F92) '
                 'mirrors the pose about the object\'s x, which the standing knight is not centred on (x-13..x+23), '
                 'so it hopped 10 to the side and took its first step at once; now x moves 10 the other way (the body '
                 'stays, the feet change places) and that frame takes no step. A step blocked by another figure\'s '
                 'box (1000:9FDF, the drawn frames\' extents; the walking steps are 25, 3, 23, 4) stopped the knight '
                 'up to a whole step away; now it is cut to the gap (3FAC), so the figures come up to touching. '
                 'Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x3f83), bytes.fromhex('c6450801'), bytes.fromhex('cd639090')),
                  ((0x1000, 0x3f92), bytes.fromhex('c6450803'), bytes.fromhex('cd639090')),
                  ((0x1000, 0x3fac), bytes.fromhex('8b36e877'), bytes.fromhex('cd639090')),
                  # an attack with up or down just after a turn is read with the facing from before it (1000:40AC):
                  # back + up threw no dagger, as the back direction had turned the knight first
                  ((0x1000, 0x40ac), bytes.fromhex('807d0803'), bytes.fromhex('cd639090')),
                  # in depth figures stop 14 apart, not 20 (the hits reach 10)
                  ((0x1000, 0xa0ab), bytes.fromhex('83f914'), bytes.fromhex('83f90e'))],
    },
    'K32': {
        'title': 'The computer knights\' lair choice ruined its own table (code audit, 6 Nov 2026). The bubble sort of '
                 'the 24 lairs by distance (1000:A986) swaps a pair, but its last store goes to [si+4] where [si+6] is '
                 'meant: a pointer lands in a distance field and a lair is lost at every swap, leaving about 4 different '
                 'lairs of 24 (emulated). A9AA: mov [si+4],cx becomes mov [si+6],cx',
        'bytes': [((0x1000, 0xa9aa), bytes.fromhex('894c04'), bytes.fromhex('894c06'))],
    },
    'K33': {
        'title': 'Limits and checks (code audit, 6 Nov 2026). Game over only when no human knight can play again, not '
                 'by a count that frogs and computer turns upset (A67B). HP never below 1 from losing armour (CE75, '
                 '0BAD), and automatic loot moves the HP of the armour actually taken (0BAD). A flight with no free path '
                 'slot lands where it is, not at a stale position (2CFB). Mythral\'s table is not read past its end '
                 '(BC2E). Limits tested with >=, not =: daggers from loot (CE1A, CE26), gold from loot (CEF8); a dragon '
                 'fight is skipped for lives <= 0, not only 0 (0D13). Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0xa67b), bytes.fromhex('ff06aacc'), bytes.fromhex('cd639090')),
                  ((0x1000, 0xce75), bytes.fromhex('294538'), bytes.fromhex('cd6390')),
                  ((0x1000, 0x0bad), bytes.fromhex('294538014438'), bytes.fromhex('cd6390909090')),
                  ((0x1000, 0x2cfb), bytes.fromhex('b8ffff'), bytes.fromhex('cd6390')),
                  ((0x1000, 0xbc2e), bytes.fromhex('8b4c02'), bytes.fromhex('cd6390')),
                  ((0x1000, 0xce1a), bytes.fromhex('7421'), bytes.fromhex('7d21')),
                  ((0x1000, 0xce26), bytes.fromhex('740e'), bytes.fromhex('7d0e')),
                  ((0x1000, 0xcef8), bytes.fromhex('740a'), bytes.fromhex('7d0a')),
                  ((0x1000, 0x0d13), bytes.fromhex('740e'), bytes.fromhex('7e0e'))],
    },
    'D26': {
        'title': 'A new turn waits for the keys to be let go (user request 6 Nov 2026): a player still holding a '
                 'direction (or fire) as the turn changed moved the next knight on the map at once. At a human\'s '
                 'turn start (D7\'s int 65h, 1000:A63F) SAVEHOOK.COM notes it, and the map loop\'s input (1000:A536, '
                 'mov [CC9Ah],bx after 83C0) stays empty until no direction or fire is held. Needs SAVEHOOK.COM '
                 'resident',
        'bytes': [((0x1000, 0xa536), bytes.fromhex('891e9acc'), bytes.fromhex('cd639090'))],
    },
    'D24': {
        'title': 'Responsive controls (user request 4 Nov 2026). The game reads its key table once a frame (two BIOS '
                 'ticks, about 110 ms), so a key tapped between two reads was lost, and a knight reads its input only '
                 'when its move is over (1000:98F6), so an attack pressed during a move was lost too. The keyboard '
                 'interrupt\'s store (1000:8271) becomes int 64h: SAVEHOOK.COM keeps a release back until the key '
                 'has been down three ticks (let through by the key test, 828B -> int 63h). The knight\'s input '
                 '(3F16 -> int 63h): a fire key pressed in the last 8 ticks gives that attack, with its directions '
                 '(input_buffer, on by default). Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x8271), bytes.fromhex('2e8887e381'), bytes.fromhex('cd64909090')),
                  ((0x1000, 0x828b), bytes.fromhex('2e80bfe381ff'), bytes.fromhex('cd6390909090')),
                  ((0x1000, 0x3f16), bytes.fromhex('894526'), bytes.fromhex('cd6390'))],
    },
    'D23': {
        'title': 'Faster drawing (measured 4 Nov 2026: in a fight of four knights about 39 % of the instructions '
                 'went to the sprite converter, which turns every piece drawn, every frame, from planes into a byte '
                 'a pixel bit by bit with rol / rcl). Its call at 1000:5EDA becomes int 63h: SAVEHOOK.COM does the '
                 'same with a table and 386 registers (DOSBox-X\'s CPU), about four times fewer instructions, and '
                 'gives masks it has no routine for to the game\'s own. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x5eda), bytes.fromhex('2eff17'), bytes.fromhex('cd6390'))],
    },
    'D22': {
        'title': 'Gore off without blood (user decisions 4 Nov 2026). With the game\'s blood setting off ([0700h], or '
                 'death_animations = off): the troll\'s blow and the Balok\'s leap no longer crush a knight down into '
                 'a pool of blood but give the plain death (1000:43B0 and 3729, the script 16E2h becomes 1310h); '
                 'SAVEHOOK.COM clears frames of blood only (colour 15) from the fight\'s pieces and paints the blood '
                 'on the knights, the Balok and the boar over with the colour beside it (draw and recolour hooks); '
                 'the new deaths (D20) are off; and every hit shows a hit marker, a white X (frames in KN3.OB, '
                 'script DS:FE60, made at the hit test 1000:A14C). Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x43b0), bytes.fromhex('c7063a78e216'), bytes.fromhex('cd6390909090')),
                  ((0x1000, 0x3729), bytes.fromhex('bee216'), bytes.fromhex('cd6390'))],
    },
    'D21': {
        'title': 'Dragon debug mode (user request 4 Nov 2026; custom rules dragon_debug_mode = 1, off by default): on '
                 'the map the keys 1-4 make knight 1-4 the target of the dragon (+46h), and Enter by a knight standing '
                 'under the dragon starts its fight. In the game only the target of the dragon is attacked, when the '
                 'dragon flies over it in its turn (1000:A5BB), and Enter only runs the action of a place (B000). '
                 'mov di,6E26h at 1000:A5BB becomes int 63h. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0xa5bb), bytes.fromhex('bf266e'), bytes.fromhex('cd6390'))],
    },
    'D20': {
        'title': 'New deaths (user request 1 Nov 2026): a knight hit again in the slumped pose of its fall (script '
                 '130E) dies by the blow: split in two by an up strike, a dagger in the forehead or the back of the '
                 'head, a long thrust (down and forward) or a back strike through the helmet, lifted on the sword by '
                 'an up and forward strike. mov di,[77E8h] at 1000:2D5E becomes int 63h, where SAVEHOOK.COM picks '
                 'the death. The pieces are added to KN3.OB and the scripts written into DS:F480 by '
                 'death_frames.py; the knights\' bank area (1000:86A7) grows by 200h paragraphs to hold them. Needs '
                 'SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x2d5e), bytes.fromhex('8b3ee877'), bytes.fromhex('cd639090')),
                  # a dagger also hits a knight slumped below its flight (1000:3E59)
                  ((0x1000, 0x3e59), bytes.fromhex('837c0c00'), bytes.fromhex('cd639090')),
                  # the striker goes on with these blows on a fallen knight too, as with the sweep (1000:4159)
                  ((0x1000, 0x4159), bytes.fromhex('837d2804'), bytes.fromhex('cd639090')),
                  # the spear trogg's blow on a slumped knight: the thrust, not the knight on its spear (1000:4357)
                  ((0x1000, 0x4357), bytes.fromhex('8b7d0e'), bytes.fromhex('cd6390')),
                  # the knights' bank area: 19C0h -> 1BC0h paragraphs (D20's pieces and D22's hit marker, room for
                  # more; SAVEHOOK.COM is loaded high, so DOS has it)
                  ((0x1000, 0x86a8), bytes.fromhex('c019'), bytes.fromhex('c01b')),
                  # with EMS the files are cached at fixed places (DS:828A: page group, offset, size): KN3.OB and
                  # HE3.OB grew into the next files (KN4.OB, KN5.OB; ki.cel), whose copies then overwrote the new
                  # pieces. Those three move on by 1600h (the groups are 8000h; they end by 7F30h at most)
                  (('DS', 0x83a6), bytes.fromhex('992b'), bytes.fromhex('9941')),
                  (('DS', 0x83be), bytes.fromhex('692b'), bytes.fromhex('6941')),
                  (('DS', 0x83c4), bytes.fromhex('a931'), bytes.fromhex('a947'))],
    },
    'K26': {
        'title': 'The troll\'s depth (found in the user\'s play test, 31 Oct 2026): the troll counted as level with '
                 'its knight within 5 in depth either way, but its swing hits only when its depth is 0-4 more than the '
                 'knight\'s. 1-5 nearer, it stood and swung at the air while the knight stood still, e.g. a knight '
                 'at the screen\'s edge with the troll off the screen. call 3C97h in its step (1000:570E) becomes '
                 'int 63h: level means 0-4, else it steps in depth. And its swing hits a standing knight only from '
                 'about 100 on, but it swung from 91 on: mov bp,[si+54h] (1000:573B, steps back within 90) becomes '
                 'int 63h, it steps back within 104. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x570e), bytes.fromhex('e886e5'), bytes.fromhex('cd6390')),
                  ((0x1000, 0x573b), bytes.fromhex('8b6c54'), bytes.fromhex('cd6390'))],
    },
    'K27': {
        'title': 'The dragon\'s far fire (found in the user\'s play test, 1 Nov 2026): the dragon keeps to x 30-100, '
                 'and it took up its far fire only for a knight 140 or more away (1000:388C, cmp ax,8Ch). Its near fire '
                 'does not reach 96, so a knight 96-139 away was never hurt while the dragon breathed fire at it. '
                 'The far fire now starts at 96',
        'bytes': [((0x1000, 0x388c), bytes.fromhex('3d8c00'), bytes.fromhex('3d6000'))],
    },
    'D19': {
        'title': 'Black Knights against 2-4 knights (Moonstone Rebuilt; user request 1 Nov 2026): practice\'s Black '
                 'Knight with 2-4 knights, and the B key with any number, is a lair fight whose monsters are computer '
                 'knights, as many as the knights, each a copy of one (the B key\'s: black, strength, constitution and '
                 'endurance 5, the Sword of Sharpness and battle armour). Their fields (1000:2824, call bx), no more '
                 'after one falls (0243), and they do not hurt each other (A14C) are int 63h. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x2824), bytes.fromhex('ffd3'), bytes.fromhex('cd63')),
                  ((0x1000, 0x0243), bytes.fromhex('a16c09'), bytes.fromhex('cd6390')),
                  ((0x1000, 0xa14c), bytes.fromhex('0bc0'), bytes.fromhex('cd63')),
                  # a dagger keeps its thrower (1000:3E3B, 3E40)
                  ((0x1000, 0x3e3b), bytes.fromhex('b21a'), bytes.fromhex('cd63')),
                  ((0x1000, 0x3e40), bytes.fromhex('c7451a2a77'), bytes.fromhex('cd63909090')),
                  # the B key's knights' daggers do double (1000:44C2)
                  ((0x1000, 0x44c2), bytes.fromhex('294538'), bytes.fromhex('cd6390')),
                  # Black Knights walk through each other (1000:A008, the walk's collision test): two that came in
                  # at the same place blocked each other for good
                  ((0x1000, 0xa008), bytes.fromhex('837d2200'), bytes.fromhex('cd639090')),
                  # a computer knight throws only from the screen, one dagger in the air at a time, and not at
                  # every decision (1000:4D45, cmp byte [si+34h],0 before its throw)
                  ((0x1000, 0x4d45), bytes.fromhex('807c3400'), bytes.fromhex('cd639090'))],
    },
    'K31': {
        'title': 'A dagger thrown to the left never left the fight (found in the user\'s play test, 6 Nov 2026): '
                 'its handler (1000:3E6F) ends it only when its x is between -10 and 0, and it flies 20 a frame, so '
                 'most daggers skipped that window and flew on for good. The daggers filled the fight\'s 20 object '
                 'slots and no new one could be thrown (1000:2A1E finds no free slot). It now ends once x is -10 or '
                 'less (3E7D: jle becomes jge)',
        'bytes': [((0x1000, 0x3e7d), bytes.fromhex('7e'), bytes.fromhex('7d'))],
    },
    'D17': {
        'title': 'CPU speed for fights (Moonstone Rebuilt; user request after a play test: fights with 2-4 knights '
                 'are slow because the game draws every sprite itself and runs out of DOSBox-X cycles). At the start '
                 'of every fight (the fight save, 1000:0307, D6) SAVEHOOK.COM runs DOSBox-X\'s own CONFIG -set '
                 'cycles=... with fight_cycles for the fight\'s 1-4 knights (custom rules; default 2600, 3250, 3500, '
                 '3750, as D23 made drawing cheaper; one number: + additional_cycles_per_knight for every knight past '
                 'the first), and at its end (1000:0ABE, mov word [0942h],0, '
                 'becomes int 63h) back to default_cycles, the conf\'s value. fight_cycles = default_cycles and 0 per knight '
                 'change nothing; speedrun '
                 'mode too. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x0abe), bytes.fromhex('c70642090000'), bytes.fromhex('cd6390909090'))],
    },
    'D15': {
        'title': 'Co-op practice (Moonstone Rebuilt; user request; with D12-D14). With 2-4 players chosen, the practice '
                 'keys 1-9 put all the knights on the same side against that lair\'s monsters (with 3-4 players as many '
                 'knights as D12 finds controllers for). They cannot hurt each other (daggers still can), the fight '
                 'goes on while a knight stands and monsters are left, and every monster goes for the knight nearest '
                 'to it. The monsters\' moves read the knight they fight from [0978h] (the knight that entered the '
                 'fight) in many places; before the fight\'s update pass calls an object\'s handler (1000:98FD, mov '
                 'bx,[di+1Ah], becomes int 63h) SAVEHOOK.COM sets [0978h] to the nearest knight standing for a monster '
                 '(switching only when another is clearly nearer) and to the first knight standing for anything else. '
                 'The fight start and each knight\'s walk-in script toggle every monster\'s pause flag (1000:025C, '
                 'mov ax,6F08h, also int 63h); in co-op only knight 1\'s walk-in does, so an even number of knights no '
                 'longer leaves the monsters frozen. Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0x025c), b'\xb8\x08\x6f', b'\xcd\x63\x90'),
                  ((0x1000, 0x98fd), b'\x8b\x5d\x1a', b'\xcd\x63\x90'),
                  # a ratman hit by a knight took the damage of the knight in [0978h] (mov si,[0978h]), not of the
                  # knight that hit it ([di+0Eh]): the same knight alone, but in co-op [0978h] is the ratman's target
                  ((0x1000, 0x34a7), b'\x8b\x36\x78\x09', b'\x8b\x75\x0e\x90'),
                  ((0x1000, 0x34c7), b'\x8b\x36\x78\x09', b'\x8b\x75\x0e\x90')],
    },
}

# --- INTR.EXE (intro and ending) -----------------------------------------------------------------------------------
# K9: skip the intro (and ending) with Enter, Space or Esc. Every intro scene waits for vertical retrace in the routine
# at 0000:0F9E; it is replaced by a far jump to new code in the unused tail of the music-module buffer (segment 0492h,
# offset 2300h; the largest intro module is 8274 bytes). When the module is loaded (first byte 1Eh = push ds) and one of
# the keys is pressed, the new code resets the stack and jumps to the intro's own shutdown path at 0000:00D1 (stop music,
# restore video and timer, exit). Otherwise it does the original retrace wait and returns through a RET at 0000:0FA3.
INTR_CAVE_SEG, INTR_CAVE_OFF = 0x0492, 0x2300
INTR_DATA_SEG, INTR_STACK_TOP = 0x06d2, 0x0800

KEY_STATE_TABLE = 0x46f3                                # INTR's own int 9 handler (0000:4774): byte per scan code,
SKIP_SCANCODES = (0x1c, 0x39, 0x01)                     # 00 = held, FF = released. Enter, Space, Esc.

def _intr_skip_code():
    """Machine code for the cave, plus offsets (within it) of words that need relocation. INTR replaces the keyboard
    interrupt and never passes keys to the BIOS, so the code reads INTR's key state table instead of int 16h."""
    c, relocs, fix = bytearray(), [], {}
    def emit(*b): c.extend(b)
    def jcc(op, label): emit(op, 0); fix[len(c) - 1] = label
    emit(0x2e, 0x80, 0x3e); flag_ref = len(c); emit(0, 0, 0x00)   # cmp byte cs:[flag], 0     already skipping?
    jcc(0x75, 'wait')                                  # jne wait
    emit(0x2e, 0x80, 0x3e, 0x00, 0x00, 0x1e)          # cmp byte cs:[0000], 1Eh   music module loaded?
    jcc(0x75, 'wait')                                  # jne wait
    emit(0x50, 0x06)                                   # push ax / push es
    emit(0xb8); relocs.append(len(c)); emit(0x00, 0x00)   # mov ax, segment 0 (INTR code)
    emit(0x8e, 0xc0)                                   # mov es, ax
    for code in SKIP_SCANCODES:
        addr = KEY_STATE_TABLE + code
        emit(0x26, 0x80, 0x3e, addr & 0xff, addr >> 8, 0x00)   # cmp byte es:[table+code], 0   held?
        jcc(0x74, 'skip')
    emit(0x07, 0x58)                                   # pop es / pop ax
    labels = {'wait': len(c)}
    emit(0xba, 0xda, 0x03)                             # mov dx, 3DAh  (original retrace wait)
    emit(0xec, 0xa8, 0x08, 0x75, 0xfb)                 # in al,dx / test al,8 / jnz -5
    emit(0xec, 0xa8, 0x08, 0x74, 0xfb)                 # in al,dx / test al,8 / jz -5
    emit(0xea, 0xa3, 0x0f); relocs.append(len(c)); emit(0x00, 0x00)   # jmp far 0000:0FA3 (ret)
    labels['skip'] = len(c)
    emit(0x07, 0x58)                                   # pop es / pop ax
    emit(0x2e, 0xc6, 0x06); flag_set = len(c); emit(0, 0, 0x01)      # mov byte cs:[flag], 1
    emit(0xb8); relocs.append(len(c)); emit(INTR_DATA_SEG & 0xff, INTR_DATA_SEG >> 8)   # mov ax, data segment
    emit(0x8e, 0xd8)                                   # mov ds, ax
    emit(0xbc, INTR_STACK_TOP & 0xff, INTR_STACK_TOP >> 8)                         # mov sp, 0800h
    emit(0xea, 0xd1, 0x00); relocs.append(len(c)); emit(0x00, 0x00)   # jmp far 0000:00D1 (shutdown)
    flag = INTR_CAVE_OFF + len(c); emit(0x00)          # flag byte
    for pos in (flag_ref, flag_set):
        c[pos:pos + 2] = bytes([flag & 0xff, flag >> 8])
    for pos, label in fix.items():
        rel = labels[label] - (pos + 1)
        if not -128 <= rel < 128:
            raise ValueError(f'INTR.EXE: short jump to {label} is out of range ({rel})')
        c[pos] = rel & 0xff
    return bytes(c), relocs

def patch_intr_skip(exe):
    """Apply K9 to an uncompressed INTR.EXE; returns the new EXE (relocation table extended)."""
    from unexepack import build_mz
    h = struct.unpack('<14H', exe[:28])
    image = bytearray(exe[h[4] * 16:])
    relocs = [struct.unpack('<HH', exe[h[12] + 4*i:h[12] + 4*i + 4]) for i in range(h[3])]
    hook = 0x0f9e
    expected = bytes.fromhex('bada0390eca80875fb90eca80874fbc3')
    if image[hook:hook + 16] != expected:
        raise ValueError('K9: unexpected bytes at 0000:0F9E (not the GOG INTR.EXE?)')
    cave = INTR_CAVE_SEG * 16 + INTR_CAVE_OFF
    code, code_relocs = _intr_skip_code()
    if any(image[cave:cave + len(code)]):
        raise ValueError('K9: cave area is not empty')
    image[cave:cave + len(code)] = code
    image[hook:hook + 5] = bytes([0xea, INTR_CAVE_OFF & 0xff, INTR_CAVE_OFF >> 8,
                                  INTR_CAVE_SEG & 0xff, INTR_CAVE_SEG >> 8])           # jmp far 0492:2300
    image[hook + 5] = 0xc3                                                               # ret (target of the jump back)
    new = [hook + 3] + [cave + r for r in code_relocs]
    relocs += [(lin & 0xf, lin >> 4) for lin in new]                                     # (offset, segment) pairs
    return build_mz(bytes(image), relocs, h[11], h[10], h[7], h[8], h[5])

def image_offset(where):
    seg, off = where
    seg = DS_SEG if seg == 'DS' else seg
    return (seg - LOAD_SEG) * 16 + off

def apply_patches(exe, ids):
    out = bytearray(exe)
    header = struct.unpack('<H', exe[8:10])[0] * 16
    for pid in ids:
        for where, old, new in PATCHES[pid]['bytes']:
            pos = header + image_offset(where)
            if len(new) != len(old):
                raise ValueError(f'{pid}: at {where} the new bytes are not as long as the old ones')
            if out[pos:pos + len(old)] != old:
                raise ValueError(f'{pid}: expected {old!r} at {where}, found {bytes(out[pos:pos + len(old)])!r}')
            out[pos:pos + len(new)] = new
    return bytes(out)
