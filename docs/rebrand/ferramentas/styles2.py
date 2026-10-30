import re,os,json,collections
R='/root/leguas'
ex=collections.Counter(); hdr=collections.Counter(); hdrx=collections.defaultdict(list); kpi=collections.Counter(); kpix={}; btn=collections.Counter(); standalone=[]; badge=collections.Counter()
for d,_,fs in os.walk(R):
    if any(x in d for x in('/docs','/.git','node_modules','/examples')) or '/templates' not in d: continue
    for f in fs:
        if not f.endswith('.html'): continue
        p=os.path.join(d,f); s=open(p,encoding='utf-8',errors='replace').read(); rel=p[len(R)+1:]
        m=re.search(r"{%\s*extends\s+['\"]([^'\"]+)",s)
        if m: ex[m.group(1)]+=1
        elif '<html' in s.lower(): standalone.append(rel)
        body=s
        b=re.search(r"{%\s*block\s+content\s*%}",s)
        if b: body=s[b.end():]
        head=body[:2500]
        h=re.search(r'<h1[^>]*>',head)
        if h:
            g=re.search(r'bg-gradient-to-\w+ from-(\w+)-\d+[^"]*?to-(\w+)-\d+',head[:h.start()+1]) 
            if g: k=f'Hero gradiente {g.group(1)}→{g.group(2)}'
            elif re.search(r'[\U0001F300-\U0001FAFF☀-➿]',head[h.end():h.end()+120]): k='Título com emoji'
            elif re.search(r'data-lucide',head[max(0,h.start()-500):h.end()+80]): 
                k='Título com ícone em card' if re.search(r'rounded-(xl|2xl)[^"]*(shadow|border)|(shadow|border)[^"]*rounded-(xl|2xl)',head[:h.start()]) else 'Título com ícone'
            else: k='Título solto'
            hdr[k]+=1; hdrx[k].append(rel)
        else:
            if not re.search(r'partials?/|/_|^_',rel) and not f.startswith('_'): hdr['Sem h1']+=1
        for c in re.findall(r'class="([^"]*)"',s):
            if re.search(r'rounded',c) and re.search(r'\bp-[3-6]\b',c) and re.search(r'(shadow|border)',c) and re.search(r'\bbg-',c) and len(c)<200:
                n=' '.join(sorted(x for x in c.split() if not x.startswith(('dark:','hover:','md:','lg:','sm:','col-','transition'))))
                kpi[n]+=1
            if re.search(r'\bpx-[2-6]\b',c) and re.search(r'\bpy-[12](\.5)?\b',c) and re.search(r'\bbg-\w+-\d+',c) and re.search(r'text-white',c):
                btn[re.search(r'\bbg-(\w+)-\d+',c).group(1)]+=1
            if 'rounded-full' in c and re.search(r'\bpx-[12](\.5)?\b',c) and re.search(r'text-(xs|\[)',c): badge[' '.join(sorted(x for x in c.split() if not x.startswith('dark:')))[:70]]+=1
json.dump(dict(ex=ex.most_common(),hdr=hdr.most_common(),hdrx={k:v[:4] for k,v in hdrx.items()},kpi=kpi.most_common(12),kpin=len(kpi),btn=btn.most_common(),badgen=len(badge),standalone=standalone),open(os.sys.argv[1],'w'),ensure_ascii=False,indent=0)
