import json
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')

import django

django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from system_config.models import SystemConfiguration

client = Client()
user = get_user_model().objects.filter(is_superuser=True).first() or get_user_model().objects.first()
if user is None:
    raise SystemExit('No user to login with')

client.force_login(user)
response = client.get('/system/whatsapp/')
csrf = client.cookies.get('csrftoken').value if 'csrftoken' in client.cookies else ''
print('GET status:', response.status_code, 'csrf:', bool(csrf))
print('csrf value:', repr(csrf))

payload = {
    'api_url': 'http://wppconnect:21465',
    'instance_name': 'leguas_wppconnect',
}
result = client.post(
    '/system/whatsapp/update-config/',
    data=json.dumps(payload),
    content_type='application/json',
    HTTP_X_CSRFTOKEN=csrf,
)
print('POST status:', result.status_code)
print('POST body head:', result.content.decode()[:300])

config = SystemConfiguration.get_config()
print('stored api:', config.whatsapp_evolution_api_url)
print('stored instance:', config.whatsapp_instance_name)
