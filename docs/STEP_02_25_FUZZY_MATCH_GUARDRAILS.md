# Step 2.25 — Fuzzy Matching Guardrails

## Purpose

Prevent lexical fuzzy matching from assigning a generic source header
to a semantically specific SOV field with unjustifiably high confidence.

A representative failure case is:

    Building → Number of Buildings

where RapidFuzz can produce a high lexical similarity because both headers
contain the word "building".

## Problem

The fuzzy matcher currently compares a normalized source header against:

1. Canonical target field names
2. Approved domain aliases

using RapidFuzz `fuzz.ratio`.

Lexical similarity does not understand field semantics.

For example:

    Building
    Number of Buildings

share the token "building", but the second field represents a count,
while the first does not explicitly indicate a count.

Therefore, a high fuzzy score alone should not establish a deterministic
schema mapping for this type of ambiguous header.

## Design Decision

Do not lower the global fuzzy threshold.

Do not modify the Hungarian global assignment algorithm.

Instead, introduce a fuzzy matching guardrail that detects when a
candidate is dominated by a more specific phrase.

The fuzzy matcher should continue to support strong lexical matches such as:

    Building Value → Building Value
    Number of Buildings → Number of Buildings
    Building Count → Number of Buildings
    # Of Buildings → Number of Buildings
    Bldg Repl Cost → Building Value

but should not treat:

    Building → Number of Buildings

as a strong deterministic match.

## Principle

Generic terms must not receive deterministic confidence merely because
they are contained inside a more specific target phrase.

The fuzzy layer is a candidate-generation mechanism, not the final
semantic authority.

Ambiguous generic headers should be allowed to proceed to:

1. value profiling
2. semantic embeddings
3. cross-encoder reranking
4. LLM reasoning
5. human review when confidence remains insufficient

## Expected Behavior

| Source Header | Expected Fuzzy Behavior |
|---|---|
| Building Value | Building Value |
| Bldg Repl Cost | Building Value |
| Number of Buildings | Number of Buildings |
| Building Count | Number of Buildings |
| # Of Buildings | Number of Buildings |
| Building | Not deterministically mapped to Number of Buildings |

## Scope

This guardrail applies only to fuzzy candidate generation.

The following components remain unchanged:

- fuzzy threshold: 0.75
- Hungarian one-to-one assignment
- minimum global assignment score: 0.50
- semantic retrieval
- cross-encoder reranking
- LLM decision layer
- target schema

## Validation

A regression test must verify that:

    fuzzy_match_header("Building")

does not return:

    Number of Buildings

as a deterministic fuzzy match with high confidence.

Existing fuzzy matcher tests must continue to pass.