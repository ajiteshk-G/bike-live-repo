"""Two-wheeler brand crawler.

Crawls official manufacturer websites (TVS Motor, Hero MotoCorp, or any other
two-wheeler brand URL entered in Brand Studio), discovers individual model pages,
extracts spec-dense text / JSON-LD / imagery from each page, and asks Gemini to
convert every model page into a structured ``VehicleItem``.

Design notes (learned by probing the live sites):
* Both TVS and Hero are server-rendered, so plain ``httpx`` works. Vida (Hero's EV
  sub-brand) is a JS app and returns no text — pages like that fall back to
  Gemini's own knowledge and are flagged in ``usp``.
* The first few KB of every page are mega-menus, so we strip navigation and keep
  the spec-dense sentences instead of the first N characters.
* TVS renders prices client-side (``₹ 000000`` placeholders). Prices absent from
  the page are filled from model knowledge and suffixed with ``(approx.)``.
* ``og:image`` is the brand logo on most TVS pages, but JSON-LD carries real
  product images. Hero has no JSON-LD but its ``og:image`` is the model banner.
* Images are downloaded into ``static/uploads/<brand>/vehicles`` so the catalog
  does not depend on OEM hot-linking policies.
"""
import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from google.genai import types

from app.config import settings
from app.schemas.brand import BrandCatalog
from app.schemas.catalog import DealershipItem, VehicleItem, VehicleVariant

logger = logging.getLogger("brand_crawler_service")

STATIC_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "uploads"
)
os.makedirs(STATIC_UPLOAD_DIR, exist_ok=True)

PLACEHOLDER_IMAGE = "/assets/placeholder-bike.svg"
MAX_MODELS = int(os.getenv("CRAWLER_MAX_MODELS", "16"))
FETCH_CONCURRENCY = int(os.getenv("CRAWLER_FETCH_CONCURRENCY", "6"))
GEMINI_CONCURRENCY = int(os.getenv("CRAWLER_GEMINI_CONCURRENCY", "6"))
PAGE_TIMEOUT_S = float(os.getenv("CRAWLER_PAGE_TIMEOUT_S", "15"))
MIN_IMAGE_BYTES = 12_000  # smaller files are icons / swatches

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

TWO_WHEELER_CATEGORIES = [
    "Commuter Motorcycle", "Premium Commuter", "Sports Motorcycle", "Naked Streetfighter",
    "Supersport", "Adventure Tourer", "Cruiser / Retro", "Scooter", "Performance Scooter",
    "Electric Scooter", "Electric Motorcycle", "Moped",
]

# Official model landing pages for the two launch brands. These are the *real*
# manufacturer URLs that get crawled; auto-discovery from the seed pages adds any
# models not listed here (up to MAX_MODELS).
KNOWN_TWO_WHEELER_BRANDS: Dict[str, Dict[str, Any]] = {
    "tvs": {
        "match": ["tvs"],
        "id": "tvs",
        "name": "TVS Motor",
        "tagline": "Making Mobility Exciting",
        "primary_color": "#1d3f8f",
        "secondary_color": "#0f172a",
        "accent_color": "#e31e24",
        "home_url": "https://www.tvsmotor.com/",
        "seed_urls": ["https://www.tvsmotor.com/"],
        "discover_pattern": r"^https://www\.tvsmotor\.com/(tvs-apache/(apache-rtr-[a-z0-9-]+|rr-310)|electric-scooters/tvs-[a-z0-9-]+|commuter/tvs-[a-z0-9-]+|tvs-(raider|ronin|radeon|star-city-plus|zest|ntorq))$",
        "discover_exclude": r"price-in|dealer|compare|enquiry|testride",
        "model_urls": [
            "https://www.tvsmotor.com/tvs-apache/apache-rtr-160-4v",
            "https://www.tvsmotor.com/tvs-apache/apache-rtr-200-4v",
            "https://www.tvsmotor.com/tvs-apache/apache-rtr-310",
            "https://www.tvsmotor.com/tvs-apache/rr-310",
            "https://www.tvsmotor.com/tvs-raider",
            "https://www.tvsmotor.com/tvs-ronin",
            "https://www.tvsmotor.com/tvs-radeon",
            "https://www.tvsmotor.com/tvs-star-city-plus",
            "https://www.tvsmotor.com/commuter/tvs-sport",
            "https://www.tvsmotor.com/commuter/tvs-ntorq",
            "https://www.tvsmotor.com/tvs-jupiter",
            "https://www.tvsmotor.com/tvs-jupiter-125/smartxonnect",
            "https://www.tvsmotor.com/tvs-zest",
            "https://www.tvsmotor.com/electric-scooters/tvs-iqube",
            "https://www.tvsmotor.com/electric-scooters/tvs-orbiter",
            "https://www.tvsmotor.com/electric-scooters/tvs-x",
            "https://www.tvsmotor.com/commuter/tvs-xl100",
            "https://www.tvsmotor.com/tvs-apache/apache-rtr-160-2v",
        ],
        # Extra spec pages that exist for some families (merged into the model's text)
        "spec_pages": {
            "https://www.tvsmotor.com/tvs-raider": "https://www.tvsmotor.com/tvs-raider/specifications",
            "https://www.tvsmotor.com/commuter/tvs-ntorq": "https://www.tvsmotor.com/tvs-ntorq/technical-specification",
        },
    },
    "hero": {
        "match": ["hero"],
        "id": "hero_motocorp",
        "name": "Hero MotoCorp",
        "tagline": "The Future of Mobility",
        "primary_color": "#e4002b",
        "secondary_color": "#111827",
        "accent_color": "#f59e0b",
        "home_url": "https://www.heromotocorp.com/en-in.html",
        "seed_urls": [
            "https://www.heromotocorp.com/en-in/motorcycles.html",
            "https://www.heromotocorp.com/en-in/scooters.html",
        ],
        "discover_pattern": r"^https://www\.heromotocorp\.com/en-in/(motorcycles|scooters)/[a-z0-9-]+\.html$",
        "discover_exclude": r"flexible-fuel|compare",
        "model_urls": [
            "https://www.heromotocorp.com/en-in/motorcycles/splendor-plus.html",
            "https://www.heromotocorp.com/en-in/motorcycles/splendor-plus-xtec-2-0.html",
            "https://www.heromotocorp.com/en-in/motorcycles/super-splendor-xtec.html",
            "https://www.heromotocorp.com/en-in/motorcycles/hf-deluxe.html",
            "https://www.heromotocorp.com/en-in/motorcycles/passion-plus.html",
            "https://www.heromotocorp.com/en-in/motorcycles/glamour-x.html",
            "https://www.heromotocorp.com/en-in/motorcycles/xtreme-125r.html",
            "https://www.heromotocorp.com/en-in/motorcycles/xtreme-160r-4v.html",
            "https://www.heromotocorp.com/en-in/motorcycles/xpulse-210.html",
            "https://www.heromotocorp.com/en-in/motorcycles/xpulse-200-4v.html",
            "https://www.heromotocorp.com/en-in/motorcycles/karizma-xmr.html",
            "https://www.heromotocorp.com/en-in/scooters/destini-125-xtec.html",
            "https://www.heromotocorp.com/en-in/scooters/pleasure-plus-xtec.html",
            "https://www.heromotocorp.com/en-in/scooters/xoom.html",
            "https://www.heromotocorp.com/en-in/scooters/xoom-125.html",
            "https://www.heromotocorp.com/en-in/scooters/xoom-160.html",
        ],
        "spec_pages": {},
    },
}

