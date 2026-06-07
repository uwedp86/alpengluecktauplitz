#!/usr/bin/env python3
"""Build multilingual static pages for Alpenglück Tauplitz.

Reads template.html, extracts the JS `translations` object, and renders
fully-localized static HTML for en/de/nl/cs with per-page SEO metadata
(canonical, hreflang, Open Graph, Twitter, geo) and JSON-LD.

Re-runnable: reads from template.html, never from its own output.
"""
import json
import os
import re
import subprocess
import sys

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(ROOT, "template.html")
BASE = "https://alpenglueck-tauplitz.be/"

LANGS = ["en", "de", "nl", "cs"]
PATHS = {"en": "", "de": "de/", "nl": "nl/", "cs": "cs/"}
OG_LOCALE = {"en": "en_US", "de": "de_DE", "nl": "nl_NL", "cs": "cs_CZ"}

TITLES = {
    "en": "Alpenglück Tauplitz – Alpine Apartment in the Styrian Alps",
    "de": "Alpenglück Tauplitz – Ferienwohnung in den Steirischen Alpen",
    "nl": "Alpenglück Tauplitz – Alpenappartement in de Stiermarkse Alpen",
    "cs": "Alpenglück Tauplitz – Alpský apartmán ve Štýrských Alpách",
}
DESCS = {
    "en": "Cosy alpine apartment in Tauplitz, Austria. Your base for the Tauplitzalm, Grundlsee, Hallstatt and the Dachstein. Book via Booking.com or Airbnb.",
    "de": "Gemütliche Ferienwohnung in Tauplitz, Österreich. Ihr Ausgangspunkt für Tauplitzalm, Grundlsee, Hallstatt und den Dachstein. Buchen über Booking.com oder Airbnb.",
    "nl": "Gezellig alpenappartement in Tauplitz, Oostenrijk. Uw uitvalsbasis voor de Tauplitzalm, Grundlsee, Hallstatt en de Dachstein. Boek via Booking.com of Airbnb.",
    "cs": "Útulný alpský apartmán v Tauplitz, Rakousko. Vaše základna pro Tauplitzalm, Grundlsee, Hallstatt a Dachstein. Rezervujte přes Booking.com nebo Airbnb.",
}


def extract_translations(html):
    """Extract the JS `translations` object literal and return it as a dict.

    Uses Node.js to evaluate the object literal (it is valid JS, not JSON).
    """
    data_soup = BeautifulSoup(html, "html.parser")
    data_script = data_soup.find("script", id="i18n-data")
    src = data_script.string if data_script else html
    m = re.search(r"var\s+translations\s*=\s*(\{.*\});", src, re.DOTALL)
    if not m:
        raise RuntimeError("Could not locate translations object in #i18n-data")
    obj = m.group(1)
    node_src = "process.stdout.write(JSON.stringify(" + obj + "));"
    out = subprocess.check_output(["node", "-e", node_src])
    return json.loads(out)


def build_lang(template_html, translations, lang):
    soup = BeautifulSoup(template_html, "html.parser")
    t = translations[lang]
    path = PATHS[lang]
    url = BASE + path
    title = TITLES[lang]
    desc = DESCS[lang]

    # Keep title/description translations consistent with the canonical SEO strings.
    t["page_title"] = title

    # <html lang>
    soup.html["lang"] = lang

    # Apply data-i18n (inner text)
    for el in soup.select("[data-i18n]"):
        key = el.get("data-i18n")
        if key in t:
            el.string = ""
            for child in list(el.children):
                child.extract()
            el.append(t[key])

    # Apply data-i18n-html (innerHTML)
    for el in soup.select("[data-i18n-html]"):
        key = el.get("data-i18n-html")
        if key in t:
            for child in list(el.children):
                child.extract()
            frag = BeautifulSoup(t[key], "html.parser")
            for node in list(frag.contents):
                el.append(node)

    # Apply data-i18n-ph (placeholder)
    for el in soup.select("[data-i18n-ph]"):
        key = el.get("data-i18n-ph")
        if key in t:
            el["placeholder"] = t[key]

    # <title>
    if soup.title:
        soup.title.string = title

    # <meta name="description">
    md = soup.find("meta", attrs={"name": "description"})
    if md:
        md["content"] = desc

    # Rewrite relative asset/link paths to absolute so subdir pages work.
    for el in soup.find_all(src=True):
        if el["src"].startswith("images/"):
            el["src"] = "/" + el["src"]
    for el in soup.find_all(href=True):
        if el["href"] == "privacy.html":
            el["href"] = "/privacy.html"
        elif el["href"].startswith("images/"):
            el["href"] = "/" + el["href"]

    # Language switcher: make buttons navigate, mark active.
    for btn in soup.select(".lang-switch button"):
        blang = btn.get("data-lang")
        btn["onclick"] = "location.href='/%s'" % PATHS[blang]
        if blang == lang:
            existing = btn.get("class", [])
            if "active" not in existing:
                btn["class"] = existing + ["active"]

    # Static pages need no runtime translation: drop the i18n data + runtime
    # scripts entirely so the pre-rendered language is never overwritten.
    for sid in ("i18n-data", "i18n-runtime"):
        s = soup.find("script", id=sid)
        if s:
            s.decompose()

    inject_head(soup, lang, url, title, desc)
    return soup


