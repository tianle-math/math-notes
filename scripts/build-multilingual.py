"""Build English, Simplified Chinese and Japanese sites from one English source.

All edits happen in disposable staging directories. The English QMD files and
reviewed translation caches are never rewritten by this build.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

from i18n import ROOT, TranslationError, documents, ensure_caches, write_json

ASSET_SUFFIXES = {".svg", ".webp", ".png", ".jpg", ".jpeg", ".gif", ".avif", ".ico",
                  ".css", ".scss", ".js", ".html", ".woff", ".woff2", ".ttf", ".otf", ".pdf"}


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
        raise TranslationError("Missing _i18n/ui.json with en, zh and ja website interface strings")
    ui = json.loads(ui_path.read_text(encoding="utf-8"))
    for locale in ("en", "zh", "ja"):
        if locale not in ui:
            raise TranslationError(f"_i18n/ui.json is missing {locale}")
    stages = {}
    for locale in ("en", "zh", "ja"):
        stage = root / ".i18n-build" / locale
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        shutil.copy2(root / "_quarto.yml", stage / "_quarto.yml")
        publish = root / "_quarto-publish.yml"
        if publish.exists():
            shutil.copy2(publish, stage / publish.name)
        else:
            write_json(stage / "_quarto-publish.yml", {"website": {"site-url": base_url}})
        copy_assets(root, stage)
        for doc in docs:
            destination = stage / doc.page
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(doc.render(caches.get(locale, {}), locale, ui[locale]), encoding="utf-8")
        output = root / "_site" if locale == "en" else root / "_site" / locale
        language_url = base_url if locale == "en" else base_url + locale + "/"
        website = {**ui[locale].get("website", {}), "site-url": language_url}
        html_format = {"lang": locale, **ui[locale].get("format", {}).get("html", {})}
        override = {"project": {"output-dir": str(output)}, "website": website,
                    "format": {"html": html_format}}
        write_json(stage / "_quarto-i18n.yml", override)
        stages[locale] = stage
    print(f"Prepared {len(docs)} source pages in English, Chinese and Japanese; English sources unchanged.")
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
