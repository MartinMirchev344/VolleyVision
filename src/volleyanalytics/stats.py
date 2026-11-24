"""Match box score computed by PostgreSQL from rallies and graded touches.

Definitions (also printed with every report):
- Points: kills + aces + block points.
- BP (break points): a player's points scored while their team was serving.
- W-L: points minus touches graded 'error' or attack 'blocked' (each lost the rally).
- Points won per set: each rally is credited to the winner's last ace/kill/block point,
  else to a block if the loser's attack was blocked, else to the loser's last error,
  else 'unclassified' (e.g. a penalty, or touches not yet recorded).
- Rejected records never count. By default unreviewed records count and the report says
  how many there are; with reviewed_only, only confirmed/corrected records count.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

_REVIEWED = "('confirmed', 'corrected')"

_BASE = f"""
WITH r AS (
    SELECT id, set_number, rally_number, serving_side, winning_side, start_sec, end_sec,
           review_status IN {_REVIEWED} AS reviewed
    FROM rallies
    WHERE match_id = :match_id
      AND review_status <> 'rejected'
      AND (NOT :reviewed_only OR review_status IN {_REVIEWED})
),
t AS (
    SELECT t.rally_id, t.sequence, t.side, t.roster_id, t.skill, t.grade,
           t.review_status IN {_REVIEWED} AS reviewed,
           r.set_number, r.serving_side, r.winning_side
    FROM touches AS t
    JOIN r ON r.id = t.rally_id
    WHERE t.review_status <> 'rejected'
      AND (NOT :reviewed_only OR t.review_status IN {_REVIEWED})
)
"""

_COUNTS = """
    count(*) FILTER (WHERE t.skill = 'serve') AS serve_total,
    count(*) FILTER (WHERE t.skill = 'serve' AND t.grade = 'error') AS serve_errors,
    count(*) FILTER (WHERE t.skill = 'serve' AND t.grade = 'ace') AS aces,
    count(*) FILTER (WHERE t.skill = 'reception') AS reception_total,
    count(*) FILTER (WHERE t.skill = 'reception' AND t.grade = 'error') AS reception_errors,
    count(*) FILTER (WHERE t.skill = 'reception' AND t.grade IN ('perfect', 'positive'))
        AS reception_positive,
    count(*) FILTER (WHERE t.skill = 'reception' AND t.grade = 'perfect') AS reception_perfect,
    count(*) FILTER (WHERE t.skill = 'attack') AS attack_total,
    count(*) FILTER (WHERE t.skill = 'attack' AND t.grade = 'error') AS attack_errors,
    count(*) FILTER (WHERE t.skill = 'attack' AND t.grade = 'blocked') AS attack_blocked,
    count(*) FILTER (WHERE t.skill = 'attack' AND t.grade = 'kill') AS kills,
    count(*) FILTER (WHERE t.skill = 'block' AND t.grade = 'point') AS block_points,
    count(*) FILTER (WHERE t.grade IN ('ace', 'kill', 'point') AND t.side = t.serving_side)
        AS break_points,
    count(*) FILTER (WHERE t.grade IN ('error', 'blocked')) AS errors,
    count(*) FILTER (WHERE t.skill IS NOT NULL AND NOT t.reviewed) AS unreviewed_touches
"""

_MATCH = """
SELECT m.competition, m.starts_at, m.venue, m.city, m.spectators,
       m.first_referee, m.second_referee, h.name AS home_team, a.name AS away_team
FROM matches AS m
JOIN teams AS h ON h.id = m.home_team_id
JOIN teams AS a ON a.id = m.away_team_id
WHERE m.id = :match_id
"""

_RECORDS = f"""{_BASE}
SELECT (SELECT count(*) FROM r) AS rallies,
       (SELECT count(*) FROM r WHERE NOT reviewed) AS unreviewed_rallies,
       (SELECT count(*) FROM t) AS touches,
       (SELECT count(*) FROM t WHERE NOT reviewed) AS unreviewed_touches
"""

_SETS = f"""{_BASE},
running AS (
    SELECT set_number, rally_number, start_sec, end_sec,
           sum((winning_side = 'home')::int) OVER w AS home,
           sum((winning_side = 'away')::int) OVER w AS away
    FROM r
    WHERE winning_side IS NOT NULL
    WINDOW w AS (PARTITION BY set_number ORDER BY rally_number)
)
SELECT set_number,
       max(home) AS home_points,
       max(away) AS away_points,
       max(end_sec) - min(start_sec) AS duration_sec,
       (array_agg(home || '-' || away ORDER BY rally_number)
           FILTER (WHERE greatest(home, away) >= 8))[1] AS partial_8,
       (array_agg(home || '-' || away ORDER BY rally_number)
           FILTER (WHERE greatest(home, away) >= 16))[1] AS partial_16,
       (array_agg(home || '-' || away ORDER BY rally_number)
           FILTER (WHERE greatest(home, away) >= 21))[1] AS partial_21