# Generic heuristics for unknown two-wheeler brand sites entered in Brand Studio.
GENERIC_MODEL_PATH_HINT = re.compile(
    r"/(motorcycles?|scooters?|bikes?|two-wheelers?|electric(-scooters?|-motorcycles?)?|ev|models?|products?)/[a-z0-9-]+(\.html?)?/?$",
    re.I,
)
SPEC_TOKEN = re.compile(
    r"\d[\d.,]*\s?(cc|kmpl|km/l|ps|bhp|hp|nm|kg|mm|km/h|kmph|kwh|kw|litres?|ltr|rpm|km\b|hrs?|h\b|min)",
    re.I,
)
FEATURE_TOKEN = re.compile(
    r"\b(abs|cbs|disc|drum|tft|lcd|bluetooth|smartxonnect|connect|navigation|riding mode|mode|traction|"
    r"usd|mono-?shock|suspension|led|projector|slipper|assist|quickshifter|cruise|tubeless|alloy|"
    r"under-?seat|storage|usb|charging|range|mileage|top speed|seat height|kerb|ground clearance|"
    r"fuel tank|battery|warranty|colou?rs?|variant|price|ex-showroom)\b",
    re.I,
)
NOISE_TOKEN_PREFIXES = ("menu", "navbar", "nav-", "mega", "footer", "breadcrumb", "cookie", "modal", "popup", "drawer", "login", "search")


