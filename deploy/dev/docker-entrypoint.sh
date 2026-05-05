#!/bin/bash

# Script de entrada para o container Django
set -e

echo "🔄 Aguardando MySQL ficar disponível..."
python << END
import sys
import time
import MySQLdb

max_tries = 30
tries = 0

while tries < max_tries:
    try:
        conn = MySQLdb.connect(
            host="${DB_HOST:-db}",
            port=int("${DB_PORT:-3306}"),
            user="${DB_USER:-leguas_user}",
            passwd="${DB_PASSWORD:-leguas_password_dev}",
            db="${DB_NAME:-leguas_db}"
        )
        conn.close()
        print("✅ MySQL está pronto!")
        sys.exit(0)
    except MySQLdb.Error as e:
        tries += 1
        print(f"⏳ Tentativa {tries}/{max_tries}: MySQL ainda não está pronto...")
        time.sleep(2)

print("❌ MySQL não ficou disponível a tempo")
sys.exit(1)
END

echo "🔄 Aplicando migrações..."
python manage.py migrate --noinput --fake-initial || echo "⚠️ Migrações falharam, mas continuando..."

echo "🔄 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "✅ Inicialização completa!"

# Executar o comando passado ao container
exec "$@"
