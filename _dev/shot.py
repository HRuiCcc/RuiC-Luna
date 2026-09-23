#!/usr/bin/env python3
"""无头截图工具：加载 luna/index.html，等待渲染完成，按需点击预设/调参后截图。
用法: shot.py out.png [--wait 30] [--click 选择器] [--set '#r-alpha=90'] [--size 1440x810]
"""
import sys, os, time, argparse
from playwright.sync_api import sync_playwright

PAGE = os.environ.get('PAGE', 'file:///Users/a111111/.zcode/workspace/default/luna/index.html')

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--wait', type=float, default=26)
ap.add_argument('--post', type=float, default=2.2, help='截图前额外等待秒数')
ap.add_argument('--click', action='append', default=[])
ap.add_argument('--set', action='append', default=[], help='形如 #id=value，直接改滑块值并派发 input')
ap.add_argument('--size', default='1440x810')
ap.add_argument('--log', action='store_true')
a = ap.parse_args()
W, H = (int(x) for x in a.size.split('x'))

with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', args=['--use-gl=angle', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
    pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
    msgs = []
    pg.on('console', lambda m: msgs.append(f'[{m.type}] {m.text}'))
    pg.on('pageerror', lambda e: msgs.append(f'[pageerror] {e}'))
    pg.goto(PAGE)
    # 等 #loading 淡出（最多 a.wait 秒）
    try:
        pg.wait_for_function("document.querySelector('#loading').classList.contains('done')", timeout=a.wait * 1000)
        print('加载完成')
    except Exception as e:
        print('等待加载超时:', e)
    for s in a.set:
        sel, val = s.split('=')
        pg.eval_on_selector(sel, "(el,v)=>{el.value=v;el.dispatchEvent(new Event('input'));el.dispatchEvent(new Event('change'));}", val)
    for c in a.click:
        pg.click(c)
    time.sleep(a.post)
    err = pg.evaluate("document.querySelector('#fatal').classList.contains('on') ? document.querySelector('#fatal').innerText : ''")
    info = pg.evaluate("""() => { const c=document.querySelector('#gl');
        return {w:c.width,h:c.height,
                stats:[...document.querySelectorAll('.card-stats dd')].map(d=>d.textContent),
                labels:[...document.querySelectorAll('.lbl')].filter(e=>+e.style.opacity>0.05).map(e=>e.textContent)}; }""")
    pg.screenshot(path=a.out)
    b.close()
    print('设备像素:', info['w'], 'x', info['h'])
    print('观测数据:', ' | '.join(info['stats']))
    print('可见标注:', ', '.join(info['labels']))
    if err:
        print('!! 错误页:', err)
    if a.log or err:
        for m in msgs[:40]:
            print(m)
