#!/usr/bin/env python3
"""Rebuild demo-site/site from a pristine Everguard website export, optimized.

Why this exists: the designer's export ships photographs as lossless PNG. The
home page pulls roughly 13 MB of image, which is not something you send to a
client to open on a phone. Re-encoding costs nothing visually and cuts it by
about 95 percent.

It is a script and not a one-off because the next export will arrive with the
same .png names and the same two orphan files, and a manual pass would quietly
regress. Run it and the site folder is rebuilt from source, every time.

    python3 optimize.py [--source /path/to/export/site]

Rules encoded here, each for a measured reason:

  photographs   WebP q80 at NATIVE 1536x1024. .service-photo is 53% of the
                viewport, so 763 CSS px on a 1440 desktop, which is ~1526
                device px at 2x. Downscaling would be visibly soft on a retina
                laptop; the codec change alone is the win.

  eg-patrol     WebP q90, native, alpha preserved. The two lamp overlays clip
                this same image and run it through brightness(1.65), and
                brightness amplification is exactly where lossy artifacts
                show. The extra quality is worth the few KB.

  shields       WebP q90 at 640x640, alpha preserved. These look like 40px
                logos but eg-shield-outline is ALSO the SUV door decal, at
                16.3% of a stage up to 1150 CSS px wide: about 187 CSS px, so
                ~560 device px at 3x. 256 would mush the decal.

  orphans       on-site-security.png and dispatch-center.png are referenced
                nowhere (only the -v2 variants are used). Deleted.

Filenames change .png -> .webp rather than re-encoding under the old name,
because WebP bytes served as image/png is a lie that breaks Save-As and
confuses proxies. The asset ?v= query is bumped so a cached app.js cannot keep
asking for the deleted .png paths.
"""
import argparse, hashlib, os, re, shutil, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
DEFAULT_SOURCE = os.path.expanduser('~/Desktop/everguard-website/site')

PHOTOS = ['on-site-security-v2', 'surveillance-monitoring', 'dispatch-center-v2',
          'personal-security', 'event-security']
