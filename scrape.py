import json
from datetime import datetime

import cloudscraper
from bs4 import BeautifulSoup


STRATEGY_URL = "https://www.strategy.com/purchases"
BITCOIN_TREASURY_BASE_URL = "https://bitcointreasuries.net/public-companies/"

TOP_COMPANIES_URL = "https://bitcointreasuries.net"


# Cloudflare protection on bitcointreasuries.net can present challenges
# when scraping multiple pages quickly. Using a small delay helps
# cloudscraper solve the challenge reliably.
scraper = cloudscraper.create_scraper(delay=10)


def fetch_strategy():
    html = scraper.get(STRATEGY_URL).text
    start = html.find("__NEXT_DATA__")
    if start == -1:
        raise RuntimeError("__NEXT_DATA__ not found")
    json_start = html.index('>', start) + 1
    json_end = html.index('</script>', json_start)
    data = json.loads(html[json_start:json_end])
    purchases = []
    for item in data['props']['pageProps']['bitcoinData']:
        purchases.append({
            'date': item['date_of_purchase'],
            'btc': item['count'],
            'avg_price_usd': item['purchase_price'],
            'total_cost_usd': item.get('total_purchase_price')
        })
    return purchases


UNDEFINED = -1
HOLE = -2
NAN = -3
POSITIVE_INFINITY = -4
NEGATIVE_INFINITY = -5
NEGATIVE_ZERO = -6


def _hydrate(values, index, cache):
    if index == UNDEFINED:
        return None
    if index == NAN:
        return float("nan")
    if index == POSITIVE_INFINITY:
        return float("inf")
    if index == NEGATIVE_INFINITY:
        return float("-inf")
    if index == NEGATIVE_ZERO:
        return -0.0
    if index in cache:
        return cache[index]

    value = values[index]
    if value is None or not isinstance(value, (list, dict)):
        cache[index] = value
    elif isinstance(value, list):
        if value and isinstance(value[0], str):
            t = value[0]
            if t == "Date":
                cache[index] = datetime.fromisoformat(value[1].replace("Z", "+00:00"))
            elif t == "null":
                obj = {}
                cache[index] = obj
                for i in range(1, len(value), 2):
                    obj[value[i]] = _hydrate(values, value[i + 1], cache)
            else:
                raise ValueError(f"Unsupported type {t}")
        else:
            arr = []
            cache[index] = arr
            for v in value:
                if v == HOLE:
                    arr.append(None)
                else:
                    arr.append(_hydrate(values, v, cache))
    else:
        obj = {}
        cache[index] = obj
        for k, v in value.items():
            obj[k] = _hydrate(values, v, cache)
    return cache[index]


def _parse_devalue(serialized):
    values = json.loads(serialized)
    return _hydrate(values, 0, {})


def _fetch_btc_treasury(url):
    html = scraper.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", {"type": "application/json"})
    if len(scripts) < 2:
        return []
    body = json.loads(scripts[1].string)["body"]
    data_str = json.loads(body)[0]["result"]["data"]
    obj = _parse_devalue(data_str)
    rows = []
    for b in obj.get("balances", []):
        date = b["date"].date().isoformat()
        btc = float(b["btcDelta"])
        price = float(b["btcMarketPrice"])
        rows.append({
            "date": date,
            "btc": btc,
            "avg_price_usd": price,
            "total_cost_usd": btc * price,
        })
    return rows


def fetch_top_company_slugs(limit: int = 10):
    """Return the slugs for the top public companies by BTC balance."""
    html = scraper.get(TOP_COMPANIES_URL).text
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", {"type": "application/json"})
    if len(scripts) < 2:
        return []
    body = json.loads(scripts[1].string)["body"]
    data_str = json.loads(body)[0]["result"]["data"]
    obj = _parse_devalue(data_str)
    public = [c for c in obj if c.get("type") == "PUBLIC_COMPANY"]
    public.sort(key=lambda c: c.get("btcBalance", 0), reverse=True)
    return [c["currentSlug"] for c in public[:limit] if c.get("currentSlug")]


def fetch_bitcointreasury_company(name: str):
    """Fetch purchase history for a given company identifier."""
    url = f"{BITCOIN_TREASURY_BASE_URL}{name}"
    return _fetch_btc_treasury(url)


def main():
    data = {
        'strategy': fetch_strategy(),
    }

    company_slugs = fetch_top_company_slugs(10)
    company_slugs = [slug for slug in company_slugs if slug != 'microstrategy']

    for name in company_slugs:
        results = fetch_bitcointreasury_company(name)
        if results:
            data[name] = results

    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    main()
