import asyncio, json, re, sys, time, os
sys.path.insert(0,'/pip')
from playwright.async_api import async_playwright
import html5lib
BASE='http://rbweb:8000'; P=json.load(open('/rb/probe.json')); S=json.load(open('/rbdata/sessions.json'))
OUT='/shots'; LOG='/rb/shots.jsonl'
ONLY=sys.argv[1] if len(sys.argv)>1 else None
def slug(u):
    s=re.sub(r'[^a-z0-9]+','-',u.lower()).strip('-'); return s or 'painel'
def prof(r):
    p=r['profiles']; ok=lambda k:p.get(k,{}).get('st')==200 and p.get(k,{}).get('html')
    u=r['url']
    if ok('anonimo'): return 'anonimo'
    if '/portal/' in u and ok('motorista') and 'driver' in u: return 'motorista'
    if '/portal' in u and ok('empresa'): return 'empresa'
    for k in('admin','operador','motorista','empresa'):
        if ok(k): return k
PAGES=[]
for r in P:
    k=prof(r) if r.get('profiles') else None
    if k: PAGES.append(dict(slug=slug(r['url'].replace('<int:','').replace('>','')),url=r['probe_url'],prof=k,route=r['url']))
PAGES+= [dict(slug='erro-404',url='/pagina-inexistente/',prof='admin',route='(404)',expect=404),dict(slug='erro-500',url='/accounting/relatorios/',prof='admin',route='(500)',expect=500),dict(slug='django-admin',url='/admin/',prof='admin',route='/admin/'),dict(slug='modo-tv',url='/?tv=1',prof='admin',route='/?tv=1')]
if ONLY: PAGES=PAGES[:int(ONLY)]
VP={'desktop':dict(width=1440,height=900),'mobile':dict(width=390,height=844)}
JOBS=[(p,v,t) for p in PAGES for v in VP for t in('claro','escuro')]
done=set()
if os.path.exists(LOG):
    for l in open(LOG):
        d=json.loads(l); done.add((d['slug'],d['vp'],d['tema']))
JOBS=[j for j in JOBS if (j[0]['slug'],j[1],j[2]) not in done]
print(len(PAGES),'pages',len(JOBS),'jobs',flush=True)
q=asyncio.Queue()
for j in JOBS: q.put_nowait(j)
lock=asyncio.Lock()
async def worker(b):
    while True:
        try: p,v,t=q.get_nowait()
        except asyncio.QueueEmpty: return
        ctx=await b.new_context(viewport=VP[v],is_mobile=v=='mobile',has_touch=v=='mobile',locale='pt-PT',timezone_id='Europe/Lisbon',device_scale_factor=1)
        await ctx.add_init_script("for(const k of ['management-theme','financial-theme','theme','color-theme']){try{localStorage.setItem(k,'%s')}catch(e){}};try{localStorage.setItem('darkMode','%s')}catch(e){}"%('dark' if t=='escuro' else 'light','true' if t=='escuro' else 'false'))
        if S.get(p['prof']): await ctx.add_cookies([dict(name='sessionid',value=S[p['prof']],url=BASE)])
        pg=await ctx.new_page(); cons=[];fail=[];bad=[]
        pg.on('console',lambda m: cons.append((m.type,m.text[:220])) if m.type in('error','warning') else None)
        pg.on('pageerror',lambda e: cons.append(('pageerror',str(e)[:220])))
        pg.on('requestfailed',lambda r: fail.append((r.url[:150],r.failure)))
        pg.on('response',lambda r: bad.append((r.status,r.url[:150])) if r.status>=400 else None)
        rec=dict(slug=p['slug'],route=p['route'],url=p['url'],prof=p['prof'],vp=v,tema=t)
        try:
            t0=time.perf_counter(); resp=await pg.goto(BASE+p['url'],wait_until='load',timeout=45000); rec['load_ms']=int((time.perf_counter()-t0)*1000)
            rec['status']=resp.status
            try: await pg.wait_for_load_state('networkidle',timeout=6000)
            except Exception: rec['no_idle']=True
            await pg.wait_for_timeout(500)
            rec['final']=pg.url.replace(BASE,'')
            nav=await pg.evaluate("()=>{const n=performance.getEntriesByType('navigation')[0];return {dcl:Math.round(n.domContentLoadedEventEnd),load:Math.round(n.loadEventEnd)}}"); rec.update(nav)
            dark=await pg.evaluate("()=>document.documentElement.classList.contains('dark')||document.body.classList.contains('dark-mode')||document.documentElement.getAttribute('data-theme')==='dark'")
            rec['dark']=dark
            rec['inline_dom']=await pg.evaluate("()=>document.querySelectorAll('[style]').length")
            rec['hscroll']=await pg.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1")
            rec['h']=await pg.evaluate("()=>document.documentElement.scrollHeight")
            rec['title']=await pg.title()
            if v=='desktop' and t=='claro':
                body=await resp.text(); pr=html5lib.HTMLParser(strict=False); pr.parse(body); rec['html_err']=len(pr.errors)
                rec['html_err_top']=sorted({e[1] for e in pr.errors})[:6]
            if t=='claro' or dark:
                await pg.screenshot(path=f"{OUT}/{p['slug']}-{v}-{t}.png",full_page=True,timeout=30000); rec['shot']=True
        except Exception as e:
            rec['error']=repr(e)[:300]
        rec['console']=cons[:30]; rec['failed']=fail[:15]; rec['bad']=bad[:15]
        async with lock:
            open(LOG,'a').write(json.dumps(rec,ensure_ascii=False)+'\n')
        await ctx.close()
async def main():
    async with async_playwright() as w:
        b=await w.chromium.launch()
        await asyncio.gather(*[worker(b) for _ in range(5)])
        await b.close()
asyncio.run(main()); print('done',flush=True)
