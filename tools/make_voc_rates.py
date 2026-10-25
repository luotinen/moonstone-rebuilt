"""K10: play the sound effects at their real rates. Every DOS sample (SAMPLES/*, and the copy DISKA/CAMEL4) is a
Creative VOC file with one 8-bit data block whose time constant is 194 (16,129 Hz). The sample data is byte for byte
the Amiga version's 8SVX sample, which the Amiga plays at its own rate (4,766-22,655 Hz), so on DOS most sounds play
too fast and too high. MAIN.EXE plays them through CT-VOICE.DRV from the first data block (1000:951D), and the driver
takes the rate from that block, so only the time-constant byte changes: 256 - 1,000,000 / rate.

RATES lists each file's rate (from the Amiga 8SVX headers; the Amiga sample name is in the comment) and the start of
the SHA-256 of the unchanged GOG file, so a file is only changed when it is the expected one. No Amiga files needed.
Usage: python -I tools/make_voc_rates.py <game dir> <output dir>   (writes <output dir>/SAMPLES/* and DISKA/CAMEL4)"""
import sys, os, struct, hashlib

RATES = {
    'BALAND': (11186, 'e8ebfd0affc2ca1f'),    # baland1
    'BALSHAKE': (16726, '94743cbf1c605101'),  # balshake3
    'BEAST1': (6005, '052f4822693e8319'),     # BEAST1.SND
    'BLOODSP': (16726, '559692c904caeef6'),   # BLOODSPURT7B
    'BONFIRE2': (8363, '989d335d4ebdf9d8'),   # bonfire2
    'CAMEL3B': (11116, 'c6aaacb0dcc17768'),   # CAMEL3B
    'CAMEL4': (11116, '19eb3be88849718b'),    # CAMEL4B
    'CAMEL7': (11116, 'a226579f20daf10c'),    # CAMEL7B
    'CHEAP1B': (16726, '39120aef0e9ac023'),   # cheap1b
    'CHEAP2B': (16726, '0fa8919d1848ca89'),   # cheap2b
    'CHOMPS': (7046, 'f66e00609122ee6f'),     # 3*chomps2
    'CHOMPS2': (7046, 'f66e00609122ee6f'),    # 3*chomps2
    'DAGMUF3': (8363, 'c83fe0fb6d1019b1'),    # dragmufl4B
    'DRAGNR': (8971, '2daf8fb289c7d333'),     # dragonbreth1b
    'DRAGRU': (4766, '880e00f5eba8872d'),     # dragongrunts1b
    'FEMSCR': (14037, 'd8a5516be65eb297'),    # femscrm4b
    'GRNT1': (11116, '7d78b08f6d90bb18'),     # grnt1c
    'GRNT3': (11116, 'a813a6a74c3ef6c9'),     # grnt3b
    'GRNT3B': (16726, 'b5c23e0fb7f06f3e'),    # grnt3
    'HEADCHOP': (11327, '5cd80a7a333e9206'),  # headchop
    'HEDLAND': (10528, '5159d6bfcf6073d7'),   # HEDLAND2
    'HIT3': (8363, '63b0adb603ced8ca'),       # Hit3.snd
    'KSTEP': (11186, 'bb1a06d92ccdf183'),     # knitestep3C
    'LION1C1': (11116, '3196ea8ac8a601bc'),   # SNDLION1c
    'LION2C1': (11116, '9bcdce829df8c707'),   # SNDLION2c
    'MUD2': (10026, '42122240db58b2f2'),      # mud2
    'MUDFAL': (11186, '854e8532e584bb41'),    # mudfal1
    'MUDHIT': (16726, '257ced99a8798116'),    # mudhit2x
    'MUDVOX': (16726, '19f5338295dc92f4'),    # mudvox1c
    'NEWKRUSH': (9346, 'db659dc108d1e82b'),   # newkrush1c
    'NITLAND': (5965, 'fe30030c9e795b43'),    # NITELAND2d
    'POPHED12': (11186, '05771c7c7d013d06'),  # pophed1
    'RATGOUG': (22655, '7d93ec1811e895ba'),   # ratgoug2 (22,727 Hz after rounding; fine on the SB16)
    'RATLEAP': (6302, 'e44a8dd981fce601'),    # ratleap1d
    'RATMPAL': (14204, '5d2bebcfdab339d8'),   # ratmpal2
    'RATSCR': (16726, '1b54e3e2a8491bf9'),    # ratscream1
    'RATSKU': (15040, 'e4089b476409ef08'),    # ratskul3
    'RJGRUNT': (15838, '9258cf090f584450'),   # RJGRUNT2
    'RJGRUNT1': (16726, '273bc195a3202fbf'),  # RJGRUNT3
    'RJGRUNT2': (16726, 'f1a4c8378c41c700'),  # RJGRUNT7
    'RJGRUNT3': (16726, '65006bb9d3bf5888'),  # RJGRUNT8
    'RJGRUNT4': (16726, '1ceb851eadbf195e'),  # RJGRUNT9
    'SCRAPE': (16726, '46958a7e760a8d80'),    # Scrape3b
    'SLICE3': (16726, 'bfeb310ac61989bc'),    # SLICE3
    'SPEAR1': (16726, '2d07751ff7709750'),    # SPEAR1
    'STRETCH': (6005, '9298fd7c71c91d70'),    # stretch2
    'SWISH': (11186, 'f4e6ce68a6b9b052'),     # swish1
    'SWORDCL': (7426, 'c7ae319c69eba5f1'),    # SwordClash3.snd
    'WIPCRAK': (8363, '22174aa4e12b6b3d'),    # wipcrak1c
}
FILES = [f'SAMPLES/{name}' for name in RATES] + ['DISKA/CAMEL4']

def fix_rate(voc, name):
    rate, digest = RATES[name]
    if hashlib.sha256(voc).hexdigest()[:16] != digest:
        raise ValueError(f'{name}: not the expected GOG file')
    out = bytearray(voc)
    block = struct.unpack('<H', voc[20:22])[0]
    if voc[block] != 1 or voc[block + 4] != 194 or voc[block + 5] != 0:
        raise ValueError(f'{name}: unexpected VOC block')
    out[block + 4] = round(256 - 1_000_000 / rate)
    return bytes(out)

def main(game, out):
    for rel in FILES:
        name = os.path.basename(rel)
        data = fix_rate(open(os.path.join(game, rel), 'rb').read(), name)
        os.makedirs(os.path.join(out, os.path.dirname(rel)), exist_ok=True)
        open(os.path.join(out, rel), 'wb').write(data)
        tc = data[struct.unpack('<H', data[20:22])[0] + 4]
        print(f'{rel:18} {RATES[name][0]:6} Hz -> time constant {tc} ({round(1_000_000 / (256 - tc))} Hz)')

if __name__ == '__main__':
    main(*sys.argv[1:3])
