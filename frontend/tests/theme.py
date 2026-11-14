import os
"""Theme preference, system tracking, persistence and reveal regression checks."""
import json
from playwright.sync_api import sync_playwright, expect

expect.set_options(timeout=30000)
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1440, "height": 960}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.getenv('APP_URL', 'http://127.0.0.1:5173'), wait_until='networkidle')
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    expect(page.locator('.employee-row').first).to_be_visible()
    page.screenshot(path='frontend/.preview/final-dark-desktop.png', full_page=True)
    page.emulate_media(color_scheme='light')
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    page.get_by_role('button', name='Switch to dark theme', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    page.wait_for_timeout(650)
    assert page.evaluate("localStorage.getItem('compass-theme')") == 'dark'
    page.reload(wait_until='networkidle')
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    expect(page.locator('.employee-row').first).to_be_visible()
    page.emulate_media(reduced_motion='reduce')
    page.get_by_role('button', name='Switch to light theme', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role('button', name='Switch to dark theme', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='frontend/.preview/final-dark-mobile.png', full_page=True)
    page.get_by_role('button', name='Choose appearance', exact=True).click()
    page.get_by_role('button', name='System', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    page.emulate_media(color_scheme='dark')
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    page.get_by_role('button', name='Results', exact=True).click()
    expect(page.locator('.report-scoreline')).to_be_visible()
    page.screenshot(path='frontend/.preview/final-dark-results-mobile.png', full_page=True)
    assert not errors, errors
    print(json.dumps({'system_default':'passed','os_change':'passed','manual_override':'passed','reload_persistence':'passed','return_to_system':'passed','reduced_motion':'passed','mobile_overflow':False,'page_errors':errors}))
    browser.close()
