#!/usr/bin/env python3
"""
update_prices.py
Vérifie les prix actuels des robots tondeuses et met à jour index.html + fiche.html.
Exécuté quotidiennement via GitHub Actions.
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

# ─── Configuration des sources par robot ─────────────────────────────────────
# Ordre des sources : le script essaie la première, puis la suivante si échec.
# "method" peut être : "json_ld", "amazon", "shopify", "meta"
ROBOTS = {
    "navimow": {
        "name": "Segway Navimow i105E",
        "sources": [
            {"url": "https://navimow.segway.com/fr-fr/products/navimow-i105e", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0CXDNFZLL", "method": "amazon"},
        ],
    },
    "ecovacs": {
        "name": "Ecovacs Goat O800 RTK",
        "sources": [
            {"url": "https://www.ecovacs.com/fr/goat-robotic-lawn-mower/goat-o800-rtk", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0DQ8KYLYR", "method": "amazon"},
        ],
    },
    "dreame": {
        "name": "Dreame A1 Pro",
        "sources": [
            {"url": "https://fr.dreametech.com/products/robot-tondeuse-dreame-a1-pro", "method": "shopify"},
            {"url": "https://www.amazon.fr/dp/B0DR35G7P3", "method": "amazon"},
        ],
    },
    "worx": {
        "name": "Worx Landroid Vision WR208E",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0CTTWLLZZ", "method": "amazon"},
            {"url": "https://eu.worx.com/fr/products/wr208e", "method": "json_ld"},
        ],
    },
    "yuka": {
        "name": "Mammotion Yuka Mini Vision",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0FKTBKDQ1", "method": "amazon"},
            {"url": "https://eu.mammotion.com/fr/products/yuka-mini-vision", "method": "shopify"},
        ],
    },
    "luba2": {
        "name": "Mammotion LUBA 2 AWD 3000X",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0DT46VJPG", "method": "amazon"},
            {"url": "https://eu.mammotion.com/fr/products/luba-2-awd-3000x", "method": "shopify"},
        ],
    },
    "husqvarna": {
        "name": "Husqvarna Automower 320 NERA",
        "sources": [
            {"url": "https://www.husqvarna.com/fr/robots-tondeuses/automower-320nera/", "method": "json_ld"},
            {"url": "https://www.amazon.fr/dp/B0CF5Q64QS", "method": "amazon"},
        ],
    },
    "mova": {
        "name": "MOVA LiDAX Ultra 1200",
        "sources": [
            {"url": "https://fr.mova.tech/products/robot-tondeuse-lidax-ultra", "method": "shopify"},
            {"url": "https://www.amazon.fr/dp/B0GD23KKHC", "method": "amazon"},
        ],
    },
    "a3pro": {
        "name": "Dreame A3 AWD Pro 3500",
        "sources": [
            {"url": "https://fr.dreametech.com/products/dreame-robot-tondeuse-a3-awd-pro-3500", "method": "shopify"},
        ],
    },
    "luba3": {
        "name": "Mammotion LUBA 3 AWD 3000",
        "sources": [
            {"url": "https://www.amazon.fr/dp/B0GCZSSZRZ", "method": "amazon"},
            {"url": "https://eu.mammotion.com/fr/products/luba-3-awd-3000", "method": "shopify"},
        ],
    },
}

# ─── Parsing des prix ─────────────────────────────────────────────────────────

def parse_price(raw: str) -> Optional[int]:
    """Convertit une chaîne de prix en entier. Ex: '949,00 €' → 949, '2 599' → 2599."""
    if not raw:
        return None
    cleaned = str(raw).strip().replace("\xa0", " ").replace("\u202f", " ")
    # Supprimer symboles monétaires
    cleaned = re.sub(r"[€$£]", "", cleaned)
    # Si terminé par ,XX ou .XX (centimes) : garder la partie entière
    m = re.match(r"^[\s]*([\d\s]+)[,.](\d{2})[\s]*$", cleaned.strip())
    if m:
        integer_part = re.sub(r"\s", "", m.group(1))
        val = int(integer_part) if integer_part.isdigit() else None
    else:
        # Sinon extraire la première suite de 3 à 5 chiffres consécutifs (avec espaces)
        cleaned_digits = re.sub(r"\s", "", cleaned)
        m2 = re.search(r"(\d{3,5})", cleaned_digits)
        val = int(m2.group(1)) if m2 else None

    if val and MIN_PRICE <= val <= MAX_PRICE:
        return val
    return None


def extract_json_ld(soup: BeautifulSoup) -> Optional[int]:
    """Extrait le prix depuis les balises JSON-LD (structured data)."""
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
    """Extrait le prix depuis une boutique Shopify (window.ShopifyAnalytics ou JSON-LD)."""
    # Méthode 1 : JSON-LD standard Shopify
    price = extract_json_ld(soup)
    if price:
        return price
    # Méthode 2 : balise meta og:price:amount
    tag = soup.find("meta", {"property": "product:price:amount"}) or \
          soup.find("meta", {"property": "og:price:amount"})
    if tag and tag.get("content"):
        return parse_price(tag["content"])
    # Méthode 3 : window.ShopifyAnalytics.meta dans les scripts
    for script in soup.find_all("script"):
        text = script.string or ""
        m = re.search(r'"price"\s*:\s*(\d+)', text)
        if m:
            # Prix Shopify en centimes (ex: 94900 = 949 €)
            raw = int(m.group(1))
            if raw > MAX_PRICE:
                raw = raw // 100  # convertir centimes → euros
            p = parse_price(str(raw))
            if p:
                return p
    return None


def extract_amazon(soup: BeautifulSoup) -> Optional[int]:
    """Extrait le prix depuis une page produit Amazon.fr."""
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
    # Fallback : JSON-LD (Amazon en intègre parfois)
    return extract_json_ld(soup)


# ─── Fetch ────────────────────────────────────────────────────────────────────

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
    """Essaie toutes les sources pour un robot et retourne le premier prix valide."""
    for source in config["sources"]:
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


# ─── Lecture du prix actuel dans les fichiers HTML ────────────────────────────

def get_current_price(content: str, robot_id: str) -> Optional[int]:
    """Lit le prix actuellement dans le fichier HTML pour un robot donné."""
    # Style index.html (ligne unique) : id:'worx',...price:'949 €',...
    m = re.search(
        rf"id:'{re.escape(robot_id)}'[^\n]*?price:'([\d\s]+) €'",
        content
    )
    if m:
        return int(m.group(1).replace(" ", ""))

    # Style fiche.html (multi-ligne) : worx: { ... price: '949 €', ...
    m = re.search(
        rf"(?s){re.escape(robot_id)}:\s*\{{[^{{}}]{{0,500}}?price:\s*'([\d\s]+) €'",
        content
    )
    if m:
        return int(m.group(1).replace(" ", ""))

    return None


def fmt(price: int) -> str:
    """Formate un entier en prix français : 2599 → '2 599'"""
    return f"{price:,}".replace(",", "\u202f")  # espace fine


def update_price_in_file(content: str, robot_id: str, old_price: int, new_price: int) -> str:
    """Remplace toutes les occurrences du prix pour un robot dans un fichier HTML."""
    old_str = fmt(old_price)
    new_str = fmt(new_price)

    # 1. price:'2 599 €' ou price: '2 599 €' (espace fine ou espace normale)
    content = re.sub(
        rf"((?:id:'{re.escape(robot_id)}'[^\n]*?|{re.escape(robot_id)}:\s*\{{[^{{}}]{{0,500}}?)price:\s*')([\d\s\u202f]+) €'",
        lambda m: m.group(0).replace(f"{old_str} €", f"{new_str} €").replace(
            f"{old_price} €", f"{new_price} €"
        ),
        content,
        flags=re.DOTALL,
    )

    # Fallback simple si le pattern ci-dessus n'a rien changé :
    # Remplace price:'OLD €' partout sur une courte fenêtre après l'id
    for pattern in [
        rf"(id:'{re.escape(robot_id)}'[^\n]{{0,400}}?price:')({re.escape(old_str)} €|{old_price} €)(')",
        rf"({re.escape(robot_id)}:\s*\{{[^{{}}]{{0,500}}?price:\s*')({re.escape(old_str)} €|{old_price} €)(')",
    ]:
        content = re.sub(pattern, rf"\g<1>{new_str} €\g<3>", content, flags=re.DOTALL)

    # 2. priceN:2599 (index.html uniquement, même ligne que l'id)
    content = re.sub(
        rf"(id:'{re.escape(robot_id)}'[^\n]{{0,400}}?priceN:){old_price}\b",
        rf"\g<1>{new_price}",
        content,
    )

    # 3. Tableau comparatif index.html : <strong>2 599 €</strong>
    # On ne remplace que si la ligne contient aussi le nom du robot (sécurité)
    lines = content.split("\n")
    robot_name = ROBOTS[robot_id]["name"]
    for i, line in enumerate(lines):
        if robot_name in line and f"{old_str} €" in line:
            lines[i] = line.replace(f"{old_str} €", f"{new_str} €")
        elif robot_name in line and f"{old_price} €" in line:
            lines[i] = line.replace(f"{old_price} €", f"{new_price} €")
    content = "\n".join(lines)

    return content


# ─── Main ─────────────────────────────────────────────────────────────────────

FILES = ["index.html", "fiche.html"]


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

    changes = []
    skipped = []

    for robot_id, config in ROBOTS.items():
        log.info(f"\n[{robot_id}] Vérification : {config['name']}")

        # Prix actuel dans les fichiers (lecture directe)
        current_price = get_current_price(contents["index.html"], robot_id) or \
                        get_current_price(contents["fiche.html"], robot_id)

        if current_price is None:
            log.warning(f"  [{robot_id}] Impossible de lire le prix actuel dans les fichiers.")
            skipped.append(robot_id)
            continue

        log.info(f"  [{robot_id}] Prix actuel dans le site : {current_price} €")

        # Récupérer le prix en ligne
        fetched_price = fetch_price(robot_id, config)

        if fetched_price is None:
            log.warning(f"  [{robot_id}] Impossible de récupérer le prix en ligne — inchangé.")
            skipped.append(robot_id)
            continue

        # Comparer
        if abs(fetched_price - current_price) <= 1:
            log.info(f"  [{robot_id}] ✅ Prix inchangé : {current_price} €")
            continue

        # Mise à jour
        diff = fetched_price - current_price
        sign = "+" if diff > 0 else ""
        log.info(f"  [{robot_id}] 💰 Changement : {current_price} € → {fetched_price} € ({sign}{diff} €)")
        changes.append({
            "id": robot_id,
            "name": config["name"],
            "old": current_price,
            "new": fetched_price,
            "diff": diff,
        })

        for fname in FILES:
            contents[fname] = update_price_in_file(contents[fname], robot_id, current_price, fetched_price)

    # ── Résumé ──────────────────────────────────────────────────────────────
    log.info("\n" + "═" * 60)
    if not changes:
        log.info("✅ Aucun changement de prix — fichiers non modifiés.")
    else:
        # Écrire les fichiers mis à jour
        for fname in FILES:
            with open(fname, "w", encoding="utf-8") as fh:
                fh.write(contents[fname])
            log.info(f"📝 {fname} mis à jour")

        log.info(f"\n💰 {len(changes)} prix mis à jour :")
        for c in changes:
            sign = "+" if c["diff"] > 0 else ""
            log.info(f"  {c['name']}: {c['old']} € → {c['new']} € ({sign}{c['diff']} €)")

        # Historique des prix
        with open("PRICE_HISTORY.md", "a", encoding="utf-8") as fh:
            fh.write(f"\n## {datetime.now().strftime('%Y-%m-%d')}\n")
            for c in changes:
                sign = "+" if c["diff"] > 0 else ""
                fh.write(f"- **{c['name']}** : {c['old']} € → {c['new']} € ({sign}{c['diff']} €)\n")

    if skipped:
        log.info(f"\n⚠️  Robots ignorés (échec fetch ou parsing) : {', '.join(skipped)}")

    log.info("═" * 60)


if __name__ == "__main__":
    main()
