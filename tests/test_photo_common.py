import unittest
from scripts import photo_common as pc


class HelpersTest(unittest.TestCase):
    def test_known_bibs(self):
        res = {"riders": [{"bib": 42, "name": "A B"}, {"bib": 7, "name": "C D"}]}
        self.assertEqual(pc.known_bibs(res), {42: "A B", 7: "C D"})

    def test_urls(self):
        self.assertEqual(pc.thumb_url("X1", 400), "https://drive.google.com/thumbnail?id=X1&sz=w400")
        self.assertEqual(pc.view_url("X1"), "https://drive.google.com/file/d/X1/view")

    def test_seq_number(self):
        self.assertEqual(pc.seq_number("DSC_0055.jpg"), 55)
        self.assertEqual(pc.seq_number("DSC_0055 (1).jpg"), 55)
        self.assertIsNone(pc.seq_number("podium.jpg"))

    def test_folder_meta(self):
        self.assertEqual(pc.folder_meta("Day 3"), ("3", None))
        self.assertEqual(pc.folder_meta("Podiums - Credit Sadie Aldridge"), ("Podiums", "Sadie Aldridge"))
        self.assertEqual(pc.folder_meta("Race Week Slideshow"), ("Slideshow", None))
        self.assertEqual(pc.folder_meta("Something Else"), ("Something Else", None))


if __name__ == "__main__":
    unittest.main()
