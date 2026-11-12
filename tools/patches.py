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
    'K34': {
        'title': 'A lair\'s monster count overwritten by a later fight (code audit, 9 Nov 2026). A lair fight leaves [898Dh] = 2 '
                 'until the next turn starts (B1B0), and the end of every fight (039E) stores the fight\'s own monster count in '
                 'the last lair when it is 2: a dragon attack in the same turn changed that lair. The end of the fight now '
                 'shifts the word right (2 becomes 1, which no check matches) and stores the count only if it was 2',
        'bytes': [((0x1000, 0x039e), bytes.fromhex('833e8d8902750b'), bytes.fromhex('d12e8d8990740b'))],   # shr word [898Dh],1 / nop / je
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
    'D38': {
        'title': 'Horses\' pictures (custom rules): the merchant\'s and map icons\' banks are loaded from KH.CEL and MH.C, '
                 'the game\'s KI.CEL and MI.C with the horses after their own frames (horse_frames.py); the original program '
                 'keeps the originals. The area of those banks (1000:869E) grows by C0h paragraphs to hold them',
        'bytes': [(('DS', 0x8b03), b'ki.cel', b'kh.cel'), (('DS', 0x8b0a), b'mi.c', b'mh.c'),
                  ((0x1000, 0x869f), bytes.fromhex('8009'), bytes.fromhex('400a')),
                  # with EMS the files are cached at fixed places (DS:828A: page group, offset, size) and po.cel's copy
                  # overwrote MH.C past MI.C's 4810 bytes: MH.C moves to the free end of group 2 (after FO1.T; 36A0h there)
                  (('DS', 0x83ce), bytes.fromhex('18000000ca12'), bytes.fromhex('02006049fd15'))],
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
    'D63': {
        'title': 'The dagger throw\'s release looks like a pistol shot (Moonstone Rebuilt; user request, 11 Nov 2026). The '
                 'knight\'s throw (script DS:0DFE, move 6) ends with the arm stretched forward and the dagger (KN4.OB '
                 'frame 10) drawn at its hand, though the flying dagger (script 0E68) is already on its way. That '
                 'piece (DS:0E60) now repeats the arm piece before it (KN1.OB frame 29), so the hand is empty and the '
                 'outstretched arm reads as a knight firing a pistol',
        'bytes': [(('DS', 0x0e60), bytes.fromhex('0c0a07023f00'), bytes.fromhex('001dfb010300'))],
    },
}

# --- Sound ids (K35, K36, K37) ---------------------------------------------------------------------------------------
# 1000:5970 plays sound id al. With a Sound Blaster the id indexes the byte table DS:7E6E (364 entries; 21 = HIT3 where
# nothing was filled in), which gives the number of a sample in the name table DS:8721, and 1000:9503 copies the 16 KB
# page with that sample to ES:C000, points DI at its VOC data block and calls CT-VOICE.DRV. The FM effects have the same
# kind of table at DS:7D02. The DOS code and animation scripts ask for the Amiga version's sound program numbers (every
# sound routine has the Amiga's constants), but the sample table was filled in against some other numbering.
# The numbers below (sample per id, rate per id, slices) describe what the Amiga's sound driver does for each program;
# they were read from the Amiga program, and no Amiga data is needed to apply them.
SB_TABLE, FM_TABLE, UNUSED_SAMPLE = 0x7e6e, 0x7d02, 21
# Ids 171 and up are never asked for. The unused ends of the two tables hold Moonstone Rebuilt's own sound ids and the
# new tables:
OWN_SOUND_IDS = {171: (4, 44),             # id: (sample, FM effect). 171 = BONFIRE2, the mines of MINEFIELD (was id 26)
                 172: (48, 13)}            # 172 = WIPCRAK, GUNSHOT's bang (was id 62, the Amiga's wind)
SOUND_RATES = SB_TABLE + 180               # K36: the VOC time constant of ids 0-179 (0 = the sample file's own)
SOUND_LAST_ID = SB_TABLE + 360             # K36: the id of the sound being played
TROLL_IDS, SCARE_IDS = FM_TABLE + 180, FM_TABLE + 188   # K35: the ids the troll's grunt and the mudmen's voice pick from
SOUND_SLICES = FM_TABLE + 192              # K37: (id, start, length) of ids that are one part of a sample; ends with 0
SOUND_RATE_SITE = 0x9537                   # K36: mov bx,6 before the driver call -> int 63h
# D65: the Amiga version's effects from a SoundFont (tools/make_amiga_audio.py), played by DOSBox-X's synth device.
# The programs in the SoundFont: all but the music parts (110-114, 116-133, 158-160) and the silence (167).
# Programs 1-100 are keys 20-119 of preset 0, programs 101-167 keys 20-86 of preset 1; keys under 15 are not used,
# because the FluidSynth in DOSBox-X (1.1.6) plays a sample whose root key is below 15 too low.
SOUND_PLAY_SITE = 0x5979                   # cmp word [8645h],3 at the start of the sound routine -> int 63h
AMIGA_PROGRAMS = [p for p in range(1, 167) if not (110 <= p <= 114 or 116 <= p <= 133 or 158 <= p <= 160)]
AMIGA_FIRST_KEY, AMIGA_PER_PRESET = 20, 100
AMIGA_PROGRAM_OF = {15: 156}               # sound ids that are not the Amiga's number: 15 is DOS's menu click (clik2)

def amiga_program(sound):
    """The Amiga program a sound id plays in the SoundFont, or 0: the id goes to the Sound Blaster as before
    (Moonstone Rebuilt's own ids, ids with no program)."""
    if sound in OWN_SOUND_IDS: return 0
    p = AMIGA_PROGRAM_OF.get(sound, sound)
    return p if p in AMIGA_PROGRAMS else 0

# K35: id -> (sample now, sample after), in groups that can be dropped one at a time. Samples (after K1): 2 beast1,
# 3 bloodsp, 4 bonfire2, 5 camel3b, 8 cheap1b, 9 cheap2b, 10 chomps, 12 dagmuf3, 13 dragnr, 15 femscr, 17 grnt3,
# 18 grnt3b, 21 hit3, 22 kstep, 23 lion1c1, 24 lion2c1, 25 mud2, 27 mudhit, 28 mudvox, 29 newkrush, 32 ratgoug,
# 33 ratleap, 34 ratmpal, 35 ratscr, 36 ratsku, 37-41 rjgrunt-rjgrunt4, 42 scrape, 43 slice3, 44 spear1, 45 stretch,
# 46 swish, 47 swordcl, 48 wipcrak.
SOUND_ID_FIXES = [
    ('knight: the grunts 6 and 19 are the knight\'s own (was the troll\'s grnt3 and RJGRUNT4)', {6: (18, 17), 19: (41, 17)}),
    ('18 is the hit, not the sword clash', {18: (47, 21)}),
    ('dragon: 26 the third chomp, 27 the fire, 29 the breath, 30-32 the knight\'s muffled cries in its mouth',
     {26: (4, 10), 27: (13, 4), 29: (4, 13), 30: (37, 12), 31: (38, 12), 32: (39, 12)}),
    ('Balok: the roars alternate between its two samples', {35: (24, 23), 37: (24, 23), 39: (24, 23), 41: (24, 23)}),
    ('troggs: 52 blood, 53 spear, 54 slice, 57 the camel groan', {52: (43, 3), 53: (3, 44), 54: (44, 43), 57: (21, 5)}),
    ('Guardian: 63 the whip crack, 64 and 70-72 its screams', {63: (12, 48), 64: (12, 15), 70: (2, 15), 71: (2, 15), 72: (2, 15)}),
    ('mudmen: 80 mud, 82 hit, 85 voice, 86 stretch, 87-89 the scare voice, 90 the crush',
     {80: (27, 25), 82: (28, 27), 85: (45, 28), 86: (8, 45), 87: (8, 9), 88: (8, 9), 89: (29, 9), 90: (35, 29)}),
    ('ratmen: 92 scream, 94 bite (no DOS sample: RATSKU, as 93), 96 gouge, 100 leap, 101-102 skull, 105 impale, '
     '107 strain (no DOS sample: HIT3, as 106), 108 scrape, 109 swish',
     {92: (36, 35), 94: (32, 36), 96: (33, 32), 100: (29, 33), 101: (29, 36), 102: (34, 36), 105: (21, 34),
      107: (42, 21), 108: (46, 42), 109: (21, 46)}),
    ('troll: 136-140 its five grunts, 141 (no DOS sample) and 142 its other grunt',
     {136: (21, 37), 137: (21, 38), 138: (21, 39), 139: (21, 40), 140: (21, 41), 141: (21, 18), 142: (21, 18)}),
    ('beast: 143-145 its roar (DOS has one of the three), 146 the gallop (no DOS sample: the knight\'s step)',
     {143: (21, 2), 144: (21, 2), 145: (21, 2), 146: (21, 22)}),
    ('mudmen: 152 the other scare voice, CHEAP1B', {152: (21, 8)}),
]
TROLL_PICKS = (136, 137, 138, 139, 140, 141, 142, 137)   # the Amiga's table at its troll routine, rand & 7
SCARE_PICKS = (152, 87, 88, 89)                          # the Amiga plays 151+152, 87+148, 88+149, 89+150; DOS one voice

# K36: the rate (Hz) the Amiga plays each program's sustained note at, for ids whose DOS sample is the Amiga's (or, for
# 30-31, 70-73, 141, 144-145, another take of the same sound at the same pitch change). Others keep the file's rate.
SOUND_RATE_HZ = {
    1: 14360, 2: 14966, 3: 14131, 4: 11084, 5: 11084, 6: 10463, 7: 9852, 8: 9852, 9: 16574, 11: 10463, 12: 10463,
    13: 9309, 16: 11745, 17: 7389, 18: 8779, 19: 10463, 20: 6982, 21: 6982, 22: 6982, 23: 6982, 24: 7389, 25: 7389,
    26: 7389, 27: 4933, 29: 4933, 30: 8287, 31: 8287, 32: 8287, 35: 11084, 36: 11084, 37: 9852, 38: 9852, 39: 8779,
    40: 8779, 41: 7830, 42: 7830, 43: 11084, 45: 7830, 46: 6982, 47: 7830, 48: 16574, 49: 7389, 50: 7389, 51: 7389,
    52: 15694, 53: 11084, 54: 14779, 56: 13185, 57: 9852, 58: 14779, 59: 11084, 60: 13964, 61: 9309, 63: 8287,
    64: 11745, 70: 11686, 71: 11686, 72: 10409, 73: 10409, 80: 12445, 81: 13964, 82: 13185, 83: 14779, 84: 13185,
    85: 11745, 86: 7830, 87: 20864, 88: 22168, 89: 12445, 90: 9852, 91: 13964, 92: 12445, 95: 13185, 96: 10463,
    97: 9309, 98: 8672, 99: 7953, 100: 6982, 101: 12445, 102: 10463, 103: 13964, 104: 12622, 105: 11405, 108: 14779,
    109: 6581, 136: 6581, 137: 6581, 138: 6581, 139: 6581, 140: 6581, 141: 6581, 142: 6581, 143: 10463, 144: 10463,
    145: 10463, 152: 31388}
MAX_TIME_CONSTANT = 212                    # 22,727 Hz, the most a Sound Blaster before the Pro plays (K10 uses it too)

# K37: id -> (start, length) in bytes of sample data: the four grunts in DRAGRU and the three chomps in CHOMPS
SOUND_SLICE_OF = {20: (0, 1856), 21: (1856, 1410), 22: (3266, 1136), 23: (4402, 1038),
                  24: (0, 2688), 25: (2688, 2884), 26: (5572, 4174), 49: (0, 2688), 50: (2688, 2884), 51: (5572, 4174)}

def time_constant(rate):
    return min(MAX_TIME_CONSTANT, round(256 - 1_000_000 / rate))

def _sound_patches():
    unused = lambda n: bytes([UNUSED_SAMPLE]) * n
    k35 = [(('DS', SB_TABLE + i), bytes([old]), bytes([new])) for _, ids in SOUND_ID_FIXES for i, (old, new) in ids.items()]
    for i, (sample, fm) in OWN_SOUND_IDS.items():
        k35 += [(('DS', SB_TABLE + i), unused(1), bytes([sample])), (('DS', FM_TABLE + i), unused(1), bytes([fm]))]
    k35 += [
        (('DS', TROLL_IDS), unused(8), bytes(TROLL_PICKS)), (('DS', SCARE_IDS), unused(4), bytes(SCARE_PICKS)),
        ((0x1000, 0x3dc4), b'\x25\x03\x00', b'\x25\x01\x00'),                      # rat on the skull: and ax,3 -> and ax,1
        ((0x1000, 0x5804), b'\x25\x03\x00\x56\xbe\x88\x7b',                        # troll: and ax,3 / push si / mov si,7B88h
                           b'\x25\x07\x00\x56\xbe' + struct.pack('<H', TROLL_IDS)),   # -> and ax,7 / ... / mov si,TROLL_IDS
        # mudmen's scare voice: call BF62h / and ax,1 / add ax,8 / call 5970h / ret
        #   -> push si / call BF62h / and ax,3 / mov si,SCARE_IDS / jmp 57EFh (the mud voice's add si,ax ...) / nop
        ((0x1000, 0x57d8), bytes.fromhex('e88767' '250100' '050800' 'e88c01' 'c3'),
                           bytes.fromhex('56' 'e88667' '250300' 'be') + struct.pack('<H', SCARE_IDS) + bytes.fromhex('eb0b' '90')),
    ]
    rates = bytes(time_constant(SOUND_RATE_HZ[i]) if i in SOUND_RATE_HZ else 0 for i in range(180))
    k36 = [
        # mov bx,7E6Eh / xlatb / mov ah,0 / and al,0FFh / call 9503h
        #   -> mov bx,7E6Eh / mov [SOUND_LAST_ID],al / xlatb / cbw / call 9503h
        ((0x1000, 0x5995), bytes.fromhex('bb6e7e' 'd7' 'b400' '24ff' 'e8633b'),
                           bytes.fromhex('bb6e7e' 'a2') + struct.pack('<H', SOUND_LAST_ID) + bytes.fromhex('d7' '98' 'e8633b')),
        ((0x1000, SOUND_RATE_SITE), b'\xbb\x06\x00', b'\xcd\x63\x90'),              # mov bx,6 -> int 63h / nop
        (('DS', SOUND_RATES), unused(180), rates), (('DS', SOUND_LAST_ID), unused(1), b'\0'),
        (('DS', SOUND_SLICES), unused(1), b'\0'),                                    # no slices
    ]
    slices = b''.join(struct.pack('<BHH', i, *SOUND_SLICE_OF[i]) for i in sorted(SOUND_SLICE_OF)) + b'\0'
    k37 = [(('DS', SOUND_SLICES), b'\0' + unused(len(slices) - 1), slices)]
    return {
        'K35': {
            'title': 'Sound ids play the sounds the Amiga version plays. The DOS code and scripts ask for the Amiga\'s '
                     'sound numbers, but the Sound Blaster table (DS:7E6E, id -> sample) was filled in against another '
                     'numbering, so about 50 of the ids the game uses played another sample, though the right one was '
                     'loaded: ' + '; '.join(what for what, _ in SOUND_ID_FIXES) + '. Three routines asked for the wrong '
                     'ids: the mudmen\'s scare voice (1000:57D8) for 8 or 9, a grunt or the head chop (now 152, 87, 88 '
                     'or 89 from a table, through the tail of the mud voice routine), the troll\'s grunt (1000:5801) '
                     'for the Balok\'s roars 34-37 (now one of the Amiga\'s eight, 136-142), and the rat on the skull '
                     '(1000:3DC1) for 101-104 (now 101-102, as on the Amiga). Moonstone Rebuilt\'s own sounds get ids '
                     'from 171 up, in the unused end of the table (171 = the mines\' BONFIRE2, which was id 26)',
            'bytes': k35,
        },
        'K36': {
            'title': 'Each sound id plays at the Amiga\'s pitch. The Amiga plays the same sample at a different rate for '
                     'each sound program (footsteps at three pitches, the Balok\'s roars at four, the troll\'s grunts '
                     '2.5 times slower than the file says); DOS played one rate per file. 1000:5995 now notes the id '
                     '(DS:' + f'{SOUND_LAST_ID:04X}' + 'h), and mov bx,6 before the driver call (1000:9537) becomes '
                     'int 63h, which SAVEHOOK.COM handles: it writes the id\'s time constant (table at DS:'
                     + f'{SOUND_RATES:04X}' + 'h, 0 = the file\'s own) into the copied VOC block. Needs SAVEHOOK.COM '
                     'resident',
            'bytes': k36,
        },
        'K37': {
            'title': 'Ids that are one part of a sample play only that part: the dragon\'s grunts 20-23 are the four '
                     'grunts in DRAGRU and the chomps 24-26 and 49-51 the three in CHOMPS; DOS played the whole sample '
                     'each time (three chomps for every bite). The K36 handler finds the id in a list (DS:'
                     + f'{SOUND_SLICES:04X}' + 'h: id, start, length) and writes a VOC block header just before the '
                     'part and an end mark after it, in the copy of the page made for this sound. Needs K36',
            'bytes': k37,
        },
        'D65': {
            'title': 'The Amiga version\'s sound effects from a SoundFont (Moonstone Rebuilt; needs the user\'s own Amiga '
                     'disk images at Setup). cmp word [8645h],3 at the start of the sound routine (1000:5979) becomes '
                     'int 63h, which SAVEHOOK.COM handles: when AMIGASND.FLG is there and the id has an Amiga sound '
                     'program, it sends "program change, note on" to the MIDI port (330h) on the next of four channels '
                     'and skips the Sound Blaster; otherwise it does the compare. Needs SAVEHOOK.COM resident',
            'bytes': [((0x1000, SOUND_PLAY_SITE), bytes.fromhex('833e458603'), bytes.fromhex('cd63909090'))],
        },
        'K38': {
            'title': 'A blocked blow makes its sword clash. CheckBlock (1000:4219) is the Amiga\'s routine with the call '
                     'that plays sound 17 left out: it loaded the number (mov ax,11h) and returned, so a block was '
                     'silent. (Before K35 the clash was heard when a knight was struck: id 18, the hit, played '
                     'SWORDCL.) The routine\'s end is rearranged in the same 14 bytes: the block that does not count '
                     '(both knights facing the same way) becomes dec word [77FCh] (it is 1 there) / pop di / pop si / '
                     'ret, and the block that holds mov al,11h / pop di / pop si / jmp 5970h. No caller uses ax',
            'bytes': [((0x1000, 0x4237), b'\x75\x1e', b'\x75\x17'),                # jne 4257h -> jne 4250h (no block)
                      ((0x1000, 0x424a), bytes.fromhex('7508' 'c706fc770000' 'eb03' 'b81100' '5f5ec3'),
                                         bytes.fromhex('7507' 'ff0efc77' '5f5ec3' 'b011' '5f5e' 'e91617'))],
        },
    }

PATCHES.update(_sound_patches())

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
