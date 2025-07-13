const express = require('express');
const cors = require('cors');
const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));

const app = express();
app.use(cors());

app.get('/api/strategy', async (req, res) => {
  try {
    const resp = await fetch('https://www.strategy.com/purchases');
    const html = await resp.text();
    const match = html.match(/<script id="__NEXT_DATA__" type="application\/json">([^<]+)/);
    if (!match) return res.status(500).json({ error: 'Unable to parse data' });
    const json = JSON.parse(match[1]);
    const purchases = json.props.pageProps.bitcoinData || [];
    res.json(purchases);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch Strategy data' });
  }
});

app.get('/api/metaplanet', async (req, res) => {
  try {
    const resp = await fetch('https://metaplanet.jp/en/analytics');
    const html = await resp.text();
    const match = html.match(/"ticker":"BTC-PURCHASES-USD"[^\[]*\"chartData\":\[(.*?)\]\}/);
    if (!match) return res.status(500).json({ error: 'Unable to parse data' });
    const data = JSON.parse('[' + match[1] + ']');
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch Metaplanet data' });
  }
});

app.use(express.static('.'));

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});
