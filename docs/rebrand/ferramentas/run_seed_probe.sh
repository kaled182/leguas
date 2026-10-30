cd /app; rm -f /rbdata/seed.sqlite3; python manage.py migrate --noinput 2>&1 | tail -1; python /rbcfg/seed.py 2>&1 | tail -8
cp /rbdata/seed.sqlite3 /rbdata/seed.pristine.sqlite3
python /rbcfg/probe.py 2>&1 | tail -5
cp /rbdata/seed.pristine.sqlite3 /rbdata/seed.sqlite3
python /rbcfg/probe2.py 2>&1 | tail -1
