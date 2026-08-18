# Municipal code corpus — source and attribution

City of Monrovia, California, Municipal Code, Title 17 (Zoning), Chapter 17.44
"Special Uses" (37 sections, numbering `17.44.NNN`). Retrieved 2026-08-18 from
the American Legal Publishing Code Library:
https://codelibrary.amlegal.com/codes/monrovia/latest/monrovia_ca/0-0-0-73051

Municipal ordinances are public records; this compilation is hosted by American
Legal Publishing, which states these documents are provided "for informational
purposes only" and "should not be relied upon as the definitive authority for
local legislation." The text is used here exclusively as reference material for
synthetic demonstration scenarios — never as legal advice. No affiliation with
or endorsement by the City of Monrovia or American Legal Publishing.

**Retrieval method:** one-time manual fetch of the chapter's section pages on
the date above (rate-limited, browser user-agent); the extracted plain text is
committed under `data/corpus/` with one file per code section, named for its
section number (e.g. `17.44.100.txt`). File identity is the stable citation key
(`Citation.chunk_id`) throughout the system — see ADR-002. No live scraper
ships with this repository.

**Why this chapter:** §17.44.100 (Home occupations) directly governs the demo
scenario (a garage converted to a home bakery), with contestable conditions
(employees, equipment, structural alteration, utilities). Adjacent sections —
§17.44.005 (accessory dwelling units), §17.44.030 (bed and breakfast homes),
§17.44.060 (large family day care) — are near-miss precedents that make
retrieval precision genuinely measurable.
