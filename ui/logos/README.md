# Bank tenant logos

Served by `GET /logos/{filename}` and referenced from a bank's `logo_url`.

Held locally rather than hot-linked so a tenant still renders its own branding
with no network, and so the demo does not depend on a third party staying up.

| File | Source | Status |
|---|---|---|
| `citi.svg` | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Citi.svg) | Public domain — below the threshold of originality (simple shapes and text) |
| `chase.svg` | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Chase_logo_2007.svg) | Public domain — below the threshold of originality |

Both remain **registered trademarks of their respective owners**. They are used
here only to identify the institution each simulated tenant stands in for. BankSym
tenants are simulations and are not affiliated with, endorsed by, or operated by
these companies. Replace these files if you have licensed brand assets.

To add another: drop an SVG here and set the bank's `logo_url` to `/logos/<name>.svg`.
A bank with no `logo_url`, or whose image fails to load, falls back to a badge
generated from its display name and brand colours.
