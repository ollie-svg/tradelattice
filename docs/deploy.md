# Deploying the site

The site is built with MkDocs Material and hosted on Cloudflare Pages at <https://tradelattice.ca>.

## One-time setup, in order

The domains are registered at GoDaddy. `tradelattice.ca` carries the Google Workspace mail records; those must survive the move.

1. **Cloudflare → Add a site → `tradelattice.ca`** (Free plan). Cloudflare scans existing records; confirm the five Google MX records below are listed before continuing. If any are missing, add them by hand.
2. **GoDaddy → tradelattice.ca → Nameservers → Change** to the two Cloudflare nameservers shown. Propagation takes minutes to a few hours; mail keeps flowing because the MX records are already in Cloudflare.
3. **Workers & Pages → Create → Pages → Connect to Git → `ollie-svg/tradelattice`** with the settings in the table below. First build takes about two minutes.
4. **Pages project → Custom domains → Add `tradelattice.ca`**. Cloudflare creates the CNAME automatically because the zone is on Cloudflare.
5. Repeat step 1 for `tradelattice.org` and `tradelattice.net` (no MX needed), move their nameservers at GoDaddy, then add one proxied `A` record `@ → 192.0.2.1` on each so the zone resolves.
6. **Bulk Redirects → Create list** `tradelattice-aliases` with two entries: `https://tradelattice.org/*` → `https://tradelattice.ca/${1}` and `https://tradelattice.net/*` → `https://tradelattice.ca/${1}`, status 301, preserve query string. Create a rule that enables the list.

## Cloudflare Pages settings

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Build command | `pip install -e .[docs] && mkdocs build --strict` |
| Build output directory | `site` |
| Environment variable | `PYTHON_VERSION=3.12` |
| Custom domain | `tradelattice.ca` |

## Google Workspace mail records (tradelattice.ca)

| Type | Name | Value | Priority |
| --- | --- | --- | --- |
| MX | @ | aspmx.l.google.com | 1 |
| MX | @ | alt1.aspmx.l.google.com | 5 |
| MX | @ | alt2.aspmx.l.google.com | 5 |
| MX | @ | alt3.aspmx.l.google.com | 10 |
| MX | @ | alt4.aspmx.l.google.com | 10 |

Also carry over any `TXT` records at `@` (Google site verification, SPF) and `google._domainkey` (DKIM) if present at GoDaddy.

## Verify

- `https://tradelattice.ca` serves the site with a valid certificate.
- `https://tradelattice.org/privacy/` lands on `https://tradelattice.ca/privacy/`.
- An email from an outside address to `hello@tradelattice.ca` arrives.

## Analytics

The Plausible tag lives in the `extrahead` block of `docs/overrides/main.html`:

```html
<script defer data-domain="tradelattice.ca" src="https://plausible.io/js/script.js"></script>
```

Add `tradelattice.ca` as a site at plausible.io before launch, or the script reports nothing.

## Local preview

```
make docs-serve
```
