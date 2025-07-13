const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');

const app = express();
app.use(express.static('public'));

async function fetchStrategy() {
  try {
    const { data } = await axios.get('https://www.strategy.com/purchases');
    const $ = cheerio.load(data);
    // Assume there's a table with id 'purchase-table'
    const purchases = [];
    $('#purchase-table tbody tr').each((i, row) => {
      const cols = $(row).find('td');
      purchases.push({
        date: $(cols[0]).text().trim(),
        btc: $(cols[1]).text().trim(),
        price: $(cols[2]).text().trim()
      });
    });
    return purchases;
  } catch (err) {
    console.error('Failed to fetch strategy.com data', err.message);
    return [];
  }
}

async function fetchMetaplanet() {
  try {
    const { data } = await axios.get('https://metaplanet.jp/en/analytics');
    const $ = cheerio.load(data);
    const purchases = [];
    // Assume purchase history section has table rows
    $("#purchase-history tbody tr").each((i, row) => {
      const cols = $(row).find('td');
      purchases.push({
        date: $(cols[0]).text().trim(),
        btc: $(cols[1]).text().trim(),
        price: $(cols[2]).text().trim()
      });
    });
    return purchases;
  } catch (err) {
    console.error('Failed to fetch metaplanet.jp data', err.message);
    return [];
  }
}

app.get('/api/purchases', async (req, res) => {
  const strategy = await fetchStrategy();
  const metaplanet = await fetchMetaplanet();
  res.json({ strategy, metaplanet });
});

app.listen(3000, () => {
  console.log('Server listening on http://localhost:3000');
});
