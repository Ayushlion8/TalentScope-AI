"""Response policy layer: decides when to clarify, recommend, compare, or refuse."""
from __future__ import annotations

import logging
import re
from app.catalog import Catalog, get_catalog
from app.models import ChatResponse, Recommendation

logger = logging.getLogger(__name__)

MAX_TURNS = 8

OFF_TOPIC_PATTERNS = [
    r"\bhiring\s+advice\b",
    r"\bhire\b.*\badvice\b",
    r"\bhow\s+should\s+i\s+hire\b",
    r"\blegal\b",
    r"\blawsuit\b",
    r"\bemployment\s+laws?\b",
    r"\bemployment\s*law\b",
    r"\blabor\s*law\b",
    r"\bhow\s+to\s+(hire|fire|interview|recruit)\b",
    r"\bsalary\b",
    r"\bcompensation\b",
    r"\bpay\s+range\b",
    r"\bresume\b",
    r"\bcv\b",
    r"\bcover\s+letter\b",
    r"\binterview\s+tip\b",
    r"\bjob\s+search\b",
    r"\bcareer\s+advice\b",
    r"\btraining\s+program\b",
    r"\bhow\s+to\s+write\b",
    r"\bnon[-\s]?shl\b",
    r"\bhackerrank\b",
    r"\bcodility\b",
    r"\btestgorilla\b",
]

LEGAL_PATTERNS = [
    r"\blegal\b",
    r"\blawsuit\b",
    r"\bemployment\s+laws?\b",
    r"\bemployment\s*law\b",
    r"\blabor\s*law\b",
    r"\bcompliance\b",
    r"\bdiscrimination\b",
    r"\badverse\s+impact\b",
]

NON_SHL_PATTERNS = [
    r"\bnon[-\s]?shl\b",
    r"\bnot\s+shl\b",
    r"\bhackerrank\b",
    r"\bcodility\b",
    r"\btestgorilla\b",
    r"\bmercer\b",
    r"\bthomas\s+international\b",
]

ASSESSMENT_SCOPE_TERMS = [
    "assessment", "assessments", "test", "tests", "shl", "screening",
    "aptitude", "cognitive", "personality", "reasoning", "skills",
]

INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"you\s+are\s+now",
    r"pretend\s+you\s+are",
    r"act\s+as\s+if",
    r"system\s*:\s*",
    r"jailbreak",
    r"prompt\s+injection",
    r"reveal\s+(your|the)\s+(prompt|instructions|system)",
    r"forget\s+(your|all)\s+instructions",
    r"override\s+(your|the)\s+(system|safety|rules)",
    r"what\s+are\s+your\s+instructions",
    r"show\s+me\s+your\s+prompt",
]

COMPARISON_PATTERNS = [
    r"\bdifferenc\w+\s+between\b",
    r"\bcompar\w+\s+(x\s+and\s+y|with)\b",
    r"\bversus\b",
    r"\bvs\.?\b",
    r"\bwhich\s+is\s+better\b",
    r"\bhow\s+does\s+\w+\s+compare\s+to\b",
    r"\bbetter\s*:\s*\w+\s+or\s+\w+",
]

