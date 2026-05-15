from heizlast.core.attic_geometry import AtticGeometry
from heizlast.core.roof_line_geometry import build_roof_facets


def test_attic_geometry_builds_multiple_roof_facets_from_lines():
    geom = AtticGeometry(
        building_width_m=8.0,
        building_length_m=10.0,
        knee_wall_height_m=1.0,
        roof_pitch_deg=35.0,
        roof_type='satteldach',
        ridge_orientation='length',
        roof_lines=(
            ('kehle', 0.50, 0.15, 0.82, 0.50),
            ('grat', 0.50, 0.85, 0.82, 0.50),
        ),
    )
    facets = geom.roof_facets()
    assert len(facets) >= 4
    assert all(f.plan_area_m2 > 0.0 for f in facets)
    assert all(f.surface_area_m2 >= f.plan_area_m2 for f in facets)


def test_build_roof_facets_preserves_total_plan_area_after_split():
    poly = ((0.0, 0.0), (8.0, 0.0), (8.0, 10.0), (0.0, 10.0))
    segs = [
        ('first', (4.0, 0.0), (4.0, 10.0)),
        ('kehle', (4.0, 5.0), (8.0, 10.0)),
    ]
    facets = build_roof_facets(poly, segs, lambda x, y: 0.5 * x)
    assert len(facets) >= 3
    total_plan = sum(f.plan_area_m2 for f in facets)
    assert abs(total_plan - 80.0) < 1e-6
