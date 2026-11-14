import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

out = Path('frontend/.preview')
out.mkdir(exist_ok=True)
results = []
expect.set_options(timeout=30000)
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, height in [(1440, 960), (768, 1024), (390, 844)]:
        page = browser.new_page(viewport={"width": width, "height": height}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(os.getenv('APP_URL', 'http://127.0.0.1:5173'), wait_until='networkidle')
        expect(page.locator('.employee-row').first).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'
        page.locator('.rail-links button').filter(has_text='All').click()
        expect(page.locator('.employee-row')).to_have_count(15)
        box = page.locator('.employee-list').bounding_box()
        page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(200)
        assert page.locator('.employee-list').evaluate('(e) => e.scrollHeight <= e.clientHeight || e.scrollTop > 0'), 'Queue cannot scroll'
        page.locator('.employee-row').last.click()
        expect(page.locator('.detail')).to_be_visible()
        page.screenshot(path=str(out / f'fresh-{width}-review.png'), full_page=True)
        page.get_by_role('button', name='Results', exact=True).click()
        expect(page.locator('.report-scoreline')).to_be_visible()
        page.screenshot(path=str(out / f'fresh-{width}-results.png'), full_page=True)
        page.get_by_role('button', name='Quality', exact=True).click()
        expect(page.locator('.quality-checks')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Report overflow'
        assert not errors, errors
        results.append({'viewport': width, 'scroll': 'passed', 'reports': 'passed', 'errors': errors})
        page.close()
    browser.close()
print(json.dumps(results, indent=2))
