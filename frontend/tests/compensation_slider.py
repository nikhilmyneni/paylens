import os
"""Verify proposal slider, exact entry and outgoing amount without writing data."""
import json
from playwright.sync_api import sync_playwright, expect

results=[]
expect.set_options(timeout=30000)
with sync_playwright() as p:
    browser=p.chromium.launch()
    for theme,width in [('light',1440),('dark',390)]:
        page=browser.new_page(viewport={'width':width,'height':960},color_scheme=theme,reduced_motion='reduce')
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(os.getenv('APP_URL', 'http://127.0.0.1:5173'),wait_until='networkidle')
        expect(page.locator('.employee-row').first).to_be_visible()
        page.locator('.employee-row').first.click()
        page.get_by_role('button',name='Propose adjustment').click()
        slider=page.get_by_role('slider',name='Adjust proposed annual pay')
        exact=page.get_by_label('Exact annual amount (INR)',exact=True)
        expect(slider).to_be_visible()
        slider.focus()
        slider.press('End')
        assert float(exact.input_value())==float(slider.get_attribute('max'))
        slider.press('Home')
        assert float(exact.input_value())==float(slider.get_attribute('min'))
        slider.scroll_into_view_if_needed()
        bounds=slider.bounding_box()
        page.mouse.click(bounds['x']+bounds['width']*.6,bounds['y']+bounds['height']/2)
        assert float(slider.get_attribute('min'))<float(exact.input_value())<float(slider.get_attribute('max'))
        exact.fill('512345.67')
        expect(page.locator('.compensation-picker-amount')).to_contain_text('5,12,345.67')
        assert abs(float(slider.input_value())-512345.67)<.011
        exact.fill('9999999.99')
        expect(page.get_by_text('Your exact amount is outside the slider range. The entered amount will be saved.')).to_be_visible()
        page.get_by_role('button',name='Use expected pay').click()
        assert float(exact.input_value())<9999999
        exact.fill('512345.67')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('.compensation-picker').screenshot(path=f'frontend/.preview/compensation-slider-{theme}.png')
        sent=[]
        def capture(route):
            sent.append(route.request.post_data_json)
            route.fulfill(status=200,content_type='application/json',body='{"id":"ADJ-TEST","state":"draft"}')
        page.route('**/api/v1/proposals',capture)
        page.get_by_label('Reason for adjustment').fill('Recorded evidence supports this proposed compensation adjustment.')
        page.get_by_role('button',name='Save draft',exact=True).click()
        expect(page.locator('.notice')).to_contain_text('ADJ-TEST saved as a draft.')
        assert sent[0]['proposed_annual']==512345.67,sent
        assert not errors,errors
        results.append({'theme':theme,'width':width,'keyboard':'passed','pointer':'passed','exact_amount':'passed','submitted_amount':sent[0]['proposed_annual'],'page_errors':errors})
        page.close()
    browser.close()
print(json.dumps(results,indent=2))
