#!/usr/bin/env python
import json
import os

import django

from system_config.whatsapp_helper import WhatsAppWPPConnectAPI

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()


api = WhatsAppWPPConnectAPI.from_config()

# Testar vários endpoints
endpoints = [
    ("/status-session", "get"),
    ("/host-device", "get"),
    ("/get-host-device", "get"),
    ("/device-info", "get"),
    ("/session-info-token", "get"),
    ("/battery-status", "get"),
    ("/get-battery-level", "get"),
    ("/all-chats", "get"),
]

print("=" * 60)
print("TESTANDO ENDPOINTS DO WPPCONNECT")
print("=" * 60)

for endpoint, method in endpoints:
    try:
        result = api._request(method, endpoint)
        print(f"\n✅ SUCCESS: {method.upper()} {endpoint}")
        print(json.dumps(result, indent=2)[:800])
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            print(f"\n❌ NOT FOUND: {endpoint}")
        elif "401" in error_msg:
            print(f"\n🔒 UNAUTHORIZED: {endpoint}")
        else:
            print(f"\n❌ ERROR {endpoint}: {error_msg[:200]}")