FROM running
GROUP BY set_number
ORDER BY set_number
"""

_POINTS_WON = f"""{_BASE},
scoring AS (
    SELECT DISTINCT ON (rally_id) rally_id, skill
    FROM t
    WHERE side = winning_side AND grade IN ('ace', 'kill', 'point')
    ORDER BY rally_id, sequence DESC
),
loser_error AS (
    SELECT DISTINCT ON (rally_id) rally_id, grade
    FROM t
    WHERE side <> winning_side AND grade IN ('error', 'blocked')
    ORDER BY rally_id, sequence DESC
)
SELECT r.set_number, r.winning_side AS side,
       CASE
           WHEN s.skill = 'serve' THEN 'serve'
           WHEN s.skill = 'attack' THEN 'attack'
           WHEN s.skill = 'block' THEN 'block'
           WHEN e.grade = 'blocked' THEN 'block'
           WHEN e.grade = 'error' THEN 'opponent_error'
           ELSE 'unclassified'
       END AS point_type,
       count(*) AS points
FROM r
LEFT JOIN scoring AS s ON s.rally_id = r.id
LEFT JOIN loser_error AS e ON e.rally_id = r.id
WHERE r.winning_side IS NOT NULL
GROUP BY 1, 2, 3
"""

_PLAYERS = f"""{_BASE}
SELECT mr.id AS roster_id, mr.side, mr.jersey_number, mr.is_libero, p.display_name,
       {_COUNTS}
