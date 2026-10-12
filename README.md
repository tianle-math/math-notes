# Tian · Mathematics & Essays

An open notebook for harmonic analysis, martingale theory, operator algebras, functional analysis, and reflections beyond mathematics. English QMD files are the canonical build source. The build produces matching English, Simplified Chinese, and Japanese editions without rewriting those source files.

The public site is <https://tianle-math.github.io/math-notes/>. English pages retain their existing addresses; translations use the same filenames under `zh/` and `ja/`. The language switch keeps readers on the corresponding page and preserves section anchors. Article discussion keys are shared across all three languages.

## Write and preview

Edit the English `.qmd` files in the repository. From the directory containing `_quarto.yml`, run:

```powershell
quarto preview
```

This is a convenient English-only editing preview. It does not replace the complete multilingual publication build.

For a new article, copy `templates/article.qmd` into `essays/`, choose a lowercase filename with hyphens, and fill in its title, date, description, and English text. Keep `lang: en`. Choose one stable `notebook-topic` value:

| Value | Section |
| --- | --- |
| `harmonic-analysis` | Harmonic Analysis |
| `martingales` | Martingale Theory |
| `operator-algebras` | Operator Algebras |
| `functional-analysis` | Functional Analysis |
| `personal` | Reflections & Essays |

The home page and matching section automatically list published articles. Keep filenames and existing heading anchors stable after publication, since links and discussions depend on them. Use `$...$` for inline mathematics and `$$...$$` for displayed mathematics. A mobile contents list must link to the same heading IDs as the desktop contents list.

An article originally written in Chinese can declare `original-language: zh-CN`. Preserve its Chinese original in the reviewed Chinese entries and maintain its English QMD as the build source. The reading notice then identifies Chinese as the original and links back to that edition; it does not mislabel the English translation as the author's original prose.

The template starts with `draft: true`. Change that only when the article is ready to publish. Production uses `draft-mode: gone`: a draft may have an empty placeholder URL, but its text must not appear in pages or indexes. Private drafts do not belong in this public repository, even if marked as drafts.

## Translation files and review

The translation engine splits English prose into page-local segments. Segment IDs include a source fingerprint, and each cache entry stores the exact source text. Mathematics, code, link destinations, HTML markup, and heading IDs are protected placeholders. The translated prose must keep every placeholder exactly once and in the same order.

- `_i18n/zh.json` and `_i18n/ja.json` contain committed, reviewed translations.
- Entries with `locked: true` are protected revisions and must not be automatically overwritten.
- `_i18n/ui.json` contains navigation, footer, language controls, article notices, and comment-interface text.
- `_i18n/glossary.json` records mathematical terminology and translation style.
- `_i18n/generated/` contains optional machine-generated entries. It is ignored by Git, reused through GitHub Actions cache, and excluded from the published website.
- `.translation-work/` and `.i18n-build/` contain disposable extraction, validation, and build files. They are also ignored and never published.

Extract the current prose and check reviewed translations with:

```powershell
python scripts/i18n.py extract
python scripts/i18n.py check
```

The extraction is written to `.translation-work/segments.json`. Add or correct entries in the reviewed language files using the exact current `id` and `source`, the translated `text`, and `locked: true` after review. Committed reviewed entries take precedence over generated entries. A change to English creates a new fingerprint; the old translation is not silently applied to the new text. Moving an unchanged paragraph within its page does not invalidate it.

Do not edit translated QMD files in `.i18n-build/`: the next build recreates them. Correct the translation cache or the English source instead. When the English interface changes, review the matching strings in `_i18n/ui.json` as well.

## Optional automatic translation

The current reviewed pages can build without a translation API. No API key or model is supplied by this project. Automatic translation is optional and requires an explicit configuration by the repository owner:

| GitHub Actions setting | Purpose |
| --- | --- |
| Secret `TRANSLATION_API_KEY` | Server-side API credential; never place it in a file or webpage. |
| Variable `TRANSLATION_MODEL` | The owner-selected model to use for translation. |
| Variable `TRANSLATION_MAX_CHARS` | Maximum new source characters per build; default `20000`. |

The implemented adapter uses the OpenAI Responses API during the build. It sends only translation segments and their mathematical context, uses `store: false`, and never runs in the reader's browser. No API request is made unless both the credential and model are configured. If translations are missing without that configuration, the build stops and reports the missing entries; the previously deployed website remains in place.

The character cap counts new masked source text across the target-language requests. It limits a batch of work, not a currency amount. Cached segments are reused; only missing source fingerprints are translated. Invalid or incomplete responses fail validation rather than publishing partial text. Generated translations have `locked: false`; mathematical structure checks do not replace review of their meaning and tone. To retain a correction permanently, move the reviewed entry into the committed language file and mark it `locked: true`.