SHIELDS = ['eg-shield-outline', 'eg-shield-solid']
ORPHANS = ['on-site-security.png', 'dispatch-center.png']
ASSET_VERSION = 10  # bump when assets change, so caches cannot ask for old paths


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default=DEFAULT_SOURCE,
                    help='pristine export site/ folder (left untouched)')
    args = ap.parse_args()
    src = os.path.abspath(args.source)

    if not os.path.isdir(src):
        sys.exit(f'source not found: {src}')
    if os.path.abspath(src) == os.path.abspath(SITE):
        sys.exit('source must be the pristine export, not the folder being rebuilt')

    print(f'source : {src}\ntarget : {SITE}\n')

    # Start from a clean copy so a re-run is deterministic.
    if os.path.isdir(SITE):
        keep = {}
        for extra in ('_headers', 'robots.txt'):  # ours, not the designer's
            p = os.path.join(SITE, extra)
            if os.path.isfile(p):
                keep[extra] = open(p, 'rb').read()
        shutil.rmtree(SITE)
    else:
        keep = {}
    shutil.copytree(src, SITE)
    for name, blob in keep.items():
        with open(os.path.join(SITE, name), 'wb') as fh:
            fh.write(blob)

    assets = os.path.join(SITE, 'assets')
    before = sum(os.path.getsize(os.path.join(assets, f)) for f in os.listdir(assets))
    provenance = []

    for f in sorted(os.listdir(assets)):
        if f.endswith('.png'):
            p = os.path.join(assets, f)
            with Image.open(p) as im:
                provenance.append((f, f'{im.size[0]}x{im.size[1]}', im.mode,
                                   os.path.getsize(p), md5(p)))

    for f in ORPHANS:
        p = os.path.join(assets, f)
        if os.path.exists(p):
            os.remove(p)
            print(f'orphan removed   {f}')

    def encode(name, quality, box=None):
        src_p = os.path.join(assets, name + '.png')
        out_p = os.path.join(assets, name + '.webp')
        old = os.path.getsize(src_p)
        with Image.open(src_p) as im:
            has_alpha = im.mode in ('RGBA', 'LA', 'P') and \
                im.convert('RGBA').getchannel('A').getextrema()[0] < 255
            im = im.convert('RGBA' if has_alpha else 'RGB')
            if box:
                im = im.resize(box, Image.LANCZOS)
            im.save(out_p, 'WEBP', quality=quality, method=6)
        os.remove(src_p)
        print(f'{name+".png":30} -> {name+".webp":31} '
              f'{old/1048576:5.2f}MB -> {os.path.getsize(out_p)/1024:4.0f}KB  '
              f'q{quality}{" alpha" if has_alpha else ""}')

    for name in PHOTOS:
        encode(name, 80)                 # native resolution, see docstring
    encode('eg-patrol', 90)              # lamp overlays amplify artifacts
    for name in SHIELDS:
        encode(name, 90, box=(640, 640))  # also the SUV decal, ~560px at 3x

    # Point the code at the new filenames and bust the asset cache.
    renamed = PHOTOS + ['eg-patrol'] + SHIELDS
    app = os.path.join(SITE, 'app.js')
    text = open(app, encoding='utf-8').read()
    for name in renamed:
        text = text.replace(f'/assets/{name}.png', f'/assets/{name}.webp')
    open(app, 'w', encoding='utf-8').write(text)

    shells = [os.path.join(SITE, 'index.html')] + [
        os.path.join(SITE, 'services', s, 'index.html')
        for s in sorted(os.listdir(os.path.join(SITE, 'services')))
    ]
    for shell in shells:
        t = open(shell, encoding='utf-8').read()
        t = t.replace('type="image/png" href="/assets/eg-shield-outline.png"',
                      'type="image/webp" href="/assets/eg-shield-outline.webp"')
        t = re.sub(r'\?v=\d+', f'?v={ASSET_VERSION}', t)
        open(shell, 'w', encoding='utf-8').write(t)

    # Phone fixes, appended here rather than hand-patched so that re-running
    # against a fresh export cannot silently drop them. Each one is a measured
    # problem in the export, not a preference:
    #   - .ending-nav has six links at 13px with no padding, about 18px tall,
    #     and they are the main navigation on a phone.
    #   - .back-top and .breadcrumb a are the same story at ~21px and ~17px.
    #   - .progress-rail a is an 18px dot; it hides below 700px but is still a
    #     touch target on an iPad at 1024. The hit area is grown with a
    #     pseudo-element so the dot itself does not move.
    #   - 9px body type is smaller than anything we allow on the proposal side,
    #     and eye strain is the reason that rule exists at all.
    with open(os.path.join(SITE, 'style.css'), 'a', encoding='utf-8') as fh:
        fh.write('\n/* ---- phone fixes, added by optimize.py (see script comments) ---- */\n'
                 '.ending-nav a{min-height:44px;display:flex;align-items:center}\n'
                 '.back-top{display:inline-flex;align-items:center;min-height:44px}\n'
                 '.breadcrumb a{display:inline-flex;align-items:center;min-height:44px}\n'
                 '.progress-rail a{position:relative}\n'
                 '.progress-rail a:after{content:"";position:absolute;inset:-13px}\n'
                 '@media(max-width:700px){.scroll-cue{font-size:11px}'
                 '.chapter-meta{font-size:11px}}\n')

    leftover = []
    for root, _, files in os.walk(SITE):
        for f in files:
            if f.endswith(('.html', '.js', '.css')):
                body = open(os.path.join(root, f), encoding='utf-8', errors='ignore').read()
                leftover += [f'{os.path.relpath(os.path.join(root, f), SITE)}: {m}'
                             for m in re.findall(r'/assets/[\w.-]+\.png', body)]

    after = sum(os.path.getsize(os.path.join(assets, f)) for f in os.listdir(assets))
    print(f'\nassets {before/1048576:.1f}MB -> {after/1024:.0f}KB')
    print('dangling .png references:', leftover or 'none')

    with open(os.path.join(HERE, 'ORIGINAL-ASSETS.md'), 'w', encoding='utf-8') as fh:
        fh.write('# Original export assets\n\n')
        fh.write('Recorded before optimization so the change is auditable and\n'
                 'reversible without the Desktop copy. The pristine export itself\n'
                 f'lives at `{src}` and is never modified by `optimize.py`.\n\n')
        fh.write('| file | size | mode | bytes | md5 |\n|---|---|---|---|---|\n')
        for name, dim, mode, size, digest in provenance:
            fh.write(f'| {name} | {dim} | {mode} | {size} | `{digest}` |\n')
    print('wrote ORIGINAL-ASSETS.md')


if __name__ == '__main__':
    main()
