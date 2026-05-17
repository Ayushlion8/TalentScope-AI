"""Catalog loader and retrieval layer for SHL Individual Test Solutions."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

from app.config import CATALOG_PATH

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOG_FILE = CATALOG_PATH

TEST_TYPE_MAP = {
    "A": "Ability & Aptitude",
    "B": "Biodata & Situational Judgement",
    "C": "Competencies",
    "D": "Development & 360",
    "E": "Assessment Exercises",
    "K": "Knowledge & Skills",
    "P": "Personality & Behavior",
    "S": "Simulations",
}

REVERSE_TEST_TYPE = {v.lower(): k for k, v in TEST_TYPE_MAP.items()}

# Keywords that map to test type categories
TYPE_KEYWORDS: dict[str, list[str]] = {
    "A": [
        "cognitive", "aptitude", "ability", "reasoning", "numerical", "verbal",
        "inductive", "deductive", "logical", "mechanical", "spatial", "checking",
        "calculation", "understanding", "reading", "comprehension",
    ],
    "B": [
        "biodata", "situational judgement", "sjt", "judgement", "judgment",
        "scenario", "situational",
    ],
    "C": [
        "competency", "competence", "competencies",
    ],
    "D": [
        "development", "360", "feedback", "survey",
    ],
    "E": [
        "exercise", "assessment center", "roleplay", "role play", "in-basket",
        "presentation", "group discussion",
    ],
    "K": [
        "knowledge", "skill", "programming", "coding", "technical", "software",
        "java", "python", "c++", "c#", ".net", "sql", "sap", "microsoft",
        "excel", "word", "accounting", "finance", "sales", "marketing",
        "typing", "data entry", "call center", "customer service",
        "agile", "scrum", "project management", "it", "web", "design",
        "linux", "network", "security", "cloud", "devops", "testing",
        "automation", "digital", "analytics", "communication",
    ],
    "P": [
        "personality", "behavior", "behaviour", "trait", "motivation",
        "values", "interest", "style", "emotional", "eq", "integrity",
        "honesty", "reliability", "attitude",
    ],
    "S": [
        "simulation", "simulate", "practical", "hands-on", "work sample",
    ],
}

# Role/position keywords
ROLE_KEYWORDS: dict[str, list[str]] = {
    "manager": ["manager", "management", "supervisor", "lead", "director", "chief", "head"],
    "professional": ["professional", "specialist", "analyst", "consultant", "engineer", "developer", "programmer", "architect", "designer", "scientist"],
    "entry": ["entry", "junior", "graduate", "intern", "apprentice", "trainee", "associate", "assistant", "clerk", "operator", "technician"],
    "sales": ["sales", "account executive", "account manager", "business development", "bdm"],
    "customer_service": ["customer service", "customer support", "call center", "contact center", "reservation", "agent", "representative", "help desk", "support"],
    "administrative": ["administrative", "admin", "secretary", "receptionist", "office", "clerical", "bookkeeping", "accounting", "cashier", "teller", "bank"],
    "it": ["it ", "information technology", "software", "developer", "programmer", "data", "cyber", "network", "system admin", "devops"],
    "leadership": ["leadership", "executive", "c-suite", "ceo", "cfo", "coo", "vp", "vice president", "senior leader"],
}

EXPLICIT_SKILL_TOKENS = {
    ".net", "agile", "aws", "azure", "c", "c#", "c++", "cloud", "css",
    "devops", "excel", "html", "java", "javascript", "linux", "oracle",
    "pl/sql", "python", "react", "sap", "scrum", "sql", "testing",
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "i", "in",
    "is", "it", "me", "my", "need", "of", "on", "or", "please", "role",
    "some", "the", "to", "with", "want", "we", "you",
    "make", "only",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9+#.]+", text.lower())
        if len(token) >= 2 and token not in STOPWORDS
    }


def _token_counts(text: str) -> Counter[str]:
    return Counter(
        token
        for token in re.split(r"[^a-z0-9+#.]+", text.lower())
        if len(token) >= 2 and token not in STOPWORDS
    )


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _searchable_text(item: dict) -> str:
    """Build a searchable text string from item metadata."""
    parts = [item.get("name", "")]
    parts.extend(item.get("test_types", []))
    parts.extend(item.get("job_levels", []))
    parts.extend(item.get("languages", []))
    desc = item.get("description", "")
    if desc:
        parts.append(desc)
    return " ".join(parts).lower()


class Catalog:
    """Loads and searches the SHL Individual Test Solutions catalog."""

    def __init__(self, path: Path | None = None):
        self.path = path or CATALOG_FILE
        self.items: list[dict] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            logger.warning("Catalog file not found: %s", self.path)
            self.items = []
            self._loaded = True
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                raw_items = json.load(f)
        except json.JSONDecodeError as exc:
            logger.exception("Catalog file is not valid JSON: %s", self.path)
            raise ValueError(f"Catalog file is not valid JSON: {self.path}") from exc

        if not isinstance(raw_items, list):
            raise ValueError(f"Catalog file must contain a JSON list: {self.path}")

        self.items = [item for item in (self._normalize_item(raw) for raw in raw_items) if item]
        logger.info("Loaded %d catalog items from %s", len(self.items), self.path)
        self._loaded = True

    @staticmethod
    def _normalize_item(raw: object) -> dict | None:
        """Normalize a catalog row and discard unusable records."""
        if not isinstance(raw, dict):
            return None

        name = str(raw.get("name", "")).strip()
        url = str(raw.get("url", "")).strip()
        if not name or not url.startswith("https://www.shl.com/"):
            logger.warning("Skipping invalid catalog row with name=%r url=%r", name, url)
            return None

        test_type_keys = [
            str(key).upper()
            for key in raw.get("test_type_keys", [])
            if str(key).upper() in TEST_TYPE_MAP
        ]
        test_types = raw.get("test_types") or [TEST_TYPE_MAP[key] for key in test_type_keys]

        return {
            "name": name,
            "slug": str(raw.get("slug", "")).strip(),
            "url": url,
            "remote_testing": bool(raw.get("remote_testing", False)),
            "adaptive_irt": bool(raw.get("adaptive_irt", False)),
            "test_type_keys": test_type_keys,
            "test_types": [str(value).strip() for value in test_types if str(value).strip()],
            "entity_id": str(raw.get("entity_id", "")).strip(),
            "description": str(raw.get("description", "")).strip(),
            "job_levels": [str(value).strip() for value in raw.get("job_levels", []) if str(value).strip()],
            "languages": [str(value).strip() for value in raw.get("languages", []) if str(value).strip()],
            "duration_minutes": raw.get("duration_minutes"),
        }

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @property
    def count(self) -> int:
        self.ensure_loaded()
        return len(self.items)

    def get_all(self) -> list[dict]:
        self.ensure_loaded()
        return self.items

    def get_by_name(self, name: str) -> dict | None:
        self.ensure_loaded()
        name_lower = name.lower().strip()
        for item in self.items:
            if item["name"].lower().strip() == name_lower:
                return item
        # Fuzzy match
        best_score = 0.0
        best_item = None
        for item in self.items:
            score = _similarity(name_lower, item["name"].lower())
            if score > best_score and score > 0.7:
                best_score = score
                best_item = item
        return best_item

    def get_by_slug(self, slug: str) -> dict | None:
        self.ensure_loaded()
        for item in self.items:
            if item.get("slug", "").lower() == slug.lower():
                return item
        return None

    def search(
        self,
        query: str = "",
        test_types: list[str] | None = None,
        remote_testing: bool | None = None,
        job_levels: list[str] | None = None,
        languages: list[str] | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        """Search catalog with multi-criteria scoring. Returns ranked results."""
        self.ensure_loaded()
        scored: list[tuple[float, dict]] = []

        # Compute weights for query words based on catalog frequency
        # Rarer words get higher weight so more specific matches rank higher
        q_word_weights: dict[str, float] = {}
        if query:
            q_words = _tokens(query)
            for qw in q_words:
                if len(qw) < 2:
                    q_word_weights[qw] = 1.0
                    continue
                # Count how many items have this word in their name
                count = sum(1 for item in self.items if qw in item["name"].lower())
                if count > 0:
                    # Weight = 1/count so rarer terms get higher weight
                    q_word_weights[qw] = 1.0 / count
                else:
                    # Check searchable text (name + types + levels + langs)
                    count = sum(1 for item in self.items if qw in _searchable_text(item))
                    if count > 0:
                        q_word_weights[qw] = 1.0 / count
                    else:
                        q_word_weights[qw] = 1.0

        for item in self.items:
            score = 0.0

            # Text relevance scoring
            if query:
                q = query.lower()
                name = item["name"].lower()
                desc = item.get("description", "").lower()
                stext = _searchable_text(item)

                # Exact full query in name
                if q in name:
                    score += 50

                # Word-level matching (each query word found in name), weighted
                q_token_counts = _token_counts(q)
                q_words = set(q_token_counts)
                name_words = set(re.split(r"[\s()\-_,.]+", name))
                overlap = q_words & name_words
                if overlap:
                    for w in overlap:
                        score += (15 + 100 * q_word_weights.get(w, 1.0)) * min(q_token_counts[w], 3)

                explicit_skills = q_words & EXPLICIT_SKILL_TOKENS
                matched_explicit_skill = False
                for skill in explicit_skills:
                    if skill in name_words or skill in name or skill in stext:
                        matched_explicit_skill = True
                        score += 150 * min(q_token_counts[skill], 3)
                if explicit_skills and not matched_explicit_skill:
                    score -= 120

                # Substring matching: each query word as substring in name
                for qw in q_words:
                    w = q_word_weights.get(qw, 1.0)
                    if len(qw) >= 3 and qw in name:
                        score += (12 + 80 * w) * min(q_token_counts[qw], 3)
                    elif len(qw) >= 3 and qw in name.replace("(", " ").replace(")", " "):
                        score += (12 + 80 * w) * min(q_token_counts[qw], 3)

                # Bonus for matching ALL query words in the full searchable text
                all_found = all(qw in stext for qw in q_words if len(qw) >= 2)
                if all_found:
                    score += 60

                # Description keyword match
                if desc:
                    desc_words = set(re.split(r"[\s()\-_,.]+", desc))
                    desc_overlap = q_words & desc_words
                    if desc_overlap:
                        score += len(desc_overlap) * 5
                    # Substring in description
                    for qw in q_words:
                        if len(qw) >= 3 and qw in desc:
                            score += 4

                # Test type keyword matching
                for key_code, keywords in TYPE_KEYWORDS.items():
                    key_label = TEST_TYPE_MAP.get(key_code, "").lower()
                    if any(kw in q for kw in keywords):
                        if key_code in item.get("test_type_keys", []):
                            score += 15
                        if key_label in q:
                            if key_code in item.get("test_type_keys", []):
                                score += 20

                # Role keyword matching against name and description
                for role_cat, role_kws in ROLE_KEYWORDS.items():
                    if any(kw in q for kw in role_kws):
                        # Check if item matches the role
                        combined = (name + " " + desc).lower()
                        if any(kw in combined for kw in role_kws):
                            score += 12

                # Fuzzy name similarity bonus
                sim = _similarity(q, name)
                if sim > 0.5:
                    score += sim * 10

            # Test type filter/scoring
            if test_types:
                item_types = set(item.get("test_type_keys", []))
                requested = set()
                for tt in test_types:
                    tt_upper = tt.upper()
                    if tt_upper in TEST_TYPE_MAP:
                        requested.add(tt_upper)
                    else:
                        # Try matching full name
                        for k, v in TEST_TYPE_MAP.items():
                            if v.lower() == tt.lower() or tt.lower() in v.lower():
                                requested.add(k)
                overlap = item_types & requested
                if overlap:
                    score += len(overlap) * 20
                elif requested:
                    score -= 10

            # Remote testing preference
            if remote_testing is not None:
                if item.get("remote_testing") == remote_testing:
                    score += 10
                elif remote_testing and not item.get("remote_testing"):
                    score -= 5

            # Job levels match
            if job_levels:
                item_levels = [jl.lower() for jl in item.get("job_levels", [])]
                for jl in job_levels:
                    if jl.lower() in " ".join(item_levels):
                        score += 10

            # Language match
            if languages:
                item_langs = [l.lower() for l in item.get("languages", [])]
                for lang in languages:
                    if lang.lower() in " ".join(item_langs):
                        score += 10

            if score > 0:
                scored.append((score, item))

        # Sort by score descending, then by name for determinism
        scored.sort(key=lambda x: (-x[0], x[1]["name"]))
        return [item for _, item in scored[:max_results]]

    def compare(self, name_a: str, name_b: str) -> tuple[dict | None, dict | None]:
        """Get two catalog items for comparison."""
        return self.get_by_name(name_a), self.get_by_name(name_b)


# Singleton catalog instance
catalog = Catalog()


def get_catalog() -> Catalog:
    """Get the global catalog instance, loading if needed."""
    catalog.ensure_loaded()
    return catalog
