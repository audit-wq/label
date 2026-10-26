"""Refresh the Care Plus label page (index.html) from Zoho Books.

Runs in GitHub Actions (.github/workflows/refresh.yml). Needs three repository secrets:
  ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN   (Zoho "Self Client", scope ZohoBooks.settings.READ)

Reads every active item (SKU, name, price, category). The Arabic name (name_sec_lang) is only
in the single-item API, so it is fetched only for items that are new or changed since the
last run (data/items.json keeps each item's last_modified_time). Python standard library only.
"""
import datetime, json, os, re, sys, time, urllib.parse, urllib.request

ORG = "938207008"
ACCOUNTS = os.environ.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com")
API = os.environ.get("ZOHO_API_URL", "https://www.zohoapis.com/books/v3")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "items.json")
TEMPLATE = os.path.join(ROOT, "scripts", "template.html")
OUT = os.path.join(ROOT, "index.html")
DATA = os.path.join(ROOT, "items-data.json")
BIDI = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮⁦⁧⁨⁩"))


def http(url, data=None, headers=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 429 or e.code >= 500:
                time.sleep(20 * (k + 1)); continue
            sys.exit("Zoho error %s on %s: %s" % (e.code, url.split("?")[0], body))
        except Exception as e:  # network hiccup
            if k == tries - 1: raise
            time.sleep(10)


def token():
    q = urllib.parse.urlencode({
        "refresh_token": os.environ["ZOHO_REFRESH_TOKEN"], "client_id": os.environ["ZOHO_CLIENT_ID"],
        "client_secret": os.environ["ZOHO_CLIENT_SECRET"], "grant_type": "refresh_token"})
    r = http(ACCOUNTS + "/oauth/v2/token?" + q, data=b"")
    if "access_token" not in r:
        sys.exit("Could not get a Zoho access token: %s" % r)
    return r["access_token"]


def price(v):
    v = float(v or 0)
    return str(int(v)) if v == int(v) else ("%.2f" % v)


def arabic(sec):
    first = (sec or "").split("\n")[0]
    return " ".join(first.translate(BIDI).split())


def main():
    hdr = {"Authorization": "Zoho-oauthtoken " + token()}
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

    items, page = [], 1
    while True:
        r = http("%s/items?organization_id=%s&filter_by=Status.Active&per_page=200&page=%d" % (API, ORG, page), headers=hdr)
        items += r.get("items", [])
        if not r.get("page_context", {}).get("has_more_page"):
            break
        page += 1
    if len(items) < 100:
        sys.exit("Only %d items returned - not updating the page." % len(items))

    new_cache, fetched, missing_ar = {}, 0, []
    for it in items:
        iid, lmt = it["item_id"], it.get("last_modified_time", "")
        old = cache.get(iid)
        rec = {"sku": (it.get("sku") or "").strip(), "name": (it.get("name") or "").strip(),
               "price": price(it.get("rate")), "cat": (it.get("category_name") or "").strip(), "lmt": lmt}
        if old and (old.get("lmt") == lmt or old.get("lmt") == "") and old.get("ar"):
            rec["ar"] = old["ar"]          # unchanged (or first run after seeding): keep the known Arabic
        else:
            d = http("%s/items/%s?organization_id=%s" % (API, iid, ORG), headers=hdr).get("item", {})
            rec["ar"] = arabic(d.get("name_sec_lang"))
            fetched += 1
            time.sleep(0.7)               # stay well under Zoho's per-minute API limit
        if not rec["ar"]:
            missing_ar.append(rec["sku"] or rec["name"])
        new_cache[iid] = rec

    rows = sorted(new_cache.values(), key=lambda r: (r["sku"] == "", r["sku"], r["name"]))
    data = [{"sku": r["sku"], "name": r["name"], "ar": r["ar"], "price": r["price"], "cat": r["cat"]} for r in rows]

    old_data = None
    if os.path.exists(OUT):
        m = re.search(r"var EMBEDDED_ITEMS=(\[.*?\]);</script>", open(OUT, encoding="utf-8").read(), re.S)
        if m:
            try: old_data = json.loads(m.group(1))
            except ValueError: old_data = None
    json.dump(new_cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)

    print("Items: %d  | Arabic looked up: %d  | Without Arabic: %s" % (len(data), fetched, ", ".join(missing_ar) or "none"))
    if old_data == data and os.path.exists(DATA):
        print("No item changes - page left as it is.")
        return
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%d %b %Y %H:%M")
    html = open(TEMPLATE, encoding="utf-8").read()
    html = html.replace("/*__ITEMS__*/[]", json.dumps(data, ensure_ascii=False)).replace("/*__STAMP__*/", stamp)
    open(OUT, "w", encoding="utf-8").write(html)
    json.dump({"stamp": stamp, "items": data}, open(os.path.join(ROOT, "items-data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("index.html updated (%s Qatar time)." % stamp)


if __name__ == "__main__":
    main()
