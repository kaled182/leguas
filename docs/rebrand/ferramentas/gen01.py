import json,sys,collections
SP=sys.argv[1]; D='/root/leguas/docs/rebrand'
s=json.load(open(f'{SP}/audit/styles.json')); t=json.load(open(f'{SP}/audit/styles2.json'))
BRAND={'#2e0a3e','#1c0627','#6b3d7d','#f7941d','#d97a0b','#efe7f6','#fff1dd','#241433','#6e5a82','#e6dcf0','#1e8e4e','#d6453f','#e0a100','#8a8296'}
TW=[('gray',15567),('emerald',2074),('amber',1596),('blue',1401),('rose',1242),('red',1174),('indigo',1157),('purple',903),('violet',623),('orange',524),('teal',372),('green',240),('primary',228),('yellow',187),('slate',91),('sky',78),('cyan',42),('pink',37),('fuchsia',32)]
tot=sum(c for _,c in s['cols'])
hero=[(k,v) for k,v in t['hdr'] if k.startswith('Hero')]; nonhero=[(k,v) for k,v in t['hdr'] if not k.startswith('Hero')]
b=sum(1 for c,_ in s['cols'] if c in BRAND)
o=[f"""# Auditoria de estilos — baseline

**Estado:** Fase 0. Análise estática de {s['files']} ficheiros `.html`, `.css` e `.js`, com commit `469a7d8`.

## 1. Resumo

| Métrica | Valor | Meta do briefing |
|---|---|---|
| Cores hardcoded distintas (hex, rgb, rgba) | {len(s['cols'])} | 0 fora de `tokens.css` |
| Ocorrências de cores hardcoded | {tot} | 0 fora de `tokens.css` |
| Cores da marca presentes | {b} de {len(BRAND)} | {len(BRAND)} |
| Classes de cor Tailwind nos templates | {sum(c for _,c in TW)} | Só tokens |
| Famílias de cor Tailwind | {len(TW)} | Roxo, laranja, neutros e 3 estados |
| Tamanhos de fonte distintos | {len(s['fs'])} | Escala única |
| Valores de raio distintos | {len(s['rad'])} | Escala única |
| Valores de sombra distintos | {len(s['shad'])} | Escala única |
| Atributos `style=""` no código | {sum(c for _,c in s['inline'])} em {len(s['inline'])} ficheiros | 0 |
| Emojis nos templates | {sum(c for _,c in s['emoji'])} em {len(s['emoji'])} ficheiros | 0 em títulos e chips |
| Gradientes | {sum(c for _,c in s['grad'])} em {len(s['grad'])} ficheiros | Só login e Modo ecrã |
| `console.log` e `console.debug` | {sum(c for _,c in s['consolelog'])} em {len(s['consolelog'])} ficheiros | 0 em produção |
| Valores antigos `#4A1A6B` e `#F59000` | 0 | 0 |
| Bases de layout | {len(t['ex'])} | 1 shell interno, portais separados |
| Páginas HTML sem base (`<html>` próprio) | {len(t['standalone'])} | Só as bases |

## 2. Tailwind e configuração

- `tailwind.config` está inline e duplicado em `templates/layouts/admin_base.html:37` e `settlements/templates/settlements/base.html:33`.
- O `primary` do projeto é azul (`#2563eb`). A marca usa roxo.
- `theme/tailwind.config.js` tem `extend: {{}}`. Não define tokens.
- `theme/package.json` fixa `tailwindcss ^3.3.2`. `dashboard_leguas/base.html:8` carrega `@tailwindcss/browser@4`. São 2 versões maiores diferentes.
- O CDN `cdn.tailwindcss.com` está em 14 templates. O critério de aceitação cobre este domínio, mas a Fase 1 tem de cobrir também o `@tailwindcss/browser@4`.

## 3. Componentes duplicados

### Cabeçalhos de página

O briefing indica 5 padrões. O código tem **{len(hero)} variantes de hero gradiente** e {len(nonhero)} outros padrões.

| Padrão | Templates |
|---|---|"""]
for k,v in t['hdr']: o.append(f"| {k} | {v} |")
o.append(f"""
### Cards

Existem **{t['kpin']} combinações distintas** de classes para cards (fundo, raio, borda e padding), depois de retirar variantes `dark:` e `hover:`.

| Classes | Usos |
|---|---|""")
for k,v in t['kpi'][:12]: o.append(f"| `{k}` | {v} |")
o.append(f"""
### Botões primários por cor de fundo

| Cor | Usos |
|---|---|""")
for k,v in t['btn']: o.append(f"| {k} | {v} |")
o.append(f"""
### Badges

Existem **{t['badgen']} combinações distintas** de classes para badges.

### Layouts

| Base | Páginas |
|---|---|""")
for k,v in t['ex']: o.append(f"| `{k}` | {v} |")
o.append("\nMenus: `layouts/partials/sidebar.html` (57 ligações), `dashboard_sidebar.html` (30), `partials/sidebar_links.html` (11).\n\n## 4. Moeda e formatos\n")
o.append(f"""- Valores com `€` antes do número: {dict(s['money']).get('prefixo €',0)} ocorrências em templates. Com `€` depois: {dict(s['money']).get('sufixo €',0)}.
- `floatformat:2` tem 363 usos. `intcomma` e `humanize` têm 0 usos. Por isso, os milhares não têm separador.
- `pluralize` tem 60 usos. Há 24 ocorrências de plural forçado, como `integração(ões)`.
- **Decisão técnica para a Fase 1:** criar 1 filtro `|eur`, testado, em vez de alterar cada cálculo. O filtro muda só a apresentação.

## 5. Famílias de cor Tailwind

| Família | Classes |
|---|---|""")
for k,v in TW: o.append(f"| {k} | {v} |")
o.append("\n## 6. Tipografia\n\n| Tamanho | Usos |\n|---|---|")
for k,v in s['fs']: o.append(f"| `{k}` | {v} |")
o.append("\n**Famílias de letra:** "+'; '.join(f"`{k}` ({v})" for k,v in s['fonts'])+".")
o.append("\n## 7. Raios\n\n| Valor | Usos |\n|---|---|")
for k,v in s['rad']: o.append(f"| `{k}` | {v} |")
o.append("\n## 8. Sombras\n\n| Valor | Usos |\n|---|---|")
for k,v in s['shad']: o.append(f"| `{k}` | {v} |")
o.append("\n## 9. Ficheiros com mais `style=\"\"`, emojis e `console.log`\n\n| Ficheiro | `style=\"\"` |\n|---|---|")
for k,v in s['inline'][:15]: o.append(f"| `{k}` | {v} |")
o.append("\n| Ficheiro | Emojis |\n|---|---|")
for k,v in s['emoji'][:15]: o.append(f"| `{k}` | {v} |")
o.append("\n| Ficheiro | `console.log` |\n|---|---|")
for k,v in s['consolelog']: o.append(f"| `{k}` | {v} |")
o.append("\n## 10. Todas as cores hardcoded\n\n| Cor | Usos | Marca | Ficheiros principais |\n|---|---|---|---|")
for c,n in s['cols']:
    o.append(f"| `{c}` | {n} | {'sim' if c in BRAND else 'não'} | {', '.join(f'`{f}` ({v})' for f,v in s['colf'][c][:3])} |")
open(D+'/01-auditoria-estilos.md','w',encoding='utf-8').write('\n'.join(o)+'\n')
print(len(hero),len(nonhero),b,tot)
