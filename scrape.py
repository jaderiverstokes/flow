import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup


STRATEGY_URL = "https://www.strategy.com/purchases"
BITCOIN_TREASURY_BASE_URL = "https://bitcointreasuries.net/public-companies/"

# List of company identifiers on bitcointreasuries.net
# e.g. for "https://bitcointreasuries.net/public-companies/mara" the
# identifier is "mara".
BITCOIN_TREASURY_COMPANIES = [
    "mara",
    "riot",
    "xxi",
    "metaplanet",
]


def fetch_strategy():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(STRATEGY_URL, headers=headers).text
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
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(url, headers=headers).text
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


def fetch_bitcointreasury_company(name: str):
    """Fetch purchase history for a given company identifier."""
    url = f"{BITCOIN_TREASURY_BASE_URL}{name}"
    return _fetch_btc_treasury(url)


def main():
    data = {
        'strategy': fetch_strategy(),
    }

    for name in BITCOIN_TREASURY_COMPANIES:
        results = fetch_bitcointreasury_company(name)
        if results:
            data[name] = results

    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    main()
