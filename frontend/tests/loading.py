import asyncio
import json
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 960})
        async def slow(route):
            await asyncio.sleep(1.2)
            await route.continue_()
        await page.route('**/api/v1/**', slow)
        await page.goto('http://127.0.0.1:5173', wait_until='domcontentloaded')
        await expect(page.locator('.list-skeleton').first).to_be_visible()
        await page.screenshot(path='frontend/.preview/fresh-loading.png')
        await expect(page.locator('.employee-row').first).to_be_visible(timeout=10000)
        await page.get_by_role('button', name='Results', exact=True).click()
        await expect(page.locator('.report-skeleton')).to_be_visible()
        await expect(page.locator('.report-scoreline')).to_be_visible(timeout=10000)
        await page.emulate_media(reduced_motion='reduce')
        reduced = await page.locator('.report-scoreline').evaluate('(e) => getComputedStyle(e).animationDuration')
        await page.unroute('**/api/v1/**', slow)
        await page.get_by_role('button', name='Inbox', exact=True).click()
        await page.route('**/timeline', lambda route: route.fulfill(status=503, content_type='application/json', body='{"detail":"Test failure"}'))
        await page.locator('.employee-row').nth(1).click()
        await expect(page.locator('.detail').get_by_role('alert')).to_be_visible()
        print(json.dumps({'list_skeleton':'passed','report_skeleton':'passed','reduced_motion_duration':reduced,'timeline_error':'passed'}))
        await browser.close()

asyncio.run(main())
