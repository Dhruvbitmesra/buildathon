# STEP 02 — SCHEMA INTELLIGENCE / SCHEMA MAPPING AGENT

## 1. Purpose

The Schema Intelligence Agent maps raw column headers from the selected SOV sheet to the
canonical target SOV schema.

Different insurance SOV files use different naming conventions.

Examples:

- `Bldg Repl Cost New` → `Building Value`
- `Bldg Value` → `Building Value`
- `Const.` → `Construction`
- `Occ.` → `Occupancy`
- `Yr Built` → `Year Built`
- `Loc #` → `Reference`

The objective is not simple string matching.

The agent must combine:

1. Header text
2. Normalised header text
3. Insurance abbreviation knowledge
4. Fuzzy similarity
5. Column value profiles
6. Semantic embeddings
7. Previously approved mappings
8. LLM reasoning for unresolved ambiguity

The core design principle is:

> Deterministic first, LLM last.

The LLM proposes a mapping for difficult cases, but it does not directly modify
the source data.

---

# 2. Why Agent 2 Is Required

Agent 1 identifies the correct worksheet and header row.

It does NOT determine what every source column means.

For example, a source workbook may contain:

| Source Column | Possible Meaning |
|---|---|
| Bldg Repl Cost New | Building Value |
| Bldg | Number of Buildings / Building-related field |
| Contents | Contents |
| BI | Business Income |
| Occ | Occupancy |
| Const | Construction |
| Yr Built | Year Built |
| Loc # | Reference |

Simple exact matching works for obvious fields such as:

`Contents → Contents`

but fails for:

`Bldg Repl Cost New → Building Value`

Therefore Agent 2 performs schema intelligence.

---

# 3. Input

Agent 2 receives the output of Agent 1.

Expected information:

- Source file name
- Selected sheet
- Detected header row
- Normalised source column names
- Raw source column names
- DataFrame
- Column profiles
- Sheet classification
- Agent 1 confidence
- Warnings

Example:

```text
file_name:
SOV_B4ID.xlsx

selected_sheet:
SOV

columns:
[
    "Loc #",
    "Bldg Repl Cost New",
    "Contents",
    "BI",
    "Occ",
    "Const",
    "Yr Built"
]