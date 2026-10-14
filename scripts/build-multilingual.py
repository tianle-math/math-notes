"""Build English, Simplified Chinese, Japanese and French sites from one English source.

All edits happen in disposable staging directories. The English QMD files and
reviewed translation caches are never rewritten by this build.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

from i18n import LANGUAGES, ROOT, TranslationError, documents, ensure_caches, write_json

ASSET_SUFFIXES = {".svg", ".webp", ".png", ".jpg", ".jpeg", ".gif", ".avif", ".ico",
                  ".css", ".scss", ".js", ".html", ".woff", ".woff2", ".ttf", ".otf", ".pdf"}


def remove_yaml_block(source: str, path: tuple[str, ...]) -> str:
    """Remove a block-mapping key only from a staged, indentation-based config.

    Quarto concatenates profile arrays. A locale's navbar list must therefore
    replace the base list before profile merging, rather than append to it.
    The committed config remains intact for ordinary English-only previews.
    """
    result, stack, skipping = [], [], None
    key_pattern = re.compile(r"^( *)([A-Za-z][\w-]*):(?:\s|$)")
    for line in source.splitlines(keepends=True):
        content = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if skipping is not None:
            if not content or content.startswith("#") or indent > skipping:
                continue
            skipping = None
        match = key_pattern.match(line)
        if match:
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, match.group(2)))
            if tuple(key for _, key in stack) == path:
                skipping = indent
                continue
        result.append(line)
    return "".join(result)


class Navigation(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nav_depth = 0
        self.label_depth = 0
        self.current = []
        self.labels = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav":
            self.nav_depth += 1
        if self.nav_depth and tag == "span" and "menu-text" in attrs.get("class", "").split():
            self.label_depth = 1
            self.current = []
        elif self.label_depth and tag == "span":
            self.label_depth += 1

    def handle_endtag(self, tag):
        if tag == "span" and self.label_depth:
            self.label_depth -= 1
            if self.label_depth == 0:
                self.labels.append(" ".join("".join(self.current).split()))
        if tag == "nav":
            self.nav_depth = max(0, self.nav_depth - 1)

    def handle_data(self, text):
        if self.label_depth:
            self.current.append(text)


def verify_navigation(root: Path, locale: str, stage: Path) -> None:
    """Catch profile-array concatenation in the actual rendered pages."""
    ui = json.loads((root / "_i18n" / "ui.json").read_text(encoding="utf-8"))[locale]
    navbar = ui.get("website", {}).get("navbar", {})
    if "left" not in navbar:
        return
    expected = [item["text"] for side in ("left", "right") for item in navbar.get(side, []) if "text" in item]
    output = root / "_site" if locale == "en" else root / "_site" / locale
    for source in [*stage.glob("*.qmd"), *(stage / "essays").glob("*.qmd")]:
        rendered = output / source.relative_to(stage).with_suffix(".html")
        text = rendered.read_text(encoding="utf-8")
        if "<body" not in text:  # Quarto's unpublished-draft placeholder.
            continue
        navigation = Navigation()
        navigation.feed(text)
        if navigation.labels != expected:
            raise TranslationError(f"{locale}/{rendered.relative_to(output)}: navbar must contain exactly the locale's {len(expected)} labels")


def configured_url(root: Path) -> str:
    profile = root / "_quarto-publish.yml"
    value = os.environ.get("SITE_URL", "").strip()
    if not value and profile.exists():
        value = json.loads(profile.read_text(encoding="utf-8"))["website"]["site-url"]
    if not value:
        raise TranslationError("Set SITE_URL or run scripts/set-site-url.py before building")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise TranslationError("SITE_URL must be the public HTTPS website root")
    return value.rstrip("/") + "/"


def copy_assets(root: Path, stage: Path) -> None:
    for source in (root / "assets").rglob("*"):
        if source.is_file() and source.suffix.lower() in ASSET_SUFFIXES and not any(p.startswith(".") for p in source.relative_to(root).parts):
            destination = stage / source.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def prepare(root: Path, base_url: str) -> dict[str, Path]:
    docs = documents(root)
    caches = ensure_caches(docs, root)
    ui_path = root / "_i18n" / "ui.json"
    if not ui_path.exists():
        raise TranslationError("Missing _i18n/ui.json with website interface strings for every language")
    ui = json.loads(ui_path.read_text(encoding="utf-8"))
    for locale in LANGUAGES:
        if locale not in ui:
            raise TranslationError(f"_i18n/ui.json is missing {locale}")
    stages = {}
    for locale in LANGUAGES:
        stage = root / ".i18n-build" / locale
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        base_config = (root / "_quarto.yml").read_text(encoding="utf-8")
        locale_navbar = ui[locale].get("website", {}).get("navbar", {})
        for side in ("left", "right"):
            if side in locale_navbar:
                base_config = remove_yaml_block(base_config, ("website", "navbar", side))
        (stage / "_quarto.yml").write_text(base_config, encoding="utf-8")
        language_url = base_url if locale == "en" else base_url + locale + "/"
        publish = root / "_quarto-publish.yml"
        publish_settings = json.loads(publish.read_text(encoding="utf-8")) if publish.exists() else {}
        # Both profiles must agree: the publishing profile can take precedence
        # for generated absolute URLs, including the locale's sitemap.
        publish_settings.setdefault("website", {})["site-url"] = language_url
        write_json(stage / "_quarto-publish.yml", publish_settings)
        copy_assets(root, stage)
        for doc in docs:
            destination = stage / doc.page
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(doc.render(caches.get(locale, {}), locale, ui[locale]), encoding="utf-8")
        output = root / "_site" if locale == "en" else root / "_site" / locale
        website = {**ui[locale].get("website", {}), "site-url": language_url}
        html_format = {"lang": locale, **ui[locale].get("format", {}).get("html", {})}
        override = {"project": {"output-dir": str(output)}, "website": website,
                    "format": {"html": html_format}}
        write_json(stage / "_quarto-i18n.yml", override)
        stages[locale] = stage
    print(f"Prepared {len(docs)} source pages in {len(stages)} languages; English sources unchanged.")
    return stages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--quarto", default=os.environ.get("QUARTO_PATH", "quarto"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--skip-finish", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    stages = prepare(root, configured_url(root))
    if args.prepare_only:
        return
    # English must run first: its output cleanup is allowed to replace the whole
    # site, while each subsequent locale owns only its own output subdirectory.
    for locale, stage in stages.items():
        print(f"Rendering {locale}…", flush=True)
        subprocess.run([args.quarto, "render", "--profile", "publish,i18n"], cwd=stage, check=True)
        verify_navigation(root, locale, stage)
    if not args.skip_finish:
        finish = root / "scripts" / "finish-site.py"
        if not finish.exists():
            raise TranslationError("Missing scripts/finish-site.py; multilingual output is not ready to publish")
        subprocess.run([sys.executable, str(finish)], cwd=root, check=True)
    print("Multilingual build finished.")


if __name__ == "__main__":
    try:
        main()
    except (TranslationError, json.JSONDecodeError, FileNotFoundError) as error:
        sys.exit(str(error))
    except subprocess.CalledProcessError:
        sys.exit("Multilingual build failed; do not publish the incomplete output.")
