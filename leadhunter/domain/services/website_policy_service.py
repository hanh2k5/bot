"""Website Policy Domain Service — Classifies domain websites vs directory/social links."""

from __future__ import annotations

from typing import Final

_ALLOWED_DIRECTORY_AND_SOCIAL_LINKS: Final[list[str]] = [
    # Social networks & E-commerce marketplaces
    "google.com", "facebook.com", "zalo.me", "tiktok.com", "youtube.com",
    "shopee.vn", "lazada.vn", "chotot.com", "instagram.com", "gg.gg", "blogspot.com",
    "kiotvietweb.vn",
    # Tax / Company directory directories
    "hosocongty.vn", "hosocongty.com", "masothue.com", "masothue.vn",
    "trangvangvietnam.com", "bizz.vn", "hosodoanhnghiep.vn", "fact-link.com",
    "thongtindoanhnghiep.co", "bizs.vn",
    # Food delivery & Aggregators
    "foody.vn", "shopeefood.vn", "now.vn", "diadiemanuong.com",
    "easysalon.vn", "pasgo.vn", "riviu.vn", "loship.vn",
]


def is_professional_website(raw: dict | str) -> bool:
    """Return True if raw lead contains a professional domain website (e.g. abc.com, xyz.vn).

    Returns False if URL is empty or belongs to directory/social networks (Facebook, Zalo, Shopee...).
    """
    if isinstance(raw, dict):
        web = raw.get("website")
    else:
        web = raw

    if not web or not isinstance(web, str):
        return False

    url = web.strip().lower()
    if not url:
        return False

    for domain in _ALLOWED_DIRECTORY_AND_SOCIAL_LINKS:
        if domain in url:
            return False

    return True
