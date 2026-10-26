# Care Plus Barcode Labels

Prints 40 x 25 mm Arabic/English barcode labels for Care Plus Car Accessories W.L.L items.
Live page: https://audit-wq.github.io/label/

## Refreshing the item list
The item list is built into `index.html`. **Actions → Refresh labels → Run workflow** reads all active
items from Zoho Books and republishes the page (about 2 minutes). It also runs every night at 00:17 Qatar time.

Needs three repository secrets (Settings → Secrets and variables → Actions):
`ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` – from a Zoho "Self Client"
(api-console.zoho.com) with scope `ZohoBooks.settings.READ`.

Files: `scripts/refresh.py` (the refresh), `scripts/template.html` (page without data),
`data/items.json` (last item list, used to look up Arabic names only for new or changed items).
