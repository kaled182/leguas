import json,re,os,collections,statistics,sys
SP=sys.argv[1]; R='/root/leguas'; D=R+'/docs/rebrand'
P=json.load(open(f'{SP}/rb/probe.json'))
SH=[json.loads(l) for l in open(f'{SP}/rb/shots.jsonl')]
os.makedirs(D+'/dados',exist_ok=True)
tplindex={}
for d,_,fs in os.walk(R):
    if any(x in d for x in('/docs','/.git','node_modules')): continue
    if '/templates' not in d: continue
    for f in fs:
        if f.endswith('.html'):
            p=os.path.join(d,f); k=p.split('/templates/',1)[1]; tplindex.setdefault(k,p)
def comp(ts):
    c=set()
    for t in ts:
        p=tplindex.get(t)
        if not p: continue
        s=open(p,encoding='utf-8',errors='replace').read()
        if t.endswith(('base.html','_base.html','_layout.html','sidebar.html','admin_base.html')) : continue
        if re.search(r'kpi|stat-card',s,re.I): c.add('KPI')
        if 'new Chart' in s: c.add('Gráfico')
        if '<table' in s: c.add('Tabela')
        if re.search(r'[mM]odal',s): c.add('Modal')
        if re.search(r'<form[^>]*method="?(post|POST)',s): c.add('Formulário')
        if re.search(r'<form(?![^>]*(post|POST))',s) or 'type="date"' in s: c.add('Filtros')
        if re.search(r'bg-gradient-to-|linear-gradient',s): c.add('Hero/gradiente')
        if re.search(r'tab[A-Z_-]|data-tab|activeTab',s): c.add('Separadores')
        if 'L.map' in s: c.add('Mapa')
    return sorted(c)
nav={}
for m in re.finditer(r'^\| \d+ \| [^|]+\| [^|]+\| `([^`]+)` \| ([^|]+) \| ([^|]+) \|',open(D+'/02-navegacao.md',encoding='utf-8').read(),re.M):
    nav.setdefault(m.group(1),(m.group(2).strip()+' › '+m.group(3).strip()))
PRE={'accounting':'Finanças (sem menu)','settlements':'Operação/Finanças (sem menu)','driversapp':'Motoristas (sem menu)','core':'Clientes (sem menu)','pricing':'Tarifas (sem menu)','fleet':'Frota (sem menu)','contracts':'Contratos (sem menu)','system':'Sistema (sem menu)','payroll':'Finanças (sem menu)','analytics':'Relatórios (sem menu)','auth':'Autenticação','converter':'Ferramentas (sem menu)','management':'Ferramentas (sem menu)'}
def group(r):
    n=r.get('name') or ''
    if n in nav: return nav[n]
    u=r['url']
    if '/portal/' in u and 'driversapp' in u or u.startswith('/contracts/portal'): return 'Portal do motorista'
    if '/portal' in u: return 'Portal da frota'
    return PRE.get(u.split('/')[1],'Outros')
pages=[r for r in P if any(d.get('st')==200 and d.get('html') for d in r.get('profiles',{}).values())]
byr=collections.defaultdict(list)
for s in SH: byr[s['route']].append(s)
def esc(x): return str(x).replace('|','\\|')
ok=lambda r:[k for k,d in r['profiles'].items() if d.get('st')==200]
L=[];rows=[]
ignore=('Cross-Origin-Opener-Policy','cdn.tailwindcss.com should not')
for r in sorted(pages,key=lambda r:(group(r),r['url'])):
    a=r['profiles'].get('admin') or {}
    best=next((r['profiles'][k] for k in('admin','operador','motorista','empresa','anonimo') if r['profiles'].get(k,{}).get('st')==200),{})
    ts=[t for t in best.get('tpl',[]) if not re.search(r'(base|_layout|sidebar|partials/)',t)]
    allts=best.get('tpl',[])
    s=byr.get(r['url'],[]); dc=[x for x in s if x['vp']=='desktop' and x['tema']=='claro']; dc=dc[0] if dc else {}
    cons=[c for x in s for c in x.get('console',[]) if not any(i in c[1] for i in ignore)]
    err={c[1] for c in cons if c[0] in('error','pageerror')}; warn={c[1] for c in cons if c[0]=='warning'}
    bad={tuple(b) for x in s for b in x.get('bad',[])}
    fail={f[0] for x in s for f in x.get('failed',[])}
    rows.append(dict(url=r['url'],probe=r['probe_url'],name=r['name'],view=r['view'],tpl=ts[:3],group=group(r),comp=comp(allts),prof=ok(r),q=best.get('q'),ms=best.get('ms'),load=dc.get('load_ms'),html=dc.get('html_err'),html_top=dc.get('html_err_top'),err=sorted(err),warn=sorted(warn),bad=sorted(bad),fail=sorted(fail),hscroll=any(x.get('hscroll') for x in s if x['vp']=='mobile'),shots=sum(1 for x in s if x.get('shot')),title=dc.get('title'),inline=dc.get('inline_dom'),dark=any(x.get('dark') for x in s)))
