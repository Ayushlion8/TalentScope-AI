"""Debug search scoring."""
import sys, re
sys.path.insert(0, ".")
from app.catalog import Catalog, TYPE_KEYWORDS

c = Catalog()
c.load()

query = "java programming"
q = query.lower()
q_words = set(q.split())
LABEL_MAP = {
    "A": "ability & aptitude", "B": "biodata & situational judgement",
    "C": "competencies", "D": "development & 360", "E": "assessment exercises",
    "K": "knowledge & skills", "P": "personality & behavior", "S": "simulations",
}

results = []
for item in c.items:
    name = item["name"].lower()
    if "java" not in name and "programming" not in name:
        continue
    desc = item.get("description", "").lower()
    score = 0
    details = []

    if q in name:
        score += 50; details.append("exact_query=50")
    name_words = set(re.split(r"[\s()\-_,.]+", name))
    overlap = q_words & name_words
    if overlap:
        s = len(overlap) * 15
        score += s; details.append(f"word_overlap({overlap})={s}")
    for qw in q_words:
        if len(qw) >= 3 and qw in name:
            score += 12; details.append(f"substr_{qw}=12")
            score += 8; details.append(f"name_match_{qw}=8")
    for key_code, keywords in TYPE_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            if key_code in item.get("test_type_keys", []):
                score += 15; details.append(f"type_kw_{key_code}=15")
    all_found = all(qw in name + " " + desc for qw in q_words if len(qw) >= 2)
    if all_found:
        score += 20; details.append("all_found=20")
    results.append((score, item["name"], details))

results.sort(key=lambda x: -x[0])
for score, name, details in results[:15]:
    print(f"{score:4d}  {name:50s}  {' | '.join(details)}")
