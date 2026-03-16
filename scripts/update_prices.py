#!/usr/bin/env python3
"""
update_prices.py
Vérifie quotidiennement :
  1. Les prix des robots tondeuses (Amazon, sites officiels)
  2. La validité des liens d'achat → bascule automatiquement sur un revendeur alternatif
Exécuté via GitHub Actions chaque jour à 06h00 UTC.
"""

import re
import time
import json
import sys
import logging
from datetime import datetime
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Dépendances manquantes. Exécuter : pip install requests beautifulsoup4 lxml")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ─── Headers réalistes pour éviter le blocage ────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}

MIN_PRICE = 300    # Prix minimum raisonnable (€)
MAX_PRICE = 6000   # Prix maximum raisonnable (€)
DELAY = 3          # Secondes entre chaque requête (politesse)

# ─── Configuration par robot ──────────────────────────────────────────────────
# sources   : utilisées pour scraper le prix (ordre de priorité)
# buy_links : liens d'achat vérifiés quotidiennement (ordre de priorité)
#             → le premier lien valide (HTTP < 400) est mis dans fiche.html
ROBOTS = {
    "navimow": {
        "name": "Segway Navimow i105E",
        "sources": [
            {"url": "https://navimow.segway.com/fr-fr/products/navimow-i105e", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0CXDNFZLL", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/i105E-p%C3%A9riph%C3%A9rique-Recommand%C3%A9-cartographie-Automatique/dp/B0CXDNFZLL",
            "https://navimow.segway.com/fr-fr/products/navimow-i105e",
            "https://www.boulanger.com/recherche/navimow+i105e",
            "https://www.darty.com/nav/extra/recherche/navimow+i105e.html",
        ],
    },
    "ecovacs": {
        "name": "Ecovacs Goat O800 RTK",
        "sources": [
            {"url": "https://www.ecovacs.com/fr/goat-robotic-lawn-mower/goat-o800-rtk", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0DQ8KYLYR", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/ECOVACS-O800-RTK-p%C3%A9riph%C3%A9rique-Cartographie/dp/B0DQ8KYLYR",
            "https://www.ecovacs.com/fr/goat-robotic-lawn-mower/goat-o800-rtk",
            "https://www.boulanger.com/recherche/ecovacs+goat+o800",
            "https://www.darty.com/nav/extra/recherche/ecovacs+goat+o800.html",
        ],
    },
    "dreame": {
        "name": "Dreame A1 Pro",
        "sources": [
            {"url": "https://fr.dreametech.com/products/robot-tondeuse-dreame-a1-pro", "method": "shopify"},
            {"url": "https://www.amazon.fr/dp/B0DR35G7P3", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/robotis%C3%A9e-Intelligente-p%C3%A9rim%C3%A9trique-OmniSense-Intelligent/dp/B0DR35G7P3",
            "https://fr.dreametech.com/products/robot-tondeuse-dreame-a1-pro",
            "https://www.boulanger.com/recherche/dreame+a1+pro+tondeuse",
            "https://www.leroymerlin.fr/recherche?q=dreame+a1+pro",
        ],
    },
    "worx": {
        "name": "Worx Landroid Vision WR208E",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0CTTWLLZZ", "method": "amazon"},
            {"url": "https://eu.worx.com/fr/products/wr208e", "method": "json_ld"},
        ],
        "buy_links": [
            "https://www.amazon.fr/WORX-p%C3%A9riph%C3%A9rique-Evitement-dobstacles-Contr%C3%B4lable/dp/B0CTTWLLZZ",
            "https://eu.worx.com/fr/products/wr208e",
            "https://www.leroymerlin.fr/recherche?q=worx+landroid+vision",
            "https://www.boulanger.com/recherche/worx+landroid+vision",
        ],
    },
    "yuka": {
        "name": "Mammotion Yuka Mini Vision",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0FKTBKDQ1", "method": "amazon"},
            {"url": "https://eu.mammotion.com/fr/products/yuka-mini-vision", "method": "shopify"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B0FKTBKDQ1",
            "https://eu.mammotion.com/fr/products/yuka-mini-vision",
            "https://www.boulanger.com/recherche/mammotion+yuka",
            "https://www.darty.com/nav/extra/recherche/mammotion+yuka.html",
        ],
    },
    "luba2": {
        "name": "Mammotion LUBA 2 AWD 3000X",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0DT46VJPG", "method": "amazon"},
            {"url": "https://eu.mammotion.com/fr/products/luba-2-awd-3000x", "method": "shopify"},
        ],
        "buy_links": [
            "https://www.amazon.fr/MAMMOTION-LUBA-AWD-P%C3%A9riph%C3%A9rique-Recommand%C3%A9/dp/B0DT46VJPG",
            "https://eu.mammotion.com/fr/products/luba-2-awd-3000x",
            "https://www.boulanger.com/recherche/mammotion+luba+2+3000",
            "https://www.darty.com/nav/extra/recherche/mammotion+luba+2.html",
        ],
    },
    "husqvarna": {
        "name": "Husqvarna Automower 320 NERA",
        "sources": [
            {"url": "https://www.husqvarna.com/fr/robots-tondeuses/automower-320nera/", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0CF5Q64QS", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/Husqvarna-Automower-320-Nera/dp/B0CF5Q64QS",
            "https://www.husqvarna.com/fr/robots-tondeuses/automower-320nera/",
            "https://www.leroymerlin.fr/recherche?q=husqvarna+automower+320",
            "https://www.boulanger.com/recherche/husqvarna+automower+320",
            "https://www.darty.com/nav/extra/recherche/husqvarna+automower+320.html",
        ],
    },
    "mova": {
        "name": "MOVA LiDAX Ultra 1200",
        "sources": [
            {"url": "https://fr.mova.tech/products/robot-tondeuse-lidax-ultra", "method": "shopify"},
            {"url": "https://www.amazon.fr/dp/B0GD23KKHC", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B0GD23KKHC",
            "https://fr.mova.tech/products/robot-tondeuse-lidax-ultra",
            "https://www.boulanger.com/recherche/mova+lidax",
            "https://www.darty.com/nav/extra/recherche/mova+lidax.html",
        ],
    },
    "a3pro": {
        "name": "Dreame A3 AWD Pro 3500",
        "sources": [
            {"url": "https://fr.dreametech.com/products/dreame-robot-tondeuse-a3-awd-pro-3500", "method": "shopify"},
        ],
        "buy_links": [
            "https://fr.dreametech.com/products/dreame-robot-tondeuse-a3-awd-pro-3500",
            "https://www.boulanger.com/recherche/dreame+a3+awd+pro",
            "https://www.leroymerlin.fr/recherche?q=dreame+a3+pro+tondeuse",
        ],
    },
    "luba3": {
        "name": "Mammotion LUBA 3 AWD 3000",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0GCZSSZRZ", "method": "amazon"},
            {"url": "https://eu.mammotion.com/fr/products/luba-3-awd-3000", "method": "shopify"},
        ],
        "buy_links": [
            "https://www.amazon.fr/Mammotion-LUBA-AWD-3000-Positionnement/dp/B0GCZSSZRZ",
            "https://eu.mammotion.com/fr/products/luba-3-awd-3000",
            "https://www.boulanger.com/recherche/mammotion+luba+3",
            "https://www.darty.com/nav/extra/recherche/mammotion+luba+3.html",
        ],
    },
    "boschxs": {
        "name": "Bosch Indego XS 300",
        "sources": [{"url": "https://www.amazon.fr/dp/B085FCXY97", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B085FCXY97",
            "https://www.leroymerlin.fr/recherche?q=bosch+indego+xs+300",
            "https://www.boulanger.com/recherche/bosch+indego+xs+300",
            "https://www.darty.com/nav/extra/recherche/bosch+indego+xs+300.html",
        ],
    },
    "boschm700": {
        "name": "Bosch Indego M+ 700",
        "sources": [{"url": "https://www.amazon.fr/dp/B09FDMXHRL", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B09FDMXHRL",
            "https://www.leroymerlin.fr/recherche?q=bosch+indego+m+700",
            "https://www.boulanger.com/recherche/bosch+indego+m700",
            "https://www.darty.com/nav/extra/recherche/bosch+indego+m700.html",
        ],
    },
    "gardenaminimo": {
        "name": "Gardena Sileno Minimo 250",
        "sources": [{"url": "https://www.amazon.fr/dp/B07GBRZFV2", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B07GBRZFV2",
            "https://www.leroymerlin.fr/recherche?q=gardena+sileno+minimo+250",
            "https://www.boulanger.com/recherche/gardena+sileno+minimo",
            "https://www.darty.com/nav/extra/recherche/gardena+sileno+minimo.html",
        ],
    },
    "gardena750": {
        "name": "Gardena Sileno Life 750",
        "sources": [{"url": "https://www.amazon.fr/dp/B07GBQWPSD", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B07GBQWPSD",
            "https://www.leroymerlin.fr/recherche?q=gardena+sileno+life+750",
            "https://www.boulanger.com/recherche/gardena+sileno+life+750",
            "https://www.darty.com/nav/extra/recherche/gardena+sileno+life.html",
        ],
    },
    "husqvarna115h": {
        "name": "Husqvarna Automower 115H",
        "sources": [
            {"url": "https://www.husqvarna.com/fr/robots-tondeuses/automower-115h/", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B09FDMXHRL", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B09FDMXHRL",
            "https://www.husqvarna.com/fr/robots-tondeuses/automower-115h/",
            "https://www.leroymerlin.fr/recherche?q=husqvarna+automower+115h",
            "https://www.boulanger.com/recherche/husqvarna+automower+115h",
        ],
    },
    "navimow108": {
        "name": "Segway Navimow i108E",
        "sources": [{"url": "https://www.amazon.fr/dp/B0D3KWNDBY", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B0D3KWNDBY",
            "https://navimow.segway.com/fr-fr/products/navimow-i108e",
            "https://www.boulanger.com/recherche/navimow+i108e",
            "https://www.darty.com/nav/extra/recherche/navimow+i108e.html",
        ],
    },
    "stiga1000": {
        "name": "Stiga A 1000",
        "sources": [{"url": "https://www.amazon.fr/dp/B0BT5W5NNS", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B0BT5W5NNS",
            "https://www.leroymerlin.fr/recherche?q=stiga+a+1000+tondeuse",
            "https://www.boulanger.com/recherche/stiga+a+1000",
            "https://www.darty.com/nav/extra/recherche/stiga+a+1000.html",
        ],
    },
    "kress": {
        "name": "Kress Mission 5 RTK",
        "sources": [{"url": "https://www.amazon.fr/dp/B0C1MKBJ5Y", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B0C1MKBJ5Y",
            "https://www.leroymerlin.fr/recherche?q=kress+mission+rtk+tondeuse",
            "https://www.boulanger.com/recherche/kress+mission+5+rtk",
            "https://www.darty.com/nav/extra/recherche/kress+mission+rtk.html",
        ],
    },
    "honda520": {
        "name": "Honda Miimo 520",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B07G1CC2SM", "method": "amazon"},
            {"url": "https://www.honda.fr/lawn-and-garden/products/miimo.html", "method": "json_ld"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B07G1CC2SM",
            "https://www.honda.fr/lawn-and-garden/products/miimo.html",
            "https://www.leroymerlin.fr/recherche?q=honda+miimo+520",
            "https://www.boulanger.com/recherche/honda+miimo+520",
            "https://www.darty.com/nav/extra/recherche/honda+miimo+520.html",
        ],
    },
    "stihl422": {
        "name": "Stihl iMow RMI 422 PC",
        "sources": [{"url": "https://www.amazon.fr/dp/B0B3VLJHQ4", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B0B3VLJHQ4",
            "https://www.stihl.fr/tondeuses-et-robots-tondeuses/robots-tondeuses/robot-tondeuse-imow-rmi-422-pc.html",
            "https://www.leroymerlin.fr/recherche?q=stihl+imow+422",
            "https://www.boulanger.com/recherche/stihl+imow+422",
        ],
    },
    "ecovacsG1": {
        "name": "Ecovacs GOAT G1",
        "sources": [{"url": "https://www.amazon.fr/dp/B0CL7NX96J", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B0CL7NX96J",
            "https://www.ecovacs.com/fr/goat-robotic-lawn-mower/goat-g1",
            "https://www.boulanger.com/recherche/ecovacs+goat+g1",
            "https://www.darty.com/nav/extra/recherche/ecovacs+goat+g1.html",
        ],
    },
    "robomow635": {
        "name": "Robomow RS635 Pro",
        "sources": [{"url": "https://www.amazon.fr/dp/B09MHQKYRR", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B09MHQKYRR",
            "https://www.leroymerlin.fr/recherche?q=robomow+rs635",
            "https://www.boulanger.com/recherche/robomow+rs635",
            "https://www.darty.com/nav/extra/recherche/robomow+rs635.html",
        ],
    },
    "stiga3000": {
        "name": "Stiga A 3000",
        "sources": [{"url": "https://www.amazon.fr/dp/B0BT5KGXNJ", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B0BT5KGXNJ",
            "https://www.leroymerlin.fr/recherche?q=stiga+a+3000+tondeuse",
            "https://www.boulanger.com/recherche/stiga+a+3000",
            "https://www.darty.com/nav/extra/recherche/stiga+a+3000.html",
        ],
    },
    "vikingmi632": {
        "name": "Viking iMow MI 632 PC",
        "sources": [{"url": "https://www.amazon.fr/dp/B09BNYTCC9", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B09BNYTCC9",
            "https://www.leroymerlin.fr/recherche?q=viking+imow+mi+632",
            "https://www.boulanger.com/recherche/viking+imow+632",
            "https://www.darty.com/nav/extra/recherche/viking+imow+632.html",
        ],
    },
    "ecoflowblade": {
        "name": "EcoFlow Blade",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0B1C5J36N", "method": "amazon"},
            {"url": "https://www.ecoflow.com/fr/blade", "method": "json_ld"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B0B1C5J36N",
            "https://www.ecoflow.com/fr/blade",
            "https://www.boulanger.com/recherche/ecoflow+blade",
            "https://www.darty.com/nav/extra/recherche/ecoflow+blade.html",
        ],
    },
    "husqvarna430x": {
        "name": "Husqvarna Automower 430X",
        "sources": [
            {"url": "https://www.husqvarna.com/fr/robots-tondeuses/automower-430x/", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0CF5NP8SR", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B0CF5NP8SR",
            "https://www.husqvarna.com/fr/robots-tondeuses/automower-430x/",
            "https://www.leroymerlin.fr/recherche?q=husqvarna+automower+430x",
            "https://www.boulanger.com/recherche/husqvarna+automower+430",
        ],
    },
    "ambrogio": {
        "name": "Ambrogio L15 Elite",
        "sources": [{"url": "https://www.amazon.fr/dp/B07YZ1KQP6", "method": "amazon"}],
        "buy_links": [
            "https://www.amazon.fr/dp/B07YZ1KQP6",
            "https://www.leroymerlin.fr/recherche?q=ambrogio+l15",
            "https://www.boulanger.com/recherche/ambrogio+l15",
            "https://www.darty.com/nav/extra/recherche/ambrogio+l15.html",
        ],
    },
    "luba2_1000": {
        "name": "Mammotion LUBA 2 AWD 1000",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0DT46TJDP", "method": "amazon"},
            {"url": "https://eu.mammotion.com/fr/products/luba-2-awd-1000", "method": "shopify"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B0DT46TJDP",
            "https://eu.mammotion.com/fr/products/luba-2-awd-1000",
            "https://www.boulanger.com/recherche/mammotion+luba+2+1000",
            "https://www.darty.com/nav/extra/recherche/mammotion+luba+2.html",
        ],
    },
    "husqvarna450": {
        "name": "Husqvarna Automower 450X NERA",
        "sources": [
            {"url": "https://www.husqvarna.com/fr/robots-tondeuses/automower-450x-nera/", "method": "json_ld"},
        ],
        "buy_links": [
            "https://www.husqvarna.com/fr/robots-tondeuses/automower-450x-nera/",
            "https://www.leroymerlin.fr/recherche?q=husqvarna+automower+450x",
            "https://www.boulanger.com/recherche/husqvarna+automower+450",
        ],
    },
    "husqvarna435": {
        "name": "Husqvarna Automower 435X AWD",
        "sources": [
            {"url": "https://www.husqvarna.com/fr/robots-tondeuses/automower-435x-awd/", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0CF5QSDYB", "method": "amazon"},
        ],
        "buy_links": [
            "https://www.amazon.fr/dp/B0CF5QSDYB",
            "https://www.husqvarna.com/fr/robots-tondeuses/automower-435x-awd/",
            "https://www.leroymerlin.fr/recherche?q=husqvarna+automower+435x+awd",
            "https://www.boulanger.com/recherche/husqvarna+automower+435",
        ],
    },
}

# ─── Parsing des prix ─────────────────────────────────────────────────────────

def parse_price(raw: str) -> Optional[int]:
    """Convertit une chaîne de prix en entier. Ex: '949,00 €' → 949, '2 599' → 2599."""
    if not raw:
        return None
    cleaned = str(raw).strip().replace("\xa0", " ").replace("\u202f", " ")
    cleaned = re.sub(r"[€$£]", "", cleaned)
    m = re.match(r"^[\s]*([\d\s]+)[,.](\d{2})[\s]*$", cleaned.strip())
    if m:
        integer_part = re.sub(r"\s", "", m.group(1))
        val = int(integer_part) if integer_part.isdigit() else None
    else:
        cleaned_digits = re.sub(r"\s", "", cleaned)
        m2 = re.search(r"(\d{3,5})", cleaned_digits)
        val = int(m2.group(1)) if m2 else None

    if val and MIN_PRICE <= val <= MAX_PRICE:
        return val
    return None


def extract_json_ld(soup: BeautifulSoup) -> Optional[int]:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if "@graph" in item:
                    items.extend(item["@graph"])
                if item.get("@type") in ("Product",):
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0]
                    price = offers.get("price") or offers.get("lowPrice")
                    if price:
                        p = parse_price(str(price))
                        if p:
                            return p
                if item.get("@type") in ("Offer", "AggregateOffer"):
                    price = item.get("price") or item.get("lowPrice")
                    if price:
                        p = parse_price(str(price))
                        if p:
                            return p
        except Exception:
            continue
    return None


def extract_shopify(soup: BeautifulSoup) -> Optional[int]:
    price = extract_json_ld(soup)
    if price:
        return price
    tag = soup.find("meta", {"property": "product:price:amount"}) or \
          soup.find("meta", {"property": "og:price:amount"})
    if tag and tag.get("content"):
        return parse_price(tag["content"])
    for script in soup.find_all("script"):
        text = script.string or ""
        m = re.search(r'"price"\s*:\s*(\d+)', text)
        if m:
            raw = int(m.group(1))
            if raw > MAX_PRICE:
                raw = raw // 100
            p = parse_price(str(raw))
            if p:
                return p
    return None


def extract_amazon(soup: BeautifulSoup) -> Optional[int]:
    selectors = [
        "span.a-price.aok-align-center span.a-offscreen",
        ".a-price .a-offscreen",
        "#corePrice_feature_div .a-price-whole",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".apexPriceToPay .a-offscreen",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            p = parse_price(el.get_text())
            if p:
                return p
    return extract_json_ld(soup)


# ─── Session HTTP ─────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        log.warning(f"    Échec fetch {url[:60]}... : {e}")
        return None


def fetch_price(robot_id: str, config: dict) -> Optional[int]:
    """Essaie les sources Amazon uniquement pour un robot et retourne le premier prix valide."""
    amazon_sources = [s for s in config["sources"] if s["method"] == "amazon"]
    for source in amazon_sources:
        url = source["url"]
        method = source["method"]
        log.info(f"  [{robot_id}] {method} → {url[:65]}...")

        soup = fetch_page(url)
        if not soup:
            time.sleep(DELAY)
            continue

        extractors = {
            "json_ld": extract_json_ld,
            "shopify": extract_shopify,
            "amazon": extract_amazon,
            "meta": lambda s: parse_price(
                (s.find("meta", {"property": "product:price:amount"}) or {}).get("content", "")
            ),
        }
        price = extractors.get(method, extract_json_ld)(soup)

        if price:
            log.info(f"  [{robot_id}] ✓ Prix trouvé : {price} €")
            return price
        else:
            log.warning(f"  [{robot_id}] Aucun prix extrait depuis {method}")

        time.sleep(DELAY)

    return None


# ─── Lecture / mise à jour des prix dans les fichiers HTML ───────────────────

def get_current_price(content: str, robot_id: str) -> Optional[int]:
    m = re.search(
        rf"id:'{re.escape(robot_id)}'[^\n]*?price:'([\d\s]+) €'",
        content
    )
    if m:
        return int(m.group(1).replace(" ", ""))

    m = re.search(
        rf"(?s){re.escape(robot_id)}:\s*\{{[^{{}}]{{0,500}}?price:\s*'([\d\s]+) €'",
        content
    )
    if m:
        return int(m.group(1).replace(" ", ""))

    return None


def fmt(price: int) -> str:
    """Formate un entier en prix français : 2599 → '2 599'"""
    return f"{price:,}".replace(",", "\u202f")


def update_price_in_file(content: str, robot_id: str, old_price: int, new_price: int) -> str:
    old_str = fmt(old_price)
    new_str = fmt(new_price)

    content = re.sub(
        rf"((?:id:'{re.escape(robot_id)}'[^\n]*?|{re.escape(robot_id)}:\s*\{{[^{{}}]{{0,500}}?)price:\s*')([\d\s\u202f]+) €'",
        lambda m: m.group(0).replace(f"{old_str} €", f"{new_str} €").replace(
            f"{old_price} €", f"{new_price} €"
        ),
        content,
        flags=re.DOTALL,
    )

    for pattern in [
        rf"(id:'{re.escape(robot_id)}'[^\n]{{0,400}}?price:')({re.escape(old_str)} €|{old_price} €)(')",
        rf"({re.escape(robot_id)}:\s*\{{[^{{}}]{{0,500}}?price:\s*')({re.escape(old_str)} €|{old_price} €)(')",
    ]:
        content = re.sub(pattern, rf"\g<1>{new_str} €\g<3>", content, flags=re.DOTALL)

    content = re.sub(
        rf"(id:'{re.escape(robot_id)}'[^\n]{{0,400}}?priceN:){old_price}\b",
        rf"\g<1>{new_price}",
        content,
    )

    lines = content.split("\n")
    robot_name = ROBOTS[robot_id]["name"]
    for i, line in enumerate(lines):
        if robot_name in line and f"{old_str} €" in line:
            lines[i] = line.replace(f"{old_str} €", f"{new_str} €")
        elif robot_name in line and f"{old_price} €" in line:
            lines[i] = line.replace(f"{old_price} €", f"{new_price} €")
    content = "\n".join(lines)

    return content


# ─── Vérification et mise à jour des liens d'achat ───────────────────────────

def check_link(url: str) -> bool:
    """Retourne True si l'URL est accessible (code HTTP < 400)."""
    try:
        resp = session.head(url, timeout=10, allow_redirects=True)
        if resp.status_code < 400:
            return True
        # HEAD bloqué par certains sites → réessayer avec GET partiel
        resp = session.get(url, timeout=10, allow_redirects=True, stream=True)
        resp.close()
        return resp.status_code < 400
    except Exception:
        return False


def find_best_buy_link(robot_id: str, config: dict) -> Optional[str]:
    """
    Teste les buy_links Amazon uniquement et retourne le premier lien valide.
    Si aucun lien Amazon n'est accessible, retourne None.
    """
    amazon_links = [u for u in config.get("buy_links", []) if "amazon.fr" in u]
    for url in amazon_links:
        log.info(f"  [{robot_id}] 🔗 Test lien → {url[:65]}...")
        if check_link(url):
            log.info(f"  [{robot_id}] ✓ Lien valide")
            return url
        else:
            log.warning(f"  [{robot_id}] ✗ Lien mort ou inaccessible")
        time.sleep(1)
    return None


def _find_robot_amazon_span(content: str, robot_id: str):
    """
    Localise le champ 'amazon:' d'un robot dans fiche.html.
    Retourne (start_of_value, end_of_value, current_value) ou None.
    On cherche le robot_id dans le contenu, puis on scanne vers l'avant
    pour trouver 'amazon:' — sans se limiter aux accolades.
    """
    # Trouver l'identifiant du robot (ex: "  navimow: {")
    m = re.search(rf"(?m)^\s*{re.escape(robot_id)}:\s*\{{", content)
    if not m:
        return None
    # Chercher 'amazon:' dans les 6000 premiers caractères après le début du bloc
    segment_start = m.start()
    segment = content[segment_start: segment_start + 6000]

    # Trouver 'amazon: null' ou "amazon: 'url'"
    m2 = re.search(r"amazon:\s*(?:'([^']*)'|(null))", segment)
    if not m2:
        return None

    val = m2.group(1)  # None si c'est null, sinon la valeur entre guillemets
    abs_start = segment_start + m2.start()
    abs_end   = segment_start + m2.end()
    return abs_start, abs_end, val


def get_current_buy_link(content: str, robot_id: str) -> Optional[str]:
    """Lit le lien d'achat actuel pour un robot (amazon: 'url' ou null)."""
    result = _find_robot_amazon_span(content, robot_id)
    if result is None:
        return None
    _, _, val = result
    return val  # None si amazon: null, sinon l'URL


def update_buy_link_in_file(content: str, robot_id: str, new_link: str) -> str:
    """Met à jour amazon: pour un robot — gère 'url' et null."""
    result = _find_robot_amazon_span(content, robot_id)
    if result is None:
        return content
    start, end, _ = result
    old_text = content[start:end]
    # Remplacer par la nouvelle valeur
    new_text = re.sub(r"amazon:\s*(?:'[^']*'|null)", f"amazon: '{new_link}'", old_text, count=1)
    return content[:start] + new_text + content[end:]


def disable_buy_link_in_file(content: str, robot_id: str) -> str:
    """Désactive amazon: d'un robot (met null) quand tous les liens sont morts."""
    result = _find_robot_amazon_span(content, robot_id)
    if result is None:
        return content
    start, end, current_val = result
    if current_val is None:
        return content  # déjà null
    old_text = content[start:end]
    new_text = re.sub(r"amazon:\s*'[^']*'", "amazon: null", old_text, count=1)
    return content[:start] + new_text + content[end:]


# ─── Fichiers à mettre à jour ─────────────────────────────────────────────────

FILES = ["index.html", "fiche.html", "robots.html", "comparatif.html", "classement.html", "quiz.html"]
# fiche.html contient les champs amazon: → c'est lui qui stocke les liens d'achat
LINK_FILE = "fiche.html"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Lire les fichiers
    contents = {}
    for f in FILES:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                contents[f] = fh.read()
        except FileNotFoundError:
            log.error(f"Fichier introuvable : {f}. Le script doit s'exécuter à la racine du projet.")
            sys.exit(1)

    price_changes = []
    link_changes = []
    skipped = []

    for robot_id, config in ROBOTS.items():
        log.info(f"\n[{robot_id}] ── {config['name']} ──────────────────────────")

        # ── 1. Vérification du prix ──────────────────────────────────────────
        current_price = get_current_price(contents["index.html"], robot_id) or \
                        get_current_price(contents["fiche.html"], robot_id)

        if current_price is None:
            log.warning(f"  [{robot_id}] Impossible de lire le prix actuel.")
            skipped.append(robot_id)
        else:
            log.info(f"  [{robot_id}] Prix actuel : {current_price} €")
            fetched_price = fetch_price(robot_id, config)

            if fetched_price is None:
                log.warning(f"  [{robot_id}] Prix en ligne introuvable — inchangé.")
                skipped.append(robot_id)
            elif abs(fetched_price - current_price) <= 1:
                log.info(f"  [{robot_id}] ✅ Prix inchangé : {current_price} €")
            else:
                diff = fetched_price - current_price
                sign = "+" if diff > 0 else ""
                log.info(f"  [{robot_id}] 💰 {current_price} € → {fetched_price} € ({sign}{diff} €)")
                price_changes.append({
                    "id": robot_id, "name": config["name"],
                    "old": current_price, "new": fetched_price, "diff": diff,
                })
                for fname in FILES:
                    contents[fname] = update_price_in_file(
                        contents[fname], robot_id, current_price, fetched_price
                    )

        # ── 2. Vérification du lien d'achat ─────────────────────────────────
        if not config.get("buy_links"):
            log.info(f"  [{robot_id}] Pas de buy_links configurés — ignoré.")
            continue

        current_link = get_current_buy_link(contents[LINK_FILE], robot_id)

        # Vérifier d'abord si le lien actuel est toujours valide
        if current_link and check_link(current_link):
            log.info(f"  [{robot_id}] ✅ Lien actuel valide : {current_link[:60]}...")
            time.sleep(1)
            continue

        if current_link:
            log.warning(f"  [{robot_id}] ⚠️  Lien actuel mort : {current_link[:60]}...")
        else:
            log.info(f"  [{robot_id}] Aucun lien actuel — recherche du meilleur lien...")

        # Chercher le meilleur lien fonctionnel parmi les alternatives
        best_link = find_best_buy_link(robot_id, config)

        if best_link and best_link != current_link:
            log.info(f"  [{robot_id}] 🔄 Nouveau lien : {best_link[:60]}...")
            link_changes.append({
                "id": robot_id, "name": config["name"],
                "old": current_link or "null", "new": best_link,
            })
            contents[LINK_FILE] = update_buy_link_in_file(
                contents[LINK_FILE], robot_id, best_link
            )
        elif not best_link:
            if current_link:
                log.warning(f"  [{robot_id}] ❌ Tous les liens morts — bouton désactivé.")
                link_changes.append({
                    "id": robot_id, "name": config["name"],
                    "old": current_link, "new": "null (désactivé)",
                })
                contents[LINK_FILE] = disable_buy_link_in_file(contents[LINK_FILE], robot_id)
            else:
                log.warning(f"  [{robot_id}] ❌ Aucun lien fonctionnel trouvé — bouton déjà désactivé.")

    # ── Résumé et écriture ────────────────────────────────────────────────────
    log.info("\n" + "═" * 60)
    has_changes = bool(price_changes or link_changes)

    if not has_changes:
        log.info("✅ Aucun changement (prix ni liens) — fichiers non modifiés.")
    else:
        for fname in FILES:
            with open(fname, "w", encoding="utf-8") as fh:
                fh.write(contents[fname])
            log.info(f"📝 {fname} mis à jour")

        today = datetime.now().strftime("%Y-%m-%d")

        if price_changes:
            log.info(f"\n💰 {len(price_changes)} prix mis à jour :")
            with open("PRICE_HISTORY.md", "a", encoding="utf-8") as fh:
                fh.write(f"\n## {today} — Prix\n")
                for c in price_changes:
                    sign = "+" if c["diff"] > 0 else ""
                    msg = f"- **{c['name']}** : {c['old']} € → {c['new']} € ({sign}{c['diff']} €)"
                    log.info(f"  {msg}")
                    fh.write(msg + "\n")

        if link_changes:
            log.info(f"\n🔗 {len(link_changes)} liens mis à jour :")
            with open("LINKS_HISTORY.md", "a", encoding="utf-8") as fh:
                fh.write(f"\n## {today} — Liens\n")
                for c in link_changes:
                    msg = f"- **{c['name']}** : `{c['old'][:60]}` → `{c['new'][:60]}`"
                    log.info(f"  {c['name']}: {c['old'][:50]} → {c['new'][:50]}")
                    fh.write(msg + "\n")

    if skipped:
        log.info(f"\n⚠️  Ignorés (échec fetch/parsing) : {', '.join(skipped)}")

    log.info("═" * 60)


if __name__ == "__main__":
    main()
