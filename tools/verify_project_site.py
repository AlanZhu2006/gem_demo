"""Browser checks for responsive layout, real media, paper data, and navigation.

Run with /tmp/gem-site-env/bin/python while project_site is served on port 8765.
"""
from pathlib import Path
import json
import re
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/project_site_review'
URL = 'http://127.0.0.1:8765/'
PAPER = Path('/home/asus/Research/Nav-graph-blind/projects/paper')


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    errors = []
    requests = []
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: requests.append(r.url))
        page.on('response', lambda r: errors.append(f'{r.status} {r.url}') if r.status >= 400 else None)
        page.goto(URL, wait_until='networkidle')
        assert page.locator('#teaser').evaluate('(v) => v.paused && !v.getAttribute("src")')
        assert not any(url.endswith('.mp4') for url in requests), 'Videos downloaded before demand under reduced motion'
        assert page.locator('#author-block').is_hidden()
        assert page.locator('#arxiv-link').is_hidden()
        assert page.locator('#code-link').is_hidden()
        report['no_invented_metadata'] = True
        report['reduced_motion_no_autoplay_or_media_download'] = True

        # Audit all local source/link targets, including downloads and transcript.
        paths = page.locator('[href],[src],[data-src]').evaluate_all('els => els.flatMap(e => [e.getAttribute("href"),e.getAttribute("src"),e.getAttribute("data-src")]).filter(Boolean)')
        for value in set(paths):
            parsed = urlparse(value)
            if parsed.scheme or value.startswith('#'):
                continue
            assert (ROOT/'project_site'/parsed.path).is_file(), value
        assert context.request.get(URL+'transcript.html').status == 200
        report['local_links'] = True

        # Compare every displayed Table I row directly with canonical TeX.
        tex = (PAPER/'tables/main_matrix.tex').read_text()
        raw_rows = [line for line in tex.splitlines() if re.search(r'&\s*(NavDP|ViNT|NoMaD)\s*&', line)]
        expected = []
        for line in raw_rows:
            cols = [x.strip() for x in line.split('&')]
            gem = re.search(r'\{(\d+/\d+)\}', cols[3]).group(1)
            delta, ci = cols[6].split(' ', 1)
            expected.append([cols[1], cols[2], gem, '+'+delta, ci])
        for index, name in enumerate(['hm3d', 'mp3d']):
            page.locator(f'#dataset-{name}').click()
            rows = page.locator('#result-rows tr').evaluate_all('rows => rows.map(r => [...r.children].map(c => c.textContent.trim()))')
            assert rows == expected[index*3:index*3+3], (name, rows, expected)
        page.locator('#dataset-mp3d').press('ArrowLeft')
        assert page.locator('#dataset-hm3d').get_attribute('aria-selected') == 'true'
        report['both_datasets_match_paper'] = True

        for name in ['outdoor', 'simulation', 'indoor']:
            page.locator(f'#tab-{name}').click()
            assert page.locator('#demo-video').get_attribute('src') == f'assets/{name}.mp4'
            page.locator('#demo-video').evaluate('(v) => v.play()')
            page.wait_for_function('document.querySelector("#demo-video").currentTime > .1')
            page.locator('#demo-video').evaluate('(v) => v.pause()')
        report['all_demonstrations_decode_and_play'] = True

        for name in ['overview', 'memory', 'readout', 'full']:
            page.locator('#method-'+name).click()
            page.wait_for_function('document.querySelector("#method-image").complete && document.querySelector("#method-image").naturalWidth > 0')
            page.locator('#expand-figure').click()
            assert page.locator('#figure-dialog').evaluate('(d) => d.open')
            page.keyboard.press('Escape')
            assert not page.locator('#figure-dialog').evaluate('(d) => d.open')
        report['method_tabs_and_dialog'] = True

        page.locator('#presentation').evaluate('(v) => v.play()')
        page.wait_for_function('document.querySelector("#presentation").currentTime > .1')
        assert page.locator('#demo-video').evaluate('(v) => v.paused')
        page.locator('#presentation').evaluate('(v) => v.pause()')
        report['full_film_plays'] = True

        # Axe runs are useful for actual tabs/dialog markup and contrast, not snapshots.
        axe = Path('/tmp/gem-web-check/node_modules/axe-core/axe.min.js')
        if axe.exists():
            page.add_script_tag(path=str(axe))
            result = page.evaluate('async () => await axe.run(document, {runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"]}})')
            violations = [{k: v[k] for k in ['id', 'impact', 'description', 'nodes']} for v in result['violations']]
            (OUT/'accessibility.json').write_text(json.dumps(violations, indent=2))
            assert not violations, [(v['id'], [n['target'] for n in v['nodes']]) for v in violations]
            report['automated_accessibility'] = 'No WCAG 2 A/AA or 2.1 AA violations detected by axe-core; not a full manual accessibility certification.'

        # Stable poster states for review; desktop and phone screenshots.
        page.reload(wait_until='networkidle')
        page.screenshot(path=str(OUT/'desktop.png'), full_page=True)
        page.screenshot(path=str(OUT/'desktop_first_screen.png'))
        for name in ['demonstrations', 'method', 'results']:
            page.locator('#'+name).screenshot(path=str(OUT/(name+'.png')))
        layouts = []
        for width in [320, 390, 768, 1440]:
            page.set_viewport_size({'width': width, 'height': 844 if width < 600 else 1000})
            page.reload(wait_until='networkidle')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
            for name in ['overview', 'memory', 'readout']:
                page.locator('#method-'+name).click()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), (width, name)
            page.locator('#method-full').click()
            if width == 390:
                page.evaluate('scrollTo(0,0)')
                page.screenshot(path=str(OUT/'mobile.png'), full_page=True)
            layouts.append(width)
        report['no_page_overflow_at_widths'] = layouts
        assert not errors, errors
        report['browser_errors'] = errors

        # Automatic teaser playback is viewport-aware in the standard motion setting.
        normal = browser.new_page(viewport={'width': 1440, 'height': 1000})
        normal.goto(URL, wait_until='networkidle')
        normal.locator('#teaser').scroll_into_view_if_needed()
        normal.wait_for_function('document.querySelector("#teaser").currentTime > .1')
        normal.locator('#teaser-toggle').click()
        assert normal.locator('#teaser').evaluate('(v) => v.paused')
        normal.locator('#teaser-toggle').click()
        normal.wait_for_function('!document.querySelector("#teaser").paused')
        normal.locator('#film').scroll_into_view_if_needed()
        normal.wait_for_function('document.querySelector("#teaser").paused')
        report['teaser_play_pause_and_offscreen_pause'] = True
        browser.close()
    report['passed'] = True
    (OUT/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
