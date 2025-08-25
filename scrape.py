import cloudscraper
import fileinput
import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser
os.environ['TZ'] = 'UTC'

COMPANIES_URL = "https://bitbo.io/treasuries"
DATE_FORMAT = "%Y-%m-%d"
SCRAPER = cloudscraper.create_scraper()


def parse_number(x, round=True):
    if x[-1] == 'M':
        return parse_number(x[:-1], False) * 1_000_000
    if x[-1] == 'B':
        return parse_number(x[:-1], False) * 1_000_000_000
    number = float(x.replace(',', ''))
    if round:
        return int(number)
    return number


def strategy():
    html = SCRAPER.get("https://www.strategy.com/purchases").text

    start = html.find("__NEXT_DATA__")
    json_start = html.index('>', start) + 1
    json_end = html.index('</script>', json_start)
    data = json.loads(html[json_start:json_end])
    return [{
        'date': item['date_of_purchase'],
        'btc': item['count'],
        'avg_price_usd': item['purchase_price'],
        'total_cost_usd': item.get('total_purchase_price'),
        'company': 'strategy'
    } for item in data['props']['pageProps']['bitcoinData']]


def metaplanet():
    html = SCRAPER.get("https://metaplanet.jp/en/analytics").text
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all('table'):
        if table.find('th', string='BTC Acquisitions'):
            break
    data = []
    for row in table.find_all('tr')[2:]:
        cols = [x.text for x in row.find_all('td')]
        data.append({
            'date': parser.parse(cols[1]).strftime(DATE_FORMAT),
            'btc': parse_number(cols[2][1:]),
            'avg_price_usd': parse_number(cols[3][1:]),
            'total_cost_usd': parse_number(cols[4][1:]),
            'company': 'metaplanet'
        })
    return data


def semler():
    return [{
        'date': parser.parse(cols[0]).strftime(DATE_FORMAT),
        'btc': parse_number(cols[1][2:]),
        'avg_price_usd': parse_number(cols[2][1:]),
        'total_cost_usd': parse_number(cols[3][1:]) * 1_000,
        'company': 'semler'
    } for row in
        BeautifulSoup(requests.get(
            "http://ir.semlerscientific.com/purchases").text, "html.parser")
        .find('table')
        .find_all('tr')[2:]
        if (cols := [x.text for x in row.find_all('td')])
    ]


def top_companies(limit):
    html = SCRAPER.get(f"{COMPANIES_URL}/#public").text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find_all('table', class_="treasuries-table")[2]
    return [row.find('td', class_="td-company").find('a')["href"].split('/')[-2]
            for row in table.find_all('tr')[1:limit+1]]


def company(name, prices):
    html = SCRAPER.get(f"{COMPANIES_URL}/{name}").text
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find('table', class_='stats-table')
    if table is None:
        return []
    data = []
    for row in table.find_all('tr')[1:]:
        cols = list(map(lambda x: x.find('span').text, row.find_all('td')))
        date = parser.parse(cols[0]).strftime(DATE_FORMAT)
        bitcoin_price_usd = prices[date]
        btc = parse_number(cols[2]) or parse_number(cols[1])
        data.append({
            "date": date,
            "btc": btc,
            "avg_price_usd": round(bitcoin_price_usd, 3),
            "total_cost_usd": round(bitcoin_price_usd * btc, 2),
            "company": name
        })
    return data


def get_prices():
    with open('prices.json', 'r') as file:
        past_prices = json.load(file)
    response = requests.get(
        "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&interval=daily&x_cg_demo_api_key=CG-HBtC1HrokNu33xXQzrj7S49t")
    if response.status_code == 200:
        new_prices = dict([(datetime.fromtimestamp(
            x[0]/1000).strftime(DATE_FORMAT), round(x[1], 2)) for x in response.json()['prices']])
    return new_prices | past_prices


def og(purchases):
    last_purchase = purchases[-1]
    for line in fileinput.input(['index.html'], inplace=True):
        if "og:title" in line:
            print(f'<meta property="og:title" content="'
                  f'{" ".join(map(str.capitalize, last_purchase["company"].split("-")))}'
                  f' has acquired {int(last_purchase["btc"]):,} BTC at ~$'
                  f'{int(last_purchase["avg_price_usd"]):,} per bitcoin" />')
        else:
            print(line, end="")


def main():
    prices = get_prices()
    with open('prices.json', 'w') as file:
        json.dump(prices, file, indent=2)
    with open('purchases.json', 'r') as file:
        all_purchases = json.load(file)
    companies = set(row['company'] for row in all_purchases)
    last_updated = {company: next(row for row in reversed(
        all_purchases) if row['company'] == company)['date'] for company in companies}
    direct_source = ['microstrategy', 'metaplanet']
    new_rows = sum([company(name, prices) for name in top_companies(
        13) if not name in direct_source], strategy() + metaplanet() + semler())
    count = 0
    for row in new_rows:
        if row['company'] in last_updated and row['date'] <= last_updated[row['company']]:
            continue
        all_purchases.append(row)
        count += 1
    print('new rows: ', count)
    all_purchases.sort(key=lambda x: datetime.fromisoformat(x['date']))
    with open('purchases.json', 'w') as f:
        json.dump(all_purchases, f, indent=2)
    og(all_purchases)


if __name__ == '__main__':
    main()