FROM match_roster AS mr
JOIN players AS p ON p.id = mr.player_id
LEFT JOIN t ON t.roster_id = mr.id
WHERE mr.match_id = :match_id
GROUP BY mr.id, mr.side, mr.jersey_number, mr.is_libero, p.display_name
ORDER BY mr.side DESC, mr.jersey_number
"""

_TEAMS = f"""{_BASE}
SELECT s.side, {_COUNTS}
FROM (VALUES ('home'), ('away')) AS s (side)
LEFT JOIN t ON t.side = s.side
GROUP BY s.side
"""

_LINEUPS = """
SELECT roster_id, set_number, role, starting_zone
FROM set_lineups
WHERE match_id = :match_id
"""

POINT_TYPES = ("serve", "attack", "block", "opponent_error", "unclassified")


def _percent(part: int, total: int) -> float | None:
    return None if total == 0 else round(100 * part / total, 1)


def _skills(row) -> dict:
    points = row.kills + row.aces + row.block_points
    return {
        "points": {
            "total": points,
            "break_points": row.break_points,
            "won_minus_lost": points - row.errors,
        },
        "serve": {"total": row.serve_total, "errors": row.serve_errors, "aces": row.aces},
        "reception": {
            "total": row.reception_total,
            "errors": row.reception_errors,
            "positive_pct": _percent(row.reception_positive, row.reception_total),
            "perfect_pct": _percent(row.reception_perfect, row.reception_total),
        },
        "attack": {
            "total": row.attack_total,
            "errors": row.attack_errors,
            "blocked": row.attack_blocked,
            "kills": row.kills,
            "kill_pct": _percent(row.kills, row.attack_total),
        },
        "block": {"points": row.block_points},
        "unreviewed_touches": row.unreviewed_touches,
    }


def match_report(session: Session, match_id: UUID, reviewed_only: bool = False) -> dict:
    params = {"match_id": match_id, "reviewed_only": reviewed_only}
    match = session.execute(text(_MATCH), params).one_or_none()
    if match is None:
        raise ValueError(f"No match with ID {match_id}.")
    records = session.execute(text(_RECORDS), params).one()

    sets = []
    sets_won = {"home": 0, "away": 0}
    for row in session.execute(text(_SETS), params):
        if row.home_points != row.away_points:
            sets_won["home" if row.home_points > row.away_points else "away"] += 1
        sets.append(
            {
                "set_number": row.set_number,
                "home_points": row.home_points,
                "away_points": row.away_points,
                "duration_sec": row.duration_sec,
                "partials": {"8": row.partial_8, "16": row.partial_16, "21": row.partial_21},
            }
        )

    points_won: dict[tuple[int, str], dict] = {}
    for row in session.execute(text(_POINTS_WON), params):
        entry = points_won.setdefault((row.set_number, row.side), dict.fromkeys(POINT_TYPES, 0))
        entry[row.point_type] = row.points

    lineups: dict = {}
    for row in session.execute(text(_LINEUPS), params):
        mark = str(row.starting_zone) if row.role == "starter" else "*"
        lineups.setdefault(row.roster_id, [""] * 5)[row.set_number - 1] = mark

    players = [
        {
            "side": row.side,
            "jersey_number": row.jersey_number,
            "name": row.display_name,
            "libero": row.is_libero,
            "sets": lineups.get(row.roster_id, [""] * 5),
            **_skills(row),
        }
        for row in session.execute(text(_PLAYERS), params)
    ]
    teams = {row.side: _skills(row) for row in session.execute(text(_TEAMS), params)}

    return {
        "match": {
            "match_id": str(match_id),
            "home_team": match.home_team,
            "away_team": match.away_team,
            "competition": match.competition,
            "starts_at": match.starts_at.isoformat() if match.starts_at else None,
            "venue": match.venue,
            "city": match.city,
            "spectators": match.spectators,
            "referees": [name for name in (match.first_referee, match.second_referee) if name],
        },
        "reviewed_only": reviewed_only,
        "records": {
            "rallies": records.rallies,
            "unreviewed_rallies": records.unreviewed_rallies,
            "touches": records.touches,
            "unreviewed_touches": records.unreviewed_touches,
        },
        "result": sets_won,
        "sets": sets,
        "points_won": [
            {"set_number": number, "side": side, **counts}
            for (number, side), counts in sorted(points_won.items(), key=lambda item: item[0])
        ],
        "players": players,
        "team_totals": teams,
    }


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}%"


def _stat_line(stats: dict) -> str:
    p, s, r, a = stats["points"], stats["serve"], stats["reception"], stats["attack"]
    positive, perfect, kill = _pct(r["positive_pct"]), _pct(r["perfect_pct"]), _pct(a["kill_pct"])
    return (
        f"{p['total']:>3} {p['break_points']:>3} {p['won_minus_lost']:>4} |"
        f" {s['total']:>3} {s['errors']:>3} {s['aces']:>3} |"
        f" {r['total']:>3} {r['errors']:>3} {positive:>5} {perfect:>5} |"
        f" {a['total']:>3} {a['errors']:>3} {a['blocked']:>3} {a['kills']:>4} {kill:>5} |"
        f" {stats['block']['points']:>3}"
    )


def render_text(report: dict) -> str:
    m, rec = report["match"], report["records"]
    unreviewed = rec["unreviewed_rallies"] + rec["unreviewed_touches"]
    total = rec["rallies"] + rec["touches"]
    if report["reviewed_only"]:
        status = "Reviewed records only"
    elif unreviewed:
        status = f"AI ESTIMATE: {unreviewed} of {total} records unreviewed"
    else:
        status = f"All {total} records reviewed"
    lines = [
        f"{m['home_team']} {report['result']['home']} - {report['result']['away']} "
        f"{m['away_team']}",
        status,
        " | ".join(
            str(value)
            for value in (
                m["competition"],
                m["starts_at"],
                ", ".join(v for v in (m["venue"], m["city"]) if v) or None,
                f"Spectators: {m['spectators']}" if m["spectators"] is not None else None,
                f"Referees: {' - '.join(m['referees'])}" if m["referees"] else None,
            )
            if value
        ),
        "",
        "Set  Time   8       16      21      Points",
    ]
    for s in report["sets"]:
        minutes = "-" if s["duration_sec"] is None else f"{s['duration_sec'] / 60:.0f}'"
        partials = "".join(f"{s['partials'][k] or '-':<8}" for k in ("8", "16", "21"))
        lines.append(
            f"{s['set_number']:<4} {minutes:<6} {partials}{s['home_points']}-{s['away_points']}"
        )
    header = (
        f"{'#':>2}  {'Name':<22} {'Sets':<10} Pts  BP  W-L | Srv Err Ace |"
        " Rec Err  Pos%  Exc% | Att Err Blk Kill Kill% | Blk"
    )
    for side, team in (("home", m["home_team"]), ("away", m["away_team"])):
        lines += ["", team, header]
        for p in (p for p in report["players"] if p["side"] == side):
            name = p["name"] + (" (L)" if p["libero"] else "")
            sets = " ".join(mark or "." for mark in p["sets"])
            lines.append(f"{p['jersey_number']:>2}  {name:<22} {sets:<10}{_stat_line(p)}")
        lines.append(
            f"{'':>2}  {'Team totals':<22} {'':<10}{_stat_line(report['team_totals'][side])}"
        )
        lines.append("Points won   Serve Attack Block OppErr Unclassified")
        for entry in (e for e in report["points_won"] if e["side"] == side):
            lines.append(
                f"Set {entry['set_number']:<8} {entry['serve']:>5} {entry['attack']:>6}"
                f" {entry['block']:>5} {entry['opponent_error']:>6} {entry['unclassified']:>12}"
            )
    return "\n".join(lines)
