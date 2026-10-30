#!/usr/bin/env python3
"""Tell search engines that pages changed, instead of waiting to be crawled.

IndexNow: participating engines share submissions with each other, so one ping
reaches Bing (and therefore DuckDuckGo and ChatGPT's search) plus the rest.
Google does not participate — it is reached through the sitemap and Search
Console, which is why both exist.

    python3 notify.py                 # submit every URL in sitemap.xml
    python3 notify.py /blog/slug/     # submit specific paths

Ownership is proven by root/<key>.txt, which build.py copies to the site root;
do not delete it. Run after the push has gone live, not before.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = "https://api.indexnow.org/indexnow"


def main():
    with open(os.path.join(ROOT, "content", "site.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    site, key = cfg["site"].rstrip("/"), cfg["indexnow_key"]

    if len(sys.argv) > 1:
        urls = [site + a if a.startswith("/") else a for a in sys.argv[1:]]
    else:
        with open(os.path.join(ROOT, "docs", "sitemap.xml"), encoding="utf-8") as fh:
            urls = re.findall(r"<loc>([^<]+)</loc>", fh.read())
    if not urls:
        raise SystemExit("nothing to submit — run build.py first")

    payload = json.dumps({
        "host": site.split("//", 1)[1],
        "key": key,
        "keyLocation": "%s/%s.txt" % (site, key),
        "urlList": urls,
    }).encode()

    req = urllib.request.Request(ENDPOINT, data=payload,
                                headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("IndexNow %s for %d URL(s)" % (resp.status, len(urls)))
    except urllib.error.HTTPError as err:
        # 422 usually means the key file is not reachable yet; 429 means slow down.
        print("IndexNow refused: %s %s" % (err.code, err.reason))
        print(err.read().decode("utf-8", "replace")[:400])
        raise SystemExit(1)

    for u in urls:
        print("  ", u)


if __name__ == "__main__":
    main()
