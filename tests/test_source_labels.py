"""Tests para metadata_source_label."""

from app.source_labels import metadata_source_label


def test_prefers_title_over_document():
    md = {"title": "Módulo 1", "document": "MI089_Semana4"}
    assert metadata_source_label(md) == "Módulo 1"


def test_falls_back_to_document():
    md = {
        "document": "MI089_Semana4",
        "topic": "Simulación completa: Recibir OT",
        "type": "Youtube",
    }
    assert metadata_source_label(md) == "MI089_Semana4"


def test_truncates_long_topic():
    long_topic = "x" * 200
    md = {"topic": long_topic}
    label = metadata_source_label(md)
    assert label is not None
    assert len(label) == 120
    assert label.endswith("…")


def test_empty_metadata_returns_none():
    assert metadata_source_label({}) is None
    assert metadata_source_label(None) is None


def test_skips_blank_strings():
    md = {"title": "  ", "document": "DocA"}
    assert metadata_source_label(md) == "DocA"