VAGUE_INDICATORS = [
    r"^\s*(hi|hello|hey|greetings)\s*[!.?]?\s*$",
    r"^\s*(help|assist|support)\s*[!.?]?\s*$",
    r"^\s*(i\s+need\s+(?:an?|some)\s+(?:assessment|test))\s*[!.?]?\s*$",
    r"^\s*(what\s+(?:do\s+you\s+have|can\s+you\s+offer|assessments\s+are\s+available))\s*[!.?]?\s*$",
    r"^\s*(recommend\w*\s+(?:an?|some)?\s*(?:assessment|test)?)\s*[!.?]?\s*$",
    r"^\s*(show\s+me\s+(?:all|some)?\s*(?:assessments|tests)?)\s*[!.?]?\s*$",
    r"^\s*(need|i\s+need)\s+hiring\s+tests?\s*[!.?]?\s*$",
    r"^\s*(need|i\s+need)\s+(?:some\s+)?tests?\s*[!.?]?\s*$",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _has_assessment_scope(text: str) -> bool:
    text_lower = text.lower()
    return any(term in text_lower for term in ASSESSMENT_SCOPE_TERMS)


def _sanitize_query_part(text: str) -> str:
    """Remove conversational filler and operational phrases that should not rank products."""
    text = text.lower()
    replacements = [
        r"\bremote\s+(testing|test|assessment|assessments)\b",
        r"\bonline\s+(testing|test|assessment|assessments)\b",
        r"\bavailable\s+for\s+remote\b",
        r"\bi\s+(need|want|am looking for|would like)\b",
        r"\bplease\b",
        r"\bspecifically\b",
        r"\brecommend(?:ed|ing|ations?)?\b",
    ]
    for pattern in replacements:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _is_refinement_override(text: str) -> bool:
    text_lower = text.lower()
    return any(
        marker in text_lower
        for marker in ["specifically", "instead", "make it", "change to", "switch to", "only", "actually"]
    )


def _extract_comparison_names(text: str) -> tuple[str | None, str | None]:
    """Try to extract two assessment names from a comparison query."""
    # "difference between X and Y"
    m = re.search(r"between\s+(.+?)\s+and\s+(.+?)(?:\s*[?.]|\s*$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # "X vs Y" or "X versus Y"
    m = re.search(r"(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\s*[?.]|\s*$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # "compare X and Y"
    m = re.search(r"compar\w+\s+(.+?)\s+(?:and|to|with)\s+(.+?)(?:\s*[?.]|\s*$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"better\s*:\s*(.+?)\s+or\s+(.+?)(?:\s*[?.]|\s*$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"which\s+is\s+better\s+(.+?)\s+or\s+(.+?)(?:\s*[?.]|\s*$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None


def _infer_test_types(text: str) -> list[str]:
    """Infer desired test type codes from query text."""
    from app.catalog import TYPE_KEYWORDS
    types = set()
    for key_code, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text.lower():
                types.add(key_code)
                break
    return list(types)


def _is_shl_assessment_query(text: str) -> bool:
    """Check if the query is at least loosely about SHL assessments."""
    shl_keywords = [
        "assessment", "test", "evaluat", "measure", "skill", "aptitude",
        "personality", "cognitive", "ability", "knowledge", "competenc",
        "reasoning", "simulation", "shl", "hire", "hiring", "recruit",
        "candidate", "employee", "role", "position", "job", "screen",
        "selection", "verify", "check", "profile", "behav",
        "programming", "coding", "technical", "java", "python", "sql",
        "excel", "accounting", "sales", "customer service", "manager",
        "developer", "engineer", "remote",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in shl_keywords)


def _conversation_has_assessment_context(messages: list[dict]) -> bool:
    """Detect whether earlier user turns established assessment intent."""
    for msg in messages[:-1]:
        if msg.get("role") == "user" and _is_shl_assessment_query(msg.get("content", "")):
            return True
    return False


def _extract_constraints(messages: list[dict]) -> dict:
    """Extract all constraints from the full conversation history."""
    constraints: dict = {
        "query_parts": [],
        "test_types": set(),
        "remote_testing": None,
        "job_levels": [],
        "languages": [],
    }

    for msg in messages:
        if msg.get("role") != "user":
            continue
        text = msg.get("content", "").lower()

        sanitized = _sanitize_query_part(text)
        if sanitized:
            constraints["query_parts"].append(sanitized)

        # Test types
        for tt in _infer_test_types(text):
            constraints["test_types"].add(tt)

        # Explicit test type mentions
        for key_code, label in {
            "A": "ability & aptitude",
            "B": "biodata & situational judgement",
            "C": "competencies",
            "D": "development & 360",
            "E": "assessment exercises",
            "K": "knowledge & skills",
            "P": "personality & behavior",
            "S": "simulations",
        }.items():
            if label in text:
                constraints["test_types"].add(key_code)

        # Remote testing
        if "remote" in text and ("test" in text or "assess" in text):
            constraints["remote_testing"] = True

        # Languages
        for lang in ["english", "spanish", "french", "german", "chinese", "japanese",
                      "portuguese", "dutch", "italian", "arabic", "korean", "russian",
                      "hindi", "thai", "vietnamese", "indonesian", "malay", "polish",
                      "czech", "turkish", "hebrew", "swedish", "norwegian", "danish",
                      "finnish", "romanian", "hungarian", "greek"]:
            if lang in text:
                constraints["languages"].append(lang.capitalize())

        # Job levels
        for level in ["entry", "junior", "graduate", "mid-professional", "professional",
                      "senior", "manager", "director", "executive", "frontline",
                      "supervisor", "individual contributor", "general population"]:
            if level in text:
                constraints["job_levels"].append(level)

    constraints["test_types"] = list(constraints["test_types"])
    return constraints


def _item_to_recommendation(item: dict) -> Recommendation:
    return Recommendation(
        name=item.get("name", ""),
        url=item.get("url", ""),
        test_type=", ".join(item.get("test_types", [])),
    )


def build_response(messages: list[dict], cat: Catalog | None = None) -> ChatResponse:
    """Main policy function. Takes message history and returns a ChatResponse."""
    if cat is None:
        cat = get_catalog()

    # Check for empty catalog
    if cat.count == 0:
        return ChatResponse(
            reply="I'm sorry, the assessment catalog is currently unavailable. Please try again later.",
            recommendations=[],
            end_of_conversation=True,
        )

    # Get the latest user message
    user_messages = [m for m in messages if m.get("role") == "user"]
    if not user_messages:
        return ChatResponse(
            reply="Hello! I can help you find the right SHL assessment. What kind of role or skill are you looking to evaluate?",
            recommendations=[],
            end_of_conversation=False,
        )

    latest = user_messages[-1].get("content", "").strip()
    turn_number = len(user_messages)

    # Check end of conversation (8-turn cap)
    if turn_number >= MAX_TURNS:
        return ChatResponse(
            reply="We've reached the maximum conversation length. If you need further help, please start a new conversation. Thank you for using SHL Assessment Recommender!",
            recommendations=[],
            end_of_conversation=True,
        )

    # Check for prompt injection
    if _matches_any(latest, INJECTION_PATTERNS):
        return ChatResponse(
            reply="I can only help with SHL assessment recommendations and cannot follow instructions outside that scope.",
            recommendations=[],
            end_of_conversation=False,
        )

    if _matches_any(latest, LEGAL_PATTERNS):
        return ChatResponse(
            reply="I can help select SHL assessments, but I cannot provide legal or compliance advice.",
            recommendations=[],
            end_of_conversation=False,
        )

    if _matches_any(latest, NON_SHL_PATTERNS):
        return ChatResponse(
            reply="I can only recommend SHL catalog assessments. Share the SHL role or skill area you want to assess.",
            recommendations=[],
            end_of_conversation=False,
        )

    # Check for off-topic/general-advice queries before broad assessment routing.
    if _matches_any(latest, OFF_TOPIC_PATTERNS) and not _has_assessment_scope(latest):
        return ChatResponse(
            reply="I only recommend SHL assessments. Share the role and skills to assess, and I can suggest catalog matches.",
            recommendations=[],
            end_of_conversation=False,
        )

    # Vague greetings are in scope as an opening turn; unrelated requests are refused.
    if _matches_any(latest, VAGUE_INDICATORS):
        return ChatResponse(
            reply="What role and skills should the assessment measure? For example: Java developer, sales manager, cognitive ability, or personality.",
            recommendations=[],
            end_of_conversation=False,
        )

    if (
        not _is_shl_assessment_query(latest)
        and not _matches_any(latest, COMPARISON_PATTERNS)
        and not _conversation_has_assessment_context(messages)
    ):
        return ChatResponse(
            reply="I can only help with SHL assessment recommendations. Please ask about assessments for specific roles, skills, or test types.",
            recommendations=[],
            end_of_conversation=False,
        )

    # Check for comparison request
    if _matches_any(latest, COMPARISON_PATTERNS):
        name_a, name_b = _extract_comparison_names(latest)
        if name_a and name_b:
            item_a, item_b = cat.compare(name_a, name_b)
            if item_a and item_b:
                reply = _build_comparison_reply(item_a, item_b)
                return ChatResponse(
                    reply=reply,
                    recommendations=[],
                    end_of_conversation=False,
                )
            else:
                missing = []
                if not item_a:
                    missing.append(name_a)
                if not item_b:
                    missing.append(name_b)
                return ChatResponse(
                    reply=f"I couldn't find {' and '.join(missing)} in the SHL Individual Test Solutions catalog. Could you check the exact assessment names?",
                    recommendations=[],
                    end_of_conversation=False,
                )
        else:
            # Comparison detected but names not parsed
            return ChatResponse(
                reply="I'd be happy to compare assessments. Please specify the two assessment names, e.g., 'Compare X and Y'.",
                recommendations=[],
                end_of_conversation=False,
            )

    # Extract constraints from full conversation
    constraints = _extract_constraints(messages)
    latest_query = _sanitize_query_part(latest)
    combined_query = " ".join(constraints["query_parts"])
    if len(user_messages) > 1 and latest_query and _is_refinement_override(latest):
        combined_query = latest_query
    elif len(user_messages) > 1 and latest_query:
        # Weight the latest user turn more heavily so stateless refinements can change direction.
        combined_query = " ".join([combined_query, latest_query, latest_query]).strip()

    # If we have some context but it's still very broad, ask one clarifying question
    if (not constraints["test_types"] and not constraints["job_levels"]
            and not any(kw in combined_query for kw in ["programming", "coding", "java", "python", "sql",
                                                         "c++", ".net", "sap", "excel", "accounting",
                                                         "sales", "customer", "manager", "leader"])):
        # Broad query with some assessment context
        if turn_number == 1 and not constraints["remote_testing"]:
            return ChatResponse(
                reply="What role and skills should the assessment measure? For example: role level, technical skill, cognitive ability, or personality.",
                recommendations=[],
                end_of_conversation=False,
            )

    # We have enough context - search the catalog
    results = cat.search(
        query=combined_query,
        test_types=constraints["test_types"] or None,
        remote_testing=constraints["remote_testing"],
        job_levels=constraints["job_levels"] or None,
        languages=constraints["languages"] or None,
        max_results=10,
    )

    if not results:
        # Try with just the latest message
        results = cat.search(query=latest, max_results=10)

    if not results:
        return ChatResponse(
            reply="I couldn't find assessments matching your criteria in the SHL Individual Test Solutions catalog. Could you try different keywords or be more specific about the role or skills you need to assess?",
            recommendations=[],
            end_of_conversation=False,
        )

    recommendations = [_item_to_recommendation(r) for r in results]
    reply = _build_recommendation_reply(recommendations, constraints)

    return ChatResponse(
        reply=reply,
        recommendations=recommendations,
        end_of_conversation=False,
    )


def _build_recommendation_reply(recommendations: list[Recommendation], constraints: dict) -> str:
    """Build a natural language reply for recommendations."""
    count = len(recommendations)
    if count == 1:
        r = recommendations[0]
        type_str = f" ({r.test_type})" if r.test_type else ""
        return f"Best match: [{r.name}]({r.url}){type_str}."

    parts = [f"Top {count} SHL catalog matches:"]
    for i, r in enumerate(recommendations[:5], 1):
        type_str = f" ({r.test_type})" if r.test_type else ""
        parts.append(f"{i}. [{r.name}]({r.url}){type_str}")

    return "\n".join(parts)


def _build_comparison_reply(item_a: dict, item_b: dict) -> str:
    """Build a grounded comparison reply using only catalog data."""
    lines = [f"**{item_a['name']}** vs **{item_b['name']}**:\n"]

    # Test types
    types_a = ", ".join(item_a.get("test_types", [])) or "N/A"
    types_b = ", ".join(item_b.get("test_types", [])) or "N/A"
    lines.append(f"- Test Type: {types_a} | {types_b}")

    # Remote testing
    rt_a = "Yes" if item_a.get("remote_testing") else "No"
    rt_b = "Yes" if item_b.get("remote_testing") else "No"
    lines.append(f"- Remote Testing: {rt_a} | {rt_b}")

    # Adaptive/IRT
    ai_a = "Yes" if item_a.get("adaptive_irt") else "No"
    ai_b = "Yes" if item_b.get("adaptive_irt") else "No"
    lines.append(f"- Adaptive/IRT: {ai_a} | {ai_b}")

    # Duration
    dur_a = f"{item_a.get('duration_minutes')} min" if item_a.get("duration_minutes") else "N/A"
    dur_b = f"{item_b.get('duration_minutes')} min" if item_b.get("duration_minutes") else "N/A"
    lines.append(f"- Duration: {dur_a} | {dur_b}")

    # Job levels
    jl_a = ", ".join(item_a.get("job_levels", [])) or "N/A"
    jl_b = ", ".join(item_b.get("job_levels", [])) or "N/A"
    lines.append(f"- Job Levels: {jl_a} | {jl_b}")

    # Languages
    lang_a = ", ".join(item_a.get("languages", [])) or "N/A"
    lang_b = ", ".join(item_b.get("languages", [])) or "N/A"
    lines.append(f"- Languages: {lang_a} | {lang_b}")

    # Description summaries
    desc_a = item_a.get("description", "")[:150]
    desc_b = item_b.get("description", "")[:150]
    if desc_a or desc_b:
        lines.append(f"\n**{item_a['name']}**: {desc_a}{'...' if len(item_a.get('description', '')) > 150 else ''}")
        lines.append(f"**{item_b['name']}**: {desc_b}{'...' if len(item_b.get('description', '')) > 150 else ''}")

    lines.append(f"\n[{item_a['name']}]({item_a['url']}) | [{item_b['name']}]({item_b['url']})")
    return "\n".join(lines)
