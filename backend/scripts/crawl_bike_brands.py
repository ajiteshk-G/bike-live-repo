"""Crawl official two-wheeler brand websites and save them as Brand Studio catalogs.

Usage (from backend/):
    PYTHONPATH=. ./.venv/bin/python scripts/crawl_bike_brands.py            # TVS + Hero
    PYTHONPATH=. ./.venv/bin/python scripts/crawl_bike_brands.py tvs        # one brand
"""
import asyncio
import logging
import sys
import time

from app.services.brand_crawler_service import BrandCrawlerService, KNOWN_TWO_WHEELER_BRANDS
from app.services.brand_service import BrandService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


async def crawl(key: str) -> None:
    profile = KNOWN_TWO_WHEELER_BRANDS[key]
    t0 = time.time()
    catalog = await BrandCrawlerService.crawl_and_extract_catalog(profile["name"], [profile["home_url"]])
    BrandService.onboard_or_save_brand(catalog, set_active=(key == "tvs"))
    real_imgs = sum(1 for v in catalog.vehicles if v.hero_image.startswith("/uploads/"))
    print(f"\n=== {catalog.name} ({catalog.id}) — {len(catalog.vehicles)} models, {real_imgs} real images, "
          f"logo={catalog.logo_url or '-'} [{time.time() - t0:.0f}s]")
    for v in catalog.vehicles:
        print(f"  {v.name:<34} {v.category:<22} {v.price_range:<30} {v.range_or_mileage:<22} "
              f"{'IMG' if v.hero_image.startswith('/uploads/') else 'placeholder'}")


async def main(keys):
    for k in keys:
        await crawl(k)
    # Exactly one catalog may be active; TVS is the demo default when present.
    if BrandService.get_brand("tvs"):
        BrandService.set_active_brand("tvs")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["tvs", "hero"]))
