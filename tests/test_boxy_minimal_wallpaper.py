"""Static quality checks for the exact wallpaper deployed to BOXY."""
import hashlib
import struct
import unittest
import zlib

from scripts.boxy_minimal_wallpaper import HEIGHT, WIDTH, generate


class WallpaperTests(unittest.TestCase):
    def test_image_is_valid_true_black_rgb_png_with_expected_size(self):
        data = generate()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (1600, 900))
        self.assertLess(len(data), 512000)
        self.assertIn(b"IDAT", data)
        self.assertIn(b"IEND", data)

    def test_wallpaper_generation_is_deterministic(self):
        data = generate()
        self.assertEqual(hashlib.sha256(data).hexdigest(), hashlib.sha256(generate()).hexdigest())


if __name__ == "__main__":
    unittest.main()
