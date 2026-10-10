#!/usr/bin/env python3
"""Regenerate the CertWatch card on the portfolio page from CertWatch's own repository.

It reads two things from https://github.com/ooseni/certwatch:
  - the roadmap in README.md, where each phase is a line "- ✅ **Phase N**: ..." (done) or
    "- ⬜ **Phase N**: ..." (planned);
  - the status of every architecture decision record in docs/decisions (MADR front matter).
It then rewrites only the parts of index.html between <!-- certwatch:NAME --> and
<!-- /certwatch:NAME --> markers: the status line and the Built, Next and Decisions bullets.
Everything else on the page, including the hand-written bullets, is left alone.

    python scripts/update_certwatch_card.py              # show what would change; exit 1 if out of date
    python scripts/update_certwatch_card.py --write      # update index.html
    python scripts/update_certwatch_card.py --summary    # print e.g. "phases 1–3 of 7", for commit messages
    python scripts/update_certwatch_card.py --certwatch-dir ~/projects/certwatch   # read a local clone

Standard library only. Set GITHUB_TOKEN to raise the GitHub API rate limit (GitHub Actions does).
Exit codes: 0 up to date (or written), 1 out of date (check mode), 2 an input could not be read.
"""
import argparse
import difflib
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = "ooseni/certwatch"
BRANCH = "main"
PAGE = Path(__file__).resolve().parent.parent / "index.html"

# Wording per phase, so the card reads like the rest of the page. A phase missing here (if the
# roadmap grows) falls back to its own roadmap description.
BUILT = {
    1: "a health-checked API scaffold with unit tests and linting",
    2: "a domain CRUD API on API Gateway (HTTP API), Lambda and DynamoDB",
    3: "daily certificate checks through EventBridge Scheduler with SNS email alerts",
    4: "a live dev-stage deployment on AWS with smoke tests",
    5: "OIDC-based CI/CD through GitHub Actions with no stored AWS keys",
    6: "authentication, least-privilege IAM and security scanning",
    7: "complete documentation with a cost breakdown",
}
NEXT = {
    1: "a health-checked API scaffold with unit tests and linting",
    2: "a domain CRUD API on DynamoDB with integration tests on LocalStack",
    3: "daily certificate checks through EventBridge Scheduler with SNS email alerts",
    4: "deployment to AWS (dev stage) with smoke tests",
    5: "CI/CD through GitHub Actions with OIDC, so no AWS keys are stored",
    6: "authentication, least-privilege IAM, tracing, alarms and security scanning",
    7: "full documentation, a cost breakdown and the final design decisions",
}
WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
         "fifteen sixteen seventeen eighteen nineteen twenty").split()
STATUS_ORDER = ["accepted", "proposed", "superseded", "deprecated", "rejected"]
MARKER = re.compile(r"(<!-- certwatch:(\w+) -->)(.*?)(<!-- /certwatch:\2 -->)", re.S)


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def words(n: int) -> str:
    return WORDS[n] if 0 <= n < len(WORDS) else str(n)


# ---------- reading CertWatch ----------

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ooseni-portfolio-card"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def read_certwatch(local: str | None) -> tuple[str, dict[str, str], str]:
    """Return (README text, {adr filename: text}, decision-log README text)."""
    if local:
        root = Path(local).expanduser()
        readme = (root / "README.md").read_text(encoding="utf-8")
        dec = root / "docs" / "decisions"
        adrs = {p.name: p.read_text(encoding="utf-8") for p in sorted(dec.glob("[0-9][0-9][0-9][0-9]-*.md"))}
        log = (dec / "README.md").read_text(encoding="utf-8") if (dec / "README.md").exists() else ""
        return readme, adrs, log
    raw = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
    try:
        readme = _get(f"{raw}/README.md").decode("utf-8")
        listing = json.loads(_get(f"https://api.github.com/repos/{REPO}/contents/docs/decisions?ref={BRANCH}"))
        names = sorted(e["name"] for e in listing if re.match(r"^\d{4}-.*\.md$", e["name"]))
        adrs = {n: _get(f"{raw}/docs/decisions/{n}").decode("utf-8") for n in names}
        log = _get(f"{raw}/docs/decisions/README.md").decode("utf-8")
    except Exception as e:  # network or API error: never write a card from partial data
        fail(f"could not read {REPO}: {e}")
    return readme, adrs, log


def roadmap(readme: str) -> list[tuple[int, bool, str]]:
    phases = [(int(n), mark == "✅", desc.strip())
              for mark, n, desc in re.findall(r"^- (✅|⬜) \*\*Phase (\d+)\*\*:\s*(.+)$", readme, re.M)]
    if not phases:
        fail("no roadmap phases found in CertWatch's README (expected '- ✅ **Phase N**: ...')")
    return sorted(phases)


