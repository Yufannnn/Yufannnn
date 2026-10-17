"""Refresh GitHub-hosted profile cards using the signed-in owner's repositories.

Run `npm ci` once, then `python scripts/update_profile_cards.py` after signing
in with `gh`. The snake animation is regenerated from the same snapshot.
Only aggregate counts are written; private repository names and commit IDs stay
in memory. Counts cover authored commits on default branches, deduplicated across
repositories, rather than GitHub's separately defined profile contributions.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
USERNAME = "Yufannnn"
EMAILS = [
    "e0773591@u.nus.edu",
    "E0773591@u.nus.edu",
    "yufan.zhu@u.nus.edu",
    "zhuyf@a-star.edu.sg",
]
SGT = timezone(timedelta(hours=8))
NOW = datetime.now(SGT)
TODAY = NOW.date()
START = TODAY - timedelta(days=364)
SINCE = datetime.combine(START, datetime.min.time(), SGT).isoformat()
UNTIL = NOW.isoformat()


def graphql(query):
    result = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps({"query": query}),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    payload = json.loads(result.stdout)
    if payload.get("errors"):
        raise RuntimeError("GitHub could not return complete profile data")
    return payload["data"]


def repositories():
    nodes = []
    cursor = None
    while True:
        after = f",after:{json.dumps(cursor)}" if cursor else ""
        data = graphql("query { viewer { login repositories(first:100,"
                       "ownerAffiliations:OWNER" + after + ") { nodes { "
                       "nameWithOwner isPrivate isFork stargazerCount "
                       "defaultBranchRef { name } } pageInfo { hasNextPage endCursor } } } }")
        viewer = data["viewer"]
        if viewer["login"] != USERNAME:
            raise RuntimeError("Sign in as the profile owner to include private work")
        connection = viewer["repositories"]
        nodes.extend(connection["nodes"])
        if not connection["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = connection["pageInfo"]["endCursor"]


def commits(repo):
    owner, name = repo["nameWithOwner"].split("/")
    records = {}
    cursor = None
    while True:
        after = f",after:{json.dumps(cursor)}" if cursor else ""
        query = ("query { repository(owner:" + json.dumps(owner) + ",name:"
                 + json.dumps(name) + ") { defaultBranchRef { target { ... on Commit { "
                 "history(first:100,since:" + json.dumps(SINCE) + ",until:"
                 + json.dumps(UNTIL) + ",author:{emails:" + json.dumps(EMAILS) + "}"
                 + after + ") { nodes { oid authoredDate } "
                 "pageInfo { hasNextPage endCursor } } } } } } }")
        history = graphql(query)["repository"]["defaultBranchRef"]["target"]["history"]
        for node in history["nodes"]:
            date = datetime.fromisoformat(node["authoredDate"].replace("Z", "+00:00")).astimezone(SGT)
            if START <= date.date() <= TODAY:
                records[node["oid"]] = date
        if not history["pageInfo"]["hasNextPage"]:
            return repo["isPrivate"], records
        cursor = history["pageInfo"]["endCursor"]


def svg(width, height, title, description, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
            '<style>text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;'
            'fill:#c9d1d9;font-size:14px}.title{fill:#58a6ff;font-size:22px;font-weight:600}'
            '.muted{fill:#8b949e;font-size:11px}.value{fill:#f0f6fc;font-weight:600}</style>'
            f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="7" '
            'fill="#0d1117" stroke="#30363d"/>' + body + '</svg>\n')


def main():
    repos = repositories()
    own = [repo for repo in repos if not repo["isFork"] and repo["defaultBranchRef"]]
    all_commits, public_ids = {}, set()
    active = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for private, records in pool.map(commits, own):
            all_commits.update(records)
            active += bool(records)
            if not private:
                public_ids.update(records)
    total = len(all_commits)
    public = len(public_ids)
    private = total - public
    public_repos = sum(not repo["isPrivate"] for repo in repos)
    stars = sum(repo["stargazerCount"] for repo in repos if not repo["isPrivate"])
    days = Counter(date.date().isoformat() for date in all_commits.values())
    hours = Counter(date.hour for date in all_commits.values())
    stamp = f"Updated {TODAY:%d %b %Y}"
    context = "Authored commits in the past 365 days on owned, non-fork default branches; includes private work; duplicate commit IDs count once."
    out = ROOT / "assets" / "github-pulse"
    out.mkdir(parents=True, exist_ok=True)

    labels = (f'<text x="28" y="42" class="title">Yufan Zhu · @{USERNAME}</text>'
              f'<text x="28" y="88"><tspan class="value">{total:,}</tspan> commits · past year</text>'
              f'<text x="28" y="117">{active} active repositories · public and private</text>'
              '<text x="28" y="158">NUS · yufan.zhu@u.nus.edu</text>'
              '<text x="28" y="187">A*STAR · zhuyf@a-star.edu.sg</text>'
              f'<text x="28" y="233" class="muted">{stamp} · Default branches · UTC+8</text>')
    values = [days[(START + timedelta(days=i)).isoformat()] for i in range(365)]
    maximum = max(max(values), 1)
    points = [(445 + i * 355 / 364, 201 - value * 125 / maximum) for i, value in enumerate(values)]
    coordinates = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    labels += ('<text x="445" y="42" class="muted">Daily authored commits</text>'
               '<line x1="445" y1="201" x2="800" y2="201" stroke="#30363d"/>'
               f'<polygon points="445,201 {coordinates} 800,201" fill="#238636" opacity=".35"/>'
               f'<polyline points="{coordinates}" fill="none" stroke="#3fb950" stroke-width="1.5"/>'
               f'<text x="445" y="224" class="muted">{START:%b %Y}</text>'
               f'<text x="800" y="224" text-anchor="end" class="muted">{TODAY:%b %Y}</text>'
               f'<text x="800" y="65" text-anchor="end" class="muted">Peak {maximum}/day</text>')
    (out / "profile.svg").write_text(svg(840, 255, "Yufan's GitHub commit activity", context, labels), encoding="utf-8")

    body = '<text x="26" y="39" class="title">Repository activity</text>'
    for y, label, value in [
        (79, "Unique commits · past year", total),
        (110, "In public repositories", public),
        (141, "In private repositories only", private),
        (172, "Public repositories", public_repos),
        (203, "Stars on public repositories", stars),
    ]:
        body += f'<text x="26" y="{y}">{label}</text><text x="385" y="{y}" text-anchor="end" class="value">{value:,}</text>'
    (out / "stats.svg").write_text(svg(415, 230, "Repository activity", context, body), encoding="utf-8")

    body = '<text x="26" y="39" class="title">Commits · UTC+8</text>'
    body += '<text x="26" y="62" class="muted">Authored time · past 365 days</text>'
    peak = max(max(hours.values(), default=0), 1)
    for hour in range(24):
        height = hours[hour] * 107 / peak
        x = 29 + hour * 14.8
        body += f'<rect x="{x:.1f}" y="{185-height:.1f}" width="11" height="{height:.1f}" fill="#3fb950"><title>{hour:02d}:00: {hours[hour]:,} commits</title></rect>'
        if hour % 6 == 0 or hour == 23:
            body += f'<text x="{x+5:.1f}" y="205" text-anchor="middle" class="muted">{hour}</text>'
    body += f'<text x="385" y="78" text-anchor="end" class="muted">Peak {peak:,}/hour</text>'
    (out / "hours.svg").write_text(svg(415, 230, "Commit times in Singapore time", context, body), encoding="utf-8")
    aggregate = {"updated_at": NOW.isoformat(), "definition": context,
                 "commits": total, "public_commits": public, "private_only_commits": private,
                 "active_repositories": active, "public_repositories": public_repos,
                 "public_stars": stars, "daily_commits": dict(sorted(days.items())),
                 "hourly_commits_sgt": {str(h): hours[h] for h in range(24)}}
    (out / "activity.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    print(f"Refreshed cards: {total:,} unique commits ({private:,} private-only), {active} active repositories.")
    subprocess.run(["node", str(ROOT / "scripts" / "update_snake.mjs")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