extra=[s for s in SH if s['route'] in('(404)','(500)','/admin/','/?tv=1')]
json.dump(dict(pages=rows,extra=[{k:v for k,v in e.items()} for e in extra]),open(D+'/dados/baseline.json','w'),ensure_ascii=False,indent=0)
PERF={'anonimo':'Público','leitor':'Autenticado','operador':'Staff','admin':'Superuser','motorista':'Motorista','empresa':'Frota'}
sg=collections.Counter(x['group'].split(' › ')[0].split(' (')[0] for x in rows)
nonp=[r for r in P if r not in pages]
adm=json.load(open(f'{SP}/rb/routes.json')); nadm=sum(1 for r in adm if r['url'].startswith('/admin'))
A=collections.Counter()
for r in nonp:
    pr=r.get('profiles',{}).get('admin') or {}
    A[pr.get('st','não testada')]+=1
qs=[x['q'] for x in rows if x['q'] is not None]; ls=[x['load'] for x in rows if x['load']]
top=sorted(rows,key=lambda x:-(x['q'] or 0))[:10]
consolepages=[x for x in rows if x['err']]; badpages=[x for x in rows if x['bad'] or x['fail']]
o=[]
o.append(f"""# Inventário de páginas e rotas — baseline

**Estado:** Fase 0. Gerado com commit `469a7d8`, em 2026-10-30.
**Dados:** seed sintético em SQLite, sem dados de produção. Valores de KPI e tempos não representam produção.
**Dados brutos:** `docs/rebrand/dados/baseline.json`.

## 1. Stack

| Camada | Tecnologia | Evidência |
|---|---|---|
| Backend | Django 5.2.18, DRF 3.16, Celery 5.4, MySQL 8 | `requirements.txt`, `production/docker-compose.yml` |
| Templates | Django Templates, {len(tplindex)} ficheiros `.html` | `my_project/settings.py` |
| CSS | Tailwind por CDN em 14 templates, mais `@tailwindcss/browser@4` em 1 | `templates/layouts/admin_base.html:35` |
| Tailwind compilado | App `theme` com `tailwindcss ^3.3.2`, sem build no deploy e config vazia | `theme/tailwind.config.js` |
| CSS próprio | `static/css/base.css`, `modern-dashboard.css`, blocos `<style>` nos templates | `static/css/` |
| JS | Alpine.js, Chart.js, `static/js/sidebar.js`, `base.js` | `admin_base.html:108-114` |
| Versões por CDN | `lucide@latest`, `alpinejs@3.x.x` e `chart.js` sem versão fixa | `admin_base.html:108-114` |
| Ícones | Lucide | `unpkg.com/lucide@latest` |
| Fontes | Inter (Google Fonts). Poppins só em 2 templates | `admin_base.html:32` |
| Tema escuro | Classe `dark` no `<html>`. 3 chaves de `localStorage`: `management-theme`, `financial-theme`, `darkMode` | `admin_base.html:19`, `settlements/base.html:15`, `static/js/base.js:18` |
| Debug toolbar | Não existe. Queries medidas com `CaptureQueriesContext` | `my_project/settings.py` |

**AVISO:** `lucide@latest`, `alpinejs@3.x.x` e `chart.js` mudam sem aviso. Uma versão nova pode partir o sistema em produção sem deploy.

## 2. Totais

| Métrica | Valor |
|---|---|
| Rotas no projeto | {len(adm)} |
| Rotas do Django admin (fora do rebrand visual) | {nadm} |
| Rotas de aplicação testadas | {len(P)} |
| Páginas HTML | {len(pages)} |
| Rotas sem página (JSON, CSV, PDF, POST, parâmetros obrigatórios) | {len(nonp)} |
| Capturas de ecrã | {sum(1 for s in SH if s.get('shot'))} |
| Páginas com erro real de consola | {len(consolepages)} |
| Páginas com pedido falhado | {len(badpages)} |
| Queries por página: mediana / máximo | {statistics.median(qs):.0f} / {max(qs)} |
| Carregamento desktop: mediana / máximo | {statistics.median(ls)/1000:.1f} s / {max(ls)/1000:.1f} s |
| Páginas com scroll horizontal em telemóvel | {sum(1 for x in rows if x['hscroll'])} |

**Páginas por grupo:** {', '.join(f'{k} {v}' for k,v in sg.most_common())}.

**Estado das rotas sem página, com o perfil superuser:** {', '.join(f'{k}: {v}' for k,v in sorted(A.items(),key=lambda kv:str(kv[0])))}.

## 3. Limitações

- O seed cria 2 registos por modelo. Listas longas e páginas com filtros não mostram o volume real.
- {A.get(400,0)+A.get(404,0)} rotas respondem 400 ou 404 sem parâmetros válidos. Não têm captura. Estão na secção 7.
- Modais não têm captura própria. A coluna "Componentes" indica as páginas com modal.
- O tempo de carregamento vem do servidor local de desenvolvimento e não do Gunicorn.
- O erro COOP da consola existe só em HTTP local e foi excluído.

## 4. Páginas
""")
o.append("| URL | View | Template | Grupo | Componentes | Perfis |\n|---|---|---|---|---|---|")
for x in rows:
    o.append(f"| `{esc(x['url'])}` | `{x['view'].replace('.views','').replace('.','.')}` | `{esc(', '.join(x['tpl']) or '-')}` | {esc(x['group'])} | {', '.join(x['comp']) or '-'} | {', '.join(PERF[k] for k in x['prof'])} |")
