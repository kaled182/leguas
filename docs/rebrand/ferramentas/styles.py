import re, os, sys, json, collections
root='/root/leguas'
skip=('/docs/','/.git','/node_modules/','/staticfiles','/theme/static_src/node_modules','/examples/','/archive/')
exts=('.html','.css','.js')
hexre=re.compile(r'#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b(?![\w-])')
rgbre=re.compile(r'rgba?\([^)]*\)')
files=[]
for d,_,fs in os.walk(root):
    if any(s in d+'/' for s in skip): continue
    for f in fs:
        if f.endswith(exts) and not f.endswith('.min.js') and not f.endswith('.min.css'): files.append(os.path.join(d,f))
cols=collections.Counter(); colf=collections.defaultdict(collections.Counter); 
fs_c=collections.Counter(); rad=collections.Counter(); shad=collections.Counter(); inline=collections.Counter(); emoji=collections.Counter(); grad=collections.Counter(); tw=collections.Counter(); fonts=collections.Counter(); cdn=collections.Counter(); kpi=collections.Counter(); hero=collections.Counter(); money=collections.Counter(); consolelog=collections.Counter()
emo=re.compile('[\U0001F300-\U0001FAFF☀-➿]')
for p in files:
    rel=p[len(root)+1:]
    try: s=open(p,encoding='utf-8',errors='replace').read()
    except: continue
    # evita ids em href/url('#a') e hash html entities
    for m in hexre.finditer(s):
        pre=s[max(0,m.start()-8):m.start()]
        if re.search(r'&|href="$|\$\("$|\(.?$|["\'`]$',pre) and not re.search(r'(color|bg|fill|stroke|background|border)[^;]*$',s[max(0,m.start()-40):m.start()],re.I): continue
        c=m.group(0).lower()
        if len(c)==4: c='#'+''.join(x*2 for x in c[1:])
        cols[c]+=1; colf[c][rel]+=1
    for m in rgbre.finditer(s):
        c=re.sub(r'\s+','',m.group(0)).lower(); cols[c]+=1; colf[c][rel]+=1
    for m in re.finditer(r'font-size\s*:\s*([\d.]+(?:px|rem|em|pt|%))',s): fs_c[m.group(1)]+=1
    for m in re.finditer(r'\btext-(xs|sm|base|lg|xl|[2-9]xl|\[[^\]]+\])\b',s): fs_c['tw:text-'+m.group(1)]+=1
    for m in re.finditer(r'border-radius\s*:\s*([^;"}]+)',s): rad[m.group(1).strip()]+=1
    for m in re.finditer(r'\brounded(?:-(?:none|sm|md|lg|xl|2xl|3xl|full|\[[^\]]+\]))?\b',s): rad['tw:'+m.group(0)]+=1
    for m in re.finditer(r'box-shadow\s*:\s*([^;"}]+)',s): shad[m.group(1).strip()[:60]]+=1
    for m in re.finditer(r'\bshadow(?:-(?:none|sm|md|lg|xl|2xl|inner))?\b',s): shad['tw:'+m.group(0)]+=1
    if p.endswith('.html'):
        n=len(re.findall(r'\sstyle="',s))
        if n: inline[rel]=n
        n=len(emo.findall(s))
        if n: emoji[rel]=n
        n=len(re.findall(r'bg-gradient-to-|linear-gradient',s))
        if n: grad[rel]=n
        for k in ('cdn.tailwindcss.com','@tailwindcss/browser','unpkg.com/lucide','alpinejs','chart.js','bootstrap','font-awesome','fontawesome','htmx','jquery','leaflet','fonts.googleapis.com','cdnjs.cloudflare.com','unpkg.com','cdn.jsdelivr.net'):
            if k in s.lower(): cdn[k]+=1
        for m in re.finditer(r'family=([A-Za-z+]+)',s): fonts[m.group(1)]+=1
        for m in re.finditer(r'bg-gradient-to-\w+ from-(\w+)-\d+ (?:via-\S+ )?to-(\w+)-\d+',s): hero[f'{m.group(1)}→{m.group(2)}']+=1
        kpi['kpi-card' ]+=len(re.findall(r'class="[^"]*kpi[^"]*"',s))
        for m in re.finditer(r'€\s?\{\{[^}]*\}\}|\{\{[^}]*\}\}\s?€',s):
            money['prefixo €' if m.group(0).startswith('€') else 'sufixo €']+=1
    for m in re.finditer(r'font-family\s*:\s*([^;"}]+)',s): fonts[m.group(1).strip()[:40]]+=1
    if p.endswith(('.js','.html')):
        n=len(re.findall(r'console\.(?:log|debug)\(',s))
        if n: consolelog[rel]=n
json.dump(dict(files=len(files),cols=cols.most_common(),colf={k:v.most_common(4) for k,v in colf.items()},fs=fs_c.most_common(),rad=rad.most_common(),shad=shad.most_common(),inline=inline.most_common(),emoji=emoji.most_common(),grad=grad.most_common(),cdn=cdn.most_common(),fonts=fonts.most_common(),hero=hero.most_common(),kpi=kpi.most_common(),money=money.most_common(),consolelog=consolelog.most_common()),open(sys.argv[1],'w'),ensure_ascii=False)
