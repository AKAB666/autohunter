
"""Combine configured authorized feeds into the app's normalized listing format."""
import os
import aiohttp
from .providers.drom import search_drom

async def fetch_listings():
    listings = []
    external_url = os.getenv("FEED_URL", "").strip()
    if external_url:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(external_url) as response:
                response.raise_for_status()
                payload = await response.json()
                if not isinstance(payload, list):
                    raise ValueError("FEED_URL must return a JSON array")
                listings.extend(payload)

    drom_rows = await search_drom(
        city_id=os.getenv("DROM_CITY_ID") or None,
        region_id=os.getenv("DROM_REGION_ID") or None,
    )
    listings.extend(drom_rows)

    # Deduplicate by canonical listing URL.
    unique = {}
    for row in listings:
        url = row.get("url")
        if url:
            unique[url] = row
    return list(unique.values())
