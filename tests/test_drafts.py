"""The draft store: round-tripping, id allocation, and the archive-on-push rule."""

import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from bbsa import drafts

BODY = "# A title\n\n## Summary\nSomething happened.\n"
META = {"program": "1475", "domain": "https://example.com", "endpoint": "/x", "type": "T"}


class DraftsTest(TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"BBSA_DRAFT_DIR": tempfile.mkdtemp()})
        env.start()
        self.addCleanup(env.stop)

    def test_round_trips_metadata_and_body(self):
        draft_id, path = drafts.save(META, BODY)
        self.assertEqual(draft_id, "d1")
        meta, body, loaded = drafts.load("d1")
        self.assertEqual(meta, META)
        self.assertEqual(body, BODY.strip())
        self.assertEqual(loaded, path)
        # Frontmatter stays human-editable, in a stable key order.
        self.assertTrue(path.read_text().startswith("---\nprogram: 1475\ndomain:"))

    def test_ids_do_not_collide_or_reuse(self):
        self.assertEqual(drafts.save(META, "# One\n\n## Summary\na")[0], "d1")
        self.assertEqual(drafts.save(META, "# Two\n\n## Summary\nb")[0], "d2")
        drafts.archive("d1")
        self.assertEqual(drafts.save(META, "# Three\n\n## Summary\nc")[0], "d3")  # not d1 again

    def test_redrafting_same_program_and_title_folds_onto_one_id(self):
        d1, _ = drafts.save(META, "# Same finding\n\n## Summary\nfirst pass")
        d2, path = drafts.save(META, "# Same finding\n\n## Summary\nrevised wording")
        self.assertEqual(d1, d2)  # folded, not duplicated
        self.assertEqual([d[0] for d in drafts.load_all()], ["d1"])
        self.assertIn("revised wording", path.read_text())
        # A different title on the same program is a different draft.
        self.assertEqual(drafts.save(META, "# Other finding\n\n## Summary\nx")[0], "d2")

    def test_ids_are_not_reused_after_every_draft_is_pushed(self):
        drafts.save(META, "# First\n\n## Summary\nfinding one")
        drafts.archive("d1", {"slug": "live-one"})
        self.assertEqual(drafts.save(META, "# Second\n\n## Summary\ntwo")[0], "d2")
        drafts.archive("d2", {"slug": "live-two"})
        archived = sorted(p.name for p in (drafts.draft_dir() / "pushed").iterdir())
        self.assertEqual(archived, ["d1.md", "d2.md"])
        self.assertIn("finding one", (drafts.draft_dir() / "pushed" / "d1.md").read_text())

    def test_load_all_skips_pushed_drafts(self):
        drafts.save(META, "# One\n\n## Summary\na")
        drafts.save(META, "# Two\n\n## Summary\nb")
        drafts.archive("d1")
        self.assertEqual([d[0] for d in drafts.load_all()], ["d2"])

    def test_archive_keeps_the_only_local_copy(self):
        drafts.save(META, BODY)
        archived = drafts.archive("d1", {"slug": "live-report"})
        self.assertFalse((drafts.draft_dir() / "d1.md").exists())
        self.assertIn("pushed_as: live-report", archived.read_text())
        self.assertIn("Something happened.", archived.read_text())

    def test_body_without_frontmatter_still_loads(self):
        meta, body = drafts.parse(BODY)
        self.assertEqual(meta, {})
        self.assertEqual(body, BODY.strip())

    def test_missing_draft_is_an_error_not_an_empty_draft(self):
        with self.assertRaises(FileNotFoundError):
            drafts.load("d9")

    def test_only_dN_names_are_drafts(self):
        self.assertTrue(drafts.is_draft_id("d12"))
        self.assertFalse(drafts.is_draft_id("260904796970"))
        self.assertFalse(drafts.is_draft_id("duplicate-report-slug"))
        drafts.draft_dir().mkdir(parents=True, exist_ok=True)
        (drafts.draft_dir() / "draft-notes.md").write_text("stray file")
        self.assertEqual(drafts.load_all(), [])
