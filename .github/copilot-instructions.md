# Leguas Franzinas - AI Coding Agent Instructions

## Project Overview
Django 4.2 multi-tenant logistics platform for Paack delivery operations, driver management, and data analytics. Built with MySQL, Tailwind CSS, and async geolocation services.

## Architecture & Key Components

### Core Apps Structure
- **`ordersmanager_paack/`** - Central data sync engine. Uses `APIConnector` class to fetch external Paack API data via authenticated requests with `COOKIE_KEY` and `SYNC_TOKEN` env vars. Models: `Order`, `Dispatch`, `Driver`. Custom QuerySets enable filtering like `.delivered()`, `.failed()`, `.by_driver_id(driver_id)`.
- **`paack_dashboard/`** - Analytics dashboard using `DashboardDataService` class for date filtering. Supports two modes: single-date (`filter_date`) and range (`start_date`/`end_date`). Always check `date_range_mode` boolean when building queries.
- **`customauth/`** - Dual authentication: Django users (staff/managers) and `DriverAccess` model (drivers). Uses session-based driver auth with `driver_access_id` in session. Login view tries Django auth first, then custom driver auth.
- **`converter/`** - AI-powered list parser with learning capabilities. `IntelligentDataDetector` class uses pattern matching + `ranking_data.json` for incremental learning. Detects fields: `endereco`, `codigo_id`, `hora`, `litros`, `quantidade`.
- **`drivers_app/`** - Driver portal with delivery history, performance metrics. Requires `is_driver_authenticated` session check in views.
- **`send_paack_reports/`** - Automated WhatsApp reporting via Evolution API. Management commands: `send_report`, `auto_send_reports`. Auto-syncs data before each report.

### Database Patterns
- **Remote MySQL**: External production DB at `45.160.176.10`. Never use hardcoded credentials outside `.env`.
- **Timezone**: Always `Europe/Lisbon` (`TIME_ZONE = 'Europe/Lisbon'`). Use `timezone.now()` from `django.utils`.
- **Custom Managers**: Models use custom QuerySets. Example: `Order.objects.delivered()` instead of `Order.objects.filter(status='delivered')`.

### External Integrations
1. **Paack API** (`ordersmanager_paack/APIConnect.py`):
   - POST to `API_URL` with complex payload including `syncsOnConsent`, `perTableParams`, `etag` values
   - Headers require `Cookie`, `Authorization` bearer token, `X-Requested-With: XMLHttpRequest`
   - Returns nested JSON with `DATA_EXTRACT_AVG`, `DATA_PIVOT` tables

2. **GeoAPI.pt** (`converter/geoapicheck.py`):
   - Async address validation using `aiohttp`
   - Token stored in `GEOAPI_TOKEN` env var
   - Views must use `async def` with `@csrf_exempt` decorator

3. **Evolution API** (WhatsApp):
   - Reports sent to group via POST with JSON payload
   - Configured in `send_paack_reports/views.py` and management commands

## Development Workflows

### Environment Setup
```bash
# Required .env variables (NEVER commit):
SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
API_URL, COOKIE_KEY, SYNC_TOKEN  # Paack API credentials
GEOAPI_TOKEN                      # Address validation
INTERNAL_API_URL                  # For inter-service communication
```

### Running & Testing
```bash
# Development server
python manage.py runserver

# Docker environment (preferred for local development)
docker-compose up -d --build    # Build and start all services
docker-compose restart web      # Restart Django after code changes
docker-compose logs -f web      # View Django logs

# Tailwind CSS (separate terminal, app: 'theme')
python manage.py tailwind start

# Static files collection (required after CSS/JS changes)
python manage.py collectstatic --noinput

# Data sync (critical for fresh data)
python manage.py shell
>>> from ordersmanager_paack.sync_service import SyncService
>>> SyncService().sync_all_data()

# Management commands
python manage.py send_report --preview              # Test report generation
python manage.py auto_send_reports --run-once       # Single report run
```

### Authentication Middleware
No custom middleware - uses session-based checks. For driver views:
```python
if not request.session.get('is_driver_authenticated'):
    return redirect('customauth:authenticate')
driver_id = request.session.get('driver_access_id')
```

## Coding Conventions

### Views & Templates
- **Login required**: Use `@login_required` for staff, session checks for drivers
- **Portuguese UI**: All user-facing text, messages, labels in `pt-PT`
- **Template inheritance**: `base_driver.html` for drivers, project-level `base.html` for staff
- **Tailwind styling**: Use utility classes, avoid custom CSS. Dark mode support via `dark:` prefix
- **Date handling**: Pass dates as strings `'YYYY-MM-DD'` in GET params, convert in view with `timezone.datetime.strptime()`

### Models
- **Timestamps**: Use `auto_now_add=True` for creation, `auto_now=True` for updates
- **String representation**: `__str__` must return meaningful Portuguese text
- **Custom QuerySets**: Define in separate QuerySet class, expose via Manager
```python
class OrderQuerySet(models.QuerySet):
    def delivered(self):
        return self.filter(status='delivered')

class OrderManager(models.Manager):
    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)
```

### Async Views
When using async (GeoAPI, bulk operations):
- Import: `from asgiref.sync import async_to_sync, sync_to_async`
- Database access: Wrap ORM calls with `@sync_to_async` or `database_sync_to_async`
- Always handle `asyncio` exceptions and log with `logger.error(..., exc_info=True)`

### Logging
Configured per-app with custom handlers. Use existing loggers:
```python
import logging
logger = logging.getLogger(__name__)  # Uses app-specific config from settings.py
logger.info("Message")  # For ordersmanager_paack, uses sync_console handler
```

## Critical Files Reference
- [my_project/settings.py](my_project/settings.py) - All env vars, installed apps, logging config
- [ordersmanager_paack/APIConnect.py](ordersmanager_paack/APIConnect.py) - External API integration pattern
- [paack_dashboard/views.py](paack_dashboard/views.py) - `DashboardDataService` date filtering pattern
- [converter/ai_detector.py](converter/ai_detector.py) - AI pattern learning system
- [customauth/views.py](customauth/views.py) - Dual authentication implementation

## Common Gotchas
1. **Static files**: Run `collectstatic` after ANY CSS/JS/image changes, even in development
2. **Tailwind**: Changes require `tailwind` app running in separate terminal to rebuild CSS
3. **Date filters**: Dashboard supports BOTH single-date and range modes - always check `date_range_mode`
4. **Driver auth**: Session-based, not Django User. Don't use `request.user` for drivers
5. **API sync**: Data can be stale. Auto-sync before reports, but manual sync needed for dashboard
6. **Timezone awareness**: MySQL stores UTC with timezone support disabled. Always use `timezone.now()` and `USE_TZ = True`
7. **Portuguese**: Field names in code (e.g., `codigo_id`, `litros`) match Portuguese conventions from external API
8. **Docker changes**: ALWAYS run `docker-compose restart web` after changing Python code, models, views, or settings. For new dependencies in `requirements.txt`, run `docker-compose up -d --build`. Migrations require restart to take effect.

## When Adding Features
- **New app**: Follow existing structure - models.py, views.py, urls.py, templates/, static/
- **Management commands**: Create in `<app>/management/commands/<name>.py`, inherit from `BaseCommand`
- **API endpoints**: Prefer function-based views with explicit decorators over class-based views
- **Migrations**: Always test on dev before production (remote DB requires careful migration planning)
- **Dark mode**: Add `dark:` variants to all color classes when styling with Tailwind
