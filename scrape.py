import json
import requests
import fileinput
import locale
from datetime import datetime
from dateutil import parser


import cloudscraper
from bs4 import BeautifulSoup
import os
os.environ['TZ'] = 'UTC'



STRATEGY_URL = "https://www.strategy.com/purchases"
BITCOIN_TREASURY_BASE_URL = "https://bitcointreasuries.net/public-companies/"

TOP_COMPANIES_URL = "https://bitbo.io/treasuries/#public"
COMPANIES_URL = "https://bitbo.io"


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
    body = json.loads(scripts[0].string)["body"]
    data_str = json.loads(body)["result"]["data"]
    obj = _parse_devalue(data_str)
    public = [c for c in obj if c.get("type") == "PUBLIC_COMPANY"]
    public.sort(key=lambda c: c.get("btcBalance", 0), reverse=True)
    return [c["currentSlug"] for c in public[:limit] if c.get("currentSlug")]


def fetch_bitcointreasury_company(name: str):
    """Fetch purchase history for a given company identifier."""
    url = f"{BITCOIN_TREASURY_BASE_URL}{name}"
    return _fetch_btc_treasury(url)

def fetch_top_companies(limit: int = 10):
    html = scraper.get(TOP_COMPANIES_URL).text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find_all('table', class_="treasuries-table")[2]
    count = 0
    companies = []
    for row in table.find_all('tr')[1:]:
        company = row.find('td', class_="td-company") # Include 'th' if not extracting headers separately
        link = company.find('a')
        companies.append(link["href"])
        count += 1
        if count >= limit:
            break
    return companies

def parse_large_number(s):
    s = s[1:].strip().upper()  # Remove leading/trailing spaces and convert to uppercase for consistency.
    if s.endswith('M'):
        return float(s[:-1]) * 1_000_000  # Remove 'M' and multiply by 1 Million.
    elif s.endswith('B'):
        return float(s[:-1]) * 1_000_000_000  # Remove 'B' and multiply by 1 Billion.
    else:
        return float(s)

def fetch_company(name, prices):
    url = f"{COMPANIES_URL}/{name}"
    html = scraper.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find('table', class_='stats-table')
    # import pdb;pdb.set_trace()
    if table is None:
        return []
        # table = soup.find('table', 
    data = []
    rows = table.find_all('tr')[1:]
    for row in rows:
        cols = list(map(lambda x: x.find('span').text, row.find_all('td')))
        date_format = "%m/%d/%Y"
        # import pdb;pdb.set_trace()
        date = parser.parse(cols[0])
        # .isoformat()
        btc = int(float(cols[2].replace(',','')))
        if btc == 0:
            btc = int(float(cols[1].replace(',','')))

        # import pdb;pdb.set_trace()
        bitcoin_price_usd = prices[int(date.timestamp() * 1000)]

        # total_cost_usd = parse_large_number(cols[2])
        # avg_price_usd = total_cost_usd / btc
        data.append({
            "date": date.isoformat(),
            "btc": btc,
            "avg_price_usd": bitcoin_price_usd,
            "total_cost_usd": bitcoin_price_usd * btc,
        })
    return data

def get_prices():
    all_prices = []
    for year in range(2020, datetime.now().year):
        # print(year)
        # url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range?vs_currency=usd&from=2025-01-01&to={datetime.now().strftime('%Y-%m-%d')}&x_cg_demo_api_key=CG-HBtC1HrokNu33xXQzrj7S49t"
        url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&interval=daily&x_cg_demo_api_key=CG-HBtC1HrokNu33xXQzrj7S49t"
        # url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range?vs_currency=usd&from={year}-01-01&to={year+1}-01-01&interval=daily&x_cg_demo_api_key=CG-HBtC1HrokNu33xXQzrj7S49t"
        
        # import pdb;pdb.set_trace()
        print(url)
        response = requests.get(url)
        print(response)
        if response.status_code == 200:
            prices = response.json()['prices']
            print('prices')
            print(prices)
            all_prices += prices
        break
    return dict(all_prices)
        # bitcoin_price_usd = price["market_data"]["current_price"]["usd"]
        # print(f"The price of Bitcoin on {date} was ${bitcoin_price_usd:.2f}")

def main():
    with open('data.json', 'r') as file:
        data = json.load(file)
    data['strategy'] = fetch_strategy()

    company_slugs = fetch_top_companies(10)
    company_slugs = [slug for slug in company_slugs if not 'microstrategy' in slug]
    prices = get_prices()
    print(company_slugs)

    for name in company_slugs:
        results = fetch_company(name,prices)
        print('name',name)
        print('results', results)
        results = fetch_bitcointreasury_company(name)
        if results:
            data[name] = results

    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

    all_rows = []
    for company, rows in data.items():
        all_rows += [{**row, 'company': company} for row in rows]
    all_rows.sort(key=lambda x: datetime.fromisoformat(x['date'].replace("Z", "+00:00")))
    last_row = all_rows[-1]
    for line in fileinput.input(['index.html'], inplace=True):
        if "og:title" in line:
            print(f'<meta property="og:title" content="'\
                  f'{" ".join(map(str.capitalize, last_row["company"].split("-")))}'\
                  f' has acquired {int(last_row["btc"]):,} BTC at ~$'\
                  f'{int(last_row["avg_price_usd"]):,} per bitcoin" />')
        else:
            print(line, end="")


if __name__ == '__main__':
    main()
