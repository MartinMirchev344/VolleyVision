"""Box-score SQL checked against a small match scored by hand.

Hand-scored set 1 (H = home, A = away). Players: H1 #1, H2 #2, A7 #7, A8 #8 libero.
  r1  H serves: H1 serve in_play, A8 rec perfect, A7 attack kill            -> A
  r2  A serves: A7 serve ace                                                -> A
  r3  A serves: A7 serve error                                              -> H
  r4  H serves: H2 serve, A8 rec poor, A7 attack blocked, H2 block point    -> H
  r5  H serves: H2 serve ace, A8 rec error                                  -> H
  r6  H serves: H2 serve, A8 rec positive, A7 attack in_play, H1 dig good,
                H1 set good, H2 attack kill                                 -> H
  r7  H serves: H2 serve, A8 rec ok, A7 attack error                        -> H
  r8  H serves: H2 serve, away rec perfect (unattributed), A7 attack kill   -> A
  r9  A serves: A7 serve, H1 rec positive, H2 attack kill,
                (A7 block error, REJECTED)                                  -> H
  r10 H serves: H1 serve, away net fault (unattributed)                     -> H
  r11 H serves: winner unknown (no touches)
  r12 REJECTED rally: A7 attack kill                                        -> A
Set 1 score 7-3 (r11 unknown, r12 rejected).
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from volleyanalytics.models import Match, MatchRoster, Player, Rally, SetLineup, Team, Touch
from volleyanalytics.stats import match_report, render_text

pytestmark = pytest.mark.integration


def _match(session: Session) -> Match:
    home, away = Team(name="Home Club"), Team(name="Away Club")
    session.add_all([home, away])
    session.flush()
    match = Match(
        home_team_id=home.id,
        away_team_id=away.id,
        competition="U20",
        starts_at=datetime(2026, 10, 12, 15, 30, tzinfo=UTC),
        venue="Sports Hall",
        city="Town",
        spectators=150,
        first_referee="Ref One",
        second_referee="Ref Two",
    )
    session.add(match)
    session.flush()
    return match


def _roster(session, match, side, jersey, name, libero=False) -> MatchRoster:
    player = Player(display_name=name)
    session.add(player)
    session.flush()
    entry = MatchRoster(
        match_id=match.id, player_id=player.id, side=side, jersey_number=jersey, is_libero=libero
    )
    session.add(entry)
    session.flush()
    return entry


def _rally(
    session,
    match,
    set_number,
    number,
    serving,
    winning,
    touches=(),
    status="unreviewed",
    start=None,
) -> Rally:
    rally = Rally(
        match_id=match.id,
        set_number=set_number,
        rally_number=number,
        serving_side=serving,
        winning_side=winning,
        start_sec=start,
        end_sec=None if start is None else start + 10,
        source="human",
        review_status=status,
    )
    session.add(rally)
    session.flush()
    for sequence, (side, roster, skill, grade, *rest) in enumerate(touches, start=1):
        session.add(
            Touch(
                match_id=match.id,
                rally_id=rally.id,
                sequence=sequence,
                side=side,
                roster_id=roster.id if roster else None,
                skill=skill,
                grade=grade,
                source="human",
                review_status=rest[0] if rest else status,
            )
        )
    session.flush()
    return rally


def _hand_scored_match(session: Session, reviewed=()) -> Match:
    match = _match(session)
    h1 = _roster(session, match, "home", 1, "Home Setter")
    h2 = _roster(session, match, "home", 2, "Home Hitter")
    a7 = _roster(session, match, "away", 7, "Away Hitter")
    a8 = _roster(session, match, "away", 8, "Away Libero", libero=True)
    for entry, role, zone in (
        (h1, "starter", 1),
        (h2, "starter", 4),
        (a7, "starter", 2),
        (a8, "libero", None),
    ):
        session.add(
            SetLineup(
                match_id=match.id,
                roster_id=entry.id,
                side=entry.side,
                set_number=1,
                role=role,
                starting_zone=zone,
            )
        )
    H, A = "home", "away"
    rallies = [
        (
            H,
            A,
            [
                (H, h1, "serve", "in_play"),
                (A, a8, "reception", "perfect"),
                (A, a7, "attack", "kill"),
            ],
        ),
        (A, A, [(A, a7, "serve", "ace")]),
        (A, H, [(A, a7, "serve", "error")]),
        (
            H,
            H,
            [
                (H, h2, "serve", "in_play"),
                (A, a8, "reception", "poor"),
                (A, a7, "attack", "blocked"),
                (H, h2, "block", "point"),
            ],
        ),
        (H, H, [(H, h2, "serve", "ace"), (A, a8, "reception", "error")]),
        (
            H,
            H,
            [
                (H, h2, "serve", "in_play"),
                (A, a8, "reception", "positive"),
                (A, a7, "attack", "in_play"),
                (H, h1, "dig", "good"),
                (H, h1, "set", "good"),
                (H, h2, "attack", "kill"),
            ],
        ),
        (
            H,
            H,
            [(H, h2, "serve", "in_play"), (A, a8, "reception", "ok"), (A, a7, "attack", "error")],
        ),
        (
            H,
            A,
            [
                (H, h2, "serve", "in_play"),
                (A, None, "reception", "perfect"),
                (A, a7, "attack", "kill"),
            ],
        ),
        (
            A,
            H,
            [
                (A, a7, "serve", "in_play"),
                (H, h1, "reception", "positive"),
                (H, h2, "attack", "kill"),
                (A, a7, "block", "error", "rejected"),
            ],
        ),
        (H, H, [(H, h1, "serve", "in_play"), (A, None, "fault", "error")]),
        (H, None, []),
    ]
    for number, (serving, winning, touches) in enumerate(rallies, start=1):
        status = "confirmed" if number in reviewed else "unreviewed"
        _rally(session, match, 1, number, serving, winning, touches, status=status)
    _rally(session, match, 1, 12, H, A, [(A, a7, "attack", "kill")], status="rejected")
    return match


def _player(report, jersey):
    return next(p for p in report["players"] if p["jersey_number"] == jersey)


def test_player_team_and_point_type_stats_match_hand_scoring(database):
    with Session(database) as session, session.begin():
        match = _hand_scored_match(session)
        report = match_report(session, match.id)

    assert report["records"] == {
        "rallies": 11,
        "unreviewed_rallies": 11,
        "touches": 28,
        "unreviewed_touches": 28,
    }
    assert report["sets"] == [
        {
            "set_number": 1,
            "home_points": 7,
            "away_points": 3,
            "duration_sec": None,
            "partials": {"8": None, "16": None, "21": None},
        }
    ]
    assert report["result"] == {"home": 1, "away": 0}

    h1, h2, a7, a8 = (_player(report, n) for n in (1, 2, 7, 8))
    assert h1["sets"] == ["1", "", "", "", ""] and a8["sets"] == ["*", "", "", "", ""]
    assert h1["points"] == {"total": 0, "break_points": 0, "won_minus_lost": 0}
    assert h1["serve"] == {"total": 2, "errors": 0, "aces": 0}
    assert h1["reception"] == {"total": 1, "errors": 0, "positive_pct": 100.0, "perfect_pct": 0.0}

    assert h2["points"] == {"total": 4, "break_points": 3, "won_minus_lost": 4}
    assert h2["serve"] == {"total": 5, "errors": 0, "aces": 1}
    assert h2["attack"] == {"total": 2, "errors": 0, "blocked": 0, "kills": 2, "kill_pct": 100.0}
    assert h2["block"] == {"points": 1}

    assert a7["points"] == {"total": 3, "break_points": 1, "won_minus_lost": 0}
    assert a7["serve"] == {"total": 3, "errors": 1, "aces": 1}
    assert a7["attack"] == {"total": 5, "errors": 1, "blocked": 1, "kills": 2, "kill_pct": 40.0}
    assert a7["block"] == {"points": 0}  # The rejected block error does not count.

    assert a8["libero"] is True
    assert a8["points"] == {"total": 0, "break_points": 0, "won_minus_lost": -1}
    assert a8["reception"] == {"total": 5, "errors": 1, "positive_pct": 40.0, "perfect_pct": 20.0}

    home, away = report["team_totals"]["home"], report["team_totals"]["away"]
    assert home["points"] == {"total": 4, "break_points": 3, "won_minus_lost": 4}
    assert home["serve"] == {"total": 7, "errors": 0, "aces": 1}
    # Team reception includes the unattributed touch; errors include the unattributed fault.
    assert away["reception"] == {"total": 6, "errors": 1, "positive_pct": 50.0, "perfect_pct": 33.3}
    assert away["points"] == {"total": 3, "break_points": 1, "won_minus_lost": -2}

    assert report["points_won"] == [
        {
            "set_number": 1,
            "side": "away",
            "serve": 1,
            "attack": 2,
            "block": 0,
            "opponent_error": 0,
            "unclassified": 0,
        },
        {
            "set_number": 1,
            "side": "home",
            "serve": 1,
            "attack": 2,
            "block": 1,
            "opponent_error": 3,
            "unclassified": 0,
        },
    ]
    text = render_text(report)
    assert "AI ESTIMATE: 39 of 39 records unreviewed" in text
    assert "Home Club 1 - 0 Away Club" in text


def test_reviewed_only_counts_confirmed_records(database):
    with Session(database) as session, session.begin():
        match = _hand_scored_match(session, reviewed={1, 2, 3})
        # Rally 4 confirmed, but its touches stay unreviewed.
        session.query(Rally).filter_by(match_id=match.id, rally_number=4).update(
            {"review_status": "confirmed"}
        )
        report = match_report(session, match.id, reviewed_only=True)
        default = match_report(session, match.id)

    assert report["records"] == {
        "rallies": 4,
        "unreviewed_rallies": 0,
        "touches": 5,
        "unreviewed_touches": 0,
    }
    assert report["sets"][0]["home_points"] == 2 and report["sets"][0]["away_points"] == 2
    a7 = _player(report, 7)
    assert a7["points"]["total"] == 2 and a7["serve"]["total"] == 2
    assert report["points_won"] == [
        {
            "set_number": 1,
            "side": "away",
            "serve": 1,
            "attack": 1,
            "block": 0,
            "opponent_error": 0,
            "unclassified": 0,
        },
        {
            "set_number": 1,
            "side": "home",
            "serve": 0,
            "attack": 0,
            "block": 0,
            "opponent_error": 1,
            "unclassified": 1,
        },
    ]
    assert "Reviewed records only" in render_text(report)
    assert default["records"]["unreviewed_rallies"] == 7


def test_set_scores_partials_duration_and_result(database):
    # Set 1: home 8 straight, away 10, home 8, away 10, home 9 -> 25-20.
    # Set 2: away wins 25 straight; one extra rally with an unknown winner.
    runs = [("home", 8), ("away", 10), ("home", 8), ("away", 10), ("home", 9)]
    with Session(database) as session, session.begin():
        match = _match(session)
        winners = [side for side, count in runs for _ in range(count)]
        for index, winner in enumerate(winners):
            _rally(session, match, 1, index + 1, None, winner, start=100 + 30 * index)
        for index in range(25):
            _rally(session, match, 2, index + 1, None, "away", start=2000 + 20 * index)
        _rally(session, match, 2, 26, None, None)
        report = match_report(session, match.id)

    first, second = report["sets"]
    assert (first["home_points"], first["away_points"]) == (25, 20)
    assert first["partials"] == {"8": "8-0", "16": "16-10", "21": "21-20"}
    assert first["duration_sec"] == pytest.approx((100 + 30 * 44 + 10) - 100)
    assert (second["home_points"], second["away_points"]) == (0, 25)
    assert second["partials"] == {"8": "0-8", "16": "0-16", "21": "0-21"}
    assert report["result"] == {"home": 1, "away": 1}
    # No touches were recorded, so every point is unclassified rather than guessed.
    for entry in report["points_won"]:
        assert entry["serve"] == entry["attack"] == entry["block"] == entry["opponent_error"] == 0
    assert sum(entry["unclassified"] for entry in report["points_won"]) == 25 + 20 + 25


def test_unknown_match_is_a_clear_error(database):
    from uuid import uuid4

    with Session(database) as session, pytest.raises(ValueError, match="No match"):
        match_report(session, uuid4())


@pytest.mark.parametrize(
    "case",
    [
        "grade_for_skill",
        "wrong_side_player",
        "duplicate_zone",
        "starter_without_zone",
        "same_teams",
    ],
)
def test_database_rejects_inconsistent_records(database, case):
    with Session(database) as session, session.begin():
        match = _match(session)
        home = _roster(session, match, "home", 1, "Home Player")
        _roster(session, match, "home", 2, "Other Home Player")
        rally = _rally(session, match, 1, 1, "home", "home")
        session.add(
            SetLineup(
                match_id=match.id,
                roster_id=home.id,
                side="home",
                set_number=1,
                role="starter",
                starting_zone=1,
            )
        )
        match_id, home_id, rally_id = match.id, home.id, rally.id
        home_team = match.home_team_id

    with pytest.raises(IntegrityError):
        with Session(database) as session, session.begin():
            if case == "grade_for_skill":
                session.add(
                    Touch(
                        match_id=match_id,
                        rally_id=rally_id,
                        sequence=1,
                        side="home",
                        skill="serve",
                        grade="kill",
                        source="human",
                    )
                )
            elif case == "wrong_side_player":  # A home player recorded on the away side.
                session.add(
                    Touch(
                        match_id=match_id,
                        rally_id=rally_id,
                        sequence=1,
                        side="away",
                        roster_id=home_id,
                        skill="serve",
                        grade="ace",
                        source="human",
                    )
                )
            elif case == "duplicate_zone":
                other = session.query(MatchRoster).filter_by(jersey_number=2).one()
                session.add(
                    SetLineup(
                        match_id=match_id,
                        roster_id=other.id,
                        side="home",
                        set_number=1,
                        role="starter",
                        starting_zone=1,
                    )
                )
            elif case == "starter_without_zone":
                other = session.query(MatchRoster).filter_by(jersey_number=2).one()
                session.add(
                    SetLineup(
                        match_id=match_id,
                        roster_id=other.id,
                        side="home",
                        set_number=1,
                        role="starter",
                        starting_zone=None,
                    )
                )
            else:
                session.add(Match(home_team_id=home_team, away_team_id=home_team))
            session.flush()
