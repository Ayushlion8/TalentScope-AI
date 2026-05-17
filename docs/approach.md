# Approach

## Objective

TalentScope AI is a deterministic SHL assessment recommender. It only answers questions about SHL Individual Test Solutions and never invents assessments or URLs.

## Conversation Handling

The API is stateless. `/chat` receives the full message history each time and derives all context from that history. The policy layer counts user turns and ends the conversation when the 8-turn cap is reached.

Routing order:

1. Empty or unavailable catalog handling.
2. Prompt-injection refusal.
3. Legal and off-topic refusal.
4. Vague query clarification.
5. Comparison routing.
6. Constraint extraction from full user history.
7. Deterministic catalog search and ranked recommendation response.

Short refinement turns are supported by reading the full history. Explicit markers such as "specifically", "instead", "make it", and "only" make the latest user turn dominate the search query so changed constraints can override earlier broad intent.

## Retrieval

The catalog loader validates rows and keeps only usable SHL URLs. Each catalog item is normalized to:

- name
- slug
- url
- remote_testing
- adaptive_irt
- test_type_keys
- test_types
- entity_id
- description
- job_levels
- languages
- duration_minutes

Search is deterministic. It scores:

- exact and partial name matches
- token overlap
- rare token matches
- description matches when descriptions exist
- inferred SHL test type
- role and seniority keywords
- remote testing, language, and job level filters

Results are sorted by score descending and then name ascending for stable output. The service returns at most 10 recommendations.

## Comparison

Comparison queries resolve two assessment names through exact or fuzzy catalog name matching. The reply uses only normalized catalog fields: test type, remote testing, adaptive/IRT, duration, job levels, languages, description, and catalog URLs.

## Refusal

The policy refuses:

- prompt injection
- requests to reveal or override instructions
- general hiring advice
- legal or compliance advice
- career, resume, salary, or unrelated questions

Refusals never include recommendations.

## Tradeoffs

Embeddings were not used because the assignment rewards grounded, reproducible behavior. The deterministic scorer is easier to test, explain, and debug. The current checked-in catalog has sparse detail fields, so the system is careful to ground comparison and recommendation text in fields that are actually present.
