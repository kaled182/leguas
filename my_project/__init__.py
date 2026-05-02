# PyMySQL não é necessário quando usamos mysqlclient
# import pymysql
# pymysql.install_as_MySQLdb()

# Importar Celery app para carregar quando Django iniciar
from .celery import app as celery_app

__all__ = ('celery_app',)
