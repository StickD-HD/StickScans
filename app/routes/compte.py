"""Connexion, déconnexion, état de la session et version qui tourne."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

from .. import auth
from .common import logger
from .models import LoginRequest

router = APIRouter()


@router.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response):
    if not auth.is_enabled():
        return {"ok": True, "next": "/"}
    ip = auth.client_ip(request)
    if auth.is_rate_limited(ip):
        raise HTTPException(429, "Trop de tentatives, réessaie dans quelques minutes")
    if not auth.check_credentials(payload.username, payload.password):
        auth.register_failure(ip)
        logger.warning("Échec de connexion depuis %s", ip)
        raise HTTPException(401, "Identifiant ou mot de passe incorrect")
    auth.clear_failures(ip)
    _set_session_cookie(response, request)
    return {"ok": True, "next": auth.safe_next_url(payload.next)}


def _set_session_cookie(response: Response, request: Request):
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.create_session_token(),
        max_age=auth.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=auth.COOKIE_SECURE or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https" or request.url.scheme == "https",
        path="/",
    )


@router.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@router.post("/api/auth/logout-others")
def logout_others(request: Request, response: Response):
    """Déconnecte tous les autres appareils (téléphone perdu, ordinateur prêté...) ; celui-ci reste connecté."""
    if not auth.is_enabled():
        raise HTTPException(400, "Pas d'authentification configurée")
    auth.revoke_all_sessions()
    _set_session_cookie(response, request)  # nouvelle session pour cet appareil, de la nouvelle génération
    logger.warning("Toutes les autres sessions ont été déconnectées (depuis %s)", auth.client_ip(request))
    return {"ok": True}


@router.get("/api/auth/status")
def auth_status(request: Request):
    return {
        "enabled": auth.is_enabled(),
        "authenticated": (not auth.is_enabled()) or auth.verify_session_token(request.cookies.get(auth.COOKIE_NAME)),
    }


# Écrit par outils/deploy.sh dans le dossier de l'instance : « commit|date|message » de la version qui tourne.
VERSION_FILE = Path(__file__).parent.parent / "VERSION"


@router.get("/api/version")
def app_version():
    try:
        commit, date, subject = (VERSION_FILE.read_text(encoding="utf-8").strip().split("|", 2) + ["", ""])[:3]
    except OSError:
        return {"commit": None, "date": None, "subject": None}
    return {"commit": commit or None, "date": date or None, "subject": subject or None}