def adr_statuses(adrs: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, text in adrs.items():
        front = re.match(r"^---\n(.*?)\n---", text, re.S)
        m = re.search(r'^status:\s*"?([A-Za-z ]+?)"?\s*$', front.group(1) if front else "", re.M | re.I)
        if not m:
            fail(f"{name} has no status in its front matter")
        status = m.group(1).strip().lower()
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        fail("no architecture decision records found in docs/decisions")
    return counts


# ---------- writing the card ----------

def plain(desc: str) -> str:
    """A roadmap description as plain, escaped text (for phases with no wording above)."""
    return html.escape(re.sub(r"[`*_]", "", desc))


def join(items: list[str]) -> str:
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def phase_range(done: list[int]) -> str:
    if done == list(range(1, len(done) + 1)):
        return f"phases 1–{done[-1]}" if len(done) > 1 else "phase 1"
    return f"{len(done)} phases"


def summary(phases) -> str:
    done = [n for n, ok, _ in phases if ok]
    total = len(phases)
    if len(done) == total:
        return f"all {total} phases"
    return f"{phase_range(done)} of {total}" if done else f"0 of {total} phases"


def render(phases, statuses: dict[str, int], log: str) -> dict[str, str]:
    done = [n for n, ok, _ in phases if ok]
    todo = [(n, d) for n, ok, d in phases if not ok]
    total = len(phases)
    descs = {n: d for n, _, d in phases}

    if len(done) == total:
        status = f"Complete · all {total} phases done"
    elif done:
        status = f"In progress · {summary(phases)} done"
    else:
        status = f"Starting · 0 of {total} phases done"

    shown = [n for n in done if not (n == 1 and len(done) > 1)]  # the scaffold is part of every later phase
    built = join([BUILT.get(n) or plain(descs[n]) for n in shown])
    built = f"{built}, all defined with AWS SAM and tested against LocalStack." if built else "the project scaffold is under way."

    upcoming = [NEXT.get(n) or plain(d) for n, d in todo[:2]]
    nxt = (upcoming[0] + (f", then {upcoming[1]}" if len(upcoming) > 1 else "") + ".") if upcoming \
        else f"all {words(total)} planned phases are complete."

    n_adr = sum(statuses.values())
    order = STATUS_ORDER + sorted(s for s in statuses if s not in STATUS_ORDER)
    parts = [f"{words(statuses[s])} {s}" + (" for the next phases" if s == "proposed" else "")
             for s in order if statuses.get(s)]
    if len(parts) == 1 and statuses.get("accepted") == n_adr:
        decisions = f"{words(n_adr)} architecture decision records, all accepted"
    else:
        listed = f"{parts[0]} and {parts[1]}" if len(parts) == 2 else join(parts)
        decisions = f"{words(n_adr)} architecture decision records, {listed}"
    slides = re.search(r"(\d+)-slide deck", log)
    if slides:
        older = re.search(r"predates ADR-0*(\d+)", log)
        covered = int(older.group(1)) - 1 if older else n_adr
        decisions += (f", also presented as a {slides.group(1)}-slide ADR deck" if covered >= n_adr
                      else f"; the first {words(covered)} are also presented as a {slides.group(1)}-slide ADR deck")
    decisions += "."

    return {
        "status": f'<p class="status"><span class="dot" aria-hidden="true"></span> {status}</p>',
        "built": f"<li><strong>Built:</strong> {built}</li>",
        "next": f"<li><strong>Next:</strong> {nxt}</li>",
        "decisions": f"<li><strong>Decisions on record:</strong> {decisions}</li>",
    }


def apply(page: str, blocks: dict[str, str]) -> str:
    found = {m.group(2) for m in MARKER.finditer(page)}
    missing = set(blocks) - found
    if missing:
        fail(f"index.html is missing the markers for: {', '.join(sorted(missing))}")
    return MARKER.sub(lambda m: m.group(1) + blocks.get(m.group(2), m.group(3)) + m.group(4), page)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="update index.html instead of only showing the change")
    ap.add_argument("--summary", action="store_true", help='print the progress, e.g. "phases 1–3 of 7"')
    ap.add_argument("--certwatch-dir", help="read a local CertWatch clone instead of GitHub")
    ap.add_argument("--page", default=str(PAGE), help="the page to update (default: index.html)")
    a = ap.parse_args()

    readme, adrs, log = read_certwatch(a.certwatch_dir)
    phases = roadmap(readme)
    if a.summary:
        print(summary(phases))
        return
    page_path = Path(a.page)
    page = page_path.read_text(encoding="utf-8")
    new = apply(page, render(phases, adr_statuses(adrs), log))
    if new == page:
        print(f"CertWatch card is up to date ({summary(phases)})")
        return
    diff = difflib.unified_diff(page.splitlines(), new.splitlines(), "index.html", "index.html (updated)", lineterm="", n=0)
    print("\n".join(diff))
    if a.write:
        page_path.write_text(new, encoding="utf-8", newline="\n")
        print(f"updated {page_path.name}: {summary(phases)}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
