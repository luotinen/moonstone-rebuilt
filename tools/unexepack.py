"""Microsoft EXEPACK unpacker: turns an EXEPACK-compressed MZ executable into a plain MZ executable with a normal
relocation table. Used for INTR.EXE directly and for MAIN.EXE after its PKLITE layer (see make_main_exe.py).
Usage: python -I tools/unexepack.py <packed.exe> <unpacked.exe>"""
import sys, struct

def unexepack(data):
    h = struct.unpack('<14H', data[:28])
    image = data[h[4] * 16:(h[2] - 1) * 512 + (h[1] or 512)]
    stub = h[11] * 16                               # EXEPACK header sits at CS:0
    real_ip, real_cs, _mem_start, _size, real_sp, real_ss, dest_paras, _skip, sig = \
        struct.unpack('<8H2s', image[stub:stub + 18])
    if sig != b'RB':
        raise ValueError('not an EXEPACK executable')
    src = image[:stub]
    dst = bytearray(dest_paras * 16)
    dst[:len(src)] = src
    s = len(src) - 1
    while src[s] == 0xff:                           # up to 15 bytes of padding
        s -= 1
    d = len(dst)
    while True:                                     # commands are read backwards from the end
        op, length = src[s], src[s - 2] | src[s - 1] << 8
        s -= 3
        if op & 0xfe == 0xb0:                       # fill: one byte repeated
            d -= length
            dst[d:d + length] = bytes([src[s]]) * length
            s -= 1
        elif op & 0xfe == 0xb2:                     # copy
            d -= length
            dst[d:d + length] = src[s - length + 1:s + 1]
            s -= length
        else:
            raise ValueError(f'bad EXEPACK command {op:02x} at {s}')
        if op & 1:
            break
    if s + 1 != d:
        raise ValueError('EXEPACK stream did not end where expected')
    # Relocation table: after the "Packed file is corrupt" message, 16 groups (segment n*0x1000) of count + offsets.
    tail = image[stub:]
    p = tail.index(b'Packed file is corrupt') + len(b'Packed file is corrupt')
    relocs = []
    for group in range(16):
        n = struct.unpack('<H', tail[p:p + 2])[0]; p += 2
        for _ in range(n):
            relocs.append((struct.unpack('<H', tail[p:p + 2])[0], group * 0x1000)); p += 2
    return build_mz(dst, relocs, real_cs, real_ip, real_ss, real_sp, min_paras=0)

def build_mz(image, relocs, cs, ip, ss, sp, min_paras):
    header = bytearray(struct.pack('<14H', 0x5a4d, 0, 0, len(relocs), 0, min_paras, 0xffff, ss, sp, 0, ip, cs, 28, 0))
    for off, seg in relocs:
        header += struct.pack('<HH', off, seg)
    while len(header) % 16:
        header += b'\0'
    out = header + bytes(image)
    struct.pack_into('<5H', out, 2, len(out) % 512, (len(out) + 511) // 512, len(relocs), len(header) // 16, min_paras)
    return bytes(out)

if __name__ == '__main__':
    open(sys.argv[2], 'wb').write(unexepack(open(sys.argv[1], 'rb').read()))
