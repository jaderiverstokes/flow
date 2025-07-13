# Bitcoin Treasury Purchases Viewer

This project contains a small website that fetches bitcoin purchase data from
* [strategy.com](https://www.strategy.com/purchases)
* [metaplanet.jp](https://metaplanet.jp/en/analytics)

The server scrapes these pages and exposes an API used by the client. Due to
network restrictions in some environments (including this repository), the data
may not load during development.

## Usage

Install dependencies with `npm install` and start the server:

```bash
node server.js
```

Then open <http://localhost:3000> to view the purchase tables.
