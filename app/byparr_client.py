"""
Client pour Byparr (résolveur de challenge Cloudflare, API compatible FlareSolverr).
Byparr tourne dans son propre conteneur sur ce même stack Docker ;
"byparr" est son nom de service, résolu via le réseau interne du stack.
"""
import os
import requests

BYPARR_URL = os.environ.get("BYPARR_URL", "http://byparr:8191/v1")
DEFAULT_TIMEOUT_MS = 60000


class ByparrError(Exception):
    pass


def fetch_html(url: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str:
    try:
        resp = requests.post(
            BYPARR_URL,
            json={
                "cmd": "request.get",
                "url": url,
                "maxTimeout": timeout_ms,
                "blockMedia": True,
            },
            timeout=(timeout_ms / 1000) + 30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ByparrError(f"Impossible de joindre Byparr : {e}") from e

    data = resp.json()
    if data.get("status") != "ok":
        raise ByparrError(f"Byparr a échoué (status={data.get('status')}) : {data.get('message')}")

    return data["solution"]["response"]
