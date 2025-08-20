import cloudscraper
import fileinput
import json
import locale
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser
os.environ['TZ'] = 'UTC'

STRATEGY_URL = "https://www.strategy.com/purchases"
COMPANIES_URL = "https://bitbo.io/treasuries"

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

def fetch_top_companies(limit: int = 10):
    url = f"{COMPANIES_URL}/#public"
    html = scraper.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find_all('table', class_="treasuries-table")[2]
    count = 0
    companies = []
    for row in table.find_all('tr')[1:]:
        company = row.find('td', class_="td-company") # Include 'th' if not extracting headers separately
        link = company.find('a')
        companies.append(link["href"].split('/')[-2])
        count += 1
        if count >= limit:
            break
    return companies

def fetch_company(name, prices):
    url = f"{COMPANIES_URL}/{name}"
    html = scraper.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find('table', class_='stats-table')
    if table is None:
        return []
    data = []
    rows = table.find_all('tr')[1:]
    for row in rows:
        cols = list(map(lambda x: x.find('span').text, row.find_all('td')))
        date_format = "%m/%d/%Y"
        date = parser.parse(cols[0])
        date_key = date.strftime('%Y-%m-%d')
        btc = int(float(cols[2].replace(',','')))
        if btc == 0:
            btc = int(float(cols[1].replace(',','')))
        if date_key in prices:
            bitcoin_price_usd = prices[date_key]
            data.append({
                "date": date_key,
                "btc": btc,
                "avg_price_usd": round(bitcoin_price_usd, 2),
                "total_cost_usd": round(bitcoin_price_usd * btc, 2),
            })
        else:
            print('missed key', date_key)
    return data

def get_prices():
    with open('prices.json', 'r') as file:
        past_prices = json.load(file)
    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&interval=daily&x_cg_demo_api_key=CG-HBtC1HrokNu33xXQzrj7S49t"
    response = requests.get(url)
    if response.status_code == 200:
        new_prices = dict([(datetime.fromtimestamp(x[0]/1000).strftime('%Y-%m-%d'), round(x[1],2)) for x in response.json()['prices']])
    return past_prices | new_prices

def main():
    prices = get_prices()
    with open('prices.json', 'w') as f:
        json.dump(prices, f, indent=2)

    with open('data.json', 'r') as file:
        data = json.load(file)

    data['strategy'] = fetch_strategy()

    company_slugs = fetch_top_companies(13)
    company_slugs = [slug for slug in company_slugs if not 'microstrategy' in slug]

    for name in company_slugs:
        results = fetch_company(name, prices)
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
