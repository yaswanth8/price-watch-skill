#!/usr/bin/env python3
"""Fold one check (offers from several stores) into a watch and decide what happens next.

Usage:
    python3 update_watch.py watch.json reading.json [settings.json] > updated.json

watch.json    the `watches/<id>` document from the dashboard
reading.json  {"offers": [
                 {"store": "bestbuy.com", "url": "https://...", "price": 279.99, "shipping": 0,
                  "tax": 0, "in_stock": true, "seller": "Best Buy", "condition": "new"},
                 ...],
               "name": "...", "sku": "...", "note": "..."}
              Every offer must be the SAME product (identity checked before it gets here).
              A check that found nothing: {"offers": [], "error": "why"}.
              Old single-store form {"price": .., "in_stock": .., "shipping": ..} still works.
settings.json the `meta/settings` document (maxPerOrder, allowedStores, currency), optional

Prints {"doc": <updated watch>, "event": <what happened>, "message": <one line for the user>}.

The watch's price is the BEST offer: the lowest landed cost (price + shipping + tax when known)
among in-stock offers. `offers` keeps every store's offer, cheapest first, with its buy link.

event:
  first          first check: report the best price and where to buy
  hit            best offer is at or under the user's target
  new-low        no target set, and the best offer beat the lowest price seen so far by at least 1%
  hit-buy        hit / new-low on a watch in buy mode, at an allowed store, under the cap:
                 prepare the cart, then ask (never place the order)
  over-cap       would be hit-buy, but over the per-order cap
  store-blocked  would be hit-buy, but no allowed store has it at that price
  dropped        cheaper than last check, not a hit
  no-change      nothing worth telling
  out-of-stock   no store has it in stock
  failed         check failed (3 in a row -> status needs-attention)

history keeps the last 90 best prices as {"t", "p", "s": store}. A watch already alerting only
fires again when the price falls at least 1% further, so daily checks don't repeat themselves.
"""
import json
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

HISTORY_CAP = 90
OFFERS_CAP = 8


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def host(url):
    h = urlparse(url or "").hostname or ""
    return h[4:] if h.startswith("www.") else h


def allowed(store, stores):
    if not stores:
        return True
    h = (store or "").lower().removeprefix("www.")
    return any(h == s or h.endswith("." + s) for s in (x.strip().lower().removeprefix("www.") for x in stores))


def money(cur, v):
    return f"{cur} {v:,.2f}".strip()


