"""Check publication boundaries, private data, links, and language consistency.

Uses only Python's standard library. Matched private values are never printed.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from i18n import LANGUAGES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
MODE = sys.argv[1] if len(sys.argv) > 1 else "output"
FAILURES = []
SNAPSHOT = ROOT / ".translation-work" / "source-checksums.json"
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


def source_pages():
    return sorted(ROOT.glob("*.qmd")) + sorted(ROOT.glob("essays/*.qmd"))


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_pages()}


def draft(path):
    text = path.read_text(encoding="utf-8")
    front = text.split("---", 2)[1] if text.startswith("---") and text.count("---") >= 2 else ""
    return bool(re.search(r"^draft:\s*true\s*(?:#.*)?$", front, re.M | re.I))


def site_url():
    configured = os.environ.get("SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/") + "/"
    profile = ROOT / "_quarto-publish.yml"
    if profile.exists():
        return json.loads(profile.read_text(encoding="utf-8"))["website"]["site-url"]
    return "/"


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.ids = set()
        self.h1 = 0
        self.math = 0
        self.math_blocks = []
        self.math_capture = None
        self.active_external = []
        self.elements = []
        self.has_content = False
        self.lang = ""
        self.language_links = []
        self.language_navs = 0
        self.navbar_items = 0
        self.in_language_nav = False
        self.comments = []
        self.comment_buttons = 0
        self.backlinks = []

    @property
    def empty(self):
        return self.elements == ["html"] and not self.has_content

    def handle_starttag(self, tag, attrs):
        self.elements.append(tag)
        attrs = dict(attrs)
        if tag != "html" or set(attrs) - {"xmlns", "lang", "xml:lang"}:
            self.has_content = True
        if tag == "html":
            self.lang = attrs.get("lang", "")
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        self.h1 += tag == "h1"
        self.math += tag == "math"
        if tag == "math":
            self.math_capture = []
        if self.math_capture is not None:
            self.math_capture.append(("start", tag, tuple(sorted(attrs.items()))))
        classes = attrs.get("class", "").split()
        if tag == "li" and "nav-item" in classes:
            self.navbar_items += 1
        if tag == "nav" and "language-switch" in classes:
            self.language_navs += 1
            self.in_language_nav = True
        if tag == "a" and self.in_language_nav:
            self.language_links.append(attrs)
        if tag == "section" and "article-comments" in classes:
            self.comments.append(attrs)
        if tag == "button" and "data-load-comments" in attrs:
            self.comment_buttons += 1
        if tag == "meta" and attrs.get("name") == "giscus:backlink":
            self.backlinks.append(attrs.get("content", ""))
        for attr in ("href", "src", "poster"):
            if attrs.get(attr):
                self.links.append((tag, attr, attrs[attr]))
        active = attrs.get("src") or attrs.get("poster")
        if tag == "link" and any(x in attrs.get("rel", "").split() for x in ("stylesheet", "preload", "preconnect", "dns-prefetch")):
            active = attrs.get("href")
        if active and (urlsplit(active).scheme in ("http", "https") or active.startswith("//")):
            self.active_external.append(active)

    def handle_endtag(self, tag):
        if self.math_capture is not None:
            self.math_capture.append(("end", tag))
            if tag == "math":
                self.math_blocks.append(tuple(self.math_capture))
                self.math_capture = None
        if tag == "nav":
            self.in_language_nav = False

    def handle_data(self, data):
        if data.strip():
            self.has_content = True
            if self.math_capture is not None:
                self.math_capture.append(("text", re.sub(r"\s+", " ", data.strip())))

    def handle_comment(self, data):
        self.has_content = True


def resolve_local(path, raw, public_url, report=True):
    """Resolve same-site URLs without letting a link escape the output tree."""
    u, public = urlsplit(raw), urlsplit(public_url)
    if u.scheme or raw.startswith("//"):
        if u.scheme not in ("http", "https") or not public.netloc or u.netloc != public.netloc:
            return None
    decoded = unquote(u.path)
    if decoded.startswith("/"):
        if not u.scheme and path.name != "404.html":
            if report:
                fail(path, "unexpected root-relative asset or link")
            return None
        prefix = public.path or "/"
        if prefix != "/":
            if not decoded.startswith(prefix):
                # A different project on the same host is not a local page.
                if u.scheme:
                    return None
                if report:
                    fail(path, "root-relative link is outside the website base path")
                return None
            decoded = decoded[len(prefix):]
        target = (OUT / decoded.lstrip("/")).resolve()
    else:
        target = (path.parent / decoded).resolve() if decoded else path
    if target.is_dir():
        target /= "index.html"
    if not target.is_relative_to(OUT.resolve()) or not target.exists():
        if report:
            fail(path, "broken local link")
        return None
    return target


def check_multilingual(pages, public_url):
    sources = source_pages()
    config_path = ROOT / "_i18n" / "giscus.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    required = {"repo", "repo-id", "category", "category-id"}
    valid_config = all(isinstance(config.get(k), str) for k in required)
    if not valid_config or not all(config[k].strip() for k in required - {"category-id"}):
        fail(config_path, "missing public discussion configuration")
    comments_ready = valid_config and all(config[k].strip() for k in required)
    expected_paths = set()
    shared_terms = {}
    for source in sources:
        relative = source.relative_to(ROOT).with_suffix(".html")
        original = (OUT / relative).resolve()
        original_page = pages.get(original)
        for locale, hreflang in LANGUAGES.items():
            prefix = Path() if locale == "en" else Path(locale)
            path = (OUT / prefix / relative).resolve()
            expected_paths.add(path)
            page = pages.get(path)
            if page is None:
                fail(path, "missing language version")
                continue
            if draft(source):
                if not page.empty:
                    fail(path, "draft contains published content")
                continue
            if page.empty:
                fail(path, "published source produced an empty page")
                continue
            for asset in ("community.css", "community.js"):
                version = hashlib.sha256((ROOT / "assets" / asset).read_bytes()).hexdigest()[:12]
                if not any(Path(urlsplit(raw).path).name == asset and urlsplit(raw).query == "v=" + version
                           for _, _, raw in page.links):
                    fail(path, "language and comment assets must use their current content version")
            valid_langs = {hreflang, "zh"} if locale == "zh" else {hreflang}
            if page.lang not in valid_langs:
                fail(path, "incorrect document language")
            expected_navbar = json.loads((ROOT / "_i18n/ui.json").read_text(encoding="utf-8"))[locale]["website"]["navbar"]["left"]
            if page.navbar_items != len(expected_navbar):
                fail(path, "navigation entries were duplicated or omitted during profile merge")
            links = {a.get("hreflang"): a for a in page.language_links}
            if page.language_navs != 1 or len(page.language_links) != len(LANGUAGES) or set(links) != set(LANGUAGES.values()):
                fail(path, "expected one complete language switch")
            else:
                for target_locale, target_lang in LANGUAGES.items():
                    target_prefix = Path() if target_locale == "en" else Path(target_locale)
                    expected = (OUT / target_prefix / relative).resolve()
                    a = links[target_lang]
                    actual = resolve_local(path, a.get("href", ""), public_url, report=False)
                    if actual != expected or a.get("lang") != target_lang:
                        fail(path, "language switch does not target the corresponding page")
                    if (a.get("aria-current") == "page") != (locale == target_locale):
                        fail(path, "incorrect current language indicator")
            if original_page and not original_page.empty:
                if page.math_blocks != original_page.math_blocks:
                    fail(path, "mathematical expressions differ from the English page")
                # Quarto derives dropdown IDs from localized navigation labels.
                # Content anchors must remain stable; those UI IDs need not.
                missing = {item for item in original_page.ids - page.ids if not item.startswith("nav-menu-")}
                if missing:
                    fail(path, "translated page is missing original heading or element IDs")
            is_article = relative.parts[0] == "essays"
            if not is_article:
                if page.comments:
                    fail(path, "comments attached to a non-article page")
                continue
            if len(page.comments) != 1:
                fail(path, "expected one article comment section")
                continue
            attrs = page.comments[0]
            expected_term = "article:" + relative.stem
            if attrs.get("data-term") != expected_term:
                fail(path, "incorrect shared article discussion key")
            shared_terms.setdefault(expected_term, set()).add(relative.as_posix())
            for key in required:
                if attrs.get("data-" + key) != config.get(key):
                    fail(path, "discussion configuration differs from the public configuration")
            if attrs.get("data-lang") != hreflang:
                fail(path, "incorrect comment interface language")
            if page.comment_buttons != int(comments_ready):
                fail(path, "comment loader does not match the actual setup state")
            discussion_url = "https://github.com/" + str(config.get("repo", "")) + "/discussions"
            if not any(tag == "a" and attr == "href" and raw == discussion_url for tag, attr, raw in page.links):
                fail(path, "missing GitHub discussion fallback link")
            expected_backlink = public_url.rstrip("/") + "/" + relative.as_posix()
            if page.backlinks != [expected_backlink]:
                fail(path, "discussion backlink must identify the English article")
    for path in pages.keys() - expected_paths:
        fail(path, "unexpected page outside the authored language versions")
    sitemap = OUT / "sitemap.xml"
    expected_urls = {
        public_url.rstrip("/") + "/" + ("" if locale == "en" else locale + "/")
        + source.relative_to(ROOT).with_suffix(".html").as_posix()
        for locale in LANGUAGES for source in sources
        if source.name != "404.qmd" and not draft(source)
    }
    try:
        locations = [node.text for node in ET.parse(sitemap).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        if not expected_urls.issubset(locations) or len(locations) != len(set(locations)):
            fail(sitemap, "sitemap must include unique URLs for every published language edition")
    except (OSError, ET.ParseError):
        fail(sitemap, "missing or invalid multilingual sitemap")
    if any(len(paths) != 1 for paths in shared_terms.values()):
        fail(OUT, "different articles share a discussion key")
    for locale in LANGUAGES:
        prefix = Path() if locale == "en" else Path(locale)
        article = (OUT / prefix / "essays/fourier-frequency-geometry-1.html").resolve()
        if article not in pages or pages[article].math != 47:
            fail(article, "expected all 47 original MathML expressions")


if MODE == "source":
    paths = set(source_pages()) | set(ROOT.glob("templates/*.qmd"))
    paths.update((ROOT / name) for name in ("_quarto.yml", "README.md"))
    for extension in ("html", "svg", "js", "css", "scss"):
        paths.update((ROOT / "assets").rglob("*." + extension))
    paths.update((ROOT / "_i18n").rglob("*.json"))
    for path in sorted(paths):
        scan(path)
    if not FAILURES:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(source_hashes(), sort_keys=True) + "\n", encoding="utf-8")
    print(f"Checked {len(paths)} source and translation files, including any generated cache.")
elif MODE == "output":
    # Cache restoration and optional API translation happen after the initial
    # source gate, so inspect the resulting cache again before publication.
    for cache in sorted((ROOT / "_i18n" / "generated").rglob("*.json")):
        scan(cache)
    htmls = sorted(OUT.rglob("*.html"))
    if not htmls:
        raise SystemExit("No rendered HTML found. Run the website build first.")
    pages = {}
    for path in htmls:
        page = Page()
        page.feed(scan(path))
        pages[path.resolve()] = page
        if page.h1 != 1 and not page.empty:
            fail(path, f"expected one main heading, found {page.h1}")
        if page.active_external:
            fail(path, "external active resource before reader consent")
    public_url = site_url()
    for path, page in pages.items():
        for tag, attr, raw in page.links:
            target = resolve_local(path, raw, public_url)
            fragment = unquote(urlsplit(raw).fragment)
            if target in pages and fragment and fragment not in pages[target].ids:
                fail(path, "missing local anchor")
    multilingual = (ROOT / "scripts/build-multilingual.py").exists() or (ROOT / "_i18n/ui.json").exists() or (OUT / "zh").exists()
    if multilingual:
        check_multilingual(pages, public_url)
    else:
        article = (OUT / "essays/fourier-frequency-geometry-1.html").resolve()
        if article not in pages or pages[article].math != 47:
            fail(article, "expected the first essay and all 47 MathML expressions")
    if SNAPSHOT.exists():
        if json.loads(SNAPSHOT.read_text(encoding="utf-8")) != source_hashes():
            fail(SNAPSHOT, "English QMD source changed after the source check")
    elif multilingual:
        fail(SNAPSHOT, "source snapshot missing; run the source check before building")
    for path in OUT.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(OUT).parts
        forbidden = path.suffix in {".qmd", ".py", ".yml", ".yaml", ".pem", ".key", ".p12", ".pfx"}
        forbidden |= path.name in {"README.md", ".env", "source-checksums.json"} or path.name.startswith(".env.")
        forbidden |= any(part in {"_i18n", ".translation-work", ".i18n-build", ".git", "private", "drafts"} for part in parts)
        if forbidden:
            fail(path, "unexpected source, cache, or private file in public output")
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and "segments" in value and "version" in value:
                fail(path, "translation cache in public output")
        # Only scan authored assets, not bundled third-party libraries.
        if "assets" in parts and path.suffix in {".js", ".css", ".svg", ".html"}:
            scan(path)
    print(f"Checked {len(htmls)} pages, local links, and {sum(p.math for p in pages.values())} MathML expressions.")
else:
    raise SystemExit("Usage: python scripts/check-site.py source|output")

if FAILURES:
    print("Publication checks failed:\n" + "\n".join(FAILURES))
    raise SystemExit(1)
print("Publication checks passed.")
