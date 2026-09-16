#!/usr/bin/env python3
"""Build web/website/ from the designer's Everguard website export.

Two jobs: make it cheap enough to open on a phone, and mount it INSIDE the
proposal site so there is one access code and one way home.

Why it is mounted rather than hosted separately: it was its own Netlify project
for a few hours, and that meant Chris typed the code twice, because
`netlify.app` is on the public suffix list and a cookie cannot span two
subdomains. Living at /website/ on the proposal site gives one gate, one login,
and a plain link back to the landing page.

The export is written for a domain root, so mounting it takes a deliberate
rewrite, all of it done here and verified afterwards:

  * every absolute path gains the /website prefix (assets, service routes, the
    four code files, the brand links)
  * app.js picks its service from path segment [1]; under a prefix that is [2],
    otherwise every service page silently renders the home page and then throws
    in capabilities.js because .service-hero does not exist
  * a "Back to the proposal" link is injected into the header and the footer,
    AFTER the path rewrite, so its href="/" still means the landing page

Image rules, each measured rather than guessed:

  photographs   WebP q80 at NATIVE 1536x1024. .service-photo is 53% of the
                viewport, so ~1526 device px at 2x on a 1440 laptop.
  eg-patrol     WebP q90, native, alpha kept. The lamp overlays clip this same
                image and run it through brightness(1.65), which is exactly
                where lossy artifacts show.
  shields       WebP q90 at 640x640, alpha kept. They look like 40px logos but
                eg-shield-outline is ALSO the SUV door decal at ~187 CSS px,
                about 560 at DPR 3, so 256 would mush it.
  orphans       on-site-security.png and dispatch-center.png are referenced
                nowhere; only the -v2 variants are used.

Run after any new export from the designer:  python3 optimize.py
"""
import argparse, hashlib, os, re, shutil, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..', 'web', 'website'))
DEFAULT_SOURCE = os.path.expanduser('~/Desktop/everguard-website/site')
BASE = '/website'

PHOTOS = ['on-site-security-v2', 'surveillance-monitoring', 'dispatch-center-v2',
          'personal-security', 'event-security']
SHIELDS = ['eg-shield-outline', 'eg-shield-solid']
ORPHANS = ['on-site-security.png', 'dispatch-center.png']
ASSET_VERSION = 11  # bump when assets change so caches cannot ask for old paths

# Absolute references in the export, each of which must gain the /website
# prefix. Written as the exact quoted token so a replace cannot run twice or
# catch something it should not.
PREFIX_TOKENS = ['"/assets/', '"/services/', '"/style.css', '"/app.js',
                 '"/capabilities.css', '"/capabilities.js', "'/assets/"]

