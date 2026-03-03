"""
Unit tests for qld_req_scraper.py logic
========================================

These are very lightweight and focus on the table‑parsing helper introduced
for the first QLD link. They don't hit the network and simply call
`get_clean_text` with a small HTML fragment.

Run with:
    pytest tests/test_qld_req_scraper.py -v
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bs4 import BeautifulSoup

from src.scrapers.qld_req_scraper import get_clean_text


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def make_qld_requirement_table():
    """Return minimal HTML representing the example tbody from the issue."""
    return (
        '<html><body>'
        '<table>'
        '<tbody class="SCXW213354277 BCX8">'
        '<tr>'
        '  <td>Occupation</td>'
        '  <td>Have an occupation on the ' \
        'Queensland Onshore Skills List.'
        '      <p><em>Note that Chefs and Cooks are unable to apply by ' \
        'working in takeaway or fast-food businesses.</em></p>'
        '  </td>'
        '</tr>'
        '</tbody>'
        '</table>'
        '</body></html>'
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_get_clean_text_parses_table_rows_as_bullets():
    html = make_qld_requirement_table()
    soup = BeautifulSoup(html, "lxml")

    text = get_clean_text(soup)

    # header should appear verbatim
    assert text.startswith("Occupation"), "expect header at top"

    # the paragraph content should be converted into bullet points
    assert "- Have an occupation on the Queensland Onshore Skills List." in text
    assert (
        "- Note that Chefs and Cooks are unable to apply by working in takeaway or fast-food businesses."
        in text
    )


def test_get_clean_text_falls_back_to_regular_logic():
    # ensure we haven't accidentally broken non-table fallback
    html = "<html><body><p>Some requirement text</p><ul><li>one</li></ul></body></html>"
    soup = BeautifulSoup(html, "lxml")
    text = get_clean_text(soup)
    assert "Some requirement text" in text
    assert "• one" in text


def test_get_clean_text_ignores_navigation_blocks():
    # Navigation/header content should be removed and not appear in output
    html = (
        '<html><body>'
        '<header><nav>Home About Contact</nav></header>'
        '<main>'
        '<table><tbody>'
        '<tr><td>Occupation</td><td>Have an occupation on the Queensland Onshore Skills List.</td></tr>'
        '</tbody></table>'
        '</main>'
        '<footer>Footer links and copyright</footer>'
        '</body></html>'
    )
    soup = BeautifulSoup(html, "lxml")
    text = get_clean_text(soup)
    assert "Home About Contact" not in text
    assert "Footer links" not in text
    assert text.startswith("Occupation")
