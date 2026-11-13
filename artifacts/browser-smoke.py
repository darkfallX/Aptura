import json,os,re
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.path.join(os.environ['LOCALAPPDATA'],'ms-playwright/chromium-1194/chrome-win/chrome.exe'),headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:3002/terminal?mode=replay',wait_until='domcontentloaded',timeout=120000)
    page.get_by_role('heading',name=re.compile('Overview')).wait_for(timeout=120000)
    slider=page.get_by_role('slider',name='Replay position')
    slider.press('End')
    page.get_by_role('button',name='Request reviewed change').wait_for()
    page.get_by_role('button',name='Request reviewed change').click(timeout=60000)
    page.get_by_text('UNCONFIGURED',exact=True).wait_for(timeout=30000)
    with page.expect_download() as download:
        page.get_by_role('button',name='Export run',exact=True).click()
    export=download.value
    export.save_as('artifacts/browser-audit.json')
    audit=json.loads(Path('artifacts/browser-audit.json').read_text(encoding='utf-8'))
    assert audit['audit']['decisions'] and audit['audit']['maturedOutcomes']
    page.screenshot(path='artifacts/research-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path='artifacts/research-mobile.png',full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile overflow'
    assert not errors,errors
    print(json.dumps({'browserErrors':errors,'auditDecisions':len(audit['audit']['decisions']),'reviewState':'UNCONFIGURED','mobileOverflow':False}))
    browser.close()
