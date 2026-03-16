from heizlast.core import calc_heatloads, ensure_auto_decks


def test_core_public_heatload_exports_are_callable():
    assert callable(calc_heatloads)
    assert callable(ensure_auto_decks)
