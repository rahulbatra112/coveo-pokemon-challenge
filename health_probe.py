#!/usr/bin/env python3
"""
Synthetic health probe for the Pokedex search, one check per layer.

Why: when "search is failing under peak," the first question is WHICH layer is
failing. Results, type-ahead, generated answers and passages each have their own
rate ceiling, and the AI layers have the lowest ones. A 200 status code can also
hide a broken feature (for example, type-ahead returning zero suggestions), so
every check tests the function, not just the status code.

What it does:
  - Runs a few gentle rounds (one request at a time, with pauses), far below the
    org's limits. This is monitoring, not a load test: load tests on Coveo must
    be arranged with Coveo first.
  - Reports, per layer: requests OK, errors by status code, typical and slowest
    response time, and whether the feature actually worked.
  - Saves the report to health_report.md.
  - Exits with code 1 if any layer is unhealthy, so a scheduler (cron, GitHub
    Actions) could run it every few minutes and alert.

Run (from the project folder, so it can read config.js):
  python3 health_probe.py            # 5 rounds
  python3 health_probe.py 10         # 10 rounds
"""

import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

ORG_ID = "69ydoe1s4lcvoorg"
SEARCH_HUB = "Pokedex"
BASE = f"https://{ORG_ID}.org.coveo.com/rest/search"
PAUSE_SECONDS = 1.5
REPORT = "health_report.md"


def read_public_key():
    with open("config.js", encoding="utf-8") as f:
        match = re.search(r'accessToken:\s*"([^"]+)"', f.read())
    if not match or "PASTE_YOUR" in match.group(1):
        sys.exit("No public key found in config.js.")
    return match.group(1)


def call(url, key, payload):
    """Returns (status, seconds, parsed_json_or_None)."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, time.perf_counter() - start, body
    except urllib.error.HTTPError as err:
        return err.code, time.perf_counter() - start, None
    except Exception:  # timeouts, DNS, connection resets
        return "network", time.perf_counter() - start, None


# Each check returns (status, seconds, worked: bool, detail: str)
def check_results(key):
    status, secs, body = call(f"{BASE}/v2", key, {
        "q": "pikachu", "searchHub": SEARCH_HUB, "numberOfResults": 3})
    count = (body or {}).get("totalCount", 0)
    return status, secs, status == 200 and count > 0, f"{count} results"


def check_typeahead(key):
    status, secs, body = call(f"{BASE}/v2/querySuggest", key, {
        "q": "pik", "searchHub": SEARCH_HUB, "count": 5, "locale": "en"})
    n = len((body or {}).get("completions", []))
    return status, secs, status == 200 and n > 0, f"{n} suggestions"


def check_answers(key):
    status, secs, body = call(f"{BASE}/v2", key, {
        "q": "What does Charmander evolve into?", "searchHub": SEARCH_HUB, "numberOfResults": 3})
    extended = (body or {}).get("extendedResults") or {}
    started = bool(extended.get("generativeQuestionAnsweringId"))
    return status, secs, status == 200 and started, (
        "answer generation started" if started else "no answer stream detected")


def check_passages(key):
    status, secs, body = call(f"{BASE}/v3/passages/retrieve", key, {
        "query": "What is Gecqua?", "searchHub": SEARCH_HUB, "maxPassages": 3,
        "localization": {"locale": "en-CA", "timezone": "America/Toronto"}})
    n = len((body or {}).get("items", []))
    return status, secs, status == 200 and n > 0, f"{n} passages"


LAYERS = [
    ("Search results", check_results),
    ("Type-ahead (QS)", check_typeahead),
    ("Generated answers (RGA)", check_answers),
    ("Passages (PR API)", check_passages),
]


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    key = read_public_key()
    stats = {name: {"times": [], "errors": {}, "worked": 0, "details": []} for name, _ in LAYERS}

    print(f"Probing {len(LAYERS)} layers x {rounds} rounds, one request at a time...")
    for r in range(1, rounds + 1):
        for name, check in LAYERS:
            status, secs, worked, detail = check(key)
            s = stats[name]
            if status == 200:
                s["times"].append(secs * 1000)
            else:
                s["errors"][str(status)] = s["errors"].get(str(status), 0) + 1
            s["worked"] += int(worked)
            s["details"].append(detail)
            time.sleep(PAUSE_SECONDS)
        print(f"  round {r}/{rounds} done")

    header = (f"| Layer | OK | Errors | Typical (ms) | Slowest (ms) | Working | Last check |\n"
              f"|---|---|---|---|---|---|---|")
    rows, unhealthy = [], []
    for name, _ in LAYERS:
        s = stats[name]
        ok = len(s["times"])
        errors = ", ".join(f"{code}x{n}" for code, n in s["errors"].items()) or "none"
        typical = f"{statistics.median(s['times']):.0f}" if s["times"] else "-"
        slowest = f"{max(s['times']):.0f}" if s["times"] else "-"
        working = f"{s['worked']}/{rounds}"
        if s["worked"] < rounds:
            unhealthy.append(name)
        rows.append(f"| {name} | {ok}/{rounds} | {errors} | {typical} | {slowest} | {working} | {s['details'][-1]} |")

    verdict = ("All layers healthy." if not unhealthy
               else "Needs attention: " + ", ".join(unhealthy) + ".")
    report = "\n".join([
        "# Pokedex search health probe", "",
        f"Org `{ORG_ID}`, search hub `{SEARCH_HUB}`, {rounds} rounds, "
        f"{PAUSE_SECONDS}s between requests.", "",
        header, *rows, "", f"**{verdict}**", "",
        "Note: a 200 status alone is not health. \"Working\" checks the feature itself "
        "(results returned, suggestions returned, answer started, passages returned).",
    ])
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(report)

    print()
    print(header)
    print("\n".join(rows))
    print(f"\n{verdict}\nSaved to {REPORT}.")
    sys.exit(1 if unhealthy else 0)


if __name__ == "__main__":
    main()
