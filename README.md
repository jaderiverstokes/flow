# ₿

````html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Bitcoin Treasury Purchases</title>
<style>
body {font-family: Arial, sans-serif; margin: 40px;}
h1 {color: #333;}
table {border-collapse: collapse; width: 100%; margin-bottom: 40px;}
th, td {border: 1px solid #ccc; padding: 8px;}
</style>
</head>
<body>
<h1>Bitcoin Treasury Purchases</h1>
<label for="companyFilter">Company:</label>
<select id="companyFilter">
  <option value="All">All</option>
</select>
<table id="purchases"></table>
<script>
fetch('data.json')
  .then(r => r.json())
  .then(data => {
    const rows = [
      ...data.strategy.map(r => ({ ...r, company: 'Strategy' })),
      ...data.metaplanet.map(r => ({ ...r, company: 'Metaplanet' }))
    ];
    rows.sort((a, b) => new Date(a.date) - new Date(b.date));

    const filter = document.getElementById('companyFilter');
    Array.from(new Set(rows.map(r => r.company))).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      filter.appendChild(opt);
    });

    const table = document.getElementById('purchases');

    function format(value) {
      return typeof value === 'number' ? value.toLocaleString() : value;
    }

    function render() {
      const company = filter.value;
      const visible = company === 'All' ? rows : rows.filter(r => r.company === company);
      if (!visible.length) {
        table.innerHTML = '<tr><td>No data</td></tr>';
        return;
      }
      const headers = Object.keys(visible[0]);
      table.innerHTML = '<tr>' + headers.map(h => '<th>' + h + '</th>').join('') + '</tr>' +
        visible.map(r => '<tr>' + headers.map(h => '<td>' + format(r[h]) + '</td>').join('') + '</tr>').join('');
    }

    filter.addEventListener('change', render);
    render();
  });
</script>
</body>
</html>
````
