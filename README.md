# Pokédex search on Coveo

**Live site:** https://rahulbatra112.github.io/coveo-pokemon-challenge/

Built for Coveo's Forward Deployed Engineer technical challenge (the "Pokémon Challenge"): every Pokémon page on [pokemondb.net](https://pokemondb.net), indexed in a Coveo organization and searchable by name or plain-language question.

## What it does

- Searches 1,028 Pokémon pages, filterable by **type** and **generation**
- Shows each Pokémon's official artwork in the results
- Answers questions with **generated answers and citations** (Coveo Relevance Generative Answering)
- Suggests queries as you type (**Query Suggestions**, preloaded from the index)
- Opens a **detail page** per Pokémon, with related Pokémon and one-click questions
- Demonstrates the **Passage Retrieval API** for teams that bring their own AI model (Bonus)

## Architecture

```
pokemondb.net sitemap
      │  Sitemap source: Pokémon pages only, selectors in web-scraping.json
      ▼
Coveo index: 1,028 items
  fields: pokemon_name, pokemon_number, pokemon_types, pokemon_generation, pokemon_image
      │
      ▼
"Pokedex" query pipeline  (condition: search hub is "Pokedex")
  partial match + stop words
  ML models: Semantic Encoder, Relevance Generative Answering,
             Passage Retrieval, Query Suggestions
      │
      ├── index.html   search page (Coveo Atomic 3.57.3), hosted on GitHub Pages
      ├── pokemon.html detail page (Search API)
      └── pr_demo.py   Passage Retrieval API demo
```

## Coveo configuration

| Area | Configuration |
|---|---|
| Source | Sitemap source on `https://pokemondb.net/static/sitemaps/pokemondb.xml`. Inclusion: `^https://pokemondb\.net/pokedex/[a-z0-9-]+$` (one name after `/pokedex/`, so move, sprite and artwork pages are skipped). Exclusion: the site's list pages (`national`, `all`, `shiny`, `stats`, `game`, `random`). |
| Web scraping | Five selectors, validated with Coveo's Web Scraper Helper on four edge cases before crawling. Types are scoped to the active form tab so regional forms don't leak in. |
| Fields | `pokemon_types` (multi-value facet), `pokemon_generation` (facet), `pokemon_number` (Integer 32, sortable), `pokemon_name` (free-text searchable), `pokemon_image` (display only) |
| Pipeline | Dedicated `Pokedex` pipeline routed by search hub. Partial match (3+ keywords, 50% must match) and stop words for question words. |
| Models | Semantic Encoder and Relevance Generative Answering on the same content (RGA with a custom prompt instruction and the required "query is not empty" condition), Passage Retrieval, and Query Suggestions (daily build, preloaded). |
| Security | The page uses a public **Anonymous search** key locked to the `Pokedex` search hub (in `config.js`). Admin tasks use private keys created for one job with a single privilege and a short expiry, entered at the terminal and never stored in the repo. |

## Files

| File | Purpose |
|---|---|
| `index.html` | Search page: Atomic components, facets, generated answers, type-ahead |
| `pokemon.html` | Detail page: fetches one item from the Search API, plus related Pokémon |
| `config.js` | Org ID, public key and search hub, shared by both pages |
| `web-scraping.json` | Web scraping configuration (exclusions and metadata selectors) |
| `qs_preload.py` | Builds the Query Suggestions preload file from the index and uploads it through the Advanced Model Configurations API |
| `default-queries.csv` | The preload file: 1,028 Pokémon names plus type and question queries (1,051 rows) |
| `pr_demo.py` / `pr_demo_output.md` | Passage Retrieval API demo and a saved run |
| `DECISIONS.md` | Every design decision, with the evidence behind it |

## Run it locally

```bash
python3 -m http.server 8000      # then open http://localhost:8000
python3 pr_demo.py               # Passage Retrieval demo (reads the public key from config.js)
python3 qs_preload.py            # needs a private key with Machine Learning > Models > Edit
```

## Data notes

- **1,028 = 1,025 + 3.** The National Pokédex has 1,025 numbered Pokémon. The other 3 are newly revealed Generation 10 Pokémon whose numbers are still "???" on pokemondb.net. The integer field stores "???" as 0, so the detail page shows `#???`.
- **Cold start.** The org had 1 search and 0 clicks, so Query Suggestions had nothing to learn from. The preload file seeds it with queries that are guaranteed to return results.

## Known limitations and next steps

- **Content quality caps AI quality.** Passages and answers still include navigation text and large move/type tables. Next: exclude those sections at indexing, then rebuild the models.
- **"List every X" questions** (for example, every "Flame Pokémon") are better served by structured data. Next: a `pokemon_species` field and facet.
- **Unannounced numbers** should be cleaned at ingestion rather than in the UI.
- **Atomic link filter.** Atomic only accepts absolute links (or ones starting with `/`), so the detail-page address is built at runtime to work on both localhost and GitHub Pages.
