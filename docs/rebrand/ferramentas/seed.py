"""Seed sintético para baseline do rebrand. Só SQLite local. Nomes fictícios."""
import json, datetime, decimal, uuid, random
import django; django.setup()
from datetime import timedelta, datetime as DT, time
from django.apps import apps
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY

random.seed(7)
PROJECT = {"customauth","management","drivers_app","converter","settlements","accounting","payroll","system_config","core","fleet_management","pricing","geozonas","sorting","analytics","contracts","app_api","dashboard_leguas"}
admin = User.objects.create_superuser("gestao","gestao@example.test","rebrand-local")
op = User.objects.create_user("operador","op@example.test","rebrand-local",is_staff=True)
leitor = User.objects.create_user("leitor","l@example.test","rebrand-local")
for u,n,a in ((admin,"Gestão","Local"),(op,"Operador","Hub")):
    u.first_name=n; u.last_name=a; u.save()

today = timezone.localdate(); now = timezone.now(); ctr = [0]
def val(f):
    ctr[0]+=1; c=ctr[0]
    if f.choices:
        return list(f.flatchoices)[0][0]
    if isinstance(f,(models.ForeignKey,models.OneToOneField)):
        M=f.remote_field.model
        q=M.objects.all()
        if isinstance(f,models.OneToOneField):
            used=f.model.objects.values_list(f.attname,flat=True)
            q=q.exclude(pk__in=list(used))
        o=q.first()
        if o is None: raise LookupError(M)
        return o
    if isinstance(f,models.DateTimeField): return now
    if isinstance(f,models.DateField): return today
    if isinstance(f,models.TimeField): return time(9,0)
    if isinstance(f,models.DurationField): return timedelta(hours=1)
    if isinstance(f,models.DecimalField): return decimal.Decimal("10.00")
    if isinstance(f,models.BooleanField): return False
    if isinstance(f,models.UUIDField): return uuid.uuid4()
    if isinstance(f,models.JSONField): return {}
    if isinstance(f,(models.BigIntegerField,models.IntegerField,models.SmallIntegerField,models.PositiveIntegerField)): return c
    if isinstance(f,models.FloatField): return 1.0
    if isinstance(f,models.EmailField): return f"seed{c}@example.test"
    if isinstance(f,models.URLField): return f"https://example.test/{c}"
    if isinstance(f,models.GenericIPAddressField): return "127.0.0.1"
    if isinstance(f,(models.FileField,)): return ""
    if isinstance(f,models.BinaryField): return b""
    if isinstance(f,(models.CharField,models.TextField,models.SlugField)):
        s=f"seed-{c}"; ml=getattr(f,'max_length',None)
        if f.name.lower() in("cp4",): return "4740"
        return s[:ml] if ml else s
    raise TypeError(type(f))

ms=[m for m in apps.get_models() if m._meta.app_label in PROJECT and not m._meta.proxy and m._meta.managed]
pending=list(ms); failed={}; N=2
for _ in range(10):
    nxt=[]
    for m in pending:
        try:
            for i in range(N):
                if i and m.objects.exists() and any(True for _ in [1]):
                    pass
                with transaction.atomic():
                    kw={}
                    for f in m._meta.concrete_fields:
                        if isinstance(f,models.AutoField) or f.primary_key and isinstance(f,models.AutoField): continue
                        if f.has_default() and not f.primary_key and not f.unique and not getattr(f,'auto_now',False) and not getattr(f,'auto_now_add',False): continue
                        if f.null and not f.unique and not f.primary_key: continue
                        if f.blank and not f.unique and isinstance(f,(models.CharField,models.TextField,models.FileField)): continue
                        v=val(f)
                        kw[f.name]=v
                    o=m(**kw); o.save_base(raw=True)
            failed.pop(m._meta.label,None)
        except Exception as e:
            if m.objects.exists():
                failed.pop(m._meta.label,None); continue
            failed[m._meta.label]=f"{type(e).__name__}: {e}"[:160]; nxt.append(m)
    if not nxt or len(nxt)==len(pending): pending=nxt; break
    pending=nxt
