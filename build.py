#!/usr/bin/env python3
"""Static site generator for dartvadius.github.io — standard library only.

A fork of platizhka-site/build.py, reshaped from a product site with a blog
into a blog with nothing else: the home page IS the post list. What carried
over unchanged in spirit: content is HTML fragments with a `key: value` header,
hreflang clusters are computed from the files that exist, dates are validated,
and the sitemap only states dates it actually knows.

    python3 build.py            # build docs/
    python3 build.py --drafts   # include posts marked `draft: true`

Output goes to docs/, which GitHub Pages serves (Settings → Pages → main /docs).
Everything in docs/ is generated: it is wiped and rebuilt on every run, so
nothing may be edited there by hand.

URLs, decided once — Pages cannot redirect, so a URL that ships is kept:

    /                 home, page 1 (root language)
    /page/N/          home, page N
    /tag/<tag>/       every post carrying <tag>
    /<slug>/          a post
    /uk/…, /ru/…      the same for the other languages

The slug is the post's file name and is the SAME in every language, which is
what joins translations into one hreflang cluster.
"""

import html
import json
import os
import re
import shutil
import sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs")

with open(os.path.join(ROOT, "content", "site.json"), encoding="utf-8") as _fh:
    CFG = json.load(_fh)

SITE = CFG["site"].rstrip("/")
LANGS = CFG["langs"]
ROOT_LANG = CFG["root_lang"]
UI = CFG["ui"]
TAGS = CFG["tags"]
APP = CFG["app"]
PER_PAGE = 10

# Bare language codes: a region code would target a COUNTRY, and our readers
# are not in one.
OG_LOCALE = {"en": "en_US", "uk": "uk_UA", "ru": "ru_RU"}
PREFIX = {lang: ("" if lang == ROOT_LANG else "/" + lang) for lang in LANGS}
# First path segments a post slug may not take, or it would shadow a section.
RESERVED = {"page", "tag", "assets"} | set(LANGS)


def url_for(lang, rel):
    """rel: '' home, 'page/2', 'tag/<tag>', '<slug>'."""
    return (PREFIX[lang] + "/" + rel).rstrip("/") + "/"


def esc(s):
    return html.escape(s, quote=True)


def read_fragment(path):
    """Split a content file into a `key: value` header and an HTML body."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if "\n---\n" not in raw:
        raise SystemExit("%s: missing '---' between header and body" % path)
    head, body = raw.split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise SystemExit("%s: header line without a colon: %r" % (path, line))
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    body = body.strip()
    if path.endswith(".md"):
        body = markdown_to_html(body, path)
    return meta, body


def markdown_to_html(text, where):
    """A `.md` post body → HTML, through python-markdown, never a parser of our
    own: platizhka-site keeps HTML fragments because a hand-rolled Markdown
    parser is a source of silent formatting bugs, and that reason stands.

    Markdown exists here for an admin UI (Sveltia CMS, if it is ever added)
    and for quick posts; HTML posts stay HTML. Raw HTML passes through, and
    `md_in_html` lets a `<figure markdown>` hold Markdown inside it.

    ⚠ No `smarty`: it turns "…" into English curly quotes, which is wrong in
    Ukrainian and Russian («…»). Typographic characters are typed as such.

    Imported lazily so a site with only HTML posts builds on the bare standard
    library, as it always has.
    """
    try:
        import markdown
    except ImportError:
        raise SystemExit("%s: a .md post needs python-markdown — pip3 install --user markdown"
                         % where)
    return markdown.markdown(text, extensions=["extra", "sane_lists"],
                             output_format="html")


def stamp_date(value, where, allow_future=False):
    """Validate a header date. ⚠ Fails the build rather than ship a doubtful
    date: a wrong lastmod is invisible to us and makes search engines distrust
    every lastmod on the site."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise SystemExit("%s: date %r is not YYYY-MM-DD" % (where, value))
    if parsed > date.today() and not allow_future:
        raise SystemExit("%s: date %r is in the future" % (where, value))
    return parsed


def human_date(d, lang):
    t = UI[lang]
    return (t["date"].replace("{M}", t["months"][d.month - 1])
            .replace("{d}", str(d.day)).replace("{y}", str(d.year)))


def minutes(body):
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    return max(1, round(words / 200))


