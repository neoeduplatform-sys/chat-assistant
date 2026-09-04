"""Tests for tail-page history pagination helpers."""

from app.chat_memory_service import ChatMemoryService


def test_tail_page_start_index_last_page():
    assert ChatMemoryService.tail_page_start_index(170, 40, 0) == 130


def test_tail_page_start_index_second_page_from_end():
    assert ChatMemoryService.tail_page_start_index(170, 40, 40) == 90


def test_tail_page_start_index_short_conversation():
    assert ChatMemoryService.tail_page_start_index(15, 40, 0) == 0


def test_tail_page_start_index_empty():
    assert ChatMemoryService.tail_page_start_index(0, 40, 0) == 0
