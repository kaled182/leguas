"""Limpeza de descontos (DriverClaim) duplicados sobre o mesmo waybill.

Contexto: até à introdução do guard `DriverClaim.active_claim_for_waybill`,
era possível criar mais do que um desconto sobre o mesmo pacote (waybill) —
p.ex. duas reclamações do mesmo pacote a gerarem dois claims de €50. Este
comando encontra esses grupos e, com --apply, remove os duplicados de forma
segura.

Regras de segurança:
  * Só agrupa claims NÃO rejeitados (REJECTED liberta o waybill).
  * Um claim é considerado BLOQUEADO (já pago, não se mexe) se:
      - tem settlement_id (entrou num acerto antigo), OU
      - tem linha PreInvoiceLostPackage numa PF com estado PAGO.
  * Por grupo, o "keeper" (o que fica) é:
      - o único bloqueado, se houver exactamente um; OU
      - o mais antigo (created_at) se nenhum estiver bloqueado.
    Se houver 2+ bloqueados no mesmo waybill → CONFLITO já pago: só reporta,
    não mexe (precisa de decisão humana).
  * Cada duplicado removido: apaga as linhas PreInvoiceLostPackage geradas a
    partir dele (api_source="auto:driver_claim:<id>"), recalcula as PFs
    afectadas e marca o claim como REJECTED com nota de auditoria.

Por defeito é DRY-RUN (só lista). Use --apply para efectivar.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


def _norm_waybill(raw):
    """Normaliza o waybill para comparação (trim + maiúsculas).

    Auto-suficiente de propósito — não depende de
    DriverClaim.normalize_waybill, para o comando poder ser copiado
    isolado para um container de produção que ainda não tenha esse método.
    """
    return (raw or "").strip().upper()


class Command(BaseCommand):
    help = (
        "Lista e (com --apply) remove descontos DriverClaim duplicados "
        "sobre o mesmo waybill."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Efectiva as remoções (por defeito é dry-run).",
        )
        parser.add_argument(
            "--driver", type=int, default=None,
            help="Limitar a um driver_id específico.",
        )

    def handle(self, *args, **opts):
        from settlements.models import DriverClaim, PreInvoiceLostPackage

        apply = opts["apply"]
        driver_id = opts["driver"]

        qs = (
            DriverClaim.objects
            .exclude(status="REJECTED")
            .exclude(waybill_number="")
            .select_related("driver", "settlement")
            .order_by("created_at")
        )
        if driver_id:
            qs = qs.filter(driver_id=driver_id)

        groups = defaultdict(list)
        for c in qs:
            key = _norm_waybill(c.waybill_number)
            if key:
                groups[key].append(c)
        dup_groups = {k: v for k, v in groups.items() if len(v) > 1}

        if not dup_groups:
            self.stdout.write(self.style.SUCCESS(
                "Nenhum desconto duplicado por waybill encontrado."
            ))
            return

        def pf_lines(claim):
            marker = f"auto:driver_claim:{claim.id}"
            return list(
                PreInvoiceLostPackage.objects
                .filter(api_source=marker)
                .select_related("pre_invoice")
            )

        def is_paid_locked(claim, lines):
            if claim.settlement_id:
                return True
            return any(
                ln.pre_invoice and ln.pre_invoice.status == "PAGO"
                for ln in lines
            )

        mode = "APLICAR" if apply else "DRY-RUN"
        self.stdout.write(self.style.WARNING(
            f"=== Dedupe DriverClaims · modo {mode} · "
            f"{len(dup_groups)} waybill(s) com duplicados ==="
        ))

        total_removed = 0
        total_manual = 0
        affected_pfs = {}

        def process():
            nonlocal total_removed, total_manual
            for wb, claims in sorted(dup_groups.items()):
                # Anexar info de linhas/lock a cada claim
                info = []
                for c in claims:
                    lines = pf_lines(c)
                    info.append((c, lines, is_paid_locked(c, lines)))

                locked = [t for t in info if t[2]]
                drv = claims[0].driver.nome_completo if claims[0].driver else "?"
                self.stdout.write("")
                self.stdout.write(self.style.HTTP_INFO(
                    f"Waybill {wb} · driver {drv} · {len(claims)} claims"
                ))

                if len(locked) >= 2:
                    total_manual += len(locked)
                    self.stdout.write(self.style.ERROR(
                        "  ⚠ CONFLITO: 2+ descontos já pagos sobre o mesmo "
                        "waybill — requer decisão manual. Claims: "
                        + ", ".join(f"#{t[0].id}" for t in locked)
                    ))
                    continue

                if len(locked) == 1:
                    keeper = locked[0][0]
                else:
                    keeper = min(claims, key=lambda c: c.created_at)

                self.stdout.write(
                    f"  ✓ Mantém #{keeper.id} "
                    f"(€{keeper.amount} · {keeper.get_status_display()} · "
                    f"{keeper.created_at:%d/%m/%Y})"
                )

                for c, lines, locked_flag in info:
                    if c.id == keeper.id:
                        continue
                    if locked_flag:
                        # Não deveria ocorrer (keeper prefere o bloqueado),
                        # mas por segurança não se mexe num pago.
                        total_manual += 1
                        self.stdout.write(self.style.ERROR(
                            f"  ⚠ #{c.id} duplicado mas já pago — manual."
                        ))
                        continue

                    line_desc = ", ".join(
                        f"PF#{ln.pre_invoice_id}({ln.pre_invoice.status})"
                        for ln in lines if ln.pre_invoice
                    ) or "sem linha PF"
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✗ Remove #{c.id} "
                        f"(€{c.amount} · {c.get_status_display()} · "
                        f"{c.created_at:%d/%m/%Y}) → {line_desc}"
                    ))
                    total_removed += 1

                    if not apply:
                        continue

                    for ln in lines:
                        pf = ln.pre_invoice
                        if pf:
                            affected_pfs[pf.id] = pf
                        ln.delete()

                    c.status = "REJECTED"
                    c.reviewed_at = timezone.now()
                    note = (
                        f"[LIMPEZA] Duplicado do desconto #{keeper.id} sobre "
                        f"o mesmo waybill {wb}. Linha(s) PF removida(s) e "
                        f"claim rejeitado por dedupe_driver_claims."
                    )
                    c.review_notes = (
                        (c.review_notes + "\n" if c.review_notes else "") + note
                    )
                    c.save(update_fields=[
                        "status", "reviewed_at", "review_notes", "updated_at",
                    ])

            # Recalcular PFs afectadas
            for pf in affected_pfs.values():
                old = pf.status
                pf.recalcular()
                pf.save()
                self.stdout.write(
                    f"  ↻ PF#{pf.id} recalculada "
                    f"({old} → {pf.status}, perdidos=€{pf.total_pacotes_perdidos})"
                )

        if apply:
            with transaction.atomic():
                process()
        else:
            process()

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=== Resumo ==="))
        self.stdout.write(f"  Duplicados a remover : {total_removed}")
        self.stdout.write(f"  Casos manuais        : {total_manual}")
        self.stdout.write(f"  PFs afectadas        : {len(affected_pfs)}")
        if not apply:
            self.stdout.write(self.style.NOTICE(
                "DRY-RUN — nada foi alterado. Reexecute com --apply para "
                "efectivar."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("Alterações aplicadas."))