def hreflang_block(rel_by_lang):
    out = ['<link rel="alternate" hreflang="%s" href="%s%s">' % (l, SITE, url_for(l, r))
           for l, r in rel_by_lang.items()]
    if ROOT_LANG in rel_by_lang:
        out.append('<link rel="alternate" hreflang="x-default" href="%s%s">'
                   % (SITE, url_for(ROOT_LANG, rel_by_lang[ROOT_LANG])))
    return "\n".join(out)


def langswitch(rel_by_lang, current):
    """⚠ A language without this page is left out, not shown disabled — the
    owner's call (2026-10-30, mock post.html state 3)."""
    out = []
    for lang in LANGS:
        if lang not in rel_by_lang:
            continue
        if lang == current:
            out.append('<a class="on" aria-current="true" href="%s" hreflang="%s" lang="%s">%s</a>'
                       % (url_for(lang, rel_by_lang[lang]), lang, lang, lang.upper()))
        else:
            out.append('<a href="%s" hreflang="%s" lang="%s">%s</a>'
                       % (url_for(lang, rel_by_lang[lang]), lang, lang, lang.upper()))
    return "".join(out)


def app_url(referrer):
    return "%s&referrer=%s" % (APP["install_url"], APP[referrer])


def render(template, lang, rel_by_lang, title, description, body, jsonld,
           og_type="website", og_image=None):
    t = UI[lang]
    subs = {
        # BODY first: fragments may carry {{APP_URL}}, and the loop is ordered.
        "BODY": body,
        "LANG": lang,
        "TITLE": esc(title),
        "DESCRIPTION": esc(description),
        "CANONICAL": SITE + url_for(lang, rel_by_lang[lang]),
        "HREFLANG": hreflang_block(rel_by_lang),
        "OG_TYPE": og_type,
        "OG_LOCALE": OG_LOCALE.get(lang, lang),
        # Absolute: the OG spec requires it and scrapers do not resolve paths.
        "OG_IMAGE": SITE + (og_image or "/assets/img/globe-poster.webp"),
        "JSONLD": json.dumps(jsonld, ensure_ascii=False, separators=(",", ":")),
        "SITE_NAME": esc(CFG["site_name"]),
        "HOME": url_for(lang, ""),
        "LANGSWITCH": langswitch(rel_by_lang, lang),
        "L_LANGUAGE": esc(t["language"]),
        "MASTODON": CFG["mastodon"],
        "HOME_APP_URL": app_url("referrer_home"),
        "FOOT_APP_URL": app_url("referrer_footer"),
        "L_FOOT_APP": esc(t["foot_app"]),
        "PRIVACY_URL": APP["privacy_url"],
        "L_PRIVACY": esc(t["privacy"]),
        "YEAR": str(date.today().year),
        "FEED": feed_path(lang),
        "L_FEED_TITLE": esc(t["home_title"]),
    }
    page = template
    for key, value in subs.items():
        page = page.replace("{{%s}}" % key, value)
    left = re.findall(r"\{\{([A-Z_]+)\}\}", page)
    if left:
        raise SystemExit("unresolved placeholders: %s" % sorted(set(left)))
    return page


def tag_label(tag, lang):
    return TAGS[tag][lang]


def item_html(lang, slug, meta):
    """One row of a post list — mock home.html, `.item`."""
    primary = meta["_tags"][0]
    cover = ('<img src="%s" alt="" loading="lazy" width="960" height="540">' % esc(meta["cover"])
             if meta.get("cover") else "")
    return ('<a class="item" href="%s">%s<div><div class="meta"><b>%s</b> · %s</div>'
            '<h3>%s</h3><p>%s</p></div></a>'
            % (url_for(lang, slug), cover, esc(tag_label(primary, lang)),
               human_date(meta["_date"], lang), esc(meta["title"]), esc(meta["summary"])))


def pager_html(lang, idx, total):
    if total < 2:
        return ""
    t = UI[lang]
    rel = lambda n: "" if n == 1 else "page/%d" % n
    bits = []
    if idx > 1:
        bits.append('<a class="pg" rel="prev" href="%s">%s</a>' % (url_for(lang, rel(idx - 1)), t["newer"]))
    for n in range(1, total + 1):
        if n == idx:
            bits.append('<span class="pg on" aria-current="page">%d</span>' % n)
        else:
            bits.append('<a class="pg" href="%s">%d</a>' % (url_for(lang, rel(n)), n))
    if idx < total:
        bits.append('<a class="pg" rel="next" href="%s">%s</a>' % (url_for(lang, rel(idx + 1)), t["older"]))
    return '<nav class="pager">%s</nav>' % "".join(bits)