def inject_head(soup, lang, url, title, desc):
    head = soup.head
    img = BASE + "images/hero.jpg"

    def meta(attrs):
        m = soup.new_tag("meta")
        for k, v in attrs.items():
            m[k] = v
        head.append(m)

    def link(attrs):
        l = soup.new_tag("link")
        for k, v in attrs.items():
            l[k] = v
        head.append(l)

    # Canonical
    link({"rel": "canonical", "href": url})

    # hreflang cluster
    link({"rel": "alternate", "hreflang": "en", "href": BASE})
    link({"rel": "alternate", "hreflang": "de", "href": BASE + "de/"})
    link({"rel": "alternate", "hreflang": "nl", "href": BASE + "nl/"})
    link({"rel": "alternate", "hreflang": "cs", "href": BASE + "cs/"})
    link({"rel": "alternate", "hreflang": "x-default", "href": BASE})

    # Open Graph
    meta({"property": "og:type", "content": "website"})
    meta({"property": "og:site_name", "content": "Alpenglück Tauplitz"})
    meta({"property": "og:title", "content": title})
    meta({"property": "og:description", "content": desc})
    meta({"property": "og:url", "content": url})
    meta({"property": "og:image", "content": img})
    meta({"property": "og:locale", "content": OG_LOCALE[lang]})

    # Twitter
    meta({"name": "twitter:card", "content": "summary_large_image"})
    meta({"name": "twitter:title", "content": title})
    meta({"name": "twitter:description", "content": desc})
    meta({"name": "twitter:image", "content": img})

    # Geo + misc
    meta({"name": "geo.region", "content": "AT-6"})
    meta({"name": "geo.placename", "content": "Tauplitz, Bad Mitterndorf"})
    meta({"name": "geo.position", "content": "47.5717;14.0086"})
    meta({"name": "ICBM", "content": "47.5717, 14.0086"})
    meta({"name": "theme-color", "content": "#3a6b4a"})
    meta({"name": "robots", "content": "index, follow"})
    meta({"name": "author", "content": "Alpenglück Tauplitz"})

    # JSON-LD
    ld = {
        "@context": "https://schema.org",
        "@type": "LodgingBusiness",
        "name": "Alpenglück Tauplitz",
        "description": desc,
        "url": url,
        "image": img,
        "inLanguage": lang,
        "email": "alpenglueck.tauplitz@gmail.com",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Tauplitz",
            "postalCode": "8982",
            "addressRegion": "Steiermark",
            "addressCountry": "AT",
            "streetAddress": "Tauplitz, 8982 Bad Mitterndorf",
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": 47.5717,
            "longitude": 14.0086,
        },
        "amenityFeature": [
            {"@type": "LocationFeatureSpecification", "name": "Fully equipped kitchen", "value": True},
            {"@type": "LocationFeatureSpecification", "name": "Bedrooms", "value": True},
            {"@type": "LocationFeatureSpecification", "name": "Modern bathroom", "value": True},
        ],
        "petsAllowed": False,
        "numberOfRooms": 3,
        "knowsLanguage": ["en", "de", "nl", "cs"],
        "sameAs": [
            "https://www.booking.com/Share-NSsUTZE",
            "https://www.airbnb.be/rooms/51036211",
        ],
    }
    script = soup.new_tag("script", type="application/ld+json")
    script.string = json.dumps(ld, ensure_ascii=False, indent=2)
    head.append(script)


def main():
    with open(TEMPLATE, encoding="utf-8") as f:
        template_html = f.read()
    translations = extract_translations(template_html)

    for lang in LANGS:
        soup = build_lang(template_html, translations, lang)
        out_html = soup.encode(formatter="html5").decode("utf-8")
        if lang == "en":
            out_path = os.path.join(ROOT, "index.html")
        else:
            d = os.path.join(ROOT, lang)
            os.makedirs(d, exist_ok=True)
            out_path = os.path.join(d, "index.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_html)
        print("wrote", os.path.relpath(out_path, ROOT))


if __name__ == "__main__":
    main()
