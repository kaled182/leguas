#!/usr/bin/env python
"""
Script para corrigir campos NOT NULL no sistema
"""

import os
import sys

import django

from system_config.models import SystemConfiguration

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()


def fix_required_fields():
    """Corrige campos obrigatórios que estão NULL"""
    print("🔧 Corrigindo campos obrigatórios...\n")

    config = SystemConfiguration.get_config()

    # Campos que devem ter valores padrão
    fields_to_fix = {
        "map_default_lat": 41.69314,
        "map_default_lng": -8.83565,
        "map_default_zoom": 12,
        "map_type": "terrain",
        "map_language": "pt-PT",
        "map_theme": "light",
    }

    fixed = []

    for field, default_value in fields_to_fix.items():
        current = getattr(config, field, None)

        if current is None or (isinstance(current, str) and current == ""):
            print(f"⚠️  '{field}' está NULL → Corrigindo para: {default_value}")
            setattr(config, field, default_value)
            fixed.append(field)
        else:
            print(f"✅ '{field}' = {current}")

    if fixed:
        print(f"\n💾 Salvando {len(fixed)} correções...")
        try:
            config.save()
            print("✅ Corrigido com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao salvar: {e}")
            return False
    else:
        print("\n✅ Todos os campos OK!")

    return True


if __name__ == "__main__":
    fix_required_fields()
