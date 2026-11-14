"""Unsupported claims and exception-state display regressions."""
import json
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def missing_band(route):
        response = route.fetch()
        body = response.json()
        item = body['items'][0]
        item.update(outcome='missing_effective_band', band_id=None, currency=None,
                    expected_annual=None, residual_pct=None, compa_ratio=None,
                    explanation='No unique effective-dated band matches the salary month.')
        body['items'] = [item]
        body['total'] = 1
        route.fulfill(response=response, json=body)
    page.route('**/comparisons?**', missing_band)
    page.goto('http://127.0.0.1:5173', wait_until='networkidle')
    expect(page.locator('.employee-row').first).to_be_visible()
    expect(page.get_by_role('button', name='Propose adjustment')).to_be_disabled()
    text = page.locator('body').inner_text()
    for claim in ('LIVE ANALYSIS', 'sealed labels', 'Ready to act?', 'Salary was matched to'):
        assert claim.lower() not in text.lower(), claim
    def low_coverage(route):
        response = route.fetch()
        body = response.json()
        body['coverage'] = {'employees': 100, 'compared': 1, 'excluded': 99, 'percent': 1}
        body['status'] = 'attention'
        route.fulfill(response=response, json=body)
    page.route('**/quality', low_coverage)
    page.get_by_role('button', name='Quality', exact=True).click()
    expect(page.locator('.quality-headline strong').first).to_have_text('1.0%')
    assert not errors, errors
    print(json.dumps({'unsupported_claims':'absent','missing_band':'safe_and_non_actionable','one_percent_coverage':'1.0%','page_errors':errors}))
    browser.close()
