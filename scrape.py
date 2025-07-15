import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup


STRATEGY_URL = "https://www.strategy.com/purchases"
METAPLANET_URL = "https://metaplanet.jp/en/analytics"
MARA_URL = "https://bitcointreasuries.net/public-companies/mara"


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


def fetch_mara():
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(MARA_URL, headers=headers).text
    soup = BeautifulSoup(html, 'html.parser')

    # The table rows are embedded in hidden <dl> elements
    dls = list(reversed(soup.select('.hidden dl')))
    entries = []
    for dl in dls:
        time = dl.find('time')
        if not time:
            continue
        data = {}
        for div in dl.find_all('div', recursive=False):
            dt = div.find('dt')
            dd = div.find('dd')
            if dt and dd:
                data[dt.get_text(strip=True)] = dd.get_text(strip=True)
        balance = float(data.get('BTC Balance', '0').replace(',', ''))
        entries.append({
            'date': time['datetime'],
            'balance': balance
        })

    # Derive purchases from balance deltas
    purchases = []
    prev = None
    for e in entries:
        delta = e['balance'] if prev is None else e['balance'] - prev
        prev = e['balance']
        if delta > 0:
            purchases.append({
                'date': e['date'],
                'btc': delta,
                'avg_price_usd': None,
                'total_cost_usd': None
            })
    return purchases


def main():
    data = {
        'strategy': fetch_strategy(),
        'metaplanet': fetch_metaplanet(),
        'mara': fetch_mara(),
    }
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    main()
