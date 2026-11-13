import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.path.join(os.environ['LOCALAPPDATA'],'ms-playwright/chromium-1194/chrome-win/chrome.exe'),headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://localhost:3002/terminal',wait_until='domcontentloaded',timeout=120000)
 page.get_by_role('button',name='Pause supervision').wait_for(timeout=60000)
 panel=page.get_by_role('region',name='Live adaptive supervisor')
 assert panel.get_by_text('AI reasoning not connected',exact=True).is_visible()
 panel.get_by_text('How live supervision works',exact=True).click()
 with page.expect_download() as pending:
  panel.get_by_role('link',name='Download the live evidence').click()
 pending.value.save_as('artifacts/live-supervision-audit.json')
 audit=json.loads(Path('artifacts/live-supervision-audit.json').read_text(encoding='utf-8'))
 observed=audit['audit']['liveObservations'];assert observed
 assert len(audit['audit']['decisions'])==len(observed)
 assert all(b['sourceTimestamp']>a['sourceTimestamp'] for a,b in zip(observed,observed[1:]))
 panel.get_by_text('How live supervision works',exact=True).click()
 page.screenshot(path='artifacts/live-supervision-desktop.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844})
 page.screenshot(path='artifacts/live-supervision-mobile.png',full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 assert not errors,errors
 print(json.dumps({'observations':len(observed),'decisions':len(audit['audit']['decisions']),'browserErrors':errors,'mobileOverflow':False,'runId':audit['snapshot']['runId']}))
 browser.close()
