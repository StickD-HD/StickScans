"""
Fréquence de vérification de chaque série, déduite de son rythme de sortie (aucun accès à la base ni au réseau ici).

Une « sortie » = un ou plusieurs nouveaux chapitres découverts à moins de 24 h d'écart. Le rythme d'une série est
l'écart médian entre ses dernières sorties (7 jours tant qu'il n'y en a pas au moins deux, borné entre 1 et 30 jours).
Selon le temps écoulé depuis la dernière sortie :
- moins de 60 % du rythme   : toutes les 12 h (la prochaine sortie n'est pas attendue tout de suite) ;
- de 60 % à 150 % du rythme : toutes les 3 h (sortie attendue : c'est là que la réactivité compte) ;
- jusqu'à 4 fois le rythme (au moins 21 jours) : toutes les 12 h (sortie en retard) ;
- au-delà                    : toutes les 48 h (série probablement en pause).
Une série en erreur est revue 6 h plus tard. Chaque intervalle varie de ±10 % pour ne pas regrouper les requêtes.
Pour une série hebdomadaire, cela fait environ 4 vérifications par jour au lieu de 24.
"""
import random
from datetime import datetime, timedelta
from statistics import median

WINDOW_HOURS = 3
NORMAL_HOURS = 12
DORMANT_HOURS = 48
ERROR_HOURS = 6
MISSING_HOURS = 48  # page introuvable : inutile d'insister, on revérifie de temps en temps
DEFAULT_CADENCE_DAYS = 7.0
MIN_CADENCE_DAYS = 1.0
MAX_CADENCE_DAYS = 30.0
DORMANT_MIN_DAYS = 21.0
JITTER = 0.10

REASONS = {
    "between": "entre deux sorties",
    "window": "sortie attendue",
    "late": "sortie en retard",
    "dormant": "série probablement en pause",
    "error": "après une erreur",
    "missing": "page introuvable",
}


def release_events(discovered: list[datetime]) -> list[datetime]:
    """Regroupe les dates de découverte de chapitres en sorties (écart de moins de 24 h = même sortie)."""
    events: list[datetime] = []
    for moment in sorted(discovered):
        if events and moment - events[-1] < timedelta(hours=24):
            continue
        events.append(moment)
    return events


def cadence_days(events: list[datetime]) -> float:
    recent = sorted(events)[-7:]
    if len(recent) < 2:
        return DEFAULT_CADENCE_DAYS
    gaps = [(b - a).total_seconds() / 86400 for a, b in zip(recent, recent[1:])]
    return min(MAX_CADENCE_DAYS, max(MIN_CADENCE_DAYS, median(gaps)))


def interval(discovered: list[datetime], added_at: datetime, now: datetime) -> tuple[float, str]:
    """(heures avant la prochaine vérification, raison) pour une série vérifiée avec succès à l'instant `now`."""
    events = release_events(discovered)
    cadence = cadence_days(events)
    since_days = (now - (events[-1] if events else added_at)).total_seconds() / 86400
    if since_days < 0.6 * cadence:
        return NORMAL_HOURS, "between"
    if since_days < 1.5 * cadence:
        return WINDOW_HOURS, "window"
    if since_days < max(4 * cadence, DORMANT_MIN_DAYS):
        return NORMAL_HOURS, "late"
    return DORMANT_HOURS, "dormant"


def jittered(hours: float, rng=random) -> timedelta:
    return timedelta(hours=hours * rng.uniform(1 - JITTER, 1 + JITTER))