print("models",len(ms),"ok",len(ms)-len(failed),"failed",len(failed))
for k,v in failed.items(): print(" F",k,v)

# Ficheiros e NIF válidos em todos os modelos, para isolar erros reais de erros do seed
for m in ms:
    up={}
    for f in m._meta.concrete_fields:
        if isinstance(f,models.FileField): up[f.name]="seed/documento.pdf"
        elif f.name.lower() in("nif","vat","contribuinte") and isinstance(f,models.CharField) and not f.unique: up[f.name]="517307243"
    if up:
        try: m.objects.update(**up)
        except Exception as e: print("up",m._meta.label,repr(e)[:100])
# Camada legível: nomes fictícios e movimento operacional
from drivers_app.models import DriverProfile, EmpresaParceira
from core.models import Partner
NAMES=["Ana Silva","Bruno Costa","Carla Sousa","Diogo Pinto","Eva Moreira","Filipe Rocha"]
for o,nm in zip(DriverProfile.objects.all(),NAMES):
    DriverProfile.objects.filter(pk=o.pk).update(nome_completo=nm)
Partner.objects.filter(pk=1).update(name="Plataforma Exemplo")
EmpresaParceira.objects.filter(pk=1).update(nome="Frota Exemplo, Lda.")
from settlements.models import CainiaoHub, CainiaoHubCP4, CainiaoOperationTask, CainiaoOperationTaskHistory
hub=CainiaoHub.objects.first() or CainiaoHub.objects.create(name="Fão")
CainiaoHub.objects.filter(pk=hub.pk).update(name="Fão")
CainiaoHubCP4.objects.get_or_create(hub=hub,cp4="4740")
st=["Delivered"]*8+["Attempt Failure"]*1+["Driver_received"]*1
n=0
for d in range(0,30):
    day=today-timedelta(days=d)
    for i in range(30):
        n+=1; s=random.choice(st)
        dt=timezone.make_aware(DT.combine(day,time(10,30)))
        CainiaoOperationTask.objects.create(waybill_number=f"LF{n:06d}",task_date=day,task_status=s,zip_code="4740-001",courier_name=random.choice(["Ana_LF","Bruno_LF","Carla_LF"]),delivery_time=dt if s=="Delivered" else None)
        CainiaoOperationTaskHistory.objects.create(waybill_number=f"LF{n:06d}",task_date=day,task_status=s,courier_name="Ana_LF",change_type="signature")
print("tasks",n)

def sess(u=None,**extra):
    s=SessionStore()
    if u:
        s[SESSION_KEY]=str(u.pk); s[BACKEND_SESSION_KEY]="django.contrib.auth.backends.ModelBackend"; s[HASH_SESSION_KEY]=u.get_session_auth_hash()
    s.update(extra); s.save(); return s.session_key
from customauth.models import DriverAccess
ss={"admin":sess(admin),"operador":sess(op),"leitor":sess(leitor)}
da=DriverAccess.objects.first()
if da:
    DriverAccess.objects.filter(pk=da.pk).update(is_active=True,driver_profile_id=DriverProfile.objects.first().pk)
    ss["motorista"]=sess(is_driver_authenticated=True,driver_access_id=da.pk,driver_profile_id=DriverProfile.objects.first().pk,driver_name="Ana Silva")
try:
    from customauth.models import EmpresaAccess
    ea=EmpresaAccess.objects.first()
    if ea:
        EmpresaAccess.objects.filter(pk=ea.pk).update(is_active=True); ss["empresa"]=sess(is_empresa_authenticated=True,empresa_access_id=ea.pk)
except Exception as e: print("empresa",e)
json.dump(ss,open("/rbdata/sessions.json","w")); print(list(ss))
