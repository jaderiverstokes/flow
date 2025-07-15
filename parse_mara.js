const fs=require('fs');
const devalue=require('devalue');
let html='';
process.stdin.setEncoding('utf8');
process.stdin.on('data',chunk=>html+=chunk);
process.stdin.on('end',()=>{
  const scripts=[...html.matchAll(/<script type="application\/json"[^>]*>(.*?)<\/script>/g)].map(m=>JSON.parse(m[1]));
  const data=devalue.parse(JSON.parse(scripts[1].body)[0].result.data);
  const rows=data.balances.map(b=>({
    date:b.date.toISOString().split('T')[0],
    btc:Number(b.btcDelta),
    avg_price_usd:Number(b.btcMarketPrice),
    total_cost_usd:Number(b.btcDelta*b.btcMarketPrice)
  }));
  console.log(JSON.stringify(rows));
});
