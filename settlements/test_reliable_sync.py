import hashlib
import io
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from openpyxl import Workbook

from system_config.models import SystemConfiguration

from .models import CainiaoOperationTask, ReliableEpodSync
from .services_reliable_sync import sync_epod_from_reliable

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def _epod_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Waybill Number", "LP No.", "Task Status", "Driver", "Task Date", "Delivery Time", "Zip Code"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class _FakeReliable:
    """Simula /api/integracoes/v1/epod/ e /epod/<id>/ficheiro/."""

    def __init__(self, files):
        self.files = files  # lista de (meta, content)
        self.downloads = []

    def get(self, url, params=None, headers=None, timeout=None):
        assert headers["Authorization"] == "Bearer segredo"
        resp = mock.Mock(status_code=200)
        if url.endswith("/epod/"):
            resp.json.return_value = {"limite": 200, "ficheiros": [m for m, _ in self.files]}
        else:
            remote_id = int(url.rstrip("/").split("/")[-2])
            self.downloads.append(remote_id)
            resp.content = next(c for m, c in self.files if m["id"] == remote_id)
        return resp


def _meta(remote_id, content, hub="viana", loaded="2026-09-28T10:00:00+01:00", atribuidas=False):
    return {
        "id": remote_id,
        "ficheiro": f"EPOD_TASK_LIST_V2_{remote_id}__hub-{hub}.xlsx",
        "sha256": hashlib.sha256(content).hexdigest(),
        "hub": hub,
        "atribuidas": atribuidas,
        "exportado_em": loaded,
        "carregado_em": loaded,
    }


@override_settings(CACHES=LOCMEM)
class ReliableEpodSyncTests(TestCase):
    def setUp(self):
        cfg = SystemConfiguration.get_config()
        cfg.reliable_api_url = "https://reliable.test"
        cfg.reliable_api_key = "segredo"
        cfg.reliable_epod_sync_enabled = True
        cfg.save()

    def _run(self, fake):
        with mock.patch("settlements.services_reliable_sync.requests.get", side_effect=fake.get):
            return sync_epod_from_reliable()

    def test_desligada_nao_faz_nada(self):
        cfg = SystemConfiguration.get_config()
        cfg.reliable_epod_sync_enabled = False
        cfg.save()
        with mock.patch("settlements.services_reliable_sync.requests.get") as get:
            self.assertIn("skipped", sync_epod_from_reliable())
        get.assert_not_called()

    def test_importa_o_mais_recente_por_hub_e_nao_repete(self):
        old = _epod_xlsx([["WB1", "LP1", "Driver_received", "Joao_LF", "2026-09-28", None, "4740-001"]])
        new = _epod_xlsx([["WB1", "LP1", "Delivered", "Joao_LF", "2026-09-28", "2026-09-28 11:00:00", "4740-001"]])
        porto = _epod_xlsx([["WB2", "LP2", "Attempt Failure", "Ana_LF", "2026-09-28", None, "4000-001"]])
        atrib = _epod_xlsx([["WB3", "LP3", "Assigned", "Rui_LF", "2026-09-28", None, "4000-002"]])
        fake = _FakeReliable([
            (_meta(1, old, loaded="2026-09-28T09:00:00+01:00"), old),
            (_meta(2, porto, hub="porto", loaded="2026-09-28T09:10:00+01:00"), porto),
            (_meta(3, atrib, hub="porto", loaded="2026-09-28T09:11:00+01:00", atribuidas=True), atrib),
            (_meta(4, new, loaded="2026-09-28T09:30:00+01:00"), new),
        ])

        result = self._run(fake)

        self.assertTrue(result["ok"], result)
        self.assertEqual((result["imported"], result["superseded"], result["skipped"]), (2, 1, 1))
        self.assertEqual(sorted(fake.downloads), [2, 4], "só o mais recente de cada hub")
        self.assertEqual(CainiaoOperationTask.objects.get(waybill_number="WB1").task_status, "Delivered")
        self.assertEqual(CainiaoOperationTask.objects.get(waybill_number="WB2").task_status, "Attempt Failure")
        self.assertFalse(CainiaoOperationTask.objects.filter(waybill_number="WB3").exists())
        self.assertEqual(
            dict(ReliableEpodSync.objects.values_list("remote_id", "status")),
            {1: "superseded", 2: "imported", 3: "skipped", 4: "imported"},
        )

        # Segunda volta com os mesmos ficheiros: nada novo.
        fake.downloads.clear()
        result = self._run(fake)
        self.assertEqual((result["found"], result["imported"]), (0, 0))
        self.assertEqual(fake.downloads, [])

    def test_sha_que_nao_confere_fica_falhado(self):
        content = _epod_xlsx([["WB1", "LP1", "Delivered", "Joao_LF", "2026-09-28", None, "4740-001"]])
        meta = _meta(1, content)
        fake = _FakeReliable([(meta, b"outro conteudo")])
        result = self._run(fake)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(ReliableEpodSync.objects.get().status, "failed")
        self.assertFalse(CainiaoOperationTask.objects.exists())

    def test_ficheiro_invalido_fica_falhado(self):
        bad = b"PK nao e um xlsx"
        fake = _FakeReliable([(_meta(1, bad), bad)])
        result = self._run(fake)
        self.assertEqual(result["failed"], 1)
        self.assertIn("Erro ao ler ficheiro", ReliableEpodSync.objects.get().message)

    def test_chave_errada(self):
        with mock.patch("settlements.services_reliable_sync.requests.get",
                        return_value=mock.Mock(status_code=401)):
            result = sync_epod_from_reliable()
        self.assertFalse(result["ok"])
        self.assertIn("401", result["error"])


@override_settings(CACHES=LOCMEM)
class ReliableSyncViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("operador", password="x")
        self.admin = User.objects.create_user("admin", password="x", is_staff=True)
        self.url = "/settlements/cainiao/reliable-sync/"

    def _post(self, body):
        return self.client.post(self.url, json.dumps(body), content_type="application/json", secure=True)

    def test_so_admin_guarda_configuracao_e_chave_nao_sai_inteira(self):
        self.client.force_login(self.user)
        self.assertEqual(self._post({"action": "save", "url": "https://x"}).status_code, 403)

        self.client.force_login(self.admin)
        d = self._post({"action": "save", "url": "https://r.test/", "key": "abcdefgh", "enabled": True}).json()
        self.assertEqual((d["url"], d["key_masked"], d["enabled"]), ("https://r.test", "…efgh", True))
        cfg = SystemConfiguration.get_config()
        self.assertEqual(cfg.reliable_api_key, "abcdefgh")

        # Chave vazia mantém a atual.
        self._post({"action": "save", "url": "https://r.test", "key": "", "enabled": False})
        self.assertEqual(SystemConfiguration.get_config().reliable_api_key, "abcdefgh")

    def test_sincronizar_agora_agenda_a_task(self):
        self.client.force_login(self.user)
        with mock.patch("settlements.tasks.sync_epod_from_reliable.delay") as delay:
            d = self._post({"action": "sync"}).json()
        delay.assert_called_once_with(triggered_by="manual:operador")
        self.assertEqual(d["url"], "", "operador não vê a configuração")

    def test_anonimo_nao_entra(self):
        self.assertEqual(self.client.get(self.url, secure=True).status_code, 302)
