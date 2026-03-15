import unittest

from agents.architect_agent import ArchitectAgent


class ArchitectAssetDetectionTests(unittest.TestCase):
    def test_infer_sprite_sheet_grid_prefers_practical_character_sheet(self) -> None:
        self.assertEqual(ArchitectAgent._infer_sprite_sheet_grid(192, 432), (4, 9))

    def test_infer_sprite_sheet_grid_detects_small_enemy_sheet(self) -> None:
        self.assertEqual(ArchitectAgent._infer_sprite_sheet_grid(128, 96), (4, 3))


if __name__ == "__main__":
    unittest.main()
