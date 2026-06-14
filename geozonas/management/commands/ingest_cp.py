"""
Importa códigos postais da GeoAPI por prefixo CP4.

Exemplos:
    python manage.py ingest_cp 4990
    python manage.py ingest_cp 4990 4740 --coords
"""

from django.core.management.base import BaseCommand, CommandError

from geozonas.services.ingest import ingest_cp4


class Command(BaseCommand):
    help = "Importa códigos postais da GeoAPI por prefixo CP4."

    def add_arguments(self, parser):
        parser.add_argument("cp4", nargs="+", help="Um ou mais prefixos CP4 (ex.: 4990)")
        parser.add_argument(
            "--coords",
            action="store_true",
            help="Enriquece cada CP com coordenadas GPS (1 chamada por CP3).",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help=(
                "Re-busca o GPS de TODOS os CP3 (default: só os em falta, "
                "para poupar tokens)."
            ),
        )

    def handle(self, *args, **options):
        prefixos = options["cp4"]
        com_coords = options["coords"]
        forcar = options["forcar"]

        for cp4 in prefixos:
            if not (cp4.isdigit() and len(cp4) == 4):
                raise CommandError(f"CP4 inválido: {cp4} (deve ter 4 dígitos)")

            self.stdout.write(f"→ A importar {cp4} ...")
            stats = ingest_cp4(
                cp4, com_coordenadas=com_coords, forcar_coords=forcar,
            )

            if not stats["ok"]:
                self.stdout.write(self.style.ERROR(f"  ✗ {cp4}: {stats.get('erro')}"))
                continue

            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ {cp4} ({stats['concelho']}): "
                    f"{stats['total']} CPs "
                    f"({stats['criados']} novos, {stats['atualizados']} atualizados"
                    + (f", {stats['com_coordenadas']} c/ coordenadas" if com_coords else "")
                    + ")"
                )
            )
