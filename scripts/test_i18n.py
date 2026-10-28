"""Safety and incremental-cache tests; no network calls or third-party packages."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import i18n


def cache_for(document, transform=lambda text: text):
    return {"version": 1, "segments": {
        s.id: {"source": s.source, "text": transform(s.source), "locked": True}
        for s in document.segments}}


class ProtectionTests(unittest.TestCase):
    def test_exact_math_code_links_attributes_and_citations(self):
        source = ('Use $x^2$ and $$\\hat f(\\xi)$$, `danger($x)`; '
                  '[reference](https://example.test/a_(b)#c){.reading-link} '
                  '<span data-x="42">value</span> and [see @paper, p. 2].')
        masked, tokens = i18n.mask(source)
        self.assertEqual(i18n.restore(masked, tokens), source)
        self.assertNotIn("x^2", masked)
        self.assertNotIn("https://", masked)
        self.assertNotIn("@paper", masked)
        self.assertNotIn("data-x", masked)
        i18n.validate_translation(masked, masked.replace("Use", "用"))

    def test_rejects_missing_duplicate_reordered_and_invented_tokens(self):
        source = "Value ⟦P0000⟧ then ⟦P0001⟧."
        bad = ["值 ⟦P0000⟧。", "值 ⟦P0000⟧ ⟦P0000⟧ ⟦P0001⟧。",
               "值 ⟦P0001⟧ ⟦P0000⟧。", "值 ⟦P0000⟧ ⟦P0001⟧ ⟦P9999⟧。",
               "值 ⟦P0000⟧ ⟦P0001⟧ ⟦BAD⟧。"]
        for translation in bad:
            with self.subTest(translation=translation), self.assertRaises(i18n.TranslationError):
                i18n.validate_translation(source, translation)

    def test_rejects_unprotected_formula_html_and_list_changes(self):
        for translation in ["Value $y$", "Value <script>x</script>", "Value `code`", "- Value", "Value\n\nNew block"]:
            with self.subTest(translation=translation), self.assertRaises(i18n.TranslationError):
                i18n.validate_translation("Value", translation)
        with self.assertRaises(i18n.TranslationError):
            i18n.validate_translation("[Text]⟦P0000⟧", "Text⟦P0000⟧")

    def test_escaped_dollars_are_not_math(self):
        source = r"Cost \$5; mathematical value $x$ and \(y+1\)."
        masked, tokens = i18n.mask(source)
        self.assertNotIn("$", masked)
        self.assertEqual(list(tokens.values()), [r"\$", "$x$", r"\(y+1\)"])
        i18n.validate_translation(masked, masked.replace("Cost", "费用"))

    def test_blockquote_prefixes_remain_immutable(self):
        source = "> A thought.\n> A second line."
        masked, tokens = i18n.mask(source)
        i18n.validate_translation(masked, masked.replace("thought", "想法"))
        self.assertEqual(i18n.restore(masked, tokens), source)
        self.assertEqual(list(tokens.values()), ["> ", "> "])

    def test_translation_cannot_insert_destination_before_protected_url(self):
        masked, _ = i18n.mask("Read [reference](https://example.test/reference).")
        for destination in ("javascript:alert(1)", "data:text/html,example", "https://other.test/"):
            translated = masked.replace("reference]", f"reference]({destination})")
            with self.subTest(destination=destination), self.assertRaisesRegex(i18n.TranslationError, "link destination"):
                i18n.validate_translation(masked, translated)
        image = masked.replace("[reference]", "![reference](https://other.test/pixel.png)")
        with self.assertRaisesRegex(i18n.TranslationError, "link destination"):
            i18n.validate_translation(masked, image)

    def test_reference_destinations_are_protected_and_cannot_be_invented(self):
        source = '[reference]: https://example.test/\n  "Original title"'
        masked, tokens = i18n.mask(source)
        self.assertNotIn("https://", masked)
        self.assertEqual(i18n.restore(masked, tokens), source)
        i18n.validate_translation(masked, masked)
        with self.assertRaisesRegex(i18n.TranslationError, "link destination"):
            i18n.validate_translation("Read [reference].", "[reference]: javascript:alert(1)")


class PublicationURLTests(unittest.TestCase):
    """Exercise the real publication gate, without rendering or network calls."""

    def check_page(self, fragment):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            for name in ("check-site.py", "i18n.py"):
                shutil.copyfile(Path(__file__).with_name(name), root / "scripts" / name)
            output = root / "_site" / "essays"
            output.mkdir(parents=True)
            page = '<html><body><h1 id="heading">Title</h1>' + fragment + '<math></math>' * 47 + '</body></html>'
            (output / "fourier-frequency-geometry-1.html").write_text(page, encoding="utf-8")
            return subprocess.run([sys.executable, str(root / "scripts/check-site.py"), "output"],
                                  capture_output=True, text=True)

    def test_publication_rejects_executable_url_schemes(self):
        urls = ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "java&#x73;cript:alert(1)",
                "java&#9;script:alert(1)", "java&#10;script:alert(1)", "java&#13;script:alert(1)",
                " &#1;javascript:alert(1)", "vbscript:msgbox(1)", "data:text/html,example")
        for url in urls:
            with self.subTest(url=url):
                result = self.check_page(f'<a href="{url}">link</a>')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("executable URL scheme", result.stdout)
                self.assertNotIn(url, result.stdout)

    def test_publication_keeps_ordinary_link_schemes_and_anchors(self):
        links = '<a href="https://example.test/">https</a><a href="http://example.test/">http</a>'
        links += '<a href="mailto:contact">mail</a><a href="tel:+1234567">phone</a>'
        links += '<a href="#heading">anchor</a><a href="fourier-frequency-geometry-1.html">relative</a>'
        result = self.check_page(links)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class DocumentTests(unittest.TestCase):
    SOURCE = '''---
title: "Sample notes"
lang: en
categories: [Mathematics, Harmonic Analysis]
notebook-topic: harmonic-analysis
---

::: {.card}
## Fourier atoms

Values $x$ and $y$ in [a link](../index.qmd#original).

$$
f(x)=x^2.

g(y)=y^2.
$$

```python
print("Do not translate")
```

```{=html}
<div>AN OPEN NOTEBOOK BY <strong>Tian</strong></div>
```

<img src="assets/a.svg" alt="A diagram" width="10">

## Another heading {.quiet}

Keep this meaning.
:::
'''

    def test_english_is_byte_exact_and_locales_keep_math_code_links_ids(self):
        doc = i18n.Document(self.SOURCE, "essays/sample.qmd")
        original = doc.render({}, "en")
        self.assertEqual(original.encode(), self.SOURCE.encode())
        cache = cache_for(doc, lambda text: text.replace("Fourier atoms", "傅里叶原子").replace("Values", "取值").replace("A diagram", "示意图"))
        translated = doc.render(cache, "zh", {"raw-replacements": {"AN OPEN NOTEBOOK BY": "开放笔记，作者"},
                                               "category_names": {"Mathematics": "数学", "Harmonic Analysis": "调和分析"}})
        self.assertIn("## 傅里叶原子 {#fourier-atoms}", translated)
        self.assertIn("## Another heading {.quiet #another-heading}", translated)
        self.assertIn('alt="示意图"', translated)
        self.assertIn("开放笔记，作者", translated)
        self.assertIn("notebook-topic: harmonic-analysis", translated)
        self.assertIn('categories: [ "数学", "调和分析"]', translated)
        self.assertIn("lang: zh", translated)
        self.assertEqual(i18n.MATH.findall(self.SOURCE), i18n.MATH.findall(translated))
        self.assertEqual([v for _, _, v in i18n.link_destinations(self.SOURCE)],
                         [v for _, _, v in i18n.link_destinations(translated)])
        self.assertIn('```python\nprint("Do not translate")\n```', translated)
        self.assertEqual(re.findall(r"(?m)^:::.*$", self.SOURCE), re.findall(r"(?m)^:::.*$", translated))

    def test_existing_heading_ids_and_internal_links_do_not_change(self):
        source = "## A custom title {#stable .class}\n\n[Go](#stable)\n"
        doc = i18n.Document(source, "index.qmd")
        localized = doc.render(cache_for(doc, lambda text: text.replace("A custom title", "自定义标题")), "zh")
        self.assertIn("## 自定义标题 {#stable .class}", localized)
        self.assertIn("[Go](#stable)", localized)

    def test_page_segments_do_not_include_code_displaymath_or_machine_metadata(self):
        doc = i18n.Document(self.SOURCE, "essays/sample.qmd")
        sources = "\n".join(s.source for s in doc.segments)
        for forbidden in ["Do not translate", "g(y)=y^2", "notebook-topic", "AN OPEN NOTEBOOK BY"]:
            self.assertNotIn(forbidden, sources)

    def test_standalone_heading_slug_tracks_english_html_break(self):
        result = i18n.stabilize_headings("# Starting with mathematics,<br>writing thoughts down. {.hero-title}\n")
        self.assertIn("#starting-with-mathematics-writing-thoughts-down.", result)


class CacheTests(unittest.TestCase):
    def test_insertion_and_reordering_preserve_unchanged_ids(self):
        first = i18n.Document("One paragraph.\n\nTwo paragraphs.\n", "index.qmd")
        second = i18n.Document("A new paragraph.\n\nTwo paragraphs.\n\nOne paragraph.\n", "index.qmd")
        missing = i18n.missing_segments([second], cache_for(first))
        self.assertEqual([s.source for s in missing], ["A new paragraph."])

    def test_formula_change_requires_translation_review(self):
        first = i18n.Document("A value $x$.\n", "essay.qmd")
        second = i18n.Document("A value $y$.\n", "essay.qmd")
        self.assertEqual(first.segments[0].source, second.segments[0].source)
        self.assertNotEqual(first.segments[0].id, second.segments[0].id)
        self.assertEqual(len(i18n.missing_segments([second], cache_for(first))), 1)

    def test_invalid_locked_entry_is_not_replaced(self):
        doc = i18n.Document("A paragraph.\n", "index.qmd")
        cache = cache_for(doc)
        cache["segments"][doc.segments[0].id]["source"] = "Older text."
        with self.assertRaisesRegex(i18n.TranslationError, "Locked"):
            i18n.missing_segments([doc], cache)

    def test_reviewed_cache_overrides_generated_and_missing_creds_never_call_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = i18n.Document("Original.\n", "index.qmd")
            reviewed = cache_for(doc, lambda _: "人工译文。")
            generated = cache_for(doc, lambda _: "旧机器译文。")
            for locale in i18n.LOCALES:
                i18n.write_json(root / "_i18n" / f"{locale}.json", reviewed)
                i18n.write_json(root / "_i18n" / "generated" / f"{locale}.json", generated)
            with patch.dict("os.environ", {}, clear=True), patch("i18n.translate_batch") as api:
                result = i18n.ensure_caches([doc], root)
                self.assertEqual(result["zh"]["segments"][doc.segments[0].id]["text"], "人工译文。")
                changed = i18n.Document("Changed.\n", "index.qmd")
                with self.assertRaisesRegex(i18n.TranslationError, "No API call"):
                    i18n.ensure_caches([changed], root)
                api.assert_not_called()

    def test_budget_is_checked_before_any_api_request(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {
                "TRANSLATION_API_KEY": "test-placeholder", "TRANSLATION_MODEL": "user-selected-model",
                "TRANSLATION_MAX_CHARS": "1"}, clear=True), patch("i18n.translate_batch") as api:
            doc = i18n.Document("Longer than one character.\n", "index.qmd")
            with self.assertRaisesRegex(i18n.TranslationError, "exceeding"):
                i18n.ensure_caches([doc], Path(tmp))
            api.assert_not_called()


class BuildTests(unittest.TestCase):
    def test_staging_is_isolated_and_configuration_keeps_locale_paths(self):
        spec = importlib.util.spec_from_file_location("build_multilingual", Path(__file__).with_name("build-multilingual.py"))
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = "---\ntitle: Sample\n---\n\nA paragraph.\n"
            (root / "index.qmd").write_text(source, encoding="utf-8")
            base_config = ("project:\n  type: website\nwebsite:\n  navbar:\n    title: Tian\n"
                           "    left:\n      - text: Home\n        href: index.qmd\n"
                           "      - text: Notes\n        menu:\n          - text: Harmonic\n"
                           "    right:\n      - text: Contact\n  page-footer: Footer\n")
            (root / "_quarto.yml").write_text(base_config, encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "main.css").write_text("body{}", encoding="utf-8")
            (root / "assets" / "private.key").write_text("not copied", encoding="utf-8")
            doc = i18n.Document(source, "index.qmd")
            for locale in i18n.LOCALES:
                i18n.write_json(root / "_i18n" / f"{locale}.json", cache_for(doc, lambda x: x.replace("A paragraph.", "段落。")))
            navigation = {"left": [{"text": "Home"}, {"text": "Notes"}, {"text": "Essays"}], "right": []}
            i18n.write_json(root / "_i18n" / "ui.json", {k: {"website": {"navbar": navigation}} for k in i18n.LANGUAGES})
            stages = build.prepare(root, "https://example.test/math-notes/")
            self.assertEqual(list(stages), ["en", "zh", "ja", "fr"])
            self.assertEqual((root / "index.qmd").read_text(), source)
            self.assertEqual((root / "_quarto.yml").read_text(), base_config)
            self.assertEqual((stages["en"] / "index.qmd").read_text(), source)
            staged_config = (stages["zh"] / "_quarto.yml").read_text()
            self.assertNotIn("left:", staged_config)
            self.assertNotIn("right:", staged_config)
            self.assertNotIn("- text:", staged_config)
            self.assertIn("title: Tian", staged_config)
            self.assertIn("page-footer: Footer", staged_config)
            self.assertFalse((stages["en"] / "assets" / "private.key").exists())
            self.assertTrue((stages["zh"] / "assets" / "main.css").exists())
            profile = json.loads((stages["fr"] / "_quarto-i18n.yml").read_text())
            self.assertEqual(profile["website"]["site-url"], "https://example.test/math-notes/fr/")
            self.assertEqual(Path(profile["project"]["output-dir"]), root / "_site" / "fr")
            self.assertEqual(profile["format"]["html"]["lang"], "fr")
            publish_profile = json.loads((stages["fr"] / "_quarto-publish.yml").read_text())
            self.assertEqual(publish_profile["website"]["site-url"], profile["website"]["site-url"])
            self.assertEqual(len(profile["website"]["navbar"]["left"]), 3)
            rendered = root / "_site" / "ja" / "index.html"
            rendered.parent.mkdir(parents=True)
            three_labels = ''.join(f'<span class="menu-text">{v}</span>' for v in ["Home", "Notes", "Essays"])
            rendered.write_text(f"<html><body><nav>{three_labels}</nav></body></html>")
            build.verify_navigation(root, "ja", stages["ja"])
            rendered.write_text(f"<html><body><nav>{three_labels}{three_labels}</nav></body></html>")
            with self.assertRaisesRegex(i18n.TranslationError, "exactly.*3 labels"):
                build.verify_navigation(root, "ja", stages["ja"])


if __name__ == "__main__":
    unittest.main()
