#!/usr/bin/env python3
"""
Preload the "Pokedex QS" Query Suggestions model with a Default Queries file.

Why: a QS model learns from past searches and clicks. A brand-new org has none,
so type-ahead would stay empty (the "cold start" problem). Coveo's documented
fix for test or low-traffic environments is a Default Queries file uploaded
through the Advanced Model Configurations API.

What this script does:
  1. Reads every Pokemon name from YOUR Coveo index (Search API, public key),
     so every suggestion is guaranteed to match a real result.
  2. Adds type queries and a few question-style queries.
  3. Writes default-queries.csv (one "query,weight" per line).
  4. Finds the QS model and uploads the file to it (private key).
  5. Downloads the file back from Coveo to prove the upload worked.

Run:  python3 qs_preload.py
You'll be asked for two keys (input is hidden). Nothing is saved to disk
except default-queries.csv, which contains no secrets.
"""

import csv
import getpass
import io
import json
import sys
import urllib.error
import urllib.request
import uuid

ORG_ID = "69ydoe1s4lcvoorg"
SEARCH_HUB = "Pokedex"
SEARCH_URL = f"https://{ORG_ID}.org.coveo.com/rest/search/v2"
PLATFORM = "https://platform.cloud.coveo.com"
MODELS_URL = f"{PLATFORM}/rest/organizations/{ORG_ID}/machinelearning/models"
CSV_PATH = "default-queries.csv"

# Popular Pokemon get a higher weight so they rank first in type-ahead.
POPULAR = [
    "Pikachu", "Charizard", "Eevee", "Mewtwo", "Mew", "Gengar", "Lucario",
    "Greninja", "Bulbasaur", "Charmander", "Squirtle", "Snorlax", "Dragonite",
    "Gyarados", "Umbreon", "Sylveon", "Rayquaza", "Garchomp", "Mimikyu",
    "Jigglypuff",
]

TYPES = [
    "Bug", "Dark", "Dragon", "Electric", "Fairy", "Fighting", "Fire", "Flying",
    "Ghost", "Grass", "Ground", "Ice", "Normal", "Poison", "Psychic", "Rock",
    "Steel", "Water",
]

# Question-style queries that also show off generated answers (RGA).
QUESTIONS = [
    "what does eevee evolve into",
    "what does charmander evolve into",
    "what type is charizard",
    "which pokemon is known as the flame pokemon",
    "what is pikachu weak to",
]

WEIGHT_POPULAR = 100
WEIGHT_TYPE = 50
WEIGHT_QUESTION = 40
WEIGHT_NAME = 20


def http(method, url, key, body=None, content_type="application/json"):
    """Small helper around urllib that returns (status, text)."""
    headers = {"Authorization": f"Bearer {key}"}
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")


def explain(status):
    hints = {
        401: "The key was rejected. Check that you pasted the whole key, with no spaces.",
        403: "The key is valid but lacks the privilege. For the upload key, it needs "
             "Machine Learning > Models > Edit.",
        404: "Not found. Check the model ID (or the org/region in this script).",
        429: "Rate limited. Wait a minute and run again.",
    }
    return hints.get(status, "Unexpected response, see the message above.")


def fetch_pokemon_names(search_key):
    """Page through the index and collect every pokemon_name."""
    names, first, page = [], 0, 500
    while True:
        payload = {
            "q": "",
            "searchHub": SEARCH_HUB,
            "numberOfResults": page,
            "firstResult": first,
            "fieldsToInclude": ["pokemon_name"],
        }
        status, text = http("POST", SEARCH_URL, search_key, json.dumps(payload).encode())
        if status != 200:
            print(f"Search API returned {status}: {text[:300]}")
            print(explain(status))
            sys.exit(1)
        data = json.loads(text)
        results = data.get("results", [])
        for r in results:
            name = (r.get("raw") or {}).get("pokemon_name")
            if isinstance(name, list):
                name = name[0] if name else None
            if name:
                names.append(name.strip())
        first += len(results)
        if not results or first >= data.get("totalCount", 0):
            break
    # De-duplicate while keeping order
    seen, unique = set(), []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            unique.append(n)
    return unique


def build_rows(names):
    present = {n.lower() for n in names}
    rows = []
    for n in POPULAR:
        if n.lower() in present:
            rows.append((n, WEIGHT_POPULAR))
    popular_lower = {p.lower() for p in POPULAR}
    for n in names:
        if n.lower() not in popular_lower:
            rows.append((n, WEIGHT_NAME))
    for t in TYPES:
        rows.append((f"{t} type pokemon", WEIGHT_TYPE))
    for q in QUESTIONS:
        rows.append((q, WEIGHT_QUESTION))
    return rows


def write_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for query, weight in rows:
        writer.writerow([query, weight])
    text = buf.getvalue()
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    return text.encode("utf-8")


def find_qs_model(ml_key):
    status, text = http("GET", MODELS_URL, ml_key)
    if status != 200:
        print(f"Could not list models ({status}): {text[:300]}")
        print(explain(status))
        return None
    data = json.loads(text)
    models = data if isinstance(data, list) else next(
        (v for v in data.values() if isinstance(v, list)), [])
    qs = [m for m in models if "querysuggest" in json.dumps(m).lower()]
    if len(qs) == 1:
        return qs[0].get("id")
    if qs:
        print("Found more than one Query Suggestions model:")
        for m in qs:
            print("  ", m.get("id"), "|", m.get("modelDisplayName") or m.get("modelName"))
    return None


def upload(ml_key, model_id, csv_bytes):
    url = (f"{MODELS_URL}/{model_id}/configs/DEFAULT_QUERIES?languageCode=en")
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="configFile"; filename="{CSV_PATH}"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    status, text = http("PUT", url, ml_key, body,
                        content_type=f"multipart/form-data; boundary={boundary}")
    return url, status, text


def main():
    print("Step 1 of 4: reading Pokemon names from your index")
    search_key = getpass.getpass("  Paste your PUBLIC search key (Anonymous search), then Enter: ").strip()
    names = fetch_pokemon_names(search_key)
    print(f"  Found {len(names)} Pokemon names.")

    print("Step 2 of 4: writing the preload file")
    rows = build_rows(names)
    csv_bytes = write_csv(rows)
    print(f"  Wrote {len(rows)} queries to {CSV_PATH}.")

    print("Step 3 of 4: finding your Query Suggestions model")
    ml_key = getpass.getpass("  Paste your PRIVATE key (Machine Learning > Models > Edit), then Enter: ").strip()
    model_id = find_qs_model(ml_key)
    if not model_id:
        model_id = input("  Paste the QS model ID (it contains 'querysuggest'): ").strip()
    print(f"  Using model: {model_id}")

    print("Step 4 of 4: uploading and verifying")
    url, status, text = upload(ml_key, model_id, csv_bytes)
    if status not in (200, 201, 202, 204):
        print(f"  Upload failed ({status}): {text[:300]}")
        print("  " + explain(status))
        sys.exit(1)
    print(f"  Upload succeeded ({status}).")

    status, text = http("GET", url, ml_key)
    if status == 200:
        preview = "\n".join(text.splitlines()[:5])
        print("  Coveo now has this file. First lines:")
        print("  " + preview.replace("\n", "\n  "))
    else:
        print(f"  Upload looked fine, but reading it back returned {status}. "
              "Check the model in the Admin Console.")

    print("\nDone. Suggestions appear after the model's next build (it rebuilds daily).")


if __name__ == "__main__":
    main()