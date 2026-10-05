#!/usr/bin/env python3
"""Step 1b: each program's description, for the catalog.

    python3 tools/sd-archive/describe.py

Reads every computer_media post from the site's WordPress REST API (the same
site fetch.py read, taken from items.json) and writes descriptions.json in the
work folder: {page URL: {summary, description}}. The summary is the post's
excerpt; the description is its opening paragraph, before the first heading.
Run it again to pick up edits on the site.
"""

import html
import json
import re
import urllib.parse

import common as C
from fetch import get


def text(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def opening(h):
    """The content before its first heading or rule, as text."""
    m = re.search(r"<(hr|h[1-6])\b", h)
    return text(h[:m.start()] if m else h)


def main():
    items = C.load("items.json")
    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(items[0]["page"]))
    out, n = {}, 1
    while True:
        url = "%s/wp-json/wp/v2/computer_media?per_page=100&page=%d&_fields=link,excerpt,content" % (origin, n)
        try:
            posts = json.loads(get(url, 60))
        except Exception as e:                  # noqa: BLE001 -- past the last page WordPress answers 400
            if n > 1 and "400" in str(e):
                break
            raise
        if not posts:
            break
        for p in posts:
            out[p["link"]] = dict(summary=text(p["excerpt"]["rendered"]), description=opening(p["content"]["rendered"]))
        n += 1
    C.save("descriptions.json", out)
    pages = {i["page"] for i in items}
    print("%d posts; %d of %d programs described" % (len(out), sum(1 for p in pages if p in out), len(pages)))


if __name__ == "__main__":
    main()
