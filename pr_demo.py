#!/usr/bin/env python3
"""
Bonus: Coveo Passage Retrieval (PR) API demo for the Pokedex org.

Passage Retrieval returns the most relevant passages (chunks of text) for a
question, with relevance scores and sources, so a customer's OWN AI model can
write the answer. Coveo handles retrieval (lexical + semantic, permissions,
relevance tuning); the customer keeps control of the model, prompt and UI.

What this script does:
  1. Sends each question to the PR API through the Pokedex search hub,
     so it uses the Pokedex pipeline and its Passage Retrieval model.
  2. Prints the passages with relevance scores and sources.
  3. Builds the grounded prompt a customer's LLM would receive.
  4. Optional: if ANTHROPIC_API_KEY is set, asks an LLM to answer
     from those passages only (bring-your-own-LLM).
  5. Saves everything to pr_demo_output.md, ready for your slides.

Run (from the project folder, so it can read config.js):
  python3 pr_demo.py                          # three sample questions
  python3 pr_demo.py "What does Eevee evolve into?"
"""

import getpass
import json
import os
import re
import sys
import urllib.error
import urllib.request

ORG_ID = "69ydoe1s4lcvoorg"
SEARCH_HUB = "Pokedex"
PR_URL = f"https://{ORG_ID}.org.coveo.com/rest/search/v3/passages/retrieve"
OUTPUT = "pr_demo_output.md"
MAX_PASSAGES = 5

SAMPLE_QUESTIONS = [
    "What does Eevee evolve into?",
    # Gecqua was revealed recently, so a general-purpose LLM is unlikely to know it.
    # Retrieval is what lets an AI answer about fresh content.
    "What is Gecqua?",
    # A "list every X" question: shows where passages help and where structured data wins.
    "Which Pokemon are known as the Flame Pokemon?",
]

LLM_MODEL = "claude-haiku-5-5"


def read_public_key():
    """Reuse the public key from config.js so you don't have to paste it."""
    try:
        with open("config.js", encoding="utf-8") as f:
            match = re.search(r'accessToken:\s*"([^"]+)"', f.read())
            if match and "PASTE_YOUR" not in match.group(1):
                return match.group(1)
    except FileNotFoundError:
        pass
    return getpass.getpass("Paste your PUBLIC search key (Anonymous search), then Enter: ").strip()


def post_json(url, headers, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")


def retrieve_passages(key, question):
    payload = {
        "query": question,
        "searchHub": SEARCH_HUB,
        "maxPassages": MAX_PASSAGES,
        "additionalFields": ["clickableuri", "pokemon_name"],
        "localization": {"locale": "en-CA", "timezone": "America/Toronto"},
    }
    status, body = post_json(PR_URL, {"Authorization": f"Bearer {key}"}, payload)
    if status == 400 and isinstance(body, str) and "searchHub" in body:
        # Fallback: the key already enforces the search hub, so it can be omitted
        payload.pop("searchHub")
        status, body = post_json(PR_URL, {"Authorization": f"Bearer {key}"}, payload)
    if status != 200:
        print(f"  Passage Retrieval API returned {status}: {str(body)[:400]}")
        hints = {401: "Key rejected: check config.js.",
                 403: "Key lacks permission for Passage Retrieval: tell Claude, we'll create a key for it.",
                 429: "Rate limited (this org allows 5 passage queries per second). Wait and rerun."}
        if status in hints:
            print("  " + hints[status])
        return None
    passages = []
    for item in body.get("items", []):
        doc = item.get("document") or {}
        name = doc.get("pokemon_name") or doc.get("title") or "Unknown"
        if isinstance(name, list):
            name = name[0]
        passages.append({
            "text": " ".join((item.get("text") or "").split()),
            "score": item.get("relevanceScore"),
            "source": name,
            "url": doc.get("clickableuri") or doc.get("uri") or "",
        })
    return passages


def grounded_prompt(question, passages):
    lines = [
        "You are a Pokedex assistant. Answer the question using only the passages below.",
        "Cite the passages you use as [1], [2], and so on.",
        "If the passages don't contain the answer, say so plainly.",
        "",
        f"Question: {question}",
        "",
        "Passages:",
    ]
    for i, p in enumerate(passages, 1):
        lines.append(f"[{i}] ({p['source']}) {p['text']}")
    return "\n".join(lines)


def ask_llm(prompt):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    status, body = post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        {"model": LLM_MODEL, "max_tokens": 400,
         "messages": [{"role": "user", "content": prompt}]})
    if status != 200:
        return f"(LLM call failed with {status}: {str(body)[:200]})"
    return "".join(block.get("text", "") for block in body.get("content", []))


def main():
    questions = sys.argv[1:] or SAMPLE_QUESTIONS
    key = read_public_key()
    report = ["# Passage Retrieval demo", "",
              f"Org `{ORG_ID}`, search hub `{SEARCH_HUB}`, up to {MAX_PASSAGES} passages per question.", ""]

    for q in questions:
        print(f"\nQUESTION: {q}")
        passages = retrieve_passages(key, q)
        if passages is None:
            sys.exit(1)
        report += [f"## {q}", ""]
        if not passages:
            print("  No passages returned.")
            report += ["No passages returned.", ""]
            continue

        for i, p in enumerate(passages, 1):
            score = f"{p['score']:.2f}" if isinstance(p["score"], (int, float)) else "n/a"
            snippet = p["text"][:220] + ("..." if len(p["text"]) > 220 else "")
            print(f"  [{i}] score {score} | {p['source']} | {p['url']}")
            print(f"      {snippet}")
            report.append(f"{i}. **{p['source']}** (score {score}): {snippet} ([source]({p['url']}))")
        report.append("")

        prompt = grounded_prompt(q, passages)
        report += ["**Grounded prompt a customer's LLM would receive:**", "", "```", prompt, "```", ""]

        answer = ask_llm(prompt)
        if answer:
            print(f"\n  LLM answer ({LLM_MODEL}), grounded in the passages above:\n  {answer}")
            report += [f"**Answer from {LLM_MODEL}, using only these passages:**", "", answer, ""]

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nSaved everything to {OUTPUT}.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Tip: set ANTHROPIC_API_KEY to also generate answers from the passages (optional).")


if __name__ == "__main__":
    main()
