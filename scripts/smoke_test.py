"""Quick smoke test for the app with real catalog data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.catalog import Catalog
from app.policy import build_response

cat = Catalog()
cat.load()
print(f"Catalog loaded: {cat.count} items")

# Test search
r = cat.search(query="programming Java", max_results=5)
print("\nJava programming search:")
for i in r:
    print(f"  - {i['name']} ({i['test_types']}) - {i.get('description', '')[:60]}")

# Test personality search
r = cat.search(query="personality assessment manager", max_results=5)
print("\nPersonality manager search:")
for i in r:
    print(f"  - {i['name']} ({i['test_types']})")

# Test full chat response
resp = build_response([{"role": "user", "content": "I need a Java programming test for mid-level developers"}], cat=cat)
print(f"\nChat response: {resp.reply[:200]}")
print(f"Recommendations: {len(resp.recommendations)}")
for rec in resp.recommendations[:3]:
    print(f"  - {rec.name} ({rec.url})")