FEED_SIZE = 20


def absolutize(fragment):
    """Root-relative src/href → absolute. A feed reader has no base URL, so
    `/assets/img/x.webp` inside an item would point at the reader's own host."""
    return re.sub(r'(\s(?:src|href|poster)=")/(?!/)', r'\1%s/' % SITE, fragment)


def rss(lang, items):
    """RSS 2.0 for one language, newest FEED_SIZE posts, full text.

    Full text rather than a summary on purpose: the readers this blog wants —
    Mastodon people, map blogs like The Map Room — read in feed readers, and a
    teaser that forces a click is the reason people unsubscribe.
    """
    from email.utils import format_datetime
    from datetime import datetime, timezone
    t = UI[lang]
    entries = []
    for slug, meta, body in items[:FEED_SIZE]:
        link = SITE + url_for(lang, slug)
        when = datetime(meta["_date"].year, meta["_date"].month, meta["_date"].day,
                        tzinfo=timezone.utc)
        cover = ('<p><img src="%s%s" alt=""></p>' % (SITE, esc(meta["cover"]))
                 if meta.get("cover") else "")
        content = cover + absolutize(body)
        entries.append(
            "<item><title>%s</title><link>%s</link><guid isPermaLink=\"true\">%s</guid>"
            "<pubDate>%s</pubDate>%s<description>%s</description>"
            "<content:encoded><![CDATA[%s]]></content:encoded></item>"
            % (esc(meta["title"]), link, link, format_datetime(when),
               "".join("<category>%s</category>" % esc(tag_label(tg, lang))
                       for tg in meta["_tags"]),
               esc(meta["description"]), content.replace("]]>", "]]]]><![CDATA[>")))
    feed_url = SITE + feed_path(lang)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
            'xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            '<title>%s</title><link>%s</link><description>%s</description>'
            '<language>%s</language>'
            '<atom:link href="%s" rel="self" type="application/rss+xml"/>%s'
            '</channel></rss>\n'
            % (esc(t["home_title"]), SITE + url_for(lang, ""), esc(t["home_desc"]),
               lang, feed_url, "".join(entries)))


def feed_path(lang):
    return PREFIX[lang] + "/feed.xml"


