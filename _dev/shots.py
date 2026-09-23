#!/usr/bin/env python3
"""一次加载，多角度批量截图"""
import time, sys, os
from playwright.sync_api import sync_playwright
PAGE=os.environ.get('PAGE','file:///Users/a111111/.zcode/workspace/default/luna/index.html')
OUT=sys.argv[1] if len(sys.argv)>1 else '/tmp/l'
# (名称, 点击选择器列表, 滑块设置列表, 等待秒)
SHOTS=[
 ('a_default',[], [], 3.0),
 ('b_closeup',['[data-preset=closeup]'], [], 4.0),
 ('c_subsolar',['[data-preset=subsolar]'], [], 4.0),
 ('d_earth',['[data-preset=earth]'], [], 4.0),
 ('e_wire',['[data-preset=default]'], [], 3.0),
 ('f_grid',[], [], 2.0),
]
with sync_playwright() as p:
    b=p.chromium.launch(channel='msedge',args=['--use-gl=angle','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
    pg=b.new_page(viewport={'width':1440,'height':810},device_scale_factor=1)
    logs=[]; pg.on('pageerror',lambda e: logs.append(str(e)))
    pg.on('console',lambda m: logs.append(f'[{m.type}] {m.text}') if m.type in ('error','warning') else None)
    pg.goto(PAGE)
    pg.wait_for_function("document.querySelector('#loading').classList.contains('done')",timeout=120000)
    print('加载完成')
    pg.evaluate('()=>{S.orbit=false;}')
    pg.evaluate("()=>{const b=document.querySelector('[data-toggle=orbit]'); b.setAttribute('aria-checked','false');}")
    import os
    only=os.environ.get('ONLY','')
    for name,clicks,sets,wait in SHOTS:
        if only and only not in name: continue
        for c in clicks: pg.click(c)
        for s in sets:
            sel,val=s.split('='); pg.eval_on_selector(sel,"(el,v)=>{el.value=v;el.dispatchEvent(new Event('input'));}",val)
        if name=='e_wire':
            pg.click('[data-toggle=wire]')
        if name=='f_grid':
            pg.click('[data-toggle=wire]'); pg.click('[data-toggle=grid]')
        time.sleep(wait)
        pg.screenshot(path=f'{OUT}_{name}.png')
        st=pg.evaluate("()=>[...document.querySelectorAll('.card-stats dd')].map(d=>d.textContent).join(' | ')")
        print(name, st)
    for l in logs[:15]: print(l)
    b.close()
