"""Shared test fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.catalog import Catalog
from app.main import app


SAMPLE_CATALOG = [
    {
        "name": "C Programming (New)",
        "slug": "c-programming-new",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/c-programming-new/",
        "remote_testing": True,
        "adaptive_irt": True,
        "test_type_keys": ["K"],
        "test_types": ["Knowledge & Skills"],
        "entity_id": "4094",
        "description": "Multi-choice test that measures the knowledge of C programming basics, functions, arrays, and advanced C concepts.",
        "job_levels": ["Mid-Professional", "Professional Individual Contributor"],
        "languages": ["English (USA)"],
        "duration_minutes": 10,
    },
    {
        "name": "Numerical Reasoning",
        "slug": "numerical-reasoning",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/numerical-reasoning/",
        "remote_testing": True,
        "adaptive_irt": True,
        "test_type_keys": ["A"],
        "test_types": ["Ability & Aptitude"],
        "entity_id": "5001",
        "description": "Measures the ability to understand and evaluate numerical data presented in tables, charts and graphs.",
        "job_levels": ["Graduate", "Professional Individual Contributor"],
        "languages": ["English (USA)", "French"],
        "duration_minutes": 17,
    },
    {
        "name": "OPQ Personality",
        "slug": "opq-personality",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/opq-personality/",
        "remote_testing": True,
        "adaptive_irt": False,
        "test_type_keys": ["P"],
        "test_types": ["Personality & Behavior"],
        "entity_id": "6001",
        "description": "Measures personality traits relevant to workplace behavior and performance.",
        "job_levels": ["Mid-Professional", "Manager", "Executive"],
        "languages": ["English (USA)", "Spanish"],
        "duration_minutes": 30,
    },
    {
        "name": "Managerial Potential Assessment",
        "slug": "managerial-potential",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/managerial-potential/",
        "remote_testing": True,
        "adaptive_irt": False,
        "test_type_keys": ["A", "P"],
        "test_types": ["Ability & Aptitude", "Personality & Behavior"],
        "entity_id": "7001",
        "description": "Assesses potential for managerial roles through cognitive ability and personality measures.",
        "job_levels": ["Manager", "Director"],
        "languages": ["English (USA)"],
        "duration_minutes": 45,
    },
    {
        "name": "SQL Server (New)",
        "slug": "sql-server-new",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/sql-server-new/",
        "remote_testing": True,
        "adaptive_irt": True,
        "test_type_keys": ["K"],
        "test_types": ["Knowledge & Skills"],
        "entity_id": "4100",
        "description": "Multi-choice test that measures the knowledge of SQL queries, tables, filtering, and aggregation.",
        "job_levels": ["Mid-Professional", "Professional Individual Contributor"],
        "languages": ["English (USA)"],
        "duration_minutes": 12,
    },
    {
        "name": "Situational Judgement Test",
        "slug": "situational-judgement",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/situational-judgement/",
        "remote_testing": True,
        "adaptive_irt": False,
        "test_type_keys": ["B"],
        "test_types": ["Biodata & Situational Judgement"],
        "entity_id": "8001",
        "description": "Presents realistic workplace scenarios to evaluate judgement and decision-making.",
        "job_levels": ["Entry", "Graduate", "Professional Individual Contributor"],
        "languages": ["English (USA)"],
        "duration_minutes": 25,
    },
]


@pytest.fixture
def sample_catalog(tmp_path: Path) -> Catalog:
    """Create a Catalog with sample data for testing."""
    catalog_file = tmp_path / "catalog.json"
    with open(catalog_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_CATALOG, f)
    cat = Catalog(path=catalog_file)
    cat.load()
    return cat


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