def normalise(w, r):
    offers = r.get("offers")
    if offers is None and r.get("price") is not None:  # old single-store reading
        offers = [{"store": w.get("store") or host(w.get("url")), "url": w.get("url"), "price": r["price"],
                   "shipping": r.get("shipping"), "tax": r.get("tax"), "in_stock": r.get("in_stock"),
                   "seller": r.get("seller"), "condition": r.get("condition")}]
    out = []
    for o in offers or []:
        if not isinstance(o.get("price"), (int, float)):
            continue
        url = o.get("url") if str(o.get("url") or "").startswith("https://") else None
        landed = float(o["price"]) + float(o.get("shipping") or 0) + float(o.get("tax") or 0)
        out.append({"store": o.get("store") or host(url), "url": url, "price": round(float(o["price"]), 2),
                    "shipping": o.get("shipping"), "landed": round(landed, 2), "inStock": o.get("in_stock"),
                    "seller": o.get("seller"), "condition": o.get("condition") or "new"})
    out.sort(key=lambda o: (o["inStock"] is False, o["landed"]))
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    w = dict(load(argv[0]))
    r = load(argv[1])
    s = load(argv[2]) if len(argv) > 2 else {}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    w["lastChecked"] = now
    for k in ("name", "sku", "currency"):
        if r.get(k) and not w.get(k):
            w[k] = r[k]
    cur = w.get("currency") or s.get("currency") or ""
    name = w.get("name") or w.get("url") or "This product"

    offers = normalise(w, r)
    if not offers:
        w["fails"] = int(w.get("fails") or 0) + 1
        w["note"] = r.get("error") or "Could not read a price from any store."
        if w["fails"] >= 3:
            w["status"] = "needs-attention"
        return out(w, "failed", f"Couldn't read prices for {name}: {w['note']}")

    w["fails"] = 0
    w["offers"] = offers[:OFFERS_CAP]
    in_stock = [o for o in offers if o["inStock"] is not False]
    if r.get("note"):
        w["note"] = r["note"]
    else:
        w.pop("note", None)
    if not in_stock:
        w["inStock"] = False
        if w.get("status") not in ("paused", "bought"):
            w["status"] = "out-of-stock"
        return out(w, "out-of-stock", f"{name} is out of stock at every store checked.")

    best = in_stock[0]
    hist = list(w.get("history") or [])
    prev = hist[-1]["p"] if hist else None
    prev_low = w.get("lowest") if isinstance(w.get("lowest"), (int, float)) else (min(h["p"] for h in hist) if hist else None)
    hist.append({"t": now, "p": best["landed"], "s": best["store"]})
    w["history"] = hist[-HISTORY_CAP:]
    w.update(price=best["landed"], store=best["store"], url=best["url"] or w.get("url"), inStock=True,
             lowest=round(min(best["landed"], prev_low) if prev_low is not None else best["landed"], 2))
    where = f"{best['store']}" + (f" ({best['url']})" if best["url"] else "")
    others = len(in_stock) - 1

    if w.get("status") in ("paused", "bought"):
        return out(w, "no-change", "")
    if prev is None:
        w["status"] = "watching"
        return out(w, "first", f"Best price for {name}: {money(cur, best['landed'])} at {where}"
                   + (f", lowest of {len(in_stock)} stores." if others else "."))

    target = w.get("target") if isinstance(w.get("target"), (int, float)) else None
    was_alerting = w.get("status") in ("alert", "cart-ready")
    if w.get("status") in (None, "new", "out-of-stock", "needs-attention"):
        w["status"] = "watching"

    if target is not None:
        is_hit, kind, why = best["landed"] <= target, "hit", f"at or under your {money(cur, target)} target"
    else:
        is_hit = prev_low is not None and best["landed"] <= prev_low * 0.99
        kind, why = "new-low", f"the lowest since you started watching (was {money(cur, prev_low or 0)})"

    if is_hit:
        last = w.get("alertedAt")
        if was_alerting and isinstance(last, (int, float)) and best["landed"] > last * 0.99:
            return out(w, "no-change", "")
        w["status"], w["alertedAt"] = "alert", best["landed"]
        if w.get("mode") == "buy":
            ok = [o for o in in_stock if allowed(o["store"], s.get("allowedStores"))
                  and (target is None or o["landed"] <= target)]
            if not ok:
                return out(w, "store-blocked", f"{name} is {money(cur, best['landed'])} at {where}, {why}, "
                           f"but that store isn't on your allowed list, so nothing was prepared.")
            pick = ok[0]
            cap = s.get("maxPerOrder")
            if isinstance(cap, (int, float)) and pick["landed"] > cap:
                return out(w, "over-cap", f"{name} is {money(cur, pick['landed'])} at {pick['store']}, {why}, "
                           f"but that's over your {money(cur, cap)} per-order cap.")
            w["buyAt"] = pick
            return out(w, "hit-buy", f"{name} is {money(cur, pick['landed'])} at {pick['store']}, {why}. "
                       f"Getting the cart ready; nothing is ordered until you say yes.")
        return out(w, kind, f"{name} is {money(cur, best['landed'])} at {where}, {why}.")

    if was_alerting:
        w["status"] = "watching"
        w.pop("alertedAt", None)
    if best["landed"] < prev - 0.005:
        return out(w, "dropped", f"{name} dropped from {money(cur, prev)} to {money(cur, best['landed'])} at {best['store']}.")
    return out(w, "no-change", "")


def out(doc, event, message):
    print(json.dumps({"doc": doc, "event": event, "message": message}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
