import unittest
from scripts import analyze_photos as ap

INDEX = {"photos": {
    "A": {"name": "DSC_0001.jpg", "folder": "Day 1", "day": "1", "photographer": None, "capturedAt": "2026-09-06T10:00:00Z", "seq": 1},
    "B": {"name": "DSC_0002.jpg", "folder": "Day 1", "day": "1", "photographer": None, "capturedAt": "2026-09-06T10:00:30Z", "seq": 2},
}}
GOOD = {"scene": "race-action", "numbers": [{"bib": 42, "confidence": "high"}],
        "riders": [{"bib": 42, "helmet": "white", "kit": "black orange", "bike": "blue", "other": ""}]}


class WorklistImportTest(unittest.TestCase):
    def test_pending(self):
        self.assertEqual(ap.pending(INDEX, {}), ["A", "B"])
        self.assertEqual(ap.pending(INDEX, {"A": GOOD}), ["B"])

    def test_validate_entry_normalises(self):
        e, err = ap.validate_entry("A", {"scene": "Race-Action", "numbers": [{"bib": "42", "confidence": "HIGH"}],
                                        "riders": [{"bib": None, "helmet": "Red"}]})
        self.assertIsNone(err)
        self.assertEqual(e["scene"], "race-action")
        self.assertEqual(e["numbers"], [{"bib": 42, "confidence": "high"}])
        self.assertEqual(e["riders"], [{"bib": None, "helmet": "red", "kit": "", "bike": "", "other": ""}])
        self.assertIn("analysedAt", e)

    def test_validate_entry_rejects_bad(self):
        self.assertIsNotNone(ap.validate_entry("A", {"scene": "party", "numbers": [], "riders": []})[1])
        self.assertIsNotNone(ap.validate_entry("A", {"scene": "scenery", "numbers": [{"bib": "x"}], "riders": []})[1])
        self.assertIsNotNone(ap.validate_entry("A", "nope")[1])

    def test_import_results(self):
        cache = {}
        n, errs = ap.import_results(cache, INDEX, {"A": GOOD, "Z": GOOD, "B": {"scene": "bad"}})
        self.assertEqual(n, 1)
        self.assertIn("A", cache)
        self.assertEqual(len(errs), 2)


RESULTS = {"riders": [{"bib": 42, "name": "Ann"}, {"bib": 47, "name": "Bob"}, {"bib": 9, "name": "Cy"}]}
CACHE = {
    "A": {"analysedAt": "x", "scene": "race-action", "numbers": [{"bib": 42, "confidence": "high"}],
          "riders": [{"bib": 42, "helmet": "white", "kit": "black jersey orange sleeves", "bike": "blue", "other": ""}]},
    "B": {"analysedAt": "x", "scene": "race-action", "numbers": [],
          "riders": [{"bib": None, "helmet": "white", "kit": "black orange", "bike": "blue", "other": ""}]},
    "C": {"analysedAt": "x", "scene": "podium", "numbers": [{"bib": 47, "confidence": "high"}, {"bib": 999, "confidence": "medium"}],
          "riders": [{"bib": 47, "helmet": "", "kit": "green", "bike": "", "other": ""}, {"bib": 999, "helmet": "", "kit": "", "bike": "", "other": ""}]},
    "D": {"analysedAt": "x", "scene": "scenery", "numbers": [], "riders": []},
}
INDEX2 = {"photos": {
    "A": {"name": "DSC_0001.jpg", "folder": "Day 1", "day": "1", "photographer": None, "capturedAt": "2026-09-06T10:00:00Z", "seq": 1},
    "B": {"name": "DSC_0002.jpg", "folder": "Day 1", "day": "1", "photographer": None, "capturedAt": "2026-09-06T10:00:30Z", "seq": 2},
    "C": {"name": "DSC_0500.jpg", "folder": "Podiums - Credit Sadie Aldridge", "day": "Podiums", "photographer": "Sadie Aldridge", "capturedAt": None, "seq": 500},
    "D": {"name": "DSC_0600.jpg", "folder": "Day 2", "day": "2", "photographer": None, "capturedAt": None, "seq": 600},
}}


class BuildTest(unittest.TestCase):
    def test_profiles_and_score(self):
        prof = ap.build_profiles(CACHE)
        self.assertIn(42, prof)
        self.assertNotIn(999, prof)
        self.assertIn(47, prof)
        self.assertGreater(ap.score(CACHE["B"]["riders"][0], prof[42]), 0.5)
        self.assertLess(ap.score(CACHE["B"]["riders"][0], prof[47]), 0.2)

    def test_propagate_infers_b(self):
        ids = ap.propagate(INDEX2, CACHE, {42, 47, 9})
        self.assertEqual(ids["B"][0]["bib"], 42)
        self.assertEqual(ids["B"][0]["method"], "inferred")
        self.assertGreaterEqual(ids["B"][0]["confidence"], ap.THRESHOLD)
        self.assertEqual(ids["A"], [{"bib": 42, "method": "number", "confidence": "high"}])

    def test_manifest(self):
        overrides = {"C": {"add_bibs": [9], "remove_bibs": [47]}, "D": {"hide": True}}
        m, summary = ap.build_manifest(INDEX2, CACHE, overrides, RESULTS)
        by = {p["fileId"]: p for p in m["photos"]}
        self.assertNotIn("D", by)
        self.assertEqual(by["C"]["bibs"], [9])
        self.assertEqual(by["C"]["unmatched"], [999])
        self.assertEqual(by["C"]["photographer"], "Sadie Aldridge")
        self.assertEqual(by["A"]["bibs"], [42])
        self.assertEqual(by["B"]["bibs"], [42])
        self.assertEqual(by["B"]["unidentifiedRiders"], 0)
        self.assertEqual(summary["byNumber"], 2)
        self.assertEqual(summary["inferred"], 1)
        self.assertEqual(m["credits"], ap.pc.CREDITS)
        self.assertEqual([p["fileId"] for p in m["photos"]], ["A", "B", "C"])

    def test_override_photographer_and_manual_only(self):
        p = {"fileId": "X", "bibs": [], "identifications": [], "photographer": None}
        out = ap.apply_overrides(p, {"add_bibs": [5], "photographer": "Pete Scullion"})
        self.assertEqual(out["bibs"], [5])
        self.assertEqual(out["identifications"], [{"bib": 5, "method": "manual", "confidence": "high"}])
        self.assertEqual(out["photographer"], "Pete Scullion")
        self.assertIsNone(ap.apply_overrides(p, {"hide": True}))


if __name__ == "__main__":
    unittest.main()
