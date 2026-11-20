import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import new_plugin_cards as npc  # noqa: E402


class DraftCopyTests(unittest.TestCase):
    def test_title_with_en_dash_and_markdown_stripped(self):
        readme = (
            "# MOVES – Audio Drama Presence Simulator\n\n"
            "<img src=\"logo.png\">\n\n"
            "Ein Satz Beschreibung mit **fett** und [Link](https://example.com).\n"
        )
        copy = npc.draft_copy(readme)
        self.assertEqual(copy['name'], 'MOVES')
        self.assertEqual(copy['subtitle'], 'Audio Drama Presence Simulator')
        self.assertEqual(copy['desc'], 'Ein Satz Beschreibung mit fett und Link.')

    def test_title_without_subtitle(self):
        copy = npc.draft_copy("# EINZELTITEL\n\nText.\n")
        self.assertEqual(copy['name'], 'EINZELTITEL')
        self.assertEqual(copy['subtitle'], '')

    def test_no_title_returns_none(self):
        self.assertIsNone(npc.draft_copy('Kein Titel hier\n'))


class ExistingCardReposTests(unittest.TestCase):
    def test_extracts_repo_names(self):
        html_text = 'xx data-release-repo="Foo-vst" yy data-release-repo="Bar-vst" zz'
        self.assertEqual(npc.existing_card_repos(html_text), {'Foo-vst', 'Bar-vst'})

    def test_empty_when_absent(self):
        self.assertEqual(npc.existing_card_repos('<html></html>'), set())


class BuildArticleTests(unittest.TestCase):
    def test_escapes_html_and_sets_attributes(self):
        info = dict(repo='X-vst')
        copy = dict(name='X & Y', subtitle='A "B"', desc='<script>bad()</script>')
        article = npc.build_article(info, copy, 'https://example.com/a.png')
        self.assertNotIn('<script>bad()', article)
        self.assertIn('X &amp; Y', article)
        self.assertIn('data-release-repo="X-vst"', article)
        self.assertIn('data-version-of="X-vst"', article)
        self.assertIn('https://example.com/a.png', article)

    def test_missing_description_gets_placeholder(self):
        info = dict(repo='Y-vst')
        copy = dict(name='Y', subtitle='', desc='')
        article = npc.build_article(info, copy, 'https://example.com/a.png')
        self.assertIn('Beschreibung bitte ergaenzen', article)


class NextNumberTests(unittest.TestCase):
    def test_increments_past_highest(self):
        html_text = '<span class="num">01 / A</span><span class="num">07 / B</span>'
        self.assertEqual(npc.next_number(html_text), 8)

    def test_defaults_to_one_when_absent(self):
        self.assertEqual(npc.next_number('no spans here'), 1)


if __name__ == '__main__':
    unittest.main()
