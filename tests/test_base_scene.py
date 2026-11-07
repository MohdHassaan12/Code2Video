"""
Unit tests for TeachingScene and BaseSceneHelper.
"""

import pytest
import numpy as np
from adapt_manim.core.base_scene import BaseSceneHelper


def test_anchor_coordinates():
    # Test top-left grid origin A1
    coord_a1 = BaseSceneHelper.get_anchor_coordinates("A1")
    assert coord_a1[0] == 0.5 + 0 * 1.0  # x = 0.5
    assert coord_a1[1] == 2.2 - 0 * 1.0  # y = 2.2
    assert coord_a1[2] == 0.0

    # Test bottom-right grid corner F6
    coord_f6 = BaseSceneHelper.get_anchor_coordinates("F6")
    assert coord_f6[0] == 0.5 + 5 * 1.0  # x = 5.5
    assert coord_f6[1] == 2.2 - 5 * 1.0  # y = -2.8
    assert coord_f6[2] == 0.0


def test_invalid_anchor_raises_value_error():
    with pytest.raises(ValueError):
        BaseSceneHelper.get_anchor_coordinates("G7")
    with pytest.raises(ValueError):
        BaseSceneHelper.get_anchor_coordinates("Z1")


def test_area_points_calculation():
    points = BaseSceneHelper.get_area_points("A1", "B2")
    expected = ["A1", "A2", "B1", "B2"]
    assert set(points) == set(expected)


def test_find_nearest_vacant_anchor():
    occupied = ["B2", "B3"]
    nearest = BaseSceneHelper.find_nearest_vacant_anchor("B2", occupied)
    assert nearest is not None
    assert nearest not in occupied
    # Should pick an adjacent cell like B1, A2, or C2
    assert nearest in ["B1", "A2", "C2"]
