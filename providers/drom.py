
"""Experimental Drom search adapter.

Endpoint and query parameter names are based on Drom's published API docs.
Response-field mapping may need adjustment against an authorized live response.
"""
import os
import aiohttp

BASE = os.getenv("DROM_API_BASE", "https://api.drom.ru/v1.2")
SEARCH_URL = BASE.rstrip("/") + "/bulls/search"

def _first(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if value not in (None, ""):
            return value
    return None

def normalize_item(item):
    if not isinstance(item, dict):
        return None
    listing_id = _first(item, "id", "bullId", "offerId")
    url = _first(item, "url", "link", "href")
    if not url and listing_id:
        url = f"https://www.drom.ru/{listing_id}.html"
    title = _first(item, "title", "name", "modelName", "carName")
    price = _first(item, "price", "priceValue", "cost")
    if not url or not title:
        return None
    try:
        price = int(float(price)) if price is not None else None
    except (TypeError, ValueError):
        price = None
    return {
        "source": "drom",
        "title": str(title),
        "price": price,
        "url": str(url),
        "city": _first(item, "city", "cityName"),
        "year": _first(item, "year", "yearOfIssue"),
        "mileage_km": _first(item, "mileage", "mileageKm", "run"),
        "market_price": None,
    }

async def search_drom(city_id=None, region_id=None, page=1):
    if os.getenv("DROM_ENABLED", "0") != "1":
        return []
    params = {"page": page}
    if city_id:
        params["cityId"] = city_id
    if region_id:
        params["regionId"] = region_id
    # Optional search parameters can be added from the bot's filters later.
    timeout = aiohttp.ClientTimeout(total=25)
    headers = {"Accept": "application/json"}
    sign = os.getenv("DROM_SIGN", "").strip()
    if sign:
        params["sign"] = sign
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(SEARCH_URL, params=params) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = next((payload[k] for k in ("bulls", "items", "results", "data", "offers")
                     if isinstance(payload.get(k), list)), [])
    else:
        rows = []
    return [normalized for row in rows if (normalized := normalize_item(row))]
