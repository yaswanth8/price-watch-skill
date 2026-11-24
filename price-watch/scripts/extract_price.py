#!/usr/bin/env python3
"""Pull price, currency, stock and identifiers out of a product page's HTML.

Usage:
    python3 extract_price.py page.html            # a saved page
    python3 extract_price.py - < page.html        # from stdin
    python3 extract_price.py --url https://...    # fetch it (many big stores block this; use the browser then)

Prints one JSON object:
    {"name", "price", "currency", "in_stock", "sku", "gtin", "mpn", "brand",
     "seller", "condition", "source", "candidates"}

`source` says where the price came from (json-ld, meta, microdata, text). Structured data
(json-ld, meta, microdata) is trustworthy; `text` is a best guess from visible prices and must
be confirmed against the page before you act on it. `price` is null when nothing was found.
Standard library only.
"""
import html as htmllib
import json
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "₹": "INR", "¥": "JPY", "C$": "CAD", "A$": "AUD"}


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    # 1.299,00 (EU) vs 1,299.00 (US)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + "." + tail if len(tail) == 2 else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def stock(v):
    if v is None:
        return None
    s = str(v).lower()
    if any(k in s for k in ("instock", "in_stock", "in stock", "limitedavailability", "onlineonly", "presale", "preorder")):
        return True
    if any(k in s for k in ("outofstock", "out_of_stock", "soldout", "discontinued", "out of stock")):
        return False
    return None


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def from_jsonld(page):
    out = None
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(htmllib.unescape(block.strip()))
        except Exception:
            continue
        for node in walk(data):
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Product" not in types and "ProductGroup" not in types:
                continue
            offers = node.get("offers")
            offer_list = [o for o in walk(offers) if isinstance(o, dict) and ("price" in o or "lowPrice" in o)] if offers else []
            if not offer_list:
                continue
            o = offer_list[0]
            brand = node.get("brand")
            seller = o.get("seller")
            out = {
                "name": node.get("name"),
                "price": num(o.get("price", o.get("lowPrice"))),
                "currency": o.get("priceCurrency"),
                "in_stock": stock(o.get("availability")),
                "sku": node.get("sku") or o.get("sku"),
                "gtin": node.get("gtin13") or node.get("gtin12") or node.get("gtin") or node.get("gtin14") or node.get("gtin8"),
                "mpn": node.get("mpn"),
                "brand": brand.get("name") if isinstance(brand, dict) else brand,
                "seller": seller.get("name") if isinstance(seller, dict) else seller,
                "condition": (str(o.get("itemCondition") or "").rsplit("/", 1)[-1].replace("Condition", "").lower() or None),
                "source": "json-ld",
            }
            if out["price"]:
                return out
    return out


def meta(page, *names):
    for n in names:
        m = re.search(r'<meta[^>]+(?:property|name|itemprop)=["\']%s["\'][^>]*content=["\']([^"\']+)' % re.escape(n), page, re.I) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']%s["\']' % re.escape(n), page, re.I)
        if m:
            return htmllib.unescape(m.group(1))
    return None


def from_meta(page):
    price = num(meta(page, "product:price:amount", "og:price:amount", "twitter:data1", "price"))
    if not price:
        return None
    return {
        "name": meta(page, "og:title", "twitter:title"),
        "price": price,
        "currency": meta(page, "product:price:currency", "og:price:currency", "priceCurrency"),
        "in_stock": stock(meta(page, "product:availability", "og:availability", "availability")),
        "sku": meta(page, "product:retailer_item_id", "sku"),
        "gtin": meta(page, "product:gtin", "gtin13", "gtin"),
        "mpn": meta(page, "product:mfr_part_no", "mpn"),
        "brand": meta(page, "product:brand", "og:brand", "brand"),
        "seller": None, "condition": meta(page, "product:condition"),
        "source": "meta",
    }


def from_microdata(page):
    m = re.search(r'itemprop=["\']price["\'][^>]*?(?:content=["\']([^"\']+)["\']|>([^<]+)<)', page, re.I)
    if not m:
        return None
    price = num(m.group(1) or m.group(2))
    if not price:
        return None
    cur = re.search(r'itemprop=["\']priceCurrency["\'][^>]*content=["\']([A-Z]{3})', page)
    avail = re.search(r'itemprop=["\']availability["\'][^>]*(?:href|content)=["\']([^"\']+)', page, re.I)
    return {"name": None, "price": price, "currency": cur.group(1) if cur else None,
            "in_stock": stock(avail.group(1) if avail else None), "sku": None, "gtin": None, "mpn": None,
            "brand": None, "seller": None, "condition": None, "source": "microdata"}


def from_text(page):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S | re.I)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", text))
    found = re.findall(r"(C\$|A\$|[$£€₹¥])\s?(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)", text)
    cands = []
    for sym, amt in found:
        v = num(amt)
        if v and v not in [c["price"] for c in cands]:
            cands.append({"price": v, "currency": SYMBOLS.get(sym)})
        if len(cands) >= 8:
            break
    if not cands:
        return None
    oos = re.search(r"out of stock|sold out|currently unavailable", text, re.I)
    return {"name": None, "price": cands[0]["price"], "currency": cands[0]["currency"],
            "in_stock": False if oos else None, "sku": None, "gtin": None, "mpn": None, "brand": None,
            "seller": None, "condition": None, "source": "text", "candidates": cands}


def extract(page):
    for fn in (from_jsonld, from_meta, from_microdata, from_text):
        r = fn(page)
        if r and r.get("price"):
            r.setdefault("candidates", [])
            if not r.get("name"):
                t = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
                r["name"] = htmllib.unescape(t.group(1)).strip() if t else None
            return r
    return {"name": None, "price": None, "currency": None, "in_stock": None, "sku": None, "gtin": None,
            "mpn": None, "brand": None, "seller": None, "condition": None, "source": None, "candidates": []}


def main(argv):
    if len(argv) >= 2 and argv[0] == "--url":
        req = urllib.request.Request(argv[1], headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        try:
            page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        except Exception as e:
            print(json.dumps({"price": None, "error": f"fetch failed: {e}. Use the browser or a fetch tool and pass the saved HTML."}))
            return 2
    elif argv and argv[0] != "-":
        page = open(argv[0], encoding="utf-8", errors="replace").read()
    else:
        page = sys.stdin.read()
    if re.search(r"captcha|robot check|are you a human|access denied", page[:20000], re.I) and not re.search(r"ld\+json", page, re.I):
        print(json.dumps({"price": None, "error": "blocked: the store showed a bot check. Use the browser instead."}))
        return 3
    print(json.dumps(extract(page), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
