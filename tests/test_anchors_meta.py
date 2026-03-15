from __future__ import annotations

from heizlast.core.anchors import (
    build_edge_span_meta,
    dump_meta,
    meta_rooms,
    parse_edge_anchor,
    parse_meta,
    update_edge_anchor_meta,
)


def test_parse_dump_meta_roundtrip_contains_expected_keys():
    raw = {'parent': 'auto_1', 'orient': 'V', 'c': '4.000', 'rooms': 'A,B'}
    s = dump_meta(raw)
    d = parse_meta(s)
    assert d['parent'] == 'auto_1'
    assert d['orient'] == 'V'
    assert d['rooms'] == 'A,B'


def test_meta_rooms_parses_room_list():
    assert meta_rooms('rooms=R1,R2|orient=V') == {'R1', 'R2'}


def test_parse_edge_anchor_reads_full_anchor_fields():
    meta = update_edge_anchor_meta('', parent='auto_outer', orient='V', c=4.0, a0=0.0, a1=4.0, s=1.5, w=1.0, rooms=('R1',))
    a = parse_edge_anchor(meta)
    assert a['parent'] == 'auto_outer'
    assert a['orient'] == 'V'
    assert float(a['c']) == 4.0
    assert float(a['a0']) == 0.0
    assert float(a['a1']) == 4.0
    assert float(a['s']) == 1.5
    assert float(a['w']) == 1.0
    assert a['rooms'] == {'R1'}


def test_update_edge_anchor_meta_overwrites_target_fields_only():
    meta = update_edge_anchor_meta('parent=old|foo=bar', orient='H', c=2.0, a0=0.0, a1=4.0, s=2.5, w=1.2, rooms=('R1', 'R2'))
    d = parse_meta(meta)
    assert d['foo'] == 'bar'
    assert d['orient'] == 'H'
    assert d['line'] == 'H:2.000'
    assert d['rooms'] == 'R1,R2'


def test_build_edge_span_meta_creates_consistent_tokens():
    meta = build_edge_span_meta(kind='auto_shared', room_ids=('A', 'B'), orient='V', c=2.0, a0=0.0, a1=4.0, uid='auto_shared_EG_V_2p000_0p000_4p000')
    assert 'auto_shared' in meta
    d = parse_meta(meta)
    assert d['rooms'] == 'A,B'
    assert d['orient'] == 'V'
    assert d['c'] == '2.000'
    assert d['a0'] == '0.000'
    assert d['a1'] == '4.000'
    assert d['edge_uid'].startswith('auto_shared_')