BACK_LABEL = 'Back to the proposal'


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default=DEFAULT_SOURCE,
                    help='pristine export site/ folder (never modified)')
    args = ap.parse_args()
    src = os.path.abspath(args.source)
    if not os.path.isdir(src):
        sys.exit(f'source not found: {src}')
    if src == OUT:
        sys.exit('source must be the pristine export, not the build output')

    print(f'source : {src}\ntarget : {OUT}\n')
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(src, OUT)

    assets = os.path.join(OUT, 'assets')
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
        src_p, out_p = os.path.join(assets, name + '.png'), os.path.join(assets, name + '.webp')
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
              f'{old/1048576:5.2f}MB -> {os.path.getsize(out_p)/1024:4.0f}KB  q{quality}'
              f'{" alpha" if has_alpha else ""}')

    for name in PHOTOS:
        encode(name, 80)
    encode('eg-patrol', 90)
    for name in SHIELDS:
        encode(name, 90, box=(640, 640))

    shells = [os.path.join(OUT, 'index.html')] + [
        os.path.join(OUT, 'services', s, 'index.html')
        for s in sorted(os.listdir(os.path.join(OUT, 'services')))]
    code = [os.path.join(OUT, 'app.js'), os.path.join(OUT, 'capabilities.js')]

    # 1) .png -> .webp, then 2) prefix every absolute path for the mount.
    for path in shells + code:
        t = open(path, encoding='utf-8').read()
        for name in PHOTOS + ['eg-patrol'] + SHIELDS:
            t = t.replace(f'/assets/{name}.png', f'/assets/{name}.webp')
        for token in PREFIX_TOKENS:
            t = t.replace(token, token[0] + BASE + token[1:])
        t = t.replace('type="image/png" href="%s/assets/eg-shield-outline.png"' % BASE,
                      'type="image/webp" href="%s/assets/eg-shield-outline.webp"' % BASE)
        t = re.sub(r'\?v=\d+', f'?v={ASSET_VERSION}', t)
        open(path, 'w', encoding='utf-8').write(t)

    # 3) The router. Under /website/ the service slug is segment [2], not [1].
    app = os.path.join(OUT, 'app.js')
    t = open(app, encoding='utf-8').read()
    old_router = "location.pathname.split('/').filter(Boolean)[1]"
    new_router = "location.pathname.split('/').filter(Boolean)[2]"
    if old_router not in t:
        sys.exit('router line not found; the export changed shape, fix this script')
    t = t.replace(old_router, new_router)

    # 4) Brand and breadcrumb links point at the export's own root.
    t = t.replace('href="/"', f'href="{BASE}/"')

    # 5) Only now inject the way home, so href="/" still means the landing page.
    #    Joey could not get out of the website without the browser back button.
    header_anchor = '<div class="header-right">'
    assert header_anchor in t, 'header markup changed'
    t = t.replace(header_anchor,
                  header_anchor + f'<a class="to-proposal" href="/">{BACK_LABEL}</a>', 1)
    foot_anchor = '<a class="back-top" href="#top">'
    assert foot_anchor in t, 'footer markup changed'
    t = t.replace(foot_anchor,
                  f'<a class="to-proposal foot-back" href="/">{BACK_LABEL}</a>' + foot_anchor, 1)
    open(app, 'w', encoding='utf-8').write(t)

    # 6) Ours, appended so a fresh export cannot silently drop it. The phone
    #    fixes are measured problems in the export: .ending-nav is six links at
    #    13px with no padding (~18px tall) and is the main navigation on a
    #    phone; .back-top and .breadcrumb a are ~21px and ~17px; .progress-rail
    #    a is an 18px dot that still gets touched on an iPad, grown with a
    #    pseudo-element so the dot itself does not move; and 9px body type is
    #    smaller than anything allowed on the proposal side.
    with open(os.path.join(OUT, 'style.css'), 'a', encoding='utf-8') as fh:
        fh.write('\n/* ---- added by optimize.py, see the script comments ---- */\n'
                 '.to-proposal{display:inline-flex;align-items:center;min-height:44px;'
                 'font-family:"DM Sans",Arial,sans-serif;font-size:13px;font-weight:600;'
                 'letter-spacing:.02em;color:var(--muted);white-space:nowrap}\n'
                 '.to-proposal:hover,.to-proposal:focus-visible{color:var(--orange)}\n'
                 '.header-right .to-proposal{margin-right:4px}\n'
                 '.foot-back{margin-right:18px}\n'
                 '@media(max-width:700px){.header-right .to-proposal{font-size:12px}}\n'
                 '.ending-nav a{min-height:44px;display:flex;align-items:center}\n'
                 '.back-top{display:inline-flex;align-items:center;min-height:44px}\n'
                 '.breadcrumb a{display:inline-flex;align-items:center;min-height:44px}\n'
                 '.progress-rail a{position:relative}\n'
                 '.progress-rail a:after{content:"";position:absolute;inset:-13px}\n'
                 '@media(max-width:700px){.scroll-cue{font-size:11px}'
                 '.chapter-meta{font-size:11px}}\n')

    # Verify: nothing may still point at a domain-root path or a deleted png.
    bad = []
    for root, _, files in os.walk(OUT):
        for f in files:
            if f.endswith(('.html', '.js', '.css')):
                rel = os.path.relpath(os.path.join(root, f), OUT)
                body = open(os.path.join(root, f), encoding='utf-8', errors='ignore').read()
                bad += [f'{rel}: {m}' for m in re.findall(r'/assets/[\w.-]+\.png', body)]
                # capabilities.js sniffs the route with route.includes('/slug/').
                # Those are substring tests, not paths to fetch, and they still
                # match under the prefix, so they must stay unprefixed.
                for m in re.finditer(r'["\']/(?!website/)[\w.-]+[\w./-]*["\']', body):
                    token = m.group(0)
                    if token.strip('"\'') == '/':      # href="/" is the way home
                        continue
                    if body[max(0, m.start() - 9):m.start()].endswith('includes('):
                        continue
                    bad.append(f'{rel}: unprefixed {token}')

    after = sum(os.path.getsize(os.path.join(assets, f)) for f in os.listdir(assets))
    print(f'\nassets {before/1048576:.1f}MB -> {after/1024:.0f}KB')
    print('unprefixed or dangling references:', bad or 'none')
    if bad:
        sys.exit('refusing to finish with broken references')

    with open(os.path.join(HERE, 'ORIGINAL-ASSETS.md'), 'w', encoding='utf-8') as fh:
        fh.write('# Original export assets\n\nRecorded before optimization so the change is\n'
                 'auditable and reversible without the Desktop copy. The pristine export\n'
                 f'lives at `{src}` and is never modified by `optimize.py`.\n\n')
        fh.write('| file | size | mode | bytes | md5 |\n|---|---|---|---|---|\n')
        for name, dim, mode, size, digest in provenance:
            fh.write(f'| {name} | {dim} | {mode} | {size} | `{digest}` |\n')
    print('wrote ORIGINAL-ASSETS.md')


if __name__ == '__main__':
    main()
