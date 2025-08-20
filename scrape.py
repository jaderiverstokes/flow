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
DATE_FORMAT = "%Y-%m-%d"

scraper = cloudscraper.create_scraper(delay=10)

def fetch_strategy():
    html = scraper.get(STRATEGY_URL).text
    start = html.find("__NEXT_DATA__")
    json_start = html.index('>', start) + 1
    json_end = html.index('</script>', json_start)
    data = json.loads(html[json_start:json_end])
    return [{
        'date': item['date_of_purchase'],
        'btc': item['count'],
        'avg_price_usd': item['purchase_price'],
        'total_cost_usd': item.get('total_purchase_price')
    } for item in data['props']['pageProps']['bitcoinData']]

def fetch_top_companies(limit: int = 10):
    url = f"{COMPANIES_URL}/#public"
    html = scraper.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find_all('table', class_="treasuries-table")[2]
    return [row.find('td', class_="td-company").find('a')["href"].split('/')[-2]
            for row in table.find_all('tr')[1:limit+1]]

def fetch_company(name, prices):
    url = f"{COMPANIES_URL}/{name}"
    html = scraper.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find('table', class_='stats-table')
    if table is None:
        return []
    data = []
    for row in table.find_all('tr')[1:]:
        cols = list(map(lambda x: x.find('span').text, row.find_all('td')))
        date = parser.parse(cols[0])
        date_key = date.strftime(DATE_FORMAT)
        parse_number = lambda x: int(float(x.replace(',','')))
        bitcoin_price_usd = prices[date_key]
        btc = parse_number(cols[2]) or parse_number(cols[1])
        data.append({
            "date": date_key,
            "btc": btc,
            "avg_price_usd": round(bitcoin_price_usd, 2),
            "total_cost_usd": round(bitcoin_price_usd * btc, 2),
        })
    return data

def get_prices():
    with open('prices.json', 'r') as file:
        past_prices = json.load(file)
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&interval=daily&x_cg_demo_api_key=CG-HBtC1HrokNu33xXQzrj7S49t"
    response = requests.get(url)
    if response.status_code == 200:
        new_prices = dict([(datetime.fromtimestamp(x[0]/1000).strftime(DATE_FORMAT), round(x[1],2)) for x in response.json()['prices']])
    return past_prices | new_prices

def main():
    prices = get_prices()
    with open('prices.json', 'w') as f:
        json.dump(prices, f, indent=2)

    with open('data.json', 'r') as file:
        data = json.load(file)
    data['strategy'] = fetch_strategy()
    for name in [slug for slug in fetch_top_companies(13) if not 'microstrategy' in slug]:
        results = fetch_company(name, prices)
        if results:
            data[name] = results
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

    all_rows = sum([[{**row, 'company': company} for row in rows] for company, rows in data.items()], [])
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