o.append(f"\n## 5. Métricas por página\n\nA coluna \"Consola\" conta erros reais, sem o aviso do Tailwind CDN, que surge em quase todas as páginas.\n\n| URL | Queries | Load (s) | Erros HTML | Consola | Pedidos falhados | Scroll móvel | Capturas |\n|---|---|---|---|---|---|---|---|")
for x in rows:
    o.append(f"| `{esc(x['url'])}` | {x['q']} | {(x['load'] or 0)/1000:.1f} | {x['html'] if x['html'] is not None else '-'} | {len(x['err'])} | {len(x['bad'])+len(x['fail'])} | {'sim' if x['hscroll'] else 'não'} | {x['shots']} |")
o.append("\n### 10 páginas com mais queries\n\n| URL | Queries |\n|---|---|")
for x in top: o.append(f"| `{esc(x['url'])}` | {x['q']} |")
o.append("\n### Erros de consola\n")
c=collections.Counter(e[:140] for x in rows for e in x['err'])
o.append("| Ocorrências (páginas) | Mensagem |\n|---|---|")
for k,v in c.most_common(25): o.append(f"| {v} | {esc(k)} |")
o.append("\n### Pedidos falhados\n\n| Páginas | Pedido |\n|---|---|")
c=collections.Counter()
for x in rows:
    for b in x['bad']: c[f"{b[0]} {re.sub(r'https?://rbweb:8000','',b[1])[:110]}"]+=1
    for f in x['fail']: c[f"falhou {re.sub(r'https?://rbweb:8000','',f)[:110]}"]+=1
for k,v in c.most_common(25): o.append(f"| {v} | `{esc(k)}` |")
o.append("\n## 6. Páginas especiais\n\n| Página | URL | Estado |\n|---|---|---|\n| Modo TV | `/?tv=1` | Parâmetro da página `/`. Captura `modo-tv-*` |\n| Erro 404 | `/pagina-inexistente/` | Captura `erro-404-*` |\n| Erro 500 | `/accounting/relatorios/` | Captura `erro-500-*`. A rota falha de verdade |\n| Django admin | `/admin/` | Captura `django-admin-*`. {} rotas fora do rebrand |\n".format(nadm))
o.append("## 7. Rotas sem página\n\n| URL | View | Estado (superuser) | Tipo |\n|---|---|---|---|")
for r in sorted(nonp,key=lambda r:r['url']):
    pr=r.get('profiles',{}).get('admin') or {}
    st=pr.get('st','não testada'); o.append(f"| `{esc(r['url'])}` | `{r['view']}` | {st} | {pr.get('ct') or '-'} |")
open(D+'/00-inventario.md','w',encoding='utf-8').write('\n'.join(o)+'\n')
print(len(rows),len(nonp),sum(1 for s in SH if s.get('shot')),len(consolepages),len(badpages)); print([(x['url'],x['err'][:1]) for x in consolepages][:12]); print(collections.Counter(tuple(b) for x in rows for b in x['bad']).most_common(8)); print(collections.Counter(f for x in rows for f in x['fail']).most_common(8)); print([x['url'] for x in top],[x['q'] for x in top]); print(sum(1 for x in rows if not x['shots']),[x['url'] for x in rows if not x['shots']][:10]); print(collections.Counter((s.get('status')) for s in SH), [ (s['slug'],s['error'][:80]) for s in SH if s.get('error')][:6]); print(sum(1 for x in rows if x['hscroll']),sum(x['html'] or 0 for x in rows)); print(collections.Counter(e for x in rows for e in (x['html_top'] or [])).most_common(8)); print('titles',collections.Counter(x['title'] for x in rows).most_common(6))
