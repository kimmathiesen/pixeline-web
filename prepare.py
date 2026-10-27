"""Turn Pixeline game discs (ISO files or already-extracted folders) into the layout the web
player serves. The originals are only read, never changed.

Per game, into <data>/<slug>/:
  * the disc's game folder (the one holding the Director projector), all names lowercased
    so URLs work on case-sensitive file systems
  * main.dxr: the start movie extracted from the projector .exe (either byte order)
  * the Lingo name 'pathname' (which DirPlayer lacks) renamed to its synonym 'moviePath'
  * meta.json with the title

usage: prepare.py <data-dir> <iso-or-folder>...
"""
import json, os, re, shutil, struct, sys, tempfile, unicodedata

DIRECTOR_EXT = ('.dxr', '.cxt', '.cct', '.dir', '.cst', '.dcr')
RENAMES = {'pathname': 'moviePath'}


def slugify(name):
    s = name.lower().replace('æ', 'ae').replace('ø', 'oe').replace('å', 'aa')
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def title_of(path):
    return os.path.splitext(os.path.basename(path.rstrip('/\\')))[0]


# --- projector ---------------------------------------------------------------------------

def find_embedded_movie(b):
    """(offset, byte order) of the start movie inside a projector, or (-1, None). Windows-made
    projectors embed it little-endian (XFIR....39VM); Mac-made ones big-endian (RIFX....MV93)."""
    for tag, kind, order in ((b'XFIR', b'39VM', '<'), (b'RIFX', b'MV93', '>')):
        p = b.find(tag)
        while p != -1 and b[p+8:p+12] != kind:
            p = b.find(tag, p + 4)
        if p != -1:
            return p, order
    return -1, None


def find_projector(root):
    best = None
    for d, _, files in os.walk(root):
        for f in files:
            if not f.lower().endswith('.exe') or f.lower().startswith(('install', 'setup')):
                continue
            path = os.path.join(d, f)
            b = open(path, 'rb').read()
            if find_embedded_movie(b)[0] != -1 and (best is None or len(b) > best[0]):
                best = (len(b), path)
    return best and best[1]


def extract_main_movie(exe, out):
    """Write the projector's start movie as a standalone file, rebasing the absolute file
    offsets the embedded memory map uses."""
    b = open(exe, 'rb').read()
    p, order = find_embedded_movie(b)
    size = struct.unpack_from(order + 'I', b, p + 4)[0] + 8
    m = bytearray(b[p:p + size])
    u32 = lambda o: struct.unpack_from(order + 'I', m, o)[0]
    tag = lambda t: t[::-1] if order == '<' else t      # FourCCs are stored byte-swapped in XFIR
    mmap = u32(24)
    if m[mmap - p:mmap - p + 4] == tag(b'mmap'):
        off = mmap - p
        struct.pack_into(order + 'I', m, 24, off)
        hdr, esz = struct.unpack_from(order + 'HH', m, off + 8)
        for i in range(u32(off + 16)):
            e = off + 8 + hdr + i * esz
            if m[e:e+4] not in (tag(b'free'), tag(b'junk')) and u32(e + 8) >= p:
                struct.pack_into(order + 'I', m, e + 8, u32(e + 8) - p)
    open(out, 'wb').write(m)


def copy_linked_casts(game_dir):
    """The start movie links its casts by the author's absolute path, e.g.
    C:\\WINDOWS\\Skrivebord\\Menu\\Speak.cst, and DirPlayer looks for them next to main.dxr.
    Copy each from the game folder named in that path, so the right one of several
    same-named casts (every song folder has a Speak.cxt) is used."""
    b = open(os.path.join(game_dir, 'main.dxr'), 'rb').read()
    for m in re.finditer(rb'[A-Za-z]:\\(?:[ -\[\]-~]+\\)*?([ -\[\]-~]+)\\([ -\[\]-~]+?)\.c[sx]t\b', b):
        folder, name = (x.decode('latin-1').lower() for x in m.groups())
        sub = next((d for d in os.listdir(game_dir) if d.lower() == folder), None)
        src = sub and next((os.path.join(game_dir, sub, f) for f in os.listdir(os.path.join(game_dir, sub))
                            if f.lower() == name + '.cxt'), None)
        dst = os.path.join(game_dir, name + '.cxt')
        if src and not os.path.exists(dst):
            shutil.copyfile(src, dst)


# --- Lingo names -------------------------------------------------------------------------

