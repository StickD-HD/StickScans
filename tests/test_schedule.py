"""Fréquence de vérification selon le rythme de sortie (app/schedule.py)."""
import random
from datetime import datetime, timedelta

import pytest

from app import schedule

NOW = datetime(2026, 11, 21, 12, 0, 0)


def weekly(last_release_days_ago: float, releases: int = 5) -> list[datetime]:
    last = NOW - timedelta(days=last_release_days_ago)
    return [last - timedelta(days=7 * i) for i in range(releases)]


def test_chapitres_d_une_meme_sortie_regroupes():
    t = datetime(2026, 11, 1, 10)
    events = schedule.release_events([t, t + timedelta(hours=2), t + timedelta(hours=20), t + timedelta(days=7)])
    assert events == [t, t + timedelta(days=7)]


def test_rythme_median_et_bornes():
    assert schedule.cadence_days(weekly(0)) == pytest.approx(7)
    assert schedule.cadence_days([NOW]) == schedule.DEFAULT_CADENCE_DAYS  # une seule sortie : rythme inconnu
    daily_bursts = [NOW - timedelta(hours=25 * i) for i in range(5)]
    assert schedule.cadence_days(daily_bursts) >= schedule.MIN_CADENCE_DAYS
    rare = [NOW - timedelta(days=90 * i) for i in range(3)]
    assert schedule.cadence_days(rare) == schedule.MAX_CADENCE_DAYS


@pytest.mark.parametrize("days_ago, hours, reason", [
    (1, 12, "between"),    # sortie d'il y a un jour : la suivante n'est pas pour tout de suite
    (5, 3, "window"),      # sortie attendue bientôt : toutes les 3 h
    (8, 3, "window"),      # légèrement en retard : on reste attentif
    (12, 12, "late"),
    (40, 48, "dormant"),   # plus rien depuis longtemps : série probablement en pause
])
def test_serie_hebdomadaire(days_ago, hours, reason):
    assert schedule.interval(weekly(days_ago), NOW - timedelta(days=200), NOW) == (hours, reason)


def test_serie_sans_sortie_connue_part_de_la_date_d_ajout():
    assert schedule.interval([], NOW - timedelta(days=1), NOW) == (12, "between")
    assert schedule.interval([], NOW - timedelta(days=6), NOW) == (3, "window")
    assert schedule.interval([], NOW - timedelta(days=60), NOW) == (48, "dormant")


def test_variation_de_plus_ou_moins_10_pourcents():
    rng = random.Random(1)
    for _ in range(200):
        delay = schedule.jittered(10, rng)
        assert timedelta(hours=9) <= delay <= timedelta(hours=11)


def test_bien_moins_de_requetes_qu_avant():
    """Simulation d'une série hebdomadaire sur 8 semaines : nombre de vérifications par jour."""
    rng = random.Random(7)
    start = NOW
    releases = [start + timedelta(days=7 * i, hours=rng.uniform(-6, 6)) for i in range(1, 9)]
    discovered, clock, checks = [], start, 0
    end = start + timedelta(days=56)
    while clock < end:
        checks += 1
        discovered += [r for r in releases if r <= clock and r not in discovered]
        hours, _ = schedule.interval(discovered, start - timedelta(days=30), clock)
        clock += schedule.jittered(hours, rng)
    per_day = checks / 56
    assert per_day < 6  # contre 24 par jour avec l'ancienne vérification toutes les heures
