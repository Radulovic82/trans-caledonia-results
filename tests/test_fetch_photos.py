import io, unittest
from pathlib import Path
from PIL import Image
from scripts import fetch_photos as fp

FIX = Path(__file__).parent / "fixtures" / "folder_view.html"


class ParseTest(unittest.TestCase):
    def test_parse_folder_view(self):
        entries = fp.parse_folder_view(FIX.read_text())
        self.assertEqual(entries, [
            {"id": "1wbUPKZFPHR2lv2HaCtD73erBphJdDE5n", "name": "Day 1", "kind": "folder"},
            {"id": "1IoOtse77Zh_CKy8377WM92Jk8LkZD3l1", "name": "DSC_0004.jpg", "kind": "file"},
        ])

    def test_list_tree_recurses_and_keeps_images_only(self):
        pages = {
            "root": '<div class="flip-entry" id="entry-F1"><a href="https://drive.google.com/drive/folders/F1"><div class="flip-entry-title">Day 2</div></a></div>'
                    '<div class="flip-entry" id="entry-V1"><a href="https://drive.google.com/file/d/V1/view"><div class="flip-entry-title">clip.mp4</div></a></div>',
            "F1": '<div class="flip-entry" id="entry-P1"><a href="https://drive.google.com/file/d/P1/view"><div class="flip-entry-title">DSC_0100.jpg</div></a></div>',
        }
        files = fp.list_tree("root", fetch=lambda fid: pages[fid])
        self.assertEqual(files, [{"id": "P1", "name": "DSC_0100.jpg", "folderId": "F1", "folder": "Day 2"}])

    def test_exif_time(self):
        im = Image.new("RGB", (8, 8)); ex = im.getexif(); ex[306] = "2026:09:10 10:40:27"
        buf = io.BytesIO(); im.save(buf, "JPEG", exif=ex.tobytes())
        self.assertEqual(fp.exif_time(buf.getvalue()), "2026-09-10T10:40:27Z")
        self.assertIsNone(fp.exif_time(b"not a jpeg"))

    def test_plan_downloads_skips_known(self):
        files = [{"id": "A", "name": "a.jpg", "folderId": "F", "folder": "Day 1"},
                 {"id": "B", "name": "b.jpg", "folderId": "F", "folder": "Day 1"}]
        index = {"photos": {"A": {"name": "a.jpg"}}}
        self.assertEqual([f["id"] for f in fp.plan_downloads(files, index, {})], ["B"])
        self.assertEqual(fp.plan_downloads(files, index, {"B": {}}), [])


if __name__ == "__main__":
    unittest.main()