def rename_lingo_names(path):
    """Rewrite Lnam chunks so built-ins DirPlayer lacks map to synonyms it has. The rebuilt
    chunk is appended and the memory map repointed; works for RIFX (big) and XFIR (little)."""
    b = bytearray(open(path, 'rb').read())
    if b[:4] not in (b'RIFX', b'XFIR') or not any(k.encode() in b for k in RENAMES):
        return 0
    E = '>' if b[:4] == b'RIFX' else '<'
    tag = (lambda t: t) if E == '>' else (lambda t: t[::-1])
    u32 = lambda o: struct.unpack_from(E + 'I', b, o)[0]
    off = u32(24)
    if b[off:off+4] != tag(b'mmap'):
        return 0
    hdr, esz = struct.unpack_from(E + 'HH', b, off + 8)
    n = 0
    for i in range(u32(off + 16)):
        e = off + 8 + hdr + i * esz
        if b[e:e+4] != tag(b'Lnam'):
            continue
        at, ln = u32(e + 8), u32(e + 4)
        d = bytes(b[at+8:at+8+ln])
        noff, cnt = struct.unpack_from('>HH', d, 16)     # Lingo chunks are always big-endian
        names, q = [], noff
        for _ in range(cnt):
            names.append(d[q+1:q+1+d[q]].decode('latin-1')); q += 1 + d[q]
        if not any(x in RENAMES for x in names):
            continue
        body = b''.join(bytes([len(x)]) + x.encode('latin-1') for x in (RENAMES.get(x, x) for x in names))
        new = bytearray(d[:noff]) + body
        struct.pack_into('>II', new, 8, len(new), len(new))
        if len(b) % 2: b.append(0)
        struct.pack_into(E + 'II', b, e + 4, len(new), len(b))
        b += tag(b'Lnam') + struct.pack(E + 'I', len(new)) + new
        n += 1
    if n:
        struct.pack_into(E + 'I', b, 4, len(b) - 8)
        open(path, 'wb').write(b)
    return n


# --- layout ------------------------------------------------------------------------------

def lowercase_tree(root):
    for d, dirs, files in os.walk(root, topdown=False):
        for name in files + dirs:
            low = name.lower()
            if low != name:
                os.rename(os.path.join(d, name), os.path.join(d, low))


def extract_iso(iso, dest):
    """Extract the ISO 9660 file system, using the Joliet tree for the long Danish names.
    The discs are Mac/PC hybrids; 7-Zip picks the Apple side there and writes zero-filled
    files, so the ISO 9660 directory records are read directly instead."""
    SECTOR = 2048
    with open(iso, 'rb') as f:
        def read(lba, size):
            f.seek(lba * SECTOR)
            return f.read(size)

        root, joliet, n = None, False, 16
        while True:
            vd = read(n, SECTOR)
            if vd[1:6] != b'CD001' or vd[0] == 255:
                break
            if vd[0] == 1 and root is None:
                root = vd[156:190]
            elif vd[0] == 2 and vd[88:90] == b'%/' and vd[90:91] in (b'@', b'C', b'E'):
                root, joliet = vd[156:190], True
            n += 1
        if root is None:
            raise RuntimeError('ikke en ISO 9660-skive')

        def walk(record, path):
            lba, size = struct.unpack_from('<I', record, 2)[0], struct.unpack_from('<I', record, 10)[0]
            data, p = read(lba, size), 0
            while p < len(data):
                ln = data[p]
                if ln == 0:                          # records never cross a sector boundary
                    p = (p // SECTOR + 1) * SECTOR
                    continue
                rec = data[p:p + ln]
                p += ln
                raw = rec[33:33 + rec[32]]
                if raw in (b'\x00', b'\x01'):
                    continue
                name = raw.decode('utf-16-be' if joliet else 'latin-1').split(';')[0].rstrip('.')
                target = os.path.join(path, name)
                if rec[25] & 2:
                    os.makedirs(target, exist_ok=True)
                    walk(rec, target)
                else:
                    flba, fsize = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
                    with open(target, 'wb') as out:
                        f.seek(flba * SECTOR)
                        left = fsize
                        while left:
                            chunk = f.read(min(left, 1 << 20))
                            if not chunk:
                                break
                            out.write(chunk)
                            left -= len(chunk)

        os.makedirs(dest, exist_ok=True)
        walk(root, dest)


def prepare(source, data_dir, log=print):
    title = title_of(source)
    slug = slugify(title)
    out = os.path.join(data_dir, slug)
    if os.path.exists(os.path.join(out, 'meta.json')):
        return slug
    with tempfile.TemporaryDirectory(dir=data_dir) as tmp:
        if os.path.isdir(source):
            disc = source
        else:
            log(f'{title}: pakker ISO ud')
            disc = os.path.join(tmp, 'disc')
            extract_iso(source, disc)
        exe = find_projector(disc)
        if not exe:
            log(f'{title}: fandt ingen Director-projector, springer over')
            return None
        stage = os.path.join(tmp, 'game')
        shutil.copytree(os.path.dirname(exe), stage, copy_function=shutil.copyfile)
        extract_main_movie(exe, os.path.join(stage, 'main.dxr'))
        copy_linked_casts(stage)
        for d, _, files in os.walk(stage):
            for f in files:
                p = os.path.join(d, f)
                if f.lower().endswith('.exe'):
                    os.remove(p)                      # the player never needs the projector
                elif f.lower().endswith(DIRECTOR_EXT):
                    rename_lingo_names(p)
        lowercase_tree(stage)
        with open(os.path.join(stage, 'meta.json'), 'w', encoding='utf-8') as fh:
            json.dump({'title': title, 'slug': slug}, fh, ensure_ascii=False)
        if os.path.exists(out):
            shutil.rmtree(out)
        shutil.move(stage, out)
    log(f'{title}: klar som /play/{slug}')
    return slug


if __name__ == '__main__':
    data = sys.argv[1]
    os.makedirs(data, exist_ok=True)
    for src in sys.argv[2:]:
        prepare(src, data)
