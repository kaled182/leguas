import json, inspect, re
import django; django.setup()
from django.urls import get_resolver, URLPattern, URLResolver
out=[]
def walk(ps,prefix='',ns=None):
    for p in ps:
        if isinstance(p,URLResolver):
            walk(p.url_patterns,prefix+str(p.pattern),(ns+':' if ns else '')+p.namespace if p.namespace else ns)
        else:
            cb=p.callback
            f=inspect.unwrap(cb)
            vc=getattr(cb,'view_class',None) or getattr(cb,'cls',None)
            mod=(vc or f).__module__; nm=(vc or f).__qualname__
            try:
                src=inspect.getsource(vc or f); 
            except Exception: src=''
            tpls=sorted(set(re.findall(r"""['"]([\w\-/\.]+\.html)['"]""",src)))
            perm=sorted(set(re.findall(r"@(login_required|staff_member_required|user_passes_test|permission_required|[a-z_]*required[a-z_]*|[a-z_]*staff[a-z_]*)",''))) 
            ms=[]
            for c in getattr(cb,'__closure__',None) or []: pass
            out.append(dict(url='/'+prefix+str(p.pattern),name=(ns+':' if ns else '')+(p.name or ''),view=f'{mod}.{nm}',templates=tpls,json='JsonResponse' in src, post="method == \"POST\"" in src or "require_POST" in src))
walk(get_resolver().url_patterns)
json.dump(out,open('/rbout/routes.json','w'),ensure_ascii=False,indent=0)
print(len(out))
