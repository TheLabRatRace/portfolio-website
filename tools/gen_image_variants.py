"""Generate width variants of the site's images, plus a manifest for srcset.

A gallery card is ~347 CSS px on a desktop and ~280 on a phone; the source
files are 1135px square. Every visitor pays for the full image and the browser
throws most of it away. This emits smaller copies alongside each source and
records what exists, so the template can offer the browser a choice.

    python tools/gen_image_variants.py                    # whole images tree
    python tools/gen_image_variants.py --dir stress       # one subdirectory
    python tools/gen_image_variants.py --widths 360,720   # custom ladder
    python tools/gen_image_variants.py --prune            # drop orphaned variants

Idempotent: a variant whose file is newer than its source is left alone, so a
re-run after adding ten images costs ten encodes, not four hundred.

Requires cwebp (`brew install webp`). Pillow is deliberately not a dependency
-- this runs on a developer's machine a few times a year, and cwebp is already
the encoder that produced the sources.
"""

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE_ROOT = ROOT / "app" / "static" / "images"
MANIFEST = IMAGE_ROOT / "variants.json"

DEFAULT_WIDTHS = (360, 540, 720, 1080)
SOURCE_SUFFIXES = (".webp",)

# `name-360w.webp` -- how a generated file is told apart from a source. Sources
# are never named this way, so the scan can skip its own output on a re-run.
VARIANT_RE = re.compile(r"-(\d+)w$")


def webp_size(path):
    """Read (width, height) out of a WebP header.

    Three container flavours exist and they store the dimensions in three
    different places, so all three are handled. Returns None for anything that
    does not parse rather than guessing -- a wrong width would put a wrong
    number in the srcset, which is worse than no srcset.
    """
    with path.open("rb") as fh:
        head = fh.read(32)
    if len(head) < 30 or head[:4] != b"RIFF" or head[8:12] != b"WEBP":
        return None
    fourcc = head[12:16]
    if fourcc == b"VP8X":
        # Extended: canvas size is two 24-bit little-endian (value - 1) fields.
        w = int.from_bytes(head[24:27], "little") + 1
        h = int.from_bytes(head[27:30], "little") + 1
        return w, h
    if fourcc == b"VP8L":
        # Lossless: 0x2f signature, then 14 bits width-1 and 14 bits height-1.
        if head[20] != 0x2F:
            return None
        bits = struct.unpack("<I", head[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if fourcc == b"VP8 ":
        # Lossy: a 3-byte frame tag, then the start code, then 14-bit dimensions.
        if head[23:26] != b"\x9d\x01\x2a":
            return None
        w = struct.unpack("<H", head[26:28])[0] & 0x3FFF
        h = struct.unpack("<H", head[28:30])[0] & 0x3FFF
        return w, h
    return None


def sources(base):
    """Every source image under `base`, excluding variants we generated."""
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if VARIANT_RE.search(path.stem):
            continue
        yield path


def variant_path(source, width):
    return source.with_name(f"{source.stem}-{width}w{source.suffix}")


def encode(source, dest, width, quality):
    subprocess.run(
        ["cwebp", "-quiet", "-q", str(quality), "-resize", str(width), "0",
         str(source), "-o", str(dest)],
        check=True,
    )


def prune(base, keep):
    """Delete variants no source claims -- e.g. after narrowing --widths."""
    removed = 0
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            if VARIANT_RE.search(path.stem) and path not in keep:
                path.unlink()
                removed += 1
    return removed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="",
                    help="subdirectory of app/static/images to process")
    ap.add_argument("--widths", default=",".join(str(w) for w in DEFAULT_WIDTHS))
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--prune", action="store_true",
                    help="delete variants not in the current width ladder")
    ap.add_argument("--force", action="store_true",
                    help="re-encode even when the variant is already current")
    args = ap.parse_args()

    if not shutil.which("cwebp"):
        sys.exit("cwebp not found on PATH -- `brew install webp`")

    base = IMAGE_ROOT / args.dir if args.dir else IMAGE_ROOT
    if not base.is_dir():
        sys.exit(f"no such directory: {base}")

    widths = sorted({int(w) for w in args.widths.split(",") if w.strip()})

    # The manifest covers the whole tree, so a run over one subdirectory merges
    # into what is already there instead of erasing the other directories.
    manifest = {}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())

    made = skipped = 0
    keep = set()

    for source in sources(base):
        size = webp_size(source)
        if size is None:
            print(f"  ?  {source.relative_to(IMAGE_ROOT)}  (unreadable header)")
            continue
        src_w = size[0]
        key = source.relative_to(IMAGE_ROOT).as_posix()

        available = []
        for width in widths:
            # Upscaling invents detail and costs bytes. A source narrower than
            # the ladder step is already the best answer for that step.
            if width >= src_w:
                continue
            dest = variant_path(source, width)
            keep.add(dest)
            if (not args.force and dest.exists()
                    and dest.stat().st_mtime >= source.stat().st_mtime):
                skipped += 1
            else:
                encode(source, dest, width, args.quality)
                made += 1
            available.append(width)

        # The source itself is the widest candidate, so it belongs in the list
        # the template hands the browser.
        available.append(src_w)
        manifest[key] = sorted(set(available))

    if args.prune:
        # Only prune what this run actually walked; a --dir run must not delete
        # the variants belonging to a directory it never looked at.
        removed = prune(base, keep)
        for key in [k for k in manifest if (IMAGE_ROOT / k).parent.is_relative_to(base)]:
            if not (IMAGE_ROOT / key).exists():
                del manifest[key]
        print(f"pruned {removed} orphaned variant(s)")

    # One line per image: still valid JSON, but a diff after adding a photo is
    # one line instead of a reflowed file.
    body = ",\n".join(
        f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in sorted(manifest.items())
    )
    MANIFEST.write_text("{\n" + body + "\n}\n")

    total = sum(len(v) for v in manifest.values())
    print(f"encoded {made}, up to date {skipped}")
    print(f"manifest {MANIFEST.relative_to(ROOT)}: "
          f"{len(manifest)} image(s), {total} candidate(s)")


if __name__ == "__main__":
    main()
