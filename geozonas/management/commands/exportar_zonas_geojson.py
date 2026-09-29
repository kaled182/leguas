"""
Exporta todas as ZonaGeo em GeoJSON (contrato do ReliableMaps).

Exemplos:
    python manage.py exportar_zonas_geojson > zonas.geojson
    python manage.py exportar_zonas_geojson --numeros
"""

import json

from django.core.management.base import BaseCommand

from geozonas.services.export import exportar_zonas


class Command(BaseCommand):
    help = "Exporta as ZonaGeo em GeoJSON para o ReliableMaps."

    def add_arguments(self, parser):
        parser.add_argument(
            "--numeros",
            action="store_true",
            help="Em vez do GeoJSON, mostra os números para conferir.",
        )

    def handle(self, *args, **opts):
        fc, numeros = exportar_zonas()
        out = numeros if opts["numeros"] else fc
        self.stdout.write(json.dumps(out, ensure_ascii=False, indent=1))
