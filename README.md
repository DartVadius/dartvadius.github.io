# dartvadius.github.io

A developer blog: how Terrella's screens work, how its maps are made, the data
behind them, and #30DayMapChallenge posts. Three languages — English at the
root, Ukrainian under `/uk/`, Russian under `/ru/`.

## How it is built

`python3 build.py` (standard library only) reads `content/`, `templates/` and
`static/`, and writes the whole site into `docs/`, which GitHub Pages serves
(Settings → Pages → Deploy from branch → `main` / `/docs`). `docs/` is wiped
and regenerated on every run — never edit it by hand, and commit it together
with the sources.

`python3 build.py --drafts` also builds posts marked `draft: true`, for a local
preview: `cd docs && python3 -m http.server`.

The generator is a fork of `platizhka-site/build.py`, reshaped for a site whose
home page is the post list. The design source of truth is the mock in
`design/screens/` (`home.html`, `post.html`); `static/site.css` was lifted from
its `blog.css`.

## URLs — decided once

Pages cannot redirect, so a URL that ships is kept.

| URL | page |
|---|---|
| `/`, `/page/N/` | the post list, 10 per page; page 1 opens with the hero |
| `/tag/<tag>/` | every post with that tag |
| `/<slug>/` | a post |
| `/uk/…`, `/ru/…` | the same in the other languages |

The slug is the post's file name and is the same in every language — that is
what links translations to each other. A post missing in a language is simply
absent there, and the language switch leaves that language out.

## Adding a post

Create `content/<lang>/posts/<slug>.html`: a `key: value` header, a line `---`,
then the body as plain HTML.

```
title:       <title>, <h1>, og:title
description: meta description; also the line under the title on the post
summary:     the one line shown in post lists
date:        YYYY-MM-DD (a future date fails the build, except for drafts)
tags:        comma-separated keys from site.json "tags"; the first is the one
             shown on the card. Must be the same in every language.
cover:       optional, e.g. /assets/img/posts/<slug>/cover.webp (16:9)
cover_alt:   optional
updated:     optional, YYYY-MM-DD
draft:       optional, true
```

Body blocks the stylesheet knows: `<h2>`, `<p>`, `<figure>` + `<figcaption>`,
`<figure><div class="pair">…</div></figure>` for before/after,
`<div class="note">`. A looping clip is
`<video autoplay muted loop playsinline preload="none" poster="…">` with an
MP4 of a few MB at most; anything long goes to YouTube (nocookie).

Images for a post go to `static/img/posts/<slug>/` and are served from
`/assets/img/posts/<slug>/`.

## Decisions (owner, 2026-10-30)

- A blog on github.io, no own domain; under the nickname **dartvadius**.
- No menu, no About, no Terrella page: header = name + language switch; the
  app is linked in the footer and in a block at the end of each post.
- Dark theme only, but every colour is a token in `site.css` so a light theme
  is one more block.
- Public texts do not stress Android: iOS versions are planned.
- Posts are written lightly, without officialese, for readers who are neither
  programmers nor cartographers.
