import unittest

import numpy as np

from bricksmith.rendering.rasterizer import (
    project, ldraw_colors, ldraw_opacity, preview_face_opacity, rasterize,
)


class RenderOrientationTests(unittest.TestCase):
    def test_palette_reads_actual_ldraw_colours(self):
        self.assertEqual(ldraw_colors()[28].lower(), "#897d62")
        self.assertEqual(ldraw_colors()[272].lower(), "#19325a")

    def test_negative_y_is_visually_up(self):
        lower = np.array([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [0.0, 0.0, 20.0]])
        upper = lower + [0.0, -24.0, 0.0]
        projected = project(np.stack([lower, upper]), azimuth=35.0)
        self.assertLess(projected[1, :, 1].mean(), projected[0, :, 1].mean())

    def test_ldraw_alpha_blends_glazing_over_opaque_geometry(self):
        self.assertAlmostEqual(ldraw_opacity()[41], 128 / 255)
        face = np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 3.0, 0.0]])
        triangles = np.stack([face, face + [0.0, 0.0, 1.0]])
        colors = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
        image = rasterize(triangles, colors, 4, 4, background="#000000",
                          opacity=np.array([1.0, 0.5]))
        np.testing.assert_allclose(image[0, 0], [0.5, 0.0, 0.5], atol=1e-5)

    def test_two_clear_mesh_skins_composite_to_material_opacity(self):
        material_alpha = ldraw_opacity()[43]
        skin_alpha = preview_face_opacity(material_alpha)
        self.assertAlmostEqual(1.0 - (1.0 - skin_alpha) ** 2,
                               material_alpha)
        self.assertEqual(preview_face_opacity(1.0), 1.0)
        self.assertEqual(preview_face_opacity(0.0), 0.0)

    def test_transparent_face_behind_opaque_is_hidden(self):
        face = np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 3.0, 0.0]])
        triangles = np.stack([face, face + [0.0, 0.0, -1.0]])
        colors = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
        image = rasterize(triangles, colors, 4, 4, background="#000000",
                          opacity=np.array([1.0, 0.5]))
        np.testing.assert_allclose(image[0, 0], [0.0, 0.0, 1.0], atol=1e-5)


if __name__ == "__main__":
    unittest.main()
