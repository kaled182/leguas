"""Rotas com nome sensível: GET em cópia descartável, restaurada a cada rota."""
import json, re, shutil, sys
src=open('/rbcfg/probe.py').read()
head=src.split("out=[]\nfor r in routes:")[0].replace("routes=json.load(open('/rbcfg/routes.json'))","routes=[]")
exec(head)
P=json.load(open('/rbout/probe.json'))
sk=[r for r in P if r.get('skipped') and not re.search(r'logout',r['url']+r['name'])]
for r in P:
    if r.get('skipped') and re.search(r'logout',r['url']+r['name']): r['never']=True
for r in sk:
    url=fill(r['url']); r['probe_url']=url; r['profiles']={}
    for prof in ('admin','operador','leitor','anonimo'):
        connection.close(); shutil.copy('/rbdata/seed.pristine.sqlite3','/rbdata/seed.sqlite3')
        c=Client(raise_request_exception=False)
        if sess[prof]: c.cookies[settings.SESSION_COOKIE_NAME]=sess[prof]
        last[0]=None
        try:
            signal.alarm(20)
            with CaptureQueriesContext(connection) as q: resp=c.get(url)
            signal.alarm(0)
            ct=resp.get('Content-Type',''); body=resp.content if 'html' in ct and not getattr(resp,'streaming',False) else b''
            wr=[x['sql'][:50] for x in q.captured_queries if re.match(r'\s*(INSERT|UPDATE|DELETE)',x['sql']) and 'django_session' not in x['sql']]
            d=dict(st=resp.status_code,ct=ct.split(';')[0],q=len(q),loc=resp.get('Location','')[:120],html=b'<html' in body[:3000].lower() or b'<!doctype' in body[:300].lower(),writes=len(wr))
            ts=[]
            for tt in (getattr(resp,'templates',None) or []):
                if tt.name and tt.name not in ts and not tt.name.startswith(('django/','admin/')): ts.append(tt.name)
            d['tpl']=ts[:40]
            if resp.status_code>=500: d['err']=last[0]
        except TO: d=dict(st=-1,err='timeout')
        except Exception as e: signal.alarm(0); d=dict(st=-2,err=repr(e)[:300])
        r['profiles'][prof]=d
    r['skipped']=False; r['sensitive']=True
json.dump(P,open('/rbout/probe.json','w'),ensure_ascii=False)
connection.close(); shutil.copy('/rbdata/seed.pristine.sqlite3','/rbdata/seed.sqlite3')
print(len(sk))
