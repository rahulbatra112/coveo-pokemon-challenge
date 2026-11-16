# Decision log – Coveo Pokémon Challenge

## D1 – Presentation scope follows the FDE brief
- Context: The pre-sales handout allows a demo and includes a customer pitch. The FDE brief asks for a non-demo deep dive plus Escalation & Recovery.
- Decision: Follow the FDE brief. Keep a short customer segment at the end of Topic 1.
- Why: The brief is role-specific, and its changes show what's being assessed: judgment and operations.

## D2 – Web source (crawler) instead of a Push source
- Options: Coveo Web source vs. scraping the site myself and pushing items.
- Decision: Web source.
- Why: The content already exists as public web pages. The crawler handles discovery, polite crawling and re-crawls with no code to maintain. Push fits content that has no crawlable page.

## D3 – Test selectors before crawling
- Decision: Validated all five selectors with Coveo's Web Scraper Helper on four edge cases: Moltres (regional form tab), Bulbasaur (dual type), Mr. Mime (hyphenated name plus regional form), Sprigatito (newest generation).
- Why: Every wrong selector costs a full re-crawl. Types are scoped to the active form tab, so Galarian types don't leak in.

## D4 – National Pokédex number as a unique key
- Decision: Extract the national number as its own field.
- Why: The site serves the same Pokémon under several URLs (e.g. /pokedex/1 and /pokedex/bulbasaur). The number makes duplicates visible and gives a stable sort.

## D5 – Sitemap source for the full catalog
- Evidence: The site's sitemap lists each Pokémon's canonical page (/pokedex/bulbasaur, priority 1.0), with no numeric aliases, plus up to nine /pokedex/<name>/moves/N pages per Pokémon.
- Decision: Sitemap source, with an inclusion rule matching exactly one name after /pokedex/.
- Why: No stray start page, no duplicate URLs, faster refreshes, and Coveo itself suggests a sitemap when one exists. A loose "contains /pokedex/" rule would have indexed thousands of move pages.
- Risk: Depends on the sitemap staying complete. Checked by reconciling the indexed count against the National Pokédex.

## D6 – Public search key with least privilege
- Decision: Anonymous search template ("Can be public"), locked to the search hub "Pokedex".
- Why: The key ships in browser code, so it can only run queries and send analytics. The search hub keeps this page's analytics separate and lets us route its traffic to its own pipeline and models.

## D7 – Atomic for the search page
- Options: Atomic (ready-made web components) vs. Headless (state library, build every UI piece myself).
- Decision: Atomic, pinned to v3.57.3.
- Why: Fastest path to a complete, accessible UI with analytics built in, and the facets, answer box and type-ahead are drop-in components. Headless is the right call when a customer needs full control over the UI or their own framework. Pinning the version keeps the page stable.

## D8 – Partial match for question-style queries
- Evidence: "What does Charmander evolve into?" returned only Bulbasaur, because every word had to match. RGA correctly refused to answer.
- Decision: Partial match on the Pokedex pipeline (3+ keywords, 50% must match).
- Why: Generated answers can only use pages that search retrieves first. Short name searches stay strict.

## D9 – Prompt instruction for concise answers
- Evidence: The Charmander answer was correct but dumped stats, moves and locations.
- Decision: Custom RGA prompt instruction limiting answers to 1–3 sentences unless the question asks for detail.
- Why: Answers should match the question. The longer-term fix is cleaner content: excluding move and location tables from what gets indexed.

## D10 – Preload type-ahead from the index itself
- Evidence: The QS model showed 0 candidates and "Limited": 1 search and 0 clicks in the org.
- Decision: Generate the Default Queries file from my own index (every Pokémon name, plus type and question queries) and upload it through the Advanced Model Configurations API, using a temporary private key with one privilege.
- Why: Every suggestion is guaranteed to return a real result. The script is reusable for any customer facing a cold start.

## D11 – Detail page on the Search API directly
- Decision: A plain HTML page that fetches one item by URL from the Search API, shows related Pokémon of the same type, and hands questions off to RGA on the search page.
- Why: A detail page needs full layout control, which Atomic's components don't give, and plain fetch calls keep it dependency-free. Public settings live in one shared config.js.

## D12 – Passage Retrieval works; content quality is the ceiling
- Evidence: The PR API returned the right pages (Gecqua first, fresh content a general AI model wouldn't know), but most passages were navigation and move/type tables, and Eevee's evolution text missed the top 5.
- Decision: Keep content as is for the demo. Next iteration: exclude move, TM, location and sprite tables plus navigation at indexing, then rebuild the models.
- Why: Answers and passages can only be as good as the chunks behind them. Changing content right before the panel risks the index and models being out of sync.

## D14: Turn on Automatic Relevance Tuning before there is traffic
- Decision: Created "Pokedex ART" and associated it with the Pokedex pipeline (November 16, 2026).
- Why: it learns which results people click, so switching it on now means it learns from the first real visitors, with no change to the page.
- Evidence: build in progress with 0 search events, 0 clicks and 0 learned queries. Coveo's documentation says an org needs enough data first, so I don't claim it changes rankings yet.

## D13 – Stop words for question words
- Evidence: Question-style queries matched hundreds of pages through words like "what," "does" and "into."
- Decision: Stop word rule on the Pokedex pipeline (what, which, who, how, does, do, did, is, are, was, the, a, an, into, of, as, in, to, for).
- Result: 857 → 500 results, with the right Pokémon ranked first. Stop words don't affect the query RGA uses, so answers were unchanged.
