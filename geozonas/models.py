"""
Modelos do módulo GeoZonas.

Catalogam a hierarquia geográfica portuguesa (Distrito > Concelho > Freguesia >
Localidade > Código Postal) a partir da GeoAPI.pt e permitem desenhar Zonas de
entrega (A/B/C/D) sobre o mapa.

Nota de arquitetura: a base de dados é MySQL 8 e NÃO usamos django.contrib.gis
(para não meter GDAL/GEOS nos containers). As geometrias são guardadas como GeoJSON
em JSONField e o ponto-em-polígono é resolvido em Python com shapely. Ver memória
[[project-geozonas-module]].
"""

from django.db import models


class Concelho(models.Model):
    nome = models.CharField("Concelho", max_length=120, unique=True)
    distrito = models.CharField("Distrito", max_length=120, blank=True)
    codigo_ine = models.CharField(
        "Código INE", max_length=12, blank=True, db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Concelho"
        verbose_name_plural = "Concelhos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Freguesia(models.Model):
    nome = models.CharField("Freguesia", max_length=180)
    concelho = models.ForeignKey(
        Concelho, on_delete=models.CASCADE, related_name="freguesias"
    )
    codigo_ine = models.CharField(
        "Código INE", max_length=12, blank=True, db_index=True
    )
    # Polígono real da freguesia (GeoJSON da GeoAPI) — camada de fundo do mapa
    geojson = models.JSONField("Polígono (GeoJSON)", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Freguesia"
        verbose_name_plural = "Freguesias"
        ordering = ["concelho__nome", "nome"]
        unique_together = [["concelho", "nome"]]

    def __str__(self):
        return f"{self.nome} ({self.concelho.nome})"


class Localidade(models.Model):
    nome = models.CharField("Localidade", max_length=180, db_index=True)
    freguesia = models.ForeignKey(
        Freguesia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="localidades",
    )

    class Meta:
        verbose_name = "Localidade"
        verbose_name_plural = "Localidades"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class CodigoPostal(models.Model):
    """Unidade atómica: um CP completo CP4-CP3 (ex.: 4990-008)."""

    FONTE_CHOICES = [
        ("geoapi", "GeoAPI"),
        ("ctt", "CTT"),
        ("seed", "Importação inicial"),
        ("manual", "Manual"),
    ]

    cp4 = models.CharField("CP4", max_length=4, db_index=True)
    cp3 = models.CharField("CP3", max_length=3)
    designacao_postal = models.CharField("Designação Postal", max_length=180, blank=True)

    localidade = models.ForeignKey(
        Localidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="cps"
    )
    freguesia = models.ForeignKey(
        Freguesia, on_delete=models.SET_NULL, null=True, blank=True, related_name="cps"
    )
    concelho = models.ForeignKey(
        Concelho, on_delete=models.SET_NULL, null=True, blank=True, related_name="cps"
    )

    # Ponto GPS (usado no point-in-polygon do mapa)
    latitude = models.DecimalField(
        "Latitude", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        "Longitude", max_digits=9, decimal_places=6, null=True, blank=True
    )

    arterias = models.JSONField("Artérias/Ruas", null=True, blank=True)
    fonte = models.CharField(max_length=10, choices=FONTE_CHOICES, default="geoapi")

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Código Postal"
        verbose_name_plural = "Códigos Postais"
        ordering = ["cp4", "cp3"]
        unique_together = [["cp4", "cp3"]]
        indexes = [
            models.Index(fields=["cp4", "cp3"], name="geozonas_co_cp4_cp3_idx"),
            models.Index(fields=["concelho"], name="geozonas_co_concelh_idx"),
        ]

    def __str__(self):
        return self.codigo_postal

    @property
    def codigo_postal(self):
        return f"{self.cp4}-{self.cp3}"

    @property
    def tem_coordenadas(self):
        return self.latitude is not None and self.longitude is not None


class ZonaGeo(models.Model):
    """
    Zona de entrega desenhada no mapa (Zona A/B/C/D...).
    Espelha-se opcionalmente numa pricing.PostalZone para o route_allocation
    continuar a atribuir motoristas sem alterações.
    """

    nome = models.CharField("Nome da Zona", max_length=100, help_text='Ex.: "Zona A"')
    codigo = models.SlugField("Código", max_length=40, unique=True)
    cor = models.CharField(
        "Cor", max_length=7, default="#2563eb", help_text="Hex, ex.: #2563eb"
    )

    # Polígono desenhado pelo utilizador no mapa (GeoJSON)
    poligono = models.JSONField("Polígono (GeoJSON)", null=True, blank=True)

    postal_zone = models.ForeignKey(
        "pricing.PostalZone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="geozonas",
        help_text="Zona de tarifário espelhada (opcional)",
    )
    motorista_default = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="geozonas_default",
    )

    is_active = models.BooleanField("Ativa", default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zona Geográfica"
        verbose_name_plural = "Zonas Geográficas"
        ordering = ["nome"]


class AreaCP4(models.Model):
    """Contorno (divisas) da área de um prefixo CP4, vindo da GeoAPI.

    O endpoint /cp/{CP4} devolve `poligono` (a fronteira da área do CP4).
    Guardamo-lo como GeoJSON para desenhar automaticamente no mapa, por
    cima do qual se definem as Zonas.
    """

    cp4 = models.CharField("CP4", max_length=4, unique=True, db_index=True)
    concelho_nome = models.CharField("Concelho", max_length=160, blank=True)
    distrito = models.CharField("Distrito", max_length=120, blank=True)
    poligono = models.JSONField("Contorno (GeoJSON)", null=True, blank=True)
    centro_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    centro_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Área CP4"
        verbose_name_plural = "Áreas CP4"
        ordering = ["cp4"]

    def __str__(self):
        return f"Área {self.cp4} ({self.concelho_nome})"


class IngestJob(models.Model):
    """Acompanhamento do progresso de uma importação de prefixo CP4."""

    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("A_CORRER", "A correr"),
        ("CONCLUIDO", "Concluído"),
        ("ERRO", "Erro"),
    ]

    cp4 = models.CharField("CP4", max_length=4, db_index=True)
    com_coordenadas = models.BooleanField(default=False)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="PENDENTE", db_index=True
    )
    concelho = models.CharField(max_length=120, blank=True)

    total = models.IntegerField("Total de CP3", default=0)
    processados = models.IntegerField("CP3 catalogados", default=0)
    coords_total = models.IntegerField(default=0)
    coords_feitas = models.IntegerField(default=0)
    coords_falhadas = models.IntegerField(default=0)

    erro = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Importação (Job)"
        verbose_name_plural = "Importações (Jobs)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.cp4} [{self.status}] {self.percent}%"

    @property
    def percent(self):
        """Percentagem global: catálogo conta como 1ª metade, coords como 2ª."""
        if self.status == "CONCLUIDO":
            return 100
        if self.status in ("PENDENTE",) or self.total == 0:
            return 0
        if not self.com_coordenadas:
            return 100 if self.processados >= self.total else 50
        # Com coordenadas: catálogo = 20%, coordenadas = 80%
        base = 20 if self.processados >= self.total else 0
        if self.coords_total:
            base += int(80 * self.coords_feitas / self.coords_total)
        return min(base, 99)

    def __str__(self):
        return self.nome
