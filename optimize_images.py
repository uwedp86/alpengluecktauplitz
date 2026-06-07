#!/usr/bin/env python3
"""Generate responsive, web-optimized image variants for Alpenglück Tauplitz.

Reads the full-resolution originals in images/*.jpg and writes downscaled
WebP + JPEG-fallback variants into images/opt/. Re-runnable and idempotent:
it only regenerates a variant when the source is newer than the output.

Naming: images/opt/<name>-<width>.<ext>
  - gallery images: 800 + 1600 WebP, 1200 JPEG fallback
  - hero image:     1200 + 2000 WebP, 1600 JPEG fallback

The lightbox uses the widest WebP variant for a sharp full-screen view,
which is still a fraction of the multi-megabyte camera originals.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "images")
OUT_DIR = os.path.join(SRC_DIR, "opt")

# Per-image variant plans: list of (width, format, quality)
GALLERY_PLAN = [
    (800, "webp", 80),
    (1600, "webp", 80),
    (1200, "jpg", 82),
]
HERO_PLAN = [
    (1200, "webp", 80),
    (2000, "webp", 82),
    (1600, "jpg", 82),
]

HERO = "hero.jpg"


def variant_path(name, width, ext):
    return os.path.join(OUT_DIR, "%s-%d.%s" % (name, width, ext))


def needs_build(src, dst):
    return not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src)


def save_variant(im, src, name, width, ext, quality):
    dst = variant_path(name, width, ext)
    if not needs_build(src, dst):
        return False
    # Never upscale.
    target_w = min(width, im.width)
    target_h = round(im.height * target_w / im.width)
    resized = im.resize((target_w, target_h), Image.LANCZOS)
    if ext == "webp":
        resized.save(dst, "WEBP", quality=quality, method=6)
    else:
        resized.convert("RGB").save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for fname in sorted(os.listdir(SRC_DIR)):
        if not fname.endswith(".jpg"):
            continue
        src = os.path.join(SRC_DIR, fname)
        name = os.path.splitext(fname)[0]
        plan = HERO_PLAN if fname == HERO else GALLERY_PLAN
        with Image.open(src) as im:
            im = im.convert("RGB")
            for width, ext, quality in plan:
                built = save_variant(im, src, name, width, ext, quality)
                tag = "wrote" if built else "skip "
                print(tag, os.path.relpath(variant_path(name, width, ext), ROOT))


if __name__ == "__main__":
    main()
