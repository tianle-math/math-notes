"""Add same-page language links and consent-gated shared article discussions."""
from html import escape
import json
import os
from pathlib import Path
import posixpath
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
LANGUAGES = {"en": "en", "zh": "zh-CN", "ja": "ja"}
NAMES = {"en": "English", "zh": "中文", "ja": "日本語"}
UI = json.loads((ROOT / "_i18n/ui.json").read_text())
CONFIG = json.loads((ROOT / "_i18n/giscus.json").read_text())
PROFILE = ROOT / "_quarto-publish.yml"
BASE = os.environ.get("SITE_URL", "").rstrip("/")
if not BASE and PROFILE.exists():
    BASE = json.loads(PROFILE.read_text())["website"]["site-url"].rstrip("/")
if not BASE:
    BASE = "https://tianle-math.github.io/math-notes"
if urlsplit(BASE).scheme != "https":
    raise SystemExit("The published website URL must use HTTPS.")


def output_path(locale, relative):
    return relative if locale == "en" else f"{locale}/{relative}"


def relative_href(current, target):
    return posixpath.relpath(target, posixpath.dirname(current) or ".")


def url_for(locale, relative):
    return f"{BASE}/{output_path(locale, relative)}"


def comments(locale, relative):
    labels = UI[locale]["ui"]
    enabled = all(CONFIG.get(key) for key in ("repo", "repo-id", "category", "category-id"))
    attrs = {**CONFIG, "term": "article:" + Path(relative).stem, "lang": LANGUAGES[locale]}
    data = " ".join(f'data-{key}="{escape(str(value), quote=True)}"' for key, value in attrs.items())
    button = f'<button type="button" data-load-comments>{escape(labels["load"])}</button>' if enabled else ""
    pending = {
        "en": "Embedded comments are being set up. You can visit the discussions on GitHub.",
        "zh": "网页内评论正在设置中，你可以先前往 GitHub 讨论区。",
        "ja": "埋め込みコメントは準備中です。GitHub のディスカッションをご利用いただけます。",
    }
    status = "" if enabled else escape(pending[locale])
    return f'''<section id="article-discussion" class="article-comments" {data} aria-labelledby="discussion-heading">
<h2 id="discussion-heading">{escape(labels['comments'])}</h2>
<p class="comments-intro">{escape(labels['intro'])}</p>
<p class="comments-help">{escape(labels['privacy'])}</p>
{button}<p role="status" aria-live="polite">{status}</p>
<div class="giscus"></div>
<a data-discussion-link href="https://github.com/{escape(CONFIG['repo'])}/discussions" target="_blank" rel="noopener noreferrer">{escape(labels['github'])} ↗</a>
</section>'''


count = 0
for path in sorted(OUT.rglob("*.html")):
    source = path.read_text(encoding="utf-8")
    if "<main " not in source or "<!-- multilingual-controls -->" in source:
        continue
    current = path.relative_to(OUT).as_posix()
    first = current.split("/", 1)[0]
    locale = first if first in ("zh", "ja") else "en"
    relative = current[len(locale) + 1:] if locale != "en" else current
    labels = UI[locale]["ui"]
    links = []
    alternatives = []
    for other, lang in LANGUAGES.items():
        target = output_path(other, relative)
        if not (OUT / target).exists():
            raise SystemExit(f"Missing language edition: {target}")
        active = ' aria-current="page"' if other == locale else ""
        links.append(f'<a href="{escape(relative_href(current, target))}" hreflang="{lang}" lang="{lang}"{active}>{NAMES[other]}</a>')
        alternatives.append(f'<link rel="alternate" hreflang="{lang}" href="{escape(url_for(other, relative))}">')
    alternatives.append(f'<link rel="alternate" hreflang="x-default" href="{escape(url_for("en", relative))}">')
    bar = f'<!-- multilingual-controls -->\n<nav class="language-switch" aria-label="{escape(labels["switch"])}">' + "".join(links) + "</nav>"
    source = re.sub(r"(<main\b[^>]*>)", lambda m: m[1] + "\n" + bar, source, count=1)
    is_article = relative.startswith("essays/")
    if is_article:
        article_source = (ROOT / Path(relative).with_suffix(".qmd")).read_text(encoding="utf-8")
        original_locale = "zh" if re.search(r"^original-language:\s*[\"']?zh(?:-CN)?", article_source, re.M) else "en"
        if locale != original_locale:
            original = relative_href(current, output_path(original_locale, relative))
            original_label, translation_label = labels["original"], labels["translation"]
            if original_locale == "zh":
                original_label = {"en": "Chinese original", "ja": "中国語の原文"}[locale]
                translation_label = {"en": "Translated from Chinese.", "ja": "この記事は中国語からの翻訳です。"}[locale]
            note = f'<aside class="translation-note"><p>{escape(translation_label)} <a data-language-link hreflang="{LANGUAGES[original_locale]}" href="{escape(original)}">{escape(original_label)} ↗</a></p></aside>' 
            source = source.replace(bar, bar + note, 1)
        source = source.replace("</main>", comments(locale, relative) + "\n</main>", 1)
        alternatives.append(f'<meta name="giscus:backlink" content="{escape(url_for("en", relative))}">')
    # Reuse the English-root local assets; no third-party resource starts here.
    css = relative_href(current, "assets/community.css")
    js = relative_href(current, "assets/community.js")
    alternatives.extend([f'<link rel="stylesheet" href="{css}">', f'<script src="{js}" defer></script>'])
    source = source.replace("</head>", "\n".join(alternatives) + "\n</head>", 1)
    path.write_text(source, encoding="utf-8")
    count += 1

# Root sitemap exposes all locales to crawlers, while each page advertises peers.
ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
ET.register_namespace("", ns)
main_map = OUT / "sitemap.xml"
if main_map.exists():
    tree = ET.parse(main_map)
    root = tree.getroot()
    existing = {entry.findtext(f"{{{ns}}}loc") for entry in root}
    for locale in ("zh", "ja"):
        localized = OUT / locale / "sitemap.xml"
        if not localized.exists():
            continue
        for entry in ET.parse(localized).getroot():
            location = entry.findtext(f"{{{ns}}}loc")
            if location not in existing:
                root.append(entry)
                existing.add(location)
    tree.write(main_map, encoding="utf-8", xml_declaration=True)
print(f"Added language controls to {count} pages and shared comments to articles.")
