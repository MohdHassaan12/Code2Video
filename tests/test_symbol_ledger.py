"""
Unit tests for SymbolLedger and Cross-Scene Memory.
"""

import pytest
from adapt_manim.core.ledger import SymbolLedgerManager


def test_symbol_ledger_initialization():
    mgr = SymbolLedgerManager("Support Vector Machine")
    assert "w" in mgr.ledger.symbols
    assert "b" in mgr.ledger.symbols
    assert mgr.ledger.symbols["w"].color_hex == "#58C4DD"


def test_extract_symbols_from_text():
    mgr = SymbolLedgerManager("General Physics")
    text = "The electric field $E$ exerts a force on charge $q$ with velocity $v$."
    mgr.extract_symbols_from_text(text, section_id="sec_1")

    assert "E" in mgr.ledger.symbols
    assert "q" in mgr.ledger.symbols
    assert "v" in mgr.ledger.symbols


def test_prompt_context_generation():
    mgr = SymbolLedgerManager("Fourier Transform")
    ctx = mgr.get_prompt_context()
    assert "PERSISTENT SYMBOL LEDGER" in ctx
    assert "\\omega" in ctx or "f(t)" in ctx
