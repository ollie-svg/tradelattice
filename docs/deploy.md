# Deploying the site

The site is built with MkDocs Material and hosted on Cloudflare Pages at <https://tradelattice.ca>.

## Cloudflare Pages settings

| Setting | Value |
| --- | --- |
| Build command | `pip install -e .[docs] && mkdocs build --strict` |
| Build output directory | `site` |
| Environment variable | `PYTHON_VERSION=3.12` |
| Custom domain | `tradelattice.ca` |

## Redirect domains

Add `tradelattice.org` and `tradelattice.net` as Bulk Redirects (301) to `https://tradelattice.ca`.

## Analytics

The Plausible tag lives in the `extrahead` block of `docs/overrides/main.html`:

```html
<script defer data-domain="tradelattice.ca" src="https://plausible.io/js/script.js"></script>
```

## Local preview

```
make docs-serve
```