def main():
    drafts = "--drafts" in sys.argv[1:]
    with open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8") as fh:
        template = fh.read()

    # ── collect posts: slug -> {lang: (meta, body)} ──────────────────────
    posts = {}
    for lang in LANGS:
        d = os.path.join(ROOT, "content", lang, "posts")
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            slug, ext = os.path.splitext(name)
            if ext not in (".html", ".md"):
                continue
            where = "%s/posts/%s" % (lang, name)
            if slug in posts and lang in posts[slug]:
                raise SystemExit("%s: the same slug exists as both .html and .md" % where)
            if slug in RESERVED or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
                raise SystemExit("%s: slug must be lowercase-hyphenated and not one of %s"
                                 % (where, sorted(RESERVED)))
            meta, body = read_fragment(os.path.join(d, name))
            draft = meta.get("draft") == "true"
            if draft and not drafts:
                continue
            for field in ("title", "description", "summary", "date", "tags"):
                if field not in meta:
                    raise SystemExit("%s: header is missing '%s'" % (where, field))
            meta["_date"] = stamp_date(meta["date"], where, allow_future=draft)
            meta["_tags"] = [t.strip() for t in meta["tags"].split(",") if t.strip()]
            unknown = [t for t in meta["_tags"] if t not in TAGS]
            if not meta["_tags"] or unknown:
                raise SystemExit("%s: unknown or empty tags %r (site.json lists %s)"
                                 % (where, unknown, sorted(TAGS)))
            posts.setdefault(slug, {})[lang] = (meta, body)

    # Tags must agree across translations, or one post would sit on a tag page
    # in one language and not in another.
    for slug, per in posts.items():
        sets = {tuple(m["_tags"]) for m, _ in per.values()}
        if len(sets) > 1:
            raise SystemExit("%s: tags differ between languages: %s" % (slug, sets))

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    built, lastmod = [], {}

    def write(lang, rel, page, stamp=None):
        path = url_for(lang, rel)
        dest = os.path.join(OUT, path.lstrip("/"), "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(page)
        built.append(path)
        if stamp:
            lastmod[path] = stamp.isoformat()

    by_lang = {lang: sorted(((s, per[lang][0], per[lang][1]) for s, per in posts.items()
                             if lang in per), key=lambda it: it[1]["_date"], reverse=True)
               for lang in LANGS}

    # ── home, paginated ──────────────────────────────────────────────────
    # A language with no posts still gets page 1: the root has to hold real
    # content (Pages cannot redirect), and the hero alone is that content.
    pages = {lang: [lst[i:i + PER_PAGE] for i in range(0, len(lst), PER_PAGE)] or [[]]
             for lang, lst in by_lang.items()}
    for lang in LANGS:
        t, chunks = UI[lang], pages[lang]
        hero_path = os.path.join(ROOT, "content", lang, "hero.html")
        with open(hero_path, encoding="utf-8") as fh:
            hero = fh.read().strip()
        for idx, chunk in enumerate(chunks, start=1):
            rel = "" if idx == 1 else "page/%d" % idx
            avail = {l: rel for l in LANGS if len(pages[l]) >= idx}
            head = (hero if idx == 1 else
                    '<div class="pagehead"><span class="meta">%s</span></div>'
                    % t["page_of"].replace("{n}", str(idx)).replace("{total}", str(len(chunks))))
            body = ('<div class="shell">%s<div class="list">%s</div>%s</div>'
                    % (head, "".join(item_html(lang, s, m) for s, m, _ in chunk),
                       pager_html(lang, idx, len(chunks))))
            title = t["home_title"] + ("" if idx == 1 else " — " + t["page_of"]
                                       .replace("{n}", str(idx)).replace("{total}", str(len(chunks))))
            jsonld = {"@context": "https://schema.org", "@type": "Blog", "name": title,
                      "url": SITE + url_for(lang, rel), "inLanguage": lang,
                      "author": {"@type": "Person", "name": CFG["author"]},
                      "blogPost": [{"@type": "BlogPosting", "headline": m["title"],
                                    "datePublished": m["date"],
                                    "author": {"@type": "Person", "name": CFG["author"]},
                                    "url": SITE + url_for(lang, s)} for s, m, _ in chunk]}
            write(lang, rel, render(template, lang, avail, title, t["home_desc"], body, jsonld),
                  max((m["_date"] for _, m, _ in chunk), default=None))

    # ── tag pages (not paginated until a tag outgrows a screen) ──────────
    for tag in TAGS:
        per_lang = {l: [it for it in by_lang[l] if tag in it[1]["_tags"]] for l in LANGS}
        avail = {l: "tag/" + tag for l in LANGS if per_lang[l]}
        for lang in avail:
            t = UI[lang]
            label = tag_label(tag, lang)
            body = ('<div class="shell"><div class="pagehead"><span class="meta">%s</span>'
                    '<h1>%s</h1></div><div class="list">%s</div></div>'
                    % (t["tag"], esc(label),
                       "".join(item_html(lang, s, m) for s, m, _ in per_lang[lang])))
            jsonld = {"@context": "https://schema.org", "@type": "CollectionPage",
                      "name": label, "url": SITE + url_for(lang, "tag/" + tag), "inLanguage": lang}
            write(lang, "tag/" + tag,
                  render(template, lang, avail, "%s — %s" % (label, CFG["site_name"]),
                         t["home_desc"], body, jsonld),
                  max(m["_date"] for _, m, _ in per_lang[lang]))

    # ── posts ────────────────────────────────────────────────────────────
    for lang in LANGS:
        t, lst = UI[lang], by_lang[lang]
        for i, (slug, meta, body) in enumerate(lst):
            avail = {l: slug for l in LANGS if l in posts[slug]}
            chips = "".join('<a class="chip on" href="%s">%s</a>'
                            % (url_for(lang, "tag/" + tg), esc(tag_label(tg, lang)))
                            for tg in meta["_tags"])
            cover = ('<div class="wide"><img src="%s" alt="%s" width="960" height="540"></div>'
                     % (esc(meta["cover"]), esc(meta.get("cover_alt", "")))
                     if meta.get("cover") else "")
            head = ('<div class="post post--head"><div class="crumbs">%s</div><h1>%s</h1>'
                    '<p class="dek">%s</p><div class="byline"><span class="meta">%s · %s · %s</span>'
                    '</div></div>'
                    % (chips, esc(meta["title"]), esc(meta["description"]), esc(CFG["author"]),
                       human_date(meta["_date"], lang),
                       t["min_read"].replace("{n}", str(minutes(body)))))
            # ⚠ The app block stays at the end of every post although the footer
            # links the app too: a reader arriving from search does not read
            # footers (owner agreed, 2026-10-30).
            app = ('<div class="app cta"><img src="%s" alt=""><div><strong>%s</strong>'
                   '<span>%s</span></div><a class="btn" href="%s">%s</a></div>'
                   % (APP["icon"], esc(APP["name"]), esc(t["app_line"]),
                      app_url("referrer_post"), esc(t["app_btn"])))
            # lst is newest first: the «previous» post is the next one in it.
            nav = []
            if i + 1 < len(lst):
                s, m, _ = lst[i + 1]
                nav.append('<a href="%s"><span class="meta">%s</span><strong>%s</strong></a>'
                           % (url_for(lang, s), t["previous"], esc(m["title"])))
            if i > 0:
                s, m, _ = lst[i - 1]
                nav.append('<a href="%s"><span class="meta">%s</span><strong>%s</strong></a>'
                           % (url_for(lang, s), t["next"], esc(m["title"])))
            page_body = ('<article>%s%s<div class="post prose">%s%s<nav class="pn">%s</nav></div></article>'
                         % (head, cover, body, app, "".join(nav)))
            jsonld = {"@context": "https://schema.org", "@type": "BlogPosting",
                      "headline": meta["title"], "description": meta["description"],
                      "datePublished": meta["date"],
                      "dateModified": meta.get("updated", meta["date"]),
                      "inLanguage": lang, "mainEntityOfPage": SITE + url_for(lang, slug),
                      "author": {"@type": "Person", "name": CFG["author"], "url": CFG["mastodon"]},
                      "keywords": [tag_label(tg, lang) for tg in meta["_tags"]]}
            if meta.get("cover"):
                jsonld["image"] = SITE + meta["cover"]
            stamp = stamp_date(meta.get("updated", meta["date"]), "%s/%s" % (lang, slug),
                               allow_future=meta.get("draft") == "true")
            write(lang, slug,
                  render(template, lang, avail, meta["title"], meta["description"], page_body,
                         jsonld, og_type="article", og_image=meta.get("cover")),
                  stamp)

    # ── feeds ────────────────────────────────────────────────────────────
    for lang in LANGS:
        with open(os.path.join(OUT, feed_path(lang).lstrip("/")), "w", encoding="utf-8") as fh:
            fh.write(rss(lang, by_lang[lang]))

    # ── static assets, sitemap, robots, llms ─────────────────────────────
    shutil.copytree(os.path.join(ROOT, "static"), os.path.join(OUT, "assets"))
    root_files = os.path.join(ROOT, "root")
    if os.path.isdir(root_files):
        for name in os.listdir(root_files):
            shutil.copy(os.path.join(root_files, name), OUT)
    # Pages would otherwise run Jekyll over docs/, which skips _-prefixed paths.
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    urls = "".join("<url><loc>%s%s</loc>%s</url>"
                   % (SITE, p, "<lastmod>%s</lastmod>" % lastmod[p] if p in lastmod else "")
                   for p in built)
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns='
                 '"http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n' % urls)
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE)
    with open(os.path.join(OUT, "llms.txt"), "w", encoding="utf-8") as fh:
        fh.write("# %s\n\n> %s\n\n## Pages\n%s\n"
                 % (CFG["site_name"], UI[ROOT_LANG]["home_desc"],
                    "\n".join("- %s%s" % (SITE, p) for p in built)))

    print("built %d pages%s" % (len(built), " (with drafts)" if drafts else ""))
    for p in built:
        print("  ", p)


if __name__ == "__main__":
    main()
