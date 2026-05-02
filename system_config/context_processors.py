import json
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings

from .models import CompanyProfile

_vite_manifest_cache = {"mtime": None, "entry": None}


def _load_vite_entry():
    manifest_path = Path(settings.STATIC_ROOT) / "vue-spa" / ".vite" / "manifest.json"
    try:
        stat = manifest_path.stat()
    except FileNotFoundError:
        _vite_manifest_cache["mtime"] = None
        _vite_manifest_cache["entry"] = None
        return None

    if _vite_manifest_cache["mtime"] == stat.st_mtime:
        return _vite_manifest_cache["entry"]

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _vite_manifest_cache["mtime"] = stat.st_mtime
        _vite_manifest_cache["entry"] = None
        return None

    entry = data.get("index.html")
    if not entry or "file" not in entry:
        _vite_manifest_cache["mtime"] = stat.st_mtime
        _vite_manifest_cache["entry"] = None
        return None

    _vite_manifest_cache["mtime"] = stat.st_mtime
    _vite_manifest_cache["entry"] = {
        "file": entry["file"],
        "css": entry.get("css", []),
    }
    return _vite_manifest_cache["entry"]


def setup_logo(request):
    profile = CompanyProfile.objects.order_by("-updated_at").first()
    if profile and profile.assets_logo:
        return {"setup_logo": SimpleNamespace(logo=profile.assets_logo)}
    return {"setup_logo": None}


def static_version(request):
    """Expose STATIC_ASSET_VERSION for cache bust in templates."""
    return {
        "STATIC_ASSET_VERSION": getattr(settings, "STATIC_ASSET_VERSION", "dev"),
        "VITE_ENTRY": _load_vite_entry(),
    }


def map_config(request):
    """Expose the active map provider config to every template.

    The `map_config` dict can be consumed by any template rendering a Leaflet
    or similar map so that it uses the tile provider configured in
    /system-config/ (Mapbox / Esri / OSM / Google).
    """
    _default = {
        "provider": "osm",
        "mapbox_token": "",
        "mapbox_style": "mapbox://styles/mapbox/streets-v12",
        "mapbox_custom": "",
        "esri_api_key": "",
        "esri_basemap": "streets",
        "osm_tile_server": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "google_maps_api_key": "",
        "default_lat": "0",
        "default_lng": "0",
        "default_zoom": 12,
        "theme": "light",
    }
    try:
        from .models import SystemConfiguration
        cfg = SystemConfiguration.get_config()
        return {
            "map_config": {
                "provider":       cfg.map_provider or "osm",
                "mapbox_token":   cfg.mapbox_access_token or "",
                "mapbox_style":   cfg.mapbox_style or "mapbox://styles/mapbox/streets-v12",
                "mapbox_custom":  cfg.mapbox_custom_style or "",
                "esri_api_key":   cfg.esri_api_key or "",
                "esri_basemap":   cfg.esri_basemap or "streets",
                "osm_tile_server": cfg.osm_tile_server
                    or "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "google_maps_api_key": cfg.google_maps_api_key or "",
                "default_lat":    str(cfg.map_default_lat) if cfg.map_default_lat is not None else "0",
                "default_lng":    str(cfg.map_default_lng) if cfg.map_default_lng is not None else "0",
                "default_zoom":   cfg.map_default_zoom or 12,
                "theme":          cfg.map_theme or "light",
            }
        }
    except Exception:
        return {"map_config": _default}
