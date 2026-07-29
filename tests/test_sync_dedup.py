import sqlite3
import threading
import unittest
from unittest.mock import patch

from app import local_records, sync_dedup


def record(record_id, company, batch, job, url):
    return {
        "record_id": record_id,
        "company": company,
        "batch": batch,
        "job": job,
        "url": url,
        "city": "",
        "dir": [],
    }


class SyncDedupTests(unittest.TestCase):
    def test_yearless_autumn_matches_explicit_2027_but_not_2026(self):
        yearless = record("a", "示例科技", "秋招", "研发类", "https://example.com/campus")
        year_2027 = record("b", "示例科技", "27秋招", "研发类", "https://example.com/campus")
        year_2026 = record("c", "示例科技", "2026届秋招", "研发类", "https://example.com/campus")
        self.assertTrue(sync_dedup._same_batch(yearless, year_2027))
        self.assertFalse(sync_dedup._same_batch(year_2027, year_2026))

    def test_url_normalization_handles_entities_and_tracking(self):
        left = record(
            "a", "Momenta", "秋招", "研发类",
            "http://www.example.com/campus/?project=27&amp;utm_source=feed#rd",
        )
        right = record(
            "b", "Momenta", "27秋招", "研发类",
            "https://example.com/campus?project=27",
        )
        self.assertEqual(sync_dedup._url(left), sync_dedup._url(right))

    def test_incoming_strong_duplicate_skips_without_ai(self):
        existing = [
            record("shr1", "示例科技有限公司", "秋招", "算法、后端", "https://jobs.example.com/campus"),
        ]
        incoming = [
            record("", "示例科技", "27秋招", "算法、后端", "https://mirror.example.com/post/1"),
        ]
        with patch("app.sync_dedup._ai_config", return_value=None):
            kept, stats = sync_dedup.deduplicate_records(
                1, incoming, existing, use_ai=False
            )
        self.assertEqual(kept, [])
        self.assertEqual(stats["exact_skipped"], 1)

    def test_existing_rules_return_survivor_mapping_without_ai(self):
        records = [
            record("new", "示例科技", "27秋招", "研发类", "https://example.com/campus?utm_source=x"),
            record("old", "示例科技有限公司", "秋招", "研发岗位集合", "http://www.example.com/campus"),
        ]
        with patch("app.sync_dedup._ai_config", return_value=None):
            mapping, stats = sync_dedup.find_ai_duplicates(1, records)
        self.assertEqual(mapping, {"new": "old"})
        self.assertEqual(stats["rule_duplicates"], 1)

    def test_ambiguous_existing_pair_reaches_ai_and_uses_valid_match(self):
        records = [
            record("new", "示例科技", "27秋招", "算法岗位", "https://example.com/post/2"),
            record("old", "示例科技有限公司", "秋招", "综合研发岗位", "https://example.com/post/1"),
        ]
        config = {
            "provider": "deepseek",
            "api_key": "test",
            "model": "test",
            "base_url": "https://example.invalid",
            "api_mode": "responses",
        }
        output = (
            '[{"candidate_id":"new","duplicate":true,"should_add":false,'
            '"matched_record_id":"old","reason":"同一招聘项目"}]'
        )
        with (
            patch("app.sync_dedup._ai_config", return_value=config),
            patch("app.sync_dedup._call_ai_provider", return_value=output),
        ):
            mapping, stats = sync_dedup.find_ai_duplicates(1, records)
        self.assertEqual(mapping, {"new": "old"})
        self.assertEqual(stats["ai_reviewed"], 1)
        self.assertEqual(stats["ai_duplicates"], 1)

    def test_merge_preserves_personal_links_and_unique_constraint(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.executescript(
            """
            CREATE TABLE shared_job_records (id TEXT PRIMARY KEY);
            CREATE TABLE job_records (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                source_shared_id TEXT
            );
            CREATE UNIQUE INDEX idx_test_source
                ON job_records(user_id, source_shared_id)
                WHERE source_shared_id IS NOT NULL;
            INSERT INTO shared_job_records(id) VALUES ('shr-old'), ('shr-dup');
            INSERT INTO job_records(id,user_id,source_shared_id)
                VALUES ('rec-a',1,'shr-old'), ('rec-b',1,'shr-dup'),
                       ('rec-c',2,'shr-dup');
            """
        )
        with (
            patch("app.local_records.database.get_db", return_value=db),
            patch("app.local_records.database._write_lock", threading.RLock()),
        ):
            removed = local_records.merge_shared_records({"shr-dup": "shr-old"})
        self.assertEqual(removed, 1)
        links = {
            row["id"]: row["source_shared_id"]
            for row in db.execute(
                "SELECT id, source_shared_id FROM job_records ORDER BY id"
            )
        }
        self.assertEqual(
            links, {"rec-a": "shr-old", "rec-b": None, "rec-c": "shr-old"}
        )


if __name__ == "__main__":
    unittest.main()
