"""Sessions de connexion (app/auth.py)."""
import json
import time

from app import auth


def test_session_valide(db):
    assert auth.verify_session_token(auth.create_session_token())


def test_session_falsifiee_ou_expiree(db):
    token = auth.create_session_token()
    payload, signature = token.rsplit(".", 1)
    assert not auth.verify_session_token(payload + "." + signature[:-2] + "xx")
    expired = auth._b64e(json.dumps({"u": auth.AUTH_USERNAME, "exp": int(time.time()) - 10, "g": 0}).encode())
    assert not auth.verify_session_token(f"{expired}.{auth._sign(expired)}")


def test_anciennes_sessions_sans_generation_restent_valides(db):
    """Les sessions ouvertes avant cette version (sans « g ») ne sont pas déconnectées par la mise à jour."""
    old = auth._b64e(json.dumps({"u": auth.AUTH_USERNAME, "exp": int(time.time()) + 3600}).encode())
    assert auth.verify_session_token(f"{old}.{auth._sign(old)}")


def test_deconnecter_les_autres_appareils(db):
    telephone = auth.create_session_token()
    ordinateur = auth.create_session_token()
    auth.revoke_all_sessions()
    assert not auth.verify_session_token(telephone)
    assert not auth.verify_session_token(ordinateur)
    assert auth.verify_session_token(auth.create_session_token())  # la nouvelle session de cet appareil


def test_generation_relue_apres_restauration(db):
    token = auth.create_session_token()
    db.set_setting(auth.GENERATION_KEY, "5")  # comme si une autre base venait d'être restaurée
    assert auth.verify_session_token(token)   # valeur encore en mémoire...
    auth.forget_generation_cache()
    assert not auth.verify_session_token(token)  # ...relue après la restauration
