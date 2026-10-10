"""Check the publication boundary, common privacy leaks, and local links.

Uses only Python's standard library. It reports filenames, never matched values.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
MODE = sys.argv[1] if len(sys.argv) > 1 else "output"
FAILURES = []
PATTERNS = {
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "credential-shaped value": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{35,}|sk-[A-Za-z0-9_-]{25,}|AKIA[A-Z0-9]{16})"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "local user path": re.compile(r"(?:[A-Za-z]:[\\/]Users[\\/]|/Users/|/home/[^/\s]+/|/workspace/|file:///)", re.I),
}


def fail(path, reason):
    FAILURES.append(f"{path.relative_to(ROOT)}: {reason}")


def scan(path):
    text = path.read_text(encoding="utf-8")
    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            fail(path, label)
    return text


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.ids = set()
        self.h1 = 0
        self.math = 0
        self.active_external = []
        self.elements = []
        self.has_content = False

    def handle_starttag(self, tag, attrs):
        self.elements.append(tag)
        attrs = dict(attrs)
        # Quarto's `draft-mode: gone` emits only an empty <html> element.
        # Do not accept attributes that could turn that placeholder into content.
        if tag != "html" or set(attrs) - {"xmlns", "lang", "xml:lang"}:
            self.has_content = True
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        self.h1 += tag == "h1"
        self.math += tag == "math"
        for attr in ("href", "src", "poster"):
            if attrs.get(attr):
                self.links.append((tag, attr, attrs[attr]))
        active = attrs.get("src") or attrs.get("poster")
        if tag == "link" and any(x in attrs.get("rel", "").split() for x in ("stylesheet", "preload", "preconnect", "dns-prefetch")):
            active = attrs.get("href")
        if active and (urlsplit(active).scheme in ("http", "https") or active.startswith("//")):
            self.active_external.append(active)

    def handle_data(self, data):
        if data.strip():
            self.has_content = True

    def handle_comment(self, data):
        self.has_content = True


if MODE == "source":
    paths = [*ROOT.glob("*.qmd"), *ROOT.glob("essays/*.qmd"), *ROOT.glob("templates/*.qmd"), ROOT / "_quarto.yml", ROOT / "README.md"]
    paths += list((ROOT / "assets").glob("*.html")) + list((ROOT / "assets").glob("*.svg"))
    for path in paths:
        scan(path)
    print(f"Checked {len(paths)} publication source files.")
elif MODE == "output":
    htmls = sorted(OUT.rglob("*.html"))
    if not htmls:
        raise SystemExit("No rendered HTML found. Run quarto render first.")
    pages = {}
    for path in htmls:
        page = Page()
        page.feed(scan(path))
        pages[path.resolve()] = page
        empty_placeholder = page.elements == ["html"] and not page.has_content
        if page.h1 != 1 and not empty_placeholder:
            fail(path, f"expected one main heading, found {page.h1}")
        if page.active_external:
            fail(path, "external active resource")
    for path, page in pages.items():
        for tag, attr, raw in page.links:
            u = urlsplit(raw)
            if u.scheme or raw.startswith("//"):
                continue
            decoded = unquote(u.path)
            if decoded.startswith("/"):
                if path.name != "404.html":
                    fail(path, "unexpected root-relative asset or link")
                    continue
                # Quarto intentionally roots 404-page links so they work at any
                # invalid URL. Account for a GitHub project site's base path.
                profile = ROOT / "_quarto-publish.yml"
                prefix = "/"
                if profile.exists():
                    config = json.loads(profile.read_text(encoding="utf-8"))
                    prefix = urlsplit(config["website"]["site-url"]).path
                if prefix != "/" and decoded.startswith(prefix):
                    decoded = decoded[len(prefix):]
                target = (OUT / decoded.lstrip("/")).resolve()
            else:
                target = (path.parent / decoded).resolve() if decoded else path
            if target.is_dir():
                target /= "index.html"
            if not target.is_relative_to(OUT.resolve()) or not target.exists():
                fail(path, f"broken local link: {raw}")
            elif u.fragment and target in pages and unquote(u.fragment) not in pages[target].ids:
                fail(path, f"missing anchor: {raw}")
    article = OUT / "essays/fourier-frequency-geometry-1.html"
    if article.resolve() not in pages or pages[article.resolve()].math < 20:
        fail(article, "expected the first essay and its rendered MathML formulas")
    for path in OUT.rglob("*"):
        if path.is_file() and (path.suffix in {".qmd", ".py", ".yml", ".yaml", ".pem", ".key"} or path.name in {".env", "README.md"}):
            fail(path, "unexpected source or private file in public output")
    print(f"Checked {len(htmls)} pages, local links, and {sum(p.math for p in pages.values())} MathML expressions.")
else:
    raise SystemExit("Usage: python scripts/check-site.py source|output")

if FAILURES:
    print("Publication checks failed:\n" + "\n".join(FAILURES))
    raise SystemExit(1)
print("Publication checks passed.")
