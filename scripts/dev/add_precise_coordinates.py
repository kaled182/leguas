#!/usr/bin/env python
"""
Script para adicionar coordenadas precisas por código postal
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from pricing.models import PostalZone

print("=" * 80)
print("ADICIONANDO COORDENADAS PRECISAS POR CÓDIGO POSTAL")
print("=" * 80)
print()

# Coordenadas específicas para os códigos postais mais comuns
# Baseado em dados do OpenStreetMap e Google Maps
postal_coords = {
    # Região do Porto e Área Metropolitana
    '4450': ('Matosinhos', 41.182400, -8.689100),
    '4435': ('Rio Tinto', 41.179100, -8.559500),
    '4460': ('Senhora da Hora', 41.189600, -8.654200),
    '4445': ('Alfena / Ermesinde', 41.223100, -8.557200),
    '4420': ('Gondomar', 41.144500, -8.534700),
    '4465': ('São Mamede de Infesta', 41.191400, -8.6003400),
    '4455': ('Perafita / Lavra', 41.230100, -8.738800),
    '4440': ('Valongo', 41.188800, -8.497900),
    '4510': ('Fânzeres', 41.165900, -8.501200),
    '4458': ('Custóias', 41.197600, -8.637600),
    
    # Região de Viana do Castelo
    '4900': ('Viana do Castelo Centro', 41.693200, -8.834400),
    '4990': ('Ponte de Lima', 41.767300, -8.583600),
    '4935': ('Viana do Castelo Norte', 41.748900, -8.846700),
    '4910': ('Caminha', 41.876000, -8.836800),
    '4905': ('Viana - Darque', 41.675500, -8.849200),
    '4940': ('Paredes de Coura', 41.914300, -8.560900),
    '4970': ('Arcos de Valdevez', 41.847000, -8.418500),
    '4920': ('Vila Nova de Cerveira', 41.940600, -8.742600),
    '4925': ('Viana - Santa Marta', 41.700600, -8.791800),
    '4980': ('Ponte da Barca', 41.805800, -8.417900),
}

created_count = 0
updated_count = 0

for cp_4, (locality, lat, lng) in postal_coords.items():
    # Verificar se já existe
    pattern = f'^{cp_4}\\d{{2}}'
    
    existing = PostalZone.objects.filter(postal_code_pattern=pattern).first()
    
    if existing:
        # Atualizar
        existing.name = locality
        existing.center_latitude = lat
        existing.center_longitude = lng
        existing.save()
        updated_count += 1
        print(f"✏️  Atualizado: {locality} ({cp_4}XX) → Lat: {lat}, Lng: {lng}")
    else:
        # Criar novo
        code = f"CP-{cp_4}"
        PostalZone.objects.create(
            name=locality,
            code=code,
            postal_code_pattern=pattern,
            center_latitude=lat,
            center_longitude=lng,
            region="NORTE" if cp_4.startswith('4') else "CENTRO",
            is_urban=True,
            average_delivery_time_hours=24
        )
        created_count += 1
        print(f"✅ Criado: {locality} ({cp_4}XX) → Lat: {lat}, Lng: {lng}")

print()
print(f"📊 Resumo:")
print(f"   ✅ Criadas: {created_count} zonas")
print(f"   ✏️  Atualizadas: {updated_count} zonas")
print()
print("🗺️  Agora o mapa deve mostrar pins distribuídos geograficamente!")
print()
