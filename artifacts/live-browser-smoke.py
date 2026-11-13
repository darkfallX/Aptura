import json,os,re
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.path.join(os.environ['LOCALAPPDATA'],'ms-playwright/chromium-1194/chrome-win/chrome.exe'),headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://localhost:3002/terminal',wait_until='domcontentloaded',timeout=120000)
 page.get_by_role('heading',name='Your live supervisor').wait_for(timeout=120000)
 page.wait_for_function("document.querySelectorAll('.live-trade').length > 0",timeout=60000)
 assert page.get_by_role('slider',name='Replay position').count()==0
 page.screenshot(path='artifacts/live-desktop.png',full_page=True)
 price=page.locator('.live-price-number').inner_text()
 assert price.startswith('$')
 page.set_viewport_size({'width':390,'height':844})
 page.screenshot(path='artifacts/live-mobile.png',full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 assert not errors,errors
 print(json.dumps({'price':price,'trades':page.locator('.live-trade').count(),'browserErrors':errors,'mobileOverflow':False}))
 browser.close()