## Build and publish

Use Quarto **1.10.19**, matching the pinned publishing workflow, and Python 3.10 or newer. The project scripts use Python's standard library; no Python package installation is required.

For a complete local build in PowerShell:

```powershell
$env:SITE_URL = "https://tianle-math.github.io/math-notes/"
python scripts/set-site-url.py
python scripts/check-site.py source
python -m unittest discover -s scripts -p "test_i18n.py"
python scripts/build-multilingual.py
python scripts/check-site.py output
```

If Quarto is not on `PATH`, pass its executable with `python scripts/build-multilingual.py --quarto "path-to-quarto"`. `--prepare-only` creates temporary language sources for inspection. `--skip-finish` is a development option that omits language controls and discussions; that output is not ready to publish.

The builder renders English first, then the two language directories, and finally adds local language controls and article comment panels. The source check records English QMD hashes, and the output check confirms that the build has not changed those files. Translation checks preserve protected formulas and links. Publication checks cover page languages, shared discussion keys, local resources, language switches, section anchors, common private data, and draft boundaries. Page totals are derived from the authored sources and grow as articles are added. The frequency-geometry article retains its original 47 MathML expressions in each edition.

GitHub Pages must use **GitHub Actions** as its build source. Pushing to `main`, or manually running **Publish mathematical notebook**, performs the complete build and publishes only `_site/`. The workflow obtains the public base URL from Pages configuration, uses scoped short-lived workflow permissions, and does not require a personal access token. A failed build or failed publication check prevents deployment of that build.

## Shared article discussions

Embedded comments are prepared for Giscus backed by GitHub Discussions but are **not yet enabled**: the Giscus App still needs authorization and the discussion category ID is not configured. Article panels currently show a setup notice and an ordinary link to GitHub Discussions, without a nonfunctional **Load comments** button.

Once configured, the browser loads only local page code until a reader selects **Load comments**. That click connects to Giscus and GitHub; posting requires a GitHub account. Readers can also open the discussion on GitHub. The comment panel uses the service's mathematical-notation support.

The repository must be public, Discussions must be enabled, and the Giscus GitHub App must have access to this repository. To complete setup, authorize that app for the intended repository, choose its discussion category, and enter the verified category ID in `_i18n/giscus.json`. That file contains public repository and category names and IDs; these identifiers are configuration, not credentials. If those settings change, update the file and rebuild. The publication check permits the explicit pending state but rejects an enabled loader with incomplete configuration.

Each article uses `article:<filename-without-extension>` as its stable discussion key. All three editions use that same key and point back to the canonical English URL, so changing languages does not create three separate discussions. Keep an article's filename unchanged to keep its existing thread. Discussion owners and moderators manage comments, deletion, locking, and moderation through GitHub. The website does not store commenter passwords or a private moderation token.

## Public identity and privacy

The site uses the public byline **Tian**, a link to **X · @tianmathmath**, and a copyright notice. It does not add a school, private email address, home address, or an expanded personal biography. The public GitHub username remains visible in the Pages and repository URLs.

Images, styling, fonts supplied by the site, and MathML rendering do not require a remote tracking or formula service. There is no analytics integration. The embedded comment service is currently disabled. Once enabled, its connection begins only when the reader opens the loader; the GitHub Discussions and X profile links are ordinary outbound links. Pages include a `no-referrer` policy. Hosting and comment services can still process their own access data.

Do not commit API credentials, personal addresses, local user paths, or private drafts. The checks catch common patterns but cannot determine whether every sentence is appropriate for public release. Git author identity is separate from page content: use GitHub's privacy settings and a `noreply` author address for public commits. Never put the private address in the site configuration.

The footer preserves the author's copyright notice with applicable-law exceptions. Publishing source on GitHub does not by itself grant an additional license to the articles or illustrations.

## Project map

- `index.qmd`: notebook introduction, four subject links, reflections, and recent articles.
- Subject `.qmd` files: section introductions, illustrations, and article lists.
- `series.qmd`: the frequency-geometry reading series.
- `essays/`: authored English articles.
- `assets/styles.scss`: the desktop and mobile reading layout.
- `assets/community.css` and `assets/community.js`: local language controls and click-to-load comments.
- `scripts/i18n.py`: prose extraction, translation cache validation, and optional API adapter.
- `scripts/build-multilingual.py` and `scripts/finish-site.py`: the complete multilingual build.
- `scripts/check-site.py`: publication checks using the standard library.
- `.github/workflows/publish.yml`: tested build and GitHub Pages deployment.
