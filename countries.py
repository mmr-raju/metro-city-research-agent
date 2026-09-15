"""Exact ISO names/codes and explicit aliases; never fuzzy-match a different country."""
import re
import unicodedata

import pycountry

from errors import CountryAmbiguityError, CountryValidationError


def _key(value: str) -> str:
    return re.sub(r"[.\s]+", " ", unicodedata.normalize("NFKC", value).strip()).strip().casefold()


ALIASES = {
    "uk": "GB", "u k": "GB", "great britain": "GB", "britain": "GB",
    "usa": "US", "u s a": "US", "u s": "US", "united states of america": "US",
    "south korea": "KR", "north korea": "KP", "russia": "RU", "vietnam": "VN",
    "bolivia": "BO", "iran": "IR", "tanzania": "TZ", "venezuela": "VE",
    "laos": "LA", "syria": "SY", "turkey": "TR", "türkiye": "TR",
    "czech republic": "CZ", "ivory coast": "CI", "cape verde": "CV",
    "swaziland": "SZ", "burma": "MM", "drc": "CD", "dr congo": "CD",
    "democratic republic of the congo": "CD", "republic of the congo": "CG",
}
AMBIGUOUS = {
    "congo": "Specify Republic of the Congo or Democratic Republic of the Congo.",
    "korea": "Specify South Korea or North Korea.",
    "guinea": None,  # Guinea itself is an exact country name.
    "virgin islands": "Specify British Virgin Islands or U.S. Virgin Islands.",
}


def normalize_country(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CountryValidationError("Enter a country name, for example Japan or Brazil.")
    if len(value) > 100 or any(ord(c) < 32 for c in value):
        raise CountryValidationError("Enter a short country name or ISO country code.")
    key = _key(value)
    if AMBIGUOUS.get(key):
        raise CountryAmbiguityError(AMBIGUOUS[key])
    if key in ALIASES:
        return pycountry.countries.get(alpha_2=ALIASES[key]).name
    matches = {
        c.alpha_2: c for c in pycountry.countries
        if key in {_key(getattr(c, attr, "")) for attr in
                   ("name", "official_name", "common_name", "alpha_2", "alpha_3")}
    }
    if len(matches) == 1:
        return next(iter(matches.values())).name
    raise CountryValidationError("Country not recognized. Use its full official name or ISO code; no country was substituted.")
