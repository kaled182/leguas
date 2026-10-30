"""Testa cada rota com 6 perfis. Regista estado, tipo, templates, queries, tempo."""
import json, re, signal, time, traceback
import django; django.setup()
from django.test.utils import setup_test_environment, CaptureQueriesContext
setup_test_environment()
from django.test import Client
from django.db import connection
from django.core.signals import got_request_exception
from django.urls import resolve
from django.apps import apps
from django.conf import settings

routes=json.load(open('/rbcfg/routes.json'))
sess=json.load(open('/rbdata/sessions.json'))
sess={**{'anonimo':None},**sess}
UNSAFE=re.compile(r'logout|sair|delete|excluir|apagar|remov|cancel|revert|reset|purge|unlink|desvincul|toggle|approve|aprov|reject|rejeit|duplicate|run-|sync|webhook|force|generate|gerar|create-all|import/execute',re.I)
last=[None]
got_request_exception.connect(lambda sender,request,**k: last.__setitem__(0,traceback.format_exc()[-700:]),weak=False)
class TO(Exception): pass
def alarm(*a): raise TO()
signal.signal(signal.SIGALRM,alarm)
def fill(u):
    def rep(m):
        conv,name=(m.group(1) or 'str'),m.group(2)
        if conv=='int':
            if name in('year','ano'): return '2026'
            if name in('month','mes'): return '10'
            if name in('day','dia'): return '30'
            return '1'
        if conv=='uuid': return '00000000-0000-0000-0000-000000000001'
        if conv=='path': return 'x'
        if 'date' in name or 'data' in name: return '2026-10-30'
        if name in('period','periodo'): return '2026-10'
        if name in('cp4',): return '4740'
        if name in('waybill','waybill_number','tracking'): return 'LF000001'
        return '1'
    return re.sub(r'<(?:(\w+):)?(\w+)>',rep,u)
out=[]
for r in routes:
    u=r['url']
    if u.startswith('/admin') or '(?P' in u or u.startswith('/static') or u.startswith('/media') or '^' in u: continue
    url=fill(u)
    rec=dict(r,probe_url=url,profiles={})
    if UNSAFE.search(u) or UNSAFE.search(r['name'] or '') or UNSAFE.search(r['view']):
        rec['skipped']=True; out.append(rec); continue
    for prof,key in sess.items():
        c=Client(raise_request_exception=False)
        if key: c.cookies[settings.SESSION_COOKIE_NAME]=key
        last[0]=None; t=time.perf_counter()
        try:
            signal.alarm(25)
            with CaptureQueriesContext(connection) as q:
                resp=c.get(url)
            signal.alarm(0)
            ct=resp.get('Content-Type','')
            body=b''
            if 'html' in ct and not getattr(resp,'streaming',False): body=resp.content
            d=dict(st=resp.status_code,ct=ct.split(';')[0],q=len(q),ms=int((time.perf_counter()-t)*1000),loc=resp.get('Location','')[:120],html=b'<html' in body[:3000].lower() or b'<!doctype' in body[:300].lower())
            ts=[]
            for tt in (getattr(resp,'templates',None) or []):
                if tt.name and tt.name not in ts and not tt.name.startswith(('django/','admin/')): ts.append(tt.name)
            if prof=='admin' or d['st']==200: d['tpl']=ts[:40]
            if resp.status_code>=500: d['err']=last[0]
        except TO:
            d=dict(st=-1,err='timeout 25s')
        except Exception as e:
            signal.alarm(0); d=dict(st=-2,err=repr(e)[:300])
        rec['profiles'][prof]=d
    out.append(rec)
json.dump(out,open('/rbout/probe.json','w'),ensure_ascii=False)
print(len(out))
