import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup


STRATEGY_URL = "https://www.strategy.com/purchases"
METAPLANET_URL = "https://metaplanet.jp/en/analytics"
MARA_URL = "https://bitcointreasuries.net/public-companies/mara"
XXI_URL = "https://bitcointreasuries.net/public-companies/xxi"


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


def fetch_metaplanet():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(METAPLANET_URL)
        driver.implicitly_wait(10)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table')
        if not table:
            return []
        rows = []
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        for tr in table.find_all('tr')[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all('td')]
            if not cells:
                continue
            item = dict(zip(headers, cells))
            # Skip summary rows lacking a date
            if not item.get('Reported'):
                continue
            def parse_btc(val):
                return float(val.replace('₿', '').replace(',', ''))

            def parse_money(val):
                val = val.replace('$', '').replace(',', '')
                multiplier = 1
                if val.endswith('B'):
                    multiplier = 1_000_000_000
                    val = val[:-1]
                elif val.endswith('M'):
                    multiplier = 1_000_000
                    val = val[:-1]
                elif val.endswith('K'):
                    multiplier = 1_000
                    val = val[:-1]
                return float(val) * multiplier

            def parse_date(val):
                from datetime import datetime
                return datetime.strptime(val, '%b %d, %Y').strftime('%Y-%m-%d')

            rows.append({
                'date': parse_date(item['Reported']),
                'btc': parse_btc(item['BTC Acquisitions']),
                'avg_price_usd': parse_money(item['Avg BTC Cost']),
                'total_cost_usd': parse_money(item['Acquisition Cost'])
            })
        return rows
    finally:
        driver.quit()


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


def fetch_mara():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(MARA_URL, headers=headers).text
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


def fetch_xxi():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(XXI_URL, headers=headers).text
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


def main():
    data = {
        'strategy': fetch_strategy(),
        'metaplanet': fetch_metaplanet(),
        'mara': fetch_mara(),
        'xxi': fetch_xxi(),
    }
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    main()
