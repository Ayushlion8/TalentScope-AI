"""URL grounding tests for scraped SHL catalog data."""
from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from app.catalog import CATALOG_URL_PREFIX, Catalog
from app.policy import build_response
from scripts.scrape_catalog import parse_list_row


def test_scraper_preserves_exact_catalog_href():
    html = """
    <tr data-entity-id="1">
      <td class="custom__table-heading__title">
        <a href="/products/product-catalog/view/sql-server-analysis-services-%28ssas%29-%28new%29/">SQL Server Analysis Services (SSAS) (New)</a>
      </td>
      <td class="custom__table-heading__general"><span class="catalogue__circle -yes"></span></td>
      <td class="custom__table-heading__general"><span class="catalogue__circle -yes"></span></td>
      <td class="product-catalogue__keys"><span class="product-catalogue__key">K</span></td>
    </tr>
    """
    row = BeautifulSoup(html, "lxml").select_one("tr")
    item = parse_list_row(row)
    assert item is not None
    assert item["source_href"] == "/products/product-catalog/view/sql-server-analysis-services-%28ssas%29-%28new%29/"
    assert item["url"] == "https://www.shl.com/products/product-catalog/view/sql-server-analysis-services-%28ssas%29-%28new%29/"
    assert "slug" not in item


def test_checked_in_catalog_urls_are_valid_catalog_urls():
    rows = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
    urls = [row["url"] for row in rows]
    assert len(rows) == 377
    assert len(urls) == len(set(urls))
    assert all(url.startswith(CATALOG_URL_PREFIX) for url in urls)
    assert all("/solutions/products/product-catalog/view/" not in url for url in urls)
    assert all(row.get("source_href") for row in rows)
    assert all("slug" not in row for row in rows)


def test_real_catalog_recommendation_urls_exactly_match_catalog_entries():
    cat = Catalog()
    cat.load()
    catalog_by_name = {item["name"]: item["url"] for item in cat.items}
    scenarios = {
        "I need a SQL skills assessment for a mid-level developer": "SQL",
        "I need a Java programming assessment for developers": "Java",
        "I need a Python coding assessment for developers": "Python",
        "I want to assess personality traits for a manager role": "Personality & Behavior",
    }
    for query, expected_signal in scenarios.items():
        resp = build_response([{"role": "user", "content": query}], cat=cat)
        assert 1 <= len(resp.recommendations) <= 10
        first = resp.recommendations[0]
        if expected_signal == "Personality & Behavior":
            assert expected_signal in first.test_type
        else:
            assert expected_signal.lower() in first.name.lower()
        for rec in resp.recommendations:
            assert rec.url.startswith(CATALOG_URL_PREFIX)
            assert rec.url == catalog_by_name[rec.name]
