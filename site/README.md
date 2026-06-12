# ts-pico.com website (Jekyll)

The public TS Pico website, migrated from the old WordPress site at ts-pico.com.
Content is plain Markdown; the site is built with [Jekyll](https://jekyllrb.com/)
and published to GitHub Pages by [`../.github/workflows/pages.yml`](../.github/workflows/pages.yml),
which also mounts the [Web Updater](../web-updater/) at **`/updater/`**.

## Layout

```
site/
├── _config.yml          site config, nav, store links, baseurl
├── index.md             home (English)
├── the-team.md          The Team
├── updates.md           Updates index (lists _posts)
├── picovideo-reservation-list.md
├── es/                  Spanish pages (/es/, /es/equipo/)
├── _posts/              the "Updates" blog (original ts-pico.com URLs kept)
├── _layouts/            default / home / page / post
├── _includes/           head / header / footer
└── assets/
    ├── css/style.css
    └── img/             images pulled from the old site
```

## Editing content

- **A page** → edit the matching `.md` file (Markdown + optional inline HTML).
- **An update/blog post** → add a file to `_posts/` named
  `YYYY-MM-DD-title.md` with front matter (`layout: post`, `title:`, `date:`).
  It will appear on `/updates/` automatically, at `/updates/title/`.
- **Nav** → edit the `nav:` list in `_config.yml`.
- **Store links** (`buy_tspico`, `buy_picovideo`) → `_config.yml`.

The `/updater/` page is NOT a Jekyll page — it's the `web-updater/` app, mounted
into the built site by the deploy workflow. Edit it under `../web-updater/`.

## Run locally

Needs Ruby ≥ 2.7 (the deploy uses 3.2). From this folder:

```sh
bundle install
bundle exec jekyll serve
# open http://localhost:4000/tspico-firmware-build/
```

(`baseurl` is `/tspico-firmware-build`, so the local URL includes that path.)

## Going live on ts-pico.com

Served today as a GitHub *project* page at
`https://timex-sinclair-projects.github.io/tspico-firmware-build/`. To switch to
the custom domain:

1. `_config.yml`: set `baseurl: ""` and `url: "https://ts-pico.com"`.
2. Add `site/CNAME` containing `ts-pico.com` (and a deploy step copies it, or
   set it in **Settings → Pages → Custom domain**).
3. At your registrar, point `ts-pico.com` at GitHub Pages
   ([apex A/AAAA records + `www` CNAME](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)).

No SEO redirects are set up (the old WordPress URLs map 1:1 except the home page
and `/updater/`, which is new).
