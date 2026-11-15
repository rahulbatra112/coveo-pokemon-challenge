# Pokedex search health probe

Org `69ydoe1s4lcvoorg`, search hub `Pokedex`, 5 rounds, 1.5s between requests.

| Layer | OK | Errors | Typical (ms) | Slowest (ms) | Working | Last check |
|---|---|---|---|---|---|---|
| Search results | 5/5 | none | 301 | 523 | 5/5 | 855 results |
| Type-ahead (QS) | 5/5 | none | 150 | 384 | 5/5 | 3 suggestions |
| Generated answers (RGA) | 5/5 | none | 277 | 465 | 5/5 | answer generation started |
| Passages (PR API) | 5/5 | none | 232 | 435 | 5/5 | 1 passages |

**All layers healthy.**

Note: a 200 status alone is not health. "Working" checks the feature itself (results returned, suggestions returned, answer started, passages returned).