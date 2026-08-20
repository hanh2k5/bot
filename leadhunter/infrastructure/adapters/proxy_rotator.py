"""Proxy Rotator — fetches and rotates free public proxies (ENV-005)."""

import logging
import requests
import random

logger = logging.getLogger(__name__)


def get_free_proxy() -> dict[str, str] | None:
    """Fetch a free proxy from public lists and format for Playwright."""
    url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=anonymous"
    try:
        res = requests.get(url, timeout=5.0)
        res.raise_for_status()
        proxies = [p.strip() for p in res.text.split("\n") if p.strip()]
        if not proxies:
            return None

        # Pick 5 random proxies to try
        candidates = random.sample(proxies, min(len(proxies), 5))
        for proxy_str in candidates:
            # Playwright format: http://ip:port
            proxy_url = f"http://{proxy_str}"
            # Verify if proxy actually works
            try:
                test_res = requests.get(
                    "https://www.google.com",
                    proxies={"http": proxy_url, "https": proxy_url},
                    timeout=2.0,
                )
                if test_res.status_code == 200:
                    logger.info(f"Using working free proxy: {proxy_url}")
                    return {"server": proxy_url}
            except Exception:
                continue
    except Exception as exc:
        logger.warning(f"Failed to fetch free proxies: {exc}")

    return None
