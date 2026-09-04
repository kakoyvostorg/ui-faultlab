import unittest

from ui_faultlab.actions import Action, normalized_to_pixels


class ActionSchemaTest(unittest.TestCase):
    def test_rejects_out_of_bounds_coordinates(self):
        with self.assertRaises(ValueError):
            Action("tap", 1.01, .5).validate()

    def test_rejects_incompatible_fields(self):
        with self.assertRaises(ValueError):
            Action("type", x=.1, text="hello").validate()

    def test_normalized_coordinates_map_to_viewport(self):
        self.assertEqual(normalized_to_pixels(0, 0, 960, 640), (0, 0))
        self.assertEqual(normalized_to_pixels(1, 1, 960, 640), (959, 639))


if __name__ == "__main__":
    unittest.main()