class BrandCrawlerService:
    # ------------------------------------------------------------------ entry
    @classmethod
    async def crawl_and_extract_catalog(cls, brand_name: str, urls: List[str]) -> BrandCatalog:
        profile = cls._match_known_brand(brand_name, urls)
        clean_urls = [u.strip() for u in (urls or []) if u and u.strip()]

        if not clean_urls and not profile:
            logger.info(f"No URLs for '{brand_name}' and not a known brand — synthesising a two-wheeler catalog.")
            return await cls._synthesise_catalog(brand_name, source_urls=[])

        brand_id = profile["id"] if profile else cls._slug(brand_name)
        display_name = profile["name"] if profile else brand_name

        async with httpx.AsyncClient(timeout=PAGE_TIMEOUT_S, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            model_urls, logo_candidates = await cls._discover_model_urls(client, profile, clean_urls)
            logger.info(f"[{brand_id}] crawling {len(model_urls)} model pages")

            sem = asyncio.Semaphore(FETCH_CONCURRENCY)

            async def fetch(u: str):
                async with sem:
                    page = await cls._fetch_model_page(client, u)
                    spec_url = (profile or {}).get("spec_pages", {}).get(u)
                    if spec_url and "error" not in page:
                        spec = await cls._fetch_model_page(client, spec_url)
                        if "error" not in spec:
                            page["spec_text"] = (page["spec_text"] + " || SPEC PAGE: " + spec["spec_text"])[:14000]
                    return page

            pages = await asyncio.gather(*[fetch(u) for u in model_urls])
            good = [p for p in pages if "error" not in p and len(p.get("spec_text", "")) > 200]
            logger.info(f"[{brand_id}] {len(good)}/{len(pages)} model pages had usable content")

            for p in pages:
                logo_candidates.extend(p.get("logo_candidates", []))

            if not good:
                logger.warning(f"[{brand_id}] no crawlable model pages — falling back to knowledge synthesis")
                return await cls._synthesise_catalog(display_name, source_urls=clean_urls or [profile["home_url"]])

            gsem = asyncio.Semaphore(GEMINI_CONCURRENCY)

            async def extract(p):
                async with gsem:
                    return await cls._extract_vehicle_from_page(display_name, p)

            extracted = await asyncio.gather(*[extract(p) for p in good])

            vehicles: List[VehicleItem] = []
            seen_names = set()
            for page, data in zip(good, extracted):
                if not data:
                    continue
                vehicle = cls._to_vehicle_item(brand_id, display_name, data, page)
                key = re.sub(r"[^a-z0-9]", "", vehicle.name.lower())
                if key in seen_names or vehicle.id in {v.id for v in vehicles}:
                    logger.info(f"[{brand_id}] duplicate model '{vehicle.name}' from {page['url']} skipped")
                    continue
                seen_names.add(key)
                vehicle.hero_image = await cls._download_best_image(client, brand_id, vehicle.id, page, vehicle.name)
                vehicles.append(vehicle)

            await asyncio.gather(cls._fill_missing_efficiency(display_name, vehicles), cls._fill_missing_specs(display_name, vehicles))
            logo_url = await cls._download_logo(client, brand_id, logo_candidates)

        if not vehicles:
            return await cls._synthesise_catalog(display_name, source_urls=clean_urls)

        brand_meta = profile or await cls._infer_brand_meta(display_name, clean_urls)
        return BrandCatalog(
            id=brand_id,
            name=brand_meta.get("name", display_name),
            tagline=brand_meta.get("tagline", f"Official {display_name} Experience"),
            logo_url=logo_url or cls._generate_brand_vector_logo(brand_id, display_name, brand_meta.get("primary_color", "#0ea5e9")),
            primary_color=brand_meta.get("primary_color", "#0ea5e9"),
            secondary_color=brand_meta.get("secondary_color", "#0f172a"),
            accent_color=brand_meta.get("accent_color", "#38bdf8"),
            avatar_name=settings.AVATAR_NAME,
            avatar_voice=settings.AVATAR_VOICE,
            source_urls=clean_urls or [brand_meta.get("home_url", "")],
            is_active=True,
            vehicles=vehicles,
            dealerships=cls._default_dealerships(brand_id, brand_meta.get("name", display_name)),
        )

    # -------------------------------------------------------------- discovery
    @classmethod
    def _match_known_brand(cls, brand_name: str, urls: List[str]) -> Optional[Dict[str, Any]]:
        haystack = (brand_name or "").lower() + " " + " ".join(urls or []).lower()
        for profile in KNOWN_TWO_WHEELER_BRANDS.values():
            if any(re.search(rf"\b{m}", haystack) for m in profile["match"]):
                return profile
        return None

    @classmethod
    async def _discover_model_urls(
        cls, client: httpx.AsyncClient, profile: Optional[Dict[str, Any]], user_urls: List[str]
    ) -> Tuple[List[str], List[str]]:
        ordered: List[str] = list(profile["model_urls"]) if profile else []
        seeds = list(dict.fromkeys((profile["seed_urls"] if profile else []) + user_urls))
        pattern = re.compile(profile["discover_pattern"]) if profile else None
        exclude = re.compile(profile["discover_exclude"]) if profile and profile.get("discover_exclude") else None
        logos: List[str] = []

        for seed in seeds:
            if not cls._is_safe_public_url(seed):
                continue
            try:
                r = await client.get(seed)
                if r.status_code >= 400:
                    continue
                final = str(r.url)
                soup = BeautifulSoup(r.text, "html.parser")
                logos.extend(cls._logo_candidates(soup, final))
                host = urlparse(final).netloc
                # A user-supplied URL that is itself a model page counts as a model.
                if not profile and GENERIC_MODEL_PATH_HINT.search(urlparse(final).path):
                    ordered.append(final)
                for a in soup.find_all("a", href=True):
                    u = urljoin(final, a["href"]).split("#")[0].split("?")[0].rstrip("/")
                    if urlparse(u).netloc != host or (exclude and exclude.search(u)):
                        continue
                    if pattern:
                        if pattern.match(u):
                            ordered.append(u)
                    elif GENERIC_MODEL_PATH_HINT.search(urlparse(u).path):
                        ordered.append(u)
            except Exception as e:
                logger.warning(f"Seed {seed} discovery failed: {type(e).__name__}")

        deduped = [u for u in dict.fromkeys(u.rstrip("/") for u in ordered) if cls._is_safe_public_url(u)]
        return deduped[:MAX_MODELS], logos

    # --------------------------------------------------------------- scraping
    @staticmethod
    def _is_safe_public_url(url: str) -> bool:
        import ipaddress
        import socket

        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return False
            host = parsed.hostname.lower()
            if host in ("localhost", "metadata.google.internal") or host.endswith(".internal"):
                return False
            for _, _, _, _, sockaddr in socket.getaddrinfo(host, None):
                ip = ipaddress.ip_address(sockaddr[0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return False
            return True
        except Exception:
            return False

    @classmethod
    def _logo_candidates(cls, soup: BeautifulSoup, base: str) -> List[str]:
        out = []
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content") and "logo" in og["content"].lower():
            out.append(urljoin(base, og["content"].strip()))
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            meta = f"{src} {img.get('alt', '')} {' '.join(img.get('class') or [])}".lower()
            if "logo" in meta and not any(x in meta for x in ("partner", "footer", "app-store", "play-store", "social")):
                out.append(urljoin(base, src.strip()))
        return out

    @classmethod
    async def _fetch_model_page(cls, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        try:
            if not cls._is_safe_public_url(url):
                return {"url": url, "error": "unsafe url"}
            r = await client.get(url)
            if r.status_code >= 400:
                return {"url": url, "error": f"HTTP {r.status_code}"}
            final = str(r.url)
            soup = BeautifulSoup(r.text, "html.parser")

            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            meta_desc = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""

            # Structured data (TVS ships schema.org Motorcycle / Product blocks)
            ld_items, ld_images = [], []
            for s in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(s.string or "")
                except Exception:
                    continue
                for item in data if isinstance(data, list) else [data]:
                    if not isinstance(item, dict) or item.get("@type") in ("BreadcrumbList", "Organization", "WebSite", "FAQPage"):
                        continue
                    ld_items.append({k: item.get(k) for k in ("@type", "name", "description", "offers", "brand") if item.get(k)})
                    imgs = item.get("image") or []
                    for im in imgs if isinstance(imgs, list) else [imgs]:
                        u = im.get("url") if isinstance(im, dict) else im
                        if isinstance(u, str) and u.strip():
                            ld_images.append(urljoin(final, u.strip()))

            og_tag = soup.find("meta", attrs={"property": "og:image"})
            og_image = urljoin(final, og_tag["content"].strip()) if og_tag and og_tag.get("content") else ""

            images = cls._collect_page_images(soup, final)
            studio_images = cls._collect_studio_frames(r.text, final)
            logos = cls._logo_candidates(soup, final)

            # React/Sitecore-JSS/Next.js pages ship their content as JSON state.
            state_text, state_images = cls._harvest_json_state(soup, final)

            for s in soup(["script", "style", "noscript", "svg", "form", "iframe", "nav", "footer"]):
                s.decompose()
            cls._strip_noise(soup)

            text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
            if len(text) < 1500 and state_text:
                text = (text + " || " + state_text).strip()
                images = list(dict.fromkeys(images + state_images))
            text = re.sub(r"(Book (Now|a Test Ride)\s*){2,}", "Book Now ", text, flags=re.I)

            return {
                "url": final,
                "title": title,
                "meta_description": meta_desc,
                "json_ld": ld_items[:3],
                "ld_images": ld_images,
                "og_image": og_image,
                "images": images,
                "studio_images": studio_images,
                "logo_candidates": logos,
                "spec_text": cls._spec_dense_text(text),
            }
        except Exception as e:
            logger.warning(f"Model page {url} could not be scraped: {type(e).__name__}: {e}")
            return {"url": url, "error": str(e)}

    @staticmethod
    def _collect_page_images(soup: BeautifulSoup, base: str) -> List[str]:
        out = []
        for tag in soup.find_all(["img", "source"]):
            for attr in ("data-src", "src", "data-srcset", "srcset", "data-lazy-src"):
                v = tag.get(attr)
                if not v:
                    continue
                u = urljoin(base, v.split(",")[0].strip().split(" ")[0])
                if re.search(r"\.(png|jpe?g|webp)(\?|$)", u, re.I):
                    out.append(u)
        return list(dict.fromkeys(out))

    @staticmethod
    def _collect_studio_frames(raw_html: str, base: str, max_dirs: int = 6) -> List[str]:
        """360°-spin / colour-configurator frames (e.g. ``.../360/1.png``, ``.../Colour/black-red/3.png``,
        ``.../Variant360/Midnight-Black/10.webp``). They are clean studio shots but live in JS/JSON, not <img>."""
        raw = raw_html.replace("\\u002F", "/").replace("\\/", "/")
        pat = re.compile(
            r"""[^"'\s,()\\<>]*/(?:[^"'\s/<>]*360[^"'\s/<>]*|colou?rs?)/(?:[^"'\s<>]+/)?(\d{1,2})(?:_[a-z0-9]+)?\.(?:png|webp|jpe?g)""",
            re.I,
        )
        by_dir: Dict[str, List[Tuple[int, str]]] = {}
        for m in pat.finditer(raw):
            u = m.group(0)
            if re.search(r"bg|background|mobile|-m\.|thumb|icon", u, re.I):
                continue
            d = u.rsplit("/", 1)[0]
            by_dir.setdefault(d, []).append((int(m.group(1)), urljoin(base, u)))
        out: List[str] = []
        for d, frames in list(by_dir.items())[:max_dirs]:
            frames = sorted(set(frames))
            picks = [frames[0]] + ([frames[len(frames) // 4]] if len(frames) > 3 else [])
            out += [u for _, u in picks]
        return list(dict.fromkeys(out))

    @staticmethod
    def _strip_noise(soup: BeautifulSoup) -> None:
        """Remove menus/footers/modals by class/id token, but never a node that holds most of the page text
        (TVS wraps real hero content in classes like ``u368-header-slide``)."""
        body = soup.body or soup
        total = max(len(body.get_text(" ", strip=True)), 1)
        doomed = []
        for el in body.find_all(True):
            if el.name == "header":
                doomed.append(el)
                continue
            tokens = [t.lower() for t in (el.get("class") or [])] + ([el.get("id").lower()] if el.get("id") else [])
            if any(t.startswith(NOISE_TOKEN_PREFIXES) for t in tokens):
                doomed.append(el)
        for el in doomed:
            if getattr(el, "decomposed", False):
                continue
            try:
                if len(el.get_text(" ", strip=True)) > 0.6 * total and el.name not in ("nav", "footer"):
                    continue
                el.decompose()
            except Exception:
                pass

    @staticmethod
    def _harvest_json_state(soup: BeautifulSoup, base: str) -> Tuple[str, List[str]]:
        """Collect human-readable strings and image URLs from embedded JSON page state."""
        texts: List[str] = []
        images: List[str] = []
        seen = set()

        def walk(node, depth=0):
            if depth > 40 or len(texts) > 4000:
                return
            if isinstance(node, dict):
                for v in node.values():
                    walk(v, depth + 1)
            elif isinstance(node, list):
                for v in node:
                    walk(v, depth + 1)
            elif isinstance(node, str):
                s = node.strip()
                if not s or s in seen:
                    return
                seen.add(s)
                if re.search(r"\.(png|jpe?g|webp)(\?|$)", s, re.I) and ("/" in s):
                    images.append(urljoin(base, s))
                    return
                if s.startswith(("http", "/", "{", "#")) or re.fullmatch(r"[0-9a-fA-F-]{16,}", s):
                    return
                clean = re.sub(r"<[^>]+>", " ", s)
                clean = re.sub(r"\s+", " ", clean).strip()
                if 2 < len(clean) <= 400 and re.search(r"[A-Za-z]", clean):
                    texts.append(clean)

        for sc in soup.find_all("script"):
            raw = sc.string or ""
            if len(raw) < 2000:
                continue
            if sc.get("type") == "application/json" or sc.get("id") in ("__NEXT_DATA__", "__JSS_STATE__", "__NUXT_DATA__"):
                try:
                    walk(json.loads(raw))
                except Exception:
                    continue
        return " | ".join(texts), list(dict.fromkeys(images))

    @staticmethod
    def _spec_dense_text(text: str, budget: int = 9000) -> str:
        """Keep the intro plus the chunks that actually carry specs / features / prices."""
        intro = text[:1200]
        chunks = re.split(r"(?<=[.!?|])\s+|\s{2,}", text)
        if len(chunks) < 8:  # sites without punctuation: fixed windows
            chunks = [text[i:i + 220] for i in range(0, len(text), 220)]
        keep, seen, total = [], set(), 0
        for c in chunks:
            c = c.strip()
            if len(c) < 12 or c in seen:
                continue
            if SPEC_TOKEN.search(c) or FEATURE_TOKEN.search(c) or "₹" in c:
                seen.add(c)
                keep.append(c[:400])
                total += len(c)
                if total > budget:
                    break
        return (intro + " || " + " | ".join(keep))[: budget + 1500]

    # ---------------------------------------------------------------- gemini
    @classmethod
    async def _gemini_json(cls, prompt: str, max_tokens: int = 4096, _attempt: int = 1) -> Optional[Dict[str, Any]]:
        try:
            from app.services.genai_client import get_genai_client

            client = get_genai_client()
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.REST_CHAT_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    # gemini-2.5-flash thinking tokens count against max_output_tokens; on long spec pages
                    # they consumed ~3.9k of 4k tokens and truncated the JSON. Extraction needs no reasoning.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            raw = (resp.text or "").strip() if resp else ""
            if not raw:
                raise ValueError("empty Gemini response")
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
            start, end = raw.find("{"), raw.rfind("}")
            if start == -1 or end == -1:
                return None
            return json.loads(re.sub(r",\s*([\]}])", r"\1", raw[start:end + 1]))
        except Exception as e:
            if _attempt < 2:
                logger.info(f"Gemini JSON extraction retry after {type(e).__name__}")
                return await cls._gemini_json(prompt, max_tokens=max_tokens + 2048, _attempt=_attempt + 1)
            logger.warning(f"Gemini JSON extraction failed: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def _expected_model(page: Dict[str, Any]) -> str:
        """Model name implied by the page title (before ':' / '|' / '-') or, failing that, the URL slug."""
        title = re.split(r"\s[:|\-–]\s|:\s", page.get("title", "") or "")[0]
        title = re.sub(r"\b(BS6|BS-VI|Price|Mileage|Bike|Smart Electric Scooter|Electric Scooter|20\d\d)\b.*$", "", title, flags=re.I)
        title = re.sub(r"^New\s+", "", title, flags=re.I).strip(" -:|")
        if len(title) >= 3:
            return title
        slug = urlparse(page.get("url", "")).path.rstrip("/").split("/")[-1].replace(".html", "")
        return slug.replace("-", " ").title()

    @classmethod
    async def _extract_vehicle_from_page(cls, brand_name: str, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prompt = f"""You are a two-wheeler product data extraction engine for the Indian market.
Convert ONE official {brand_name} model web page into structured JSON.

PAGE URL: {page['url']}
PAGE TITLE: {page.get('title', '')}
THIS PAGE IS ABOUT: {cls._expected_model(page)}  <-- the "name" you output MUST be this model. The page also links to sibling models; ignore their specs.
META DESCRIPTION: {page.get('meta_description', '')}
STRUCTURED DATA (schema.org): {json.dumps(page.get('json_ld', []))[:2000]}
SPEC-DENSE PAGE TEXT:
{page.get('spec_text', '')}

RULES:
1. This page describes exactly ONE model (possibly with several variants). Use the model name as marketed (e.g. "TVS Apache RTR 160 4V", "Hero Splendor+").
2. Take every number (cc, PS, Nm, kmpl, km range, kg, mm, litres, kWh, charging time, ₹ prices) FROM THE PAGE TEXT when present.
3. Only if a value is genuinely absent from the page, fill it from your own knowledge of this exact Indian-market model. Never invent a value you do not know — use "" instead.
4. Ignore placeholder prices like "₹ 000000" or EMI amounts ("₹1,899/month"). If no real ex-showroom price is on the page, give your best-known current Indian ex-showroom price and append " (approx.)".
5. Prices are EX-SHOWROOM rupees, formatted like "₹1,18,000" or a range "₹1,18,000 - ₹1,32,000" (no space after ₹, no city/on-road notes). Never use "Lakh" for prices below ₹1,00,000.
6. category MUST be one of: {json.dumps(TWO_WHEELER_CATEGORIES)}.
7. key_highlights: 4-6 real features rider-facing features from the page (e.g. "Dual-channel ABS", "5-inch TFT with SmartXonnect", "Race-tuned USD forks", "i3S idle stop-start").
8. competitors: 2-4 real Indian-market rival models from OTHER brands in the same segment.
9. Output ONLY this JSON object:
{{
  "name": "", "tagline": "", "category": "", "price_range": "",
  "engine_specs": "one line summary, e.g. '159.7cc single-cylinder oil-cooled, 17.55 PS, 14.73 Nm' or '4.4 kW hub motor, 3.5 kWh battery'",
  "fuel_or_battery": "Petrol / Electric (3.5 kWh) / Petrol + CNG",
  "range_or_mileage": "MUST contain a number: '47 kmpl (claimed)' or '145 km IDC range' (never marketing text like '15% more mileage')",
  "displacement_cc": "", "max_power": "", "max_torque": "", "kerb_weight": "", "seat_height": "",
  "fuel_tank_or_battery": "", "top_speed": "", "braking": "",
  "riding_modes": [], "colors": [], "key_highlights": [], "usp": "", "competitors": [],
  "variants": [{{"name": "", "price_ex_showroom": "", "engine_or_battery": "", "transmission": "5-speed manual / CVT automatic / Single-speed", "key_features": []}}],
  "data_completeness": "page | page+knowledge | knowledge"
}}"""
        return await cls._gemini_json(prompt)

    @classmethod
    def _to_vehicle_item(cls, brand_id: str, brand_name: str, d: Dict[str, Any], page: Dict[str, Any]) -> VehicleItem:
        def s(key: str, default: str = "") -> str:
            v = d.get(key)
            return str(v).strip() if v not in (None, [], {}) else default

        def lst(key: str) -> List[str]:
            v = d.get(key)
            return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []

        name = s("name") or page.get("title", "").split(":")[0].split("|")[0].strip() or f"{brand_name} Model"
        category = s("category")
        if category not in TWO_WHEELER_CATEGORIES:
            low = f"{category} {name}".lower()
            category = (
                "Electric Scooter" if ("electric" in low or "ev" in low.split()) and "scoot" in low
                else "Electric Motorcycle" if "electric" in low
                else "Scooter" if "scoot" in low
                else "Commuter Motorcycle"
            )

        variants = []
        for v in d.get("variants") or []:
            if isinstance(v, dict) and v.get("name"):
                variants.append(VehicleVariant(
                    name=str(v.get("name")),
                    price_ex_showroom=str(v.get("price_ex_showroom") or s("price_range", "Contact dealer")),
                    engine_or_battery=str(v.get("engine_or_battery") or s("engine_specs")),
                    transmission=str(v.get("transmission") or ("Single-speed" if "electric" in category.lower() else "Manual")),
                    key_features=[str(x) for x in (v.get("key_features") or []) if x][:6],
                ))
        if not variants:
            variants.append(VehicleVariant(
                name="Standard", price_ex_showroom=s("price_range", "Contact dealer"),
                engine_or_battery=s("engine_specs"), transmission="Standard", key_features=lst("key_highlights")[:3],
            ))

        usp = s("usp", f"Official {name} from {brand_name}.")
        if d.get("data_completeness") == "knowledge":
            usp += " (Details compiled from public model information; official page provided limited data.)"

        return VehicleItem(
            id=f"{brand_id}_{cls._slug(re.sub(rf'^{re.escape(brand_name.split()[0])}\s+', '', name, flags=re.I))}"[:64],
            name=name,
            tagline=s("tagline", page.get("meta_description", "")[:120]),
            category=category,
            price_range=s("price_range", "Contact dealer"),
            hero_image=PLACEHOLDER_IMAGE,
            engine_specs=s("engine_specs"),
            seating_capacity="Rider + Pillion",
            fuel_or_battery=s("fuel_or_battery", "Petrol"),
            range_or_mileage=s("range_or_mileage"),
            key_highlights=lst("key_highlights")[:6] or ["Official manufacturer specifications"],
            usp=usp,
            variants=variants[:6],
            source_url=page.get("url"),
            displacement_cc=s("displacement_cc") or None,
            max_power=s("max_power") or None,
            max_torque=s("max_torque") or None,
            kerb_weight=s("kerb_weight") or None,
            seat_height=s("seat_height") or None,
            fuel_tank_or_battery=s("fuel_tank_or_battery") or None,
            top_speed=s("top_speed") or None,
            braking=s("braking") or None,
            riding_modes=lst("riding_modes") or None,
            colors=lst("colors") or None,
            competitors=lst("competitors") or None,
        )

    @classmethod
    async def _fill_missing_efficiency(cls, brand_name: str, vehicles: List[VehicleItem]) -> None:
        """Replace marketing copy ("15% more mileage") with a real claimed kmpl / km range figure."""
        ok = re.compile(r"\d+(\.\d+)?\s?(kmpl|km/l|km\b|km\s)", re.I)
        gaps = [v for v in vehicles if not ok.search(v.range_or_mileage or "")]
        if not gaps:
            return
        data = await cls._gemini_json(
            f"""For these {brand_name} two-wheelers sold in India, give the manufacturer-claimed fuel efficiency
(petrol, in kmpl) or IDC/claimed range (electric, in km). Use only figures you are confident about; else "".
Models: {json.dumps([{"id": v.id, "name": v.name, "fuel": v.fuel_or_battery} for v in gaps])}
Return JSON: {{"items": [{{"id": "", "value": "e.g. '65 kmpl' or '145 km IDC range'"}}]}}""",
            max_tokens=1024,
        ) or {}
        by_id = {i.get("id"): (i.get("value") or "").strip() for i in data.get("items", []) if isinstance(i, dict)}
        for v in gaps:
            val = by_id.get(v.id, "")
            if ok.search(val):
                v.range_or_mileage = f"{val} (approx.)" if "approx" not in val.lower() else val
            elif not ok.search(v.range_or_mileage or ""):
                v.range_or_mileage = ""
        logger.info(f"[{brand_name}] filled efficiency for {sum(1 for v in gaps if v.range_or_mileage)}/{len(gaps)} models")

    SPEC_FILL_FIELDS = ("displacement_cc", "max_power", "max_torque", "kerb_weight", "seat_height",
                        "fuel_tank_or_battery", "top_speed", "braking")

    @classmethod
    async def _fill_missing_specs(cls, brand_name: str, vehicles: List[VehicleItem]) -> None:
        """Official pages often omit seat height / kerb weight / top speed. Fill blanks from model knowledge,
        marked "(approx.)"; never overwrite a value that was scraped from the page."""
        gaps = [
            {"id": v.id, "name": v.name, "fuel": v.fuel_or_battery,
             "missing": [f for f in cls.SPEC_FILL_FIELDS if not getattr(v, f, None)] + ([] if v.riding_modes else ["riding_modes"])}
            for v in vehicles
        ]
        gaps = [g for g in gaps if g["missing"]]
        if not gaps:
            return
        data = await cls._gemini_json(
            f"""For these {brand_name} two-wheelers currently sold in India, provide ONLY the listed missing
manufacturer specifications. Use short spec strings with units: displacement_cc "159.7 cc" (EVs: "" ),
max_power "16.04 PS @ 9250 rpm" (EVs: motor peak power in kW), max_torque "14.73 Nm @ 7250 rpm",
kerb_weight "144 kg", seat_height "800 mm", fuel_tank_or_battery "12 L" or "3.4 kWh", top_speed "114 km/h",
braking "Front disc / rear drum, single-channel ABS", riding_modes as a list (empty list if none).
If you are not confident about a value, return "" (or [] for riding_modes). Do not guess wildly.
Models: {json.dumps(gaps)}
Return JSON: {{"items": [{{"id": "", "<field>": "<value>"}}]}}""",
            max_tokens=4096,
        ) or {}
        filled = 0
        by_id = {v.id: v for v in vehicles}
        for item in data.get("items", []) if isinstance(data, dict) else []:
            v = by_id.get(item.get("id")) if isinstance(item, dict) else None
            if not v:
                continue
            for f in cls.SPEC_FILL_FIELDS:
                val = item.get(f)
                if isinstance(val, str) and val.strip() and not getattr(v, f, None):
                    val = val.strip()
                    setattr(v, f, val if "approx" in val.lower() else f"{val} (approx.)")
                    filled += 1
            modes = item.get("riding_modes")
            if not v.riding_modes and isinstance(modes, list) and modes:
                v.riding_modes = [str(m).strip() for m in modes if str(m).strip()][:6]
                filled += 1
        logger.info(f"[{brand_name}] knowledge-filled {filled} missing spec values across {len(gaps)} models")

    # ----------------------------------------------------------------- images
    @classmethod
    def _rank_image_candidates(cls, page: Dict[str, Any]) -> List[str]:
        page_path = urlparse(page["url"]).path.rstrip("/")
        slug = page_path.split("/")[-1].replace(".html", "").lower()
        tokens = [t for t in re.split(r"[-_]", slug) if len(t) > 2 and t not in ("tvs", "hero", "new", "html")]
        bad = re.compile(r"logo|icon|badge|sprite|swatch|colou?r-?dot|navbar|new-product-images|plp|thumb|dealer|app-?store|play-?store|whatsapp|offer|discover-fold|corporate-website/product|background|frame_\d|cnbc|news|award", re.I)

        def own_part(u: str) -> str:
            path = urlparse(u).path
            return (path[len(page_path):] if page_path and path.startswith(page_path) else path).lower()

        scored = []
        studio = list(page.get("studio_images", []))
        ld = list(page.get("ld_images", []))
        for i, u in enumerate(studio + ld + ([page["og_image"]] if page.get("og_image") else []) + page.get("images", [])):
            if i >= len(studio) and bad.search(u):
                continue
            low = own_part(u)
            score = 10 if i < len(studio) else (6 if i < len(studio) + len(ld) else 0)
            score += sum(3 for t in tokens if t in low)
            score += 3 if re.search(r"360|/colou?rs?/|variant|side|profile|studio|cutout", low) else 0
            score += 1 if re.search(r"desk|desktop|width=2000|1920|1440|\.png", u.lower()) else 0
            score -= 3 if re.search(r"banner|ambassador|campaign|lifestyle|tvc|-mob|mobile|width=750", u.lower()) else 0
            scored.append((score, -i, u))

        out, seen = [], set()
        for _, _, u in sorted(scored, key=lambda x: (-x[0], -x[1])):
            key = u.split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            out.append(u)
        return out[:40]

    @staticmethod
    def _sniff_image_ext(data: bytes, content_type: str = "") -> Optional[str]:
        head = data[:16]
        if head.startswith(b"\x89PNG"):
            return "png"
        if head.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return "webp"
        if head[4:12] in (b"ftypavif", b"ftypavis"):
            return "avif"
        if head.startswith(b"GIF8"):
            return "gif"
        if b"<svg" in data[:512].lower():
            return "svg"
        return None

    @classmethod
    async def _download(cls, client: httpx.AsyncClient, url: str, dest_dir: str, stem: str, min_bytes: int) -> Optional[str]:
        try:
            if not cls._is_safe_public_url(url):
                return None
            r = await client.get(url, headers={**BROWSER_HEADERS, "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8"})
            if r.status_code != 200 or len(r.content) < min_bytes:
                return None
            # TVS's CDN serves images as application/octet-stream, so trust magic bytes over content-type.
            ext = cls._sniff_image_ext(r.content, r.headers.get("content-type", ""))
            if not ext:
                return None
            os.makedirs(dest_dir, exist_ok=True)
            fname = f"{stem}.{ext}"
            with open(os.path.join(dest_dir, fname), "wb") as f:
                f.write(r.content)
            return fname
        except Exception as e:
            logger.debug(f"image download failed {url}: {e}")
            return None

    @staticmethod
    def _product_shot_score(data: bytes) -> float:
        """Heuristic: studio product shots have transparent/white edges and bike-like proportions;
        ad banners are very wide, busy-edged, and often carry people/text."""
        try:
            from io import BytesIO
            from PIL import Image, ImageStat

            im = Image.open(BytesIO(data))
            im.load()
            w, h = im.size
            if min(w, h) < 220:
                return -10
            score = 0.0
            if max(ImageStat.Stat(im.convert("L")).stddev) < 12:
                return -10  # blank / solid-colour frame (e.g. lazy-load placeholder)
            ratio = w / h
            score += 2 if 1.05 <= ratio <= 2.1 else (-4 if ratio > 2.5 or ratio < 0.7 else -1)
            score += 1 if min(w, h) >= 400 else 0
            rgba = im.convert("RGBA")
            # sample a 4% border strip on all sides
            bw, bh = max(2, w // 25), max(2, h // 25)
            strips = [rgba.crop((0, 0, w, bh)), rgba.crop((0, h - bh, w, h)), rgba.crop((0, 0, bw, h)), rgba.crop((w - bw, 0, w, h))]
            alpha = sum(ImageStat.Stat(s.split()[3]).mean[0] for s in strips) / 4
            if alpha < 40:  # transparent background
                score += 5
            else:
                rgb = [s.convert("RGB") for s in strips]
                mean = sum(sum(ImageStat.Stat(s).mean) / 3 for s in rgb) / 4
                std = sum(sum(ImageStat.Stat(s).stddev) / 3 for s in rgb) / 4
                if mean > 228 and std < 18:
                    score += 4  # plain white studio background
                elif std < 12:
                    score += 1  # plain but coloured backdrop
                else:
                    score -= 2  # busy scene / banner
            return score
        except Exception:
            return -10

    @classmethod
    async def _download_best_image(cls, client: httpx.AsyncClient, brand_id: str, vehicle_id: str, page: Dict[str, Any], vehicle_name: str = "") -> str:
        """Fetch several candidates and keep the one that most looks like a studio product shot."""
        candidates = cls._rank_image_candidates(page)[:32]

        async def grab(u: str):
            try:
                if not cls._is_safe_public_url(u):
                    return None
                r = await client.get(u, headers={**BROWSER_HEADERS, "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8"})
                if r.status_code != 200 or len(r.content) < MIN_IMAGE_BYTES:
                    return None
                ext = cls._sniff_image_ext(r.content)
                if not ext or ext == "svg":
                    return None
                # small rank bonus keeps structured-data / highly relevant images ahead on ties
                rank_bonus = 1.5 * (1 - candidates.index(u) / max(len(candidates), 1))
                return (cls._product_shot_score(r.content) + rank_bonus, u, ext, r.content)
            except Exception:
                return None

        results = [r for r in await asyncio.gather(*[grab(u) for u in candidates]) if r and r[0] > -5]
        if not results:
            logger.info(f"[{brand_id}] no usable image for {vehicle_id}; using placeholder")
            return PLACEHOLDER_IMAGE
        results.sort(key=lambda r: -r[0])
        # Vision-check the shortlist in batches of 8 (Hero pages carry ~100 untitled media_<hash> images).
        pick_row = None
        vision_ok = False
        for start in range(0, min(len(results), 24), 8):
            batch = results[start:start + 8]
            pick = await cls._vision_pick(vehicle_name or vehicle_id, [r[3] for r in batch])
            if pick is None:
                continue
            vision_ok = True
            if pick >= 0:
                pick_row = batch[pick]
                break
        if pick_row is None:
            if vision_ok:
                logger.info(f"[{brand_id}] vision found no clean photo of {vehicle_id}; using placeholder")
                return PLACEHOLDER_IMAGE
            pick_row = results[0]
        score, url, ext, content = pick_row
        dest = os.path.join(STATIC_UPLOAD_DIR, brand_id, "vehicles")
        os.makedirs(dest, exist_ok=True)
        for old in os.listdir(dest):
            if old.rsplit(".", 1)[0] == vehicle_id:
                os.remove(os.path.join(dest, old))
        with open(os.path.join(dest, f"{vehicle_id}.{ext}"), "wb") as f:
            f.write(content)
        logger.debug(f"[{brand_id}] {vehicle_id}: picked {url} (score {score:.1f} of {len(results)})")
        return f"/uploads/{brand_id}/vehicles/{vehicle_id}.{ext}"

    @classmethod
    async def _vision_pick(cls, vehicle_name: str, images: List[bytes]) -> Optional[int]:
        """Ask Gemini which candidate is a clean product photo of the vehicle. Returns index, -1 for none,
        or None if the call failed (caller falls back to heuristics)."""
        if len(images) == 1:
            return 0
        try:
            from io import BytesIO
            from PIL import Image
            from app.services.genai_client import get_genai_client

            parts: List[Any] = [
                f"Below are {len(images)} candidate images (numbered from 0) scraped from the official page of the "
                f"two-wheeler '{vehicle_name}'. Pick the ONE best image to use as its catalog hero photo: the whole "
                f"vehicle clearly visible, ideally a studio/side or 3/4 shot on a plain background; avoid ad banners with "
                f"big text, celebrity/people-dominated shots, close-ups of parts (dashboards, wheels), other models, "
                f"illustrations, and blank frames. Reply JSON {{\"best\": <index or -1 if none show this vehicle>}}."
            ]
            for i, data in enumerate(images):
                im = Image.open(BytesIO(data)).convert("RGBA")
                bg = Image.new("RGBA", im.size, "white"); bg.alpha_composite(im)
                im = bg.convert("RGB"); im.thumbnail((448, 448))
                buf = BytesIO(); im.save(buf, "JPEG", quality=80)
                parts += [f"Image {i}:", types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")]
            resp = await asyncio.to_thread(
                get_genai_client().models.generate_content,
                model=settings.REST_CHAT_MODEL,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0, max_output_tokens=64, response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            best = int(json.loads(resp.text).get("best", -1))
            return best if -1 <= best < len(images) else None
        except Exception as e:
            logger.warning(f"vision pick failed for {vehicle_name}: {type(e).__name__}: {e}")
            return None

    @classmethod
    async def _download_logo(cls, client: httpx.AsyncClient, brand_id: str, candidates: List[str]) -> str:
        dest = os.path.join(STATIC_UPLOAD_DIR, brand_id, "logos")
        for cand in list(dict.fromkeys(candidates))[:8]:
            fname = await cls._download(client, cand, dest, "logo", 400)
            if fname:
                return f"/uploads/{brand_id}/logos/{fname}"
        return ""

    # ------------------------------------------------------- fallbacks & meta
    @classmethod
    async def _infer_brand_meta(cls, brand_name: str, urls: List[str]) -> Dict[str, Any]:
        data = await cls._gemini_json(
            f"""Return JSON for the two-wheeler brand "{brand_name}" (sources: {urls}):
{{"name": "official display name", "tagline": "real brand tagline if known", "primary_color": "#hex brand colour",
"secondary_color": "#0f172a", "accent_color": "#hex", "home_url": "{urls[0] if urls else ''}"}}""",
            max_tokens=512,
        )
        return data or {"name": brand_name, "tagline": f"Official {brand_name} Experience", "primary_color": "#0ea5e9"}

    @classmethod
    async def _synthesise_catalog(cls, brand_name: str, source_urls: List[str]) -> BrandCatalog:
        """Knowledge-only catalog for JS-only sites or fictional brands (no crawlable pages)."""
        brand_id = cls._slug(brand_name)
        data = await cls._gemini_json(
            f"""Build a two-wheeler catalog JSON for "{brand_name}" in the Indian market.
If it is a real brand, list its REAL current models with real specs and Indian ex-showroom prices (append " (approx.)" to prices).
If it is fictional, create 5 realistic contemporary Indian two-wheelers (a 110cc commuter, a 125cc commuter, a 160cc sporty motorcycle,
a 125cc scooter and an electric scooter) — normal production vehicles, priced ₹70,000 - ₹1,80,000.
Categories must be from {json.dumps(TWO_WHEELER_CATEGORIES)}.
{{"name": "", "tagline": "", "primary_color": "#hex", "accent_color": "#hex",
"vehicles": [{{"name": "", "tagline": "", "category": "", "price_range": "", "engine_specs": "", "fuel_or_battery": "",
"range_or_mileage": "", "displacement_cc": "", "max_power": "", "max_torque": "", "kerb_weight": "", "seat_height": "",
"fuel_tank_or_battery": "", "top_speed": "", "braking": "", "riding_modes": [], "colors": [], "key_highlights": [],
"usp": "", "competitors": [], "variants": [{{"name": "", "price_ex_showroom": "", "engine_or_battery": "", "transmission": "", "key_features": []}}],
"data_completeness": "knowledge"}}]}}""",
            max_tokens=8192,
        ) or {}
        vehicles = [
            cls._to_vehicle_item(brand_id, brand_name, v, {"url": (source_urls or [""])[0], "title": v.get("name", "")})
            for v in data.get("vehicles", []) if isinstance(v, dict)
        ]
        primary = data.get("primary_color") or "#0ea5e9"
        return BrandCatalog(
            id=brand_id,
            name=data.get("name") or brand_name,
            tagline=data.get("tagline") or f"Official {brand_name} Experience",
            logo_url=cls._generate_brand_vector_logo(brand_id, brand_name, primary),
            primary_color=primary,
            secondary_color="#0f172a",
            accent_color=data.get("accent_color") or "#38bdf8",
            avatar_name=settings.AVATAR_NAME,
            avatar_voice=settings.AVATAR_VOICE,
            source_urls=source_urls,
            is_active=True,
            vehicles=vehicles,
            dealerships=cls._default_dealerships(brand_id, data.get("name") or brand_name),
        )

    @staticmethod
    def _default_dealerships(brand_id: str, brand_name: str) -> List[DealershipItem]:
        """Placeholder showroom entries for the brand JSON; bookable dealerships live in the DB."""
        cities = [("Mumbai", "Andheri West"), ("Bengaluru", "Indiranagar"), ("Delhi", "Karol Bagh"), ("Chennai", "Anna Nagar")]
        return [
            DealershipItem(
                id=f"{brand_id}_{city.lower()}",
                name=f"{brand_name} Authorised Dealer - {area}",
                address=f"{area}, {city}",
                city=city,
                phone="",
                rating=4.6,
                available_advisors=["Sales Consultant", "Product Specialist"],
                has_test_drive_home_pickup=True,
            )
            for city, area in cities
        ]

    @staticmethod
    def _slug(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_") or hashlib.md5((text or "x").encode()).hexdigest()[:8]

    @classmethod
    def _generate_brand_vector_logo(cls, brand_id: str, brand_name: str, primary_color: str) -> str:
        """Simple SVG wordmark for brands whose logo could not be downloaded."""
        dest_dir = os.path.join(STATIC_UPLOAD_DIR, brand_id.lower(), "logos")
        os.makedirs(dest_dir, exist_ok=True)
        color = primary_color if (primary_color or "").startswith("#") else "#0ea5e9"
        words = [w for w in (brand_name or "").split() if w]
        initials = "".join(w[0].upper() for w in words[:2]) or "2W"
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 54" width="220" height="54">
  <circle cx="27" cy="27" r="20" fill="{color}"/>
  <text x="27" y="32" fill="#fff" font-family="system-ui,sans-serif" font-weight="900" font-size="14" text-anchor="middle">{initials}</text>
  <text x="56" y="31" fill="#0f172a" font-family="system-ui,sans-serif" font-weight="900" font-size="15" letter-spacing="1.2">{(brand_name or '').upper()[:16]}</text>
</svg>'''
        try:
            with open(os.path.join(dest_dir, "logo.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
            return f"/uploads/{brand_id.lower()}/logos/logo.svg"
        except Exception as e:
            logger.warning(f"Failed to write SVG logo: {e}")
            return ""
