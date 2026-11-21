"""Chapitres, nouveautés, progression et historique (app/database.py)."""
from conftest import make_parsed, nolink_chapter, site_chapter


def _add_series(db, numbers, url="https://www.scan-manga.com/serie-test.html"):
    return db.insert_series(url, make_parsed([site_chapter(n) for n in numbers]))


def _chapters(db, series_id):
    return {c["number"]: c for c in db.get_chapters_for_series(series_id)}


def _history_numbers(db):
    return sorted(c["number"] for c in db.get_reading_history())


# --- Nouveaux chapitres ---

def test_ajout_sans_bruit(db):
    _add_series(db, [1, 2, 3])
    assert db.get_recent_updates() == []  # les chapitres trouvés à l'ajout ne sont pas des nouveautés


def test_nouveau_chapitre_avec_lien(db):
    sid = _add_series(db, [1, 2, 3])
    new = db.update_series_result(sid, make_parsed([site_chapter(n) for n in (1, 2, 3, 4)]))
    assert [c["number"] for c in new] == ["4"]
    assert [u["number"] for u in db.get_recent_updates()] == ["4"]


def test_chapitre_sans_lien_nouveau_seulement_au_dela_du_dernier_connu(db):
    sid = _add_series(db, [5, 6])
    db.update_series_result(sid, make_parsed([site_chapter(5), site_chapter(6)]))  # liste synchronisée
    new = db.update_series_result(sid, make_parsed([
        site_chapter(5), site_chapter(6),
        nolink_chapter(2),   # ancien chapitre qui apparaît : enregistré sans bruit
        nolink_chapter(7),   # au-delà du dernier connu : vraie nouveauté
    ]))
    assert [c["number"] for c in new] == ["7"]
    assert set(_chapters(db, sid)) == {"2", "5", "6", "7"}


def test_lien_de_lecture_qui_apparait_plus_tard(db):
    sid = db.insert_series("https://www.scan-manga.com/s.html", make_parsed([nolink_chapter(3)]))
    db.update_series_result(sid, make_parsed([site_chapter(3)]))
    chapter = _chapters(db, sid)["3"]
    assert chapter["link_type"] == "site" and chapter["url"]


# --- Lecture et historique ---

def test_premiere_lecture_seul_le_chapitre_atteint_entre_dans_l_historique(db):
    sid = _add_series(db, range(1, 11))
    db.mark_read_up_to(sid, 5.0)
    chapters = _chapters(db, sid)
    assert all(chapters[str(n)]["is_read"] for n in range(1, 6))
    assert not chapters["6"]["is_read"]
    assert _history_numbers(db) == ["5"]


def test_lecture_suivante_l_ecart_entre_dans_l_historique(db):
    sid = _add_series(db, range(1, 21))
    db.mark_read_up_to(sid, 5.0)
    db.mark_read_up_to(sid, 9.0)
    assert _history_numbers(db) == ["5", "6", "7", "8", "9"]


def test_rattrapage_de_plus_de_30_chapitres(db):
    sid = _add_series(db, range(1, 101))
    db.mark_read_up_to(sid, 1.0)
    db.mark_read_up_to(sid, 50.0)  # 49 chapitres d'un coup : rattrapage, pas une lecture
    assert _history_numbers(db) == ["1", "50"]
    assert db.get_series_by_id(sid)["unread_count"] == 50


def test_tout_marquer_lu_sans_historique(db):
    sid = _add_series(db, [1, 2, 3])
    db.mark_all_read(sid)
    assert db.get_series_by_id(sid)["unread_count"] == 0
    assert db.get_reading_history() == []


def test_alignement_anilist_sans_historique(db):
    sid = _add_series(db, [1, 2, 3, 4])
    assert db.mark_read_through(sid, 3.0) == 3
    assert db.get_series_by_id(sid)["unread_count"] == 1
    assert db.get_reading_history() == []


def test_retirer_de_l_historique_garde_le_chapitre_lu(db):
    sid = _add_series(db, [1, 2])
    db.mark_read_up_to(sid, 2.0)
    entry = db.get_reading_history()[0]
    db.remove_from_history([entry["chapter_id"]])
    assert db.get_reading_history() == []
    assert _chapters(db, sid)["2"]["is_read"] == 1


def test_reinitialiser_la_progression(db):
    sid = _add_series(db, [1, 2, 3])
    db.mark_read_up_to(sid, 3.0)
    db.mark_all_unread(sid)
    assert db.get_series_by_id(sid)["unread_count"] == 3
    assert db.get_reading_history() == []


def test_progression_anilist_est_le_plus_haut_chapitre_lu(db):
    sid = _add_series(db, [1, 2, 3])
    assert db.get_max_read_chapter_number(sid) is None
    db.set_chapter_read(_chapters(db, sid)["2"]["id"], True)
    assert db.get_max_read_chapter_number(sid) == 2


# --- Titres et couvertures verrouillés (fonction retirée) ---

def test_verrous_retires_au_demarrage(db):
    sid = _add_series(db, [1])
    with db.get_conn() as conn:
        conn.execute("UPDATE series SET title = 'Titre manuel', title_locked = 1, cover_locked = 1 WHERE id = ?", (sid,))
    db.init_db()
    s = db.get_series_by_id(sid)
    assert (s["title_locked"], s["cover_locked"]) == (0, 0)
    db.update_series_result(sid, make_parsed([site_chapter(1)], title="Titre du site"))
    assert db.get_series_by_id(sid)["title"] == "Titre du site"


def test_couverture_anilist_affichee(db):
    sid = _add_series(db, [1])
    db.set_series_anilist_data(sid, cover_url="https://s4.anilist.co/cover.jpg")
    assert db.get_series_by_id(sid)["cover_url"] == "https://s4.anilist.co/cover.jpg"


# --- Journal des vérifications ---

def test_verification_interrompue(db):
    run = db.start_check_run("auto", 3)
    db.finish_check_run(run, 12.0, status="interrompue")
    assert db.get_check_run(run)["status"] == "interrompue"


def test_verification_terminee_par_defaut(db):
    run = db.start_check_run("auto", 0)
    db.finish_check_run(run, 1.0)
    assert db.get_check_run(run)["status"] == "terminée"


# --- Réglages des mises à jour ---

def test_reglages_mises_a_jour(db):
    assert db.get_update_settings() == {"skip_completed": True, "skip_unread": False, "skip_never_read": False}
    db.set_update_settings({"skip_unread": True, "skip_completed": None})
    assert db.get_update_settings() == {"skip_completed": True, "skip_unread": True, "skip_never_read": False}


def test_plateforme_et_popularite_enregistrees(db):
    sid = db.insert_series("https://www.scan-manga.com/p.html", make_parsed([site_chapter(1)], platform="Webtoons", popularity=245))
    db.update_series_result(sid, make_parsed([site_chapter(1)], platform="Webtoons", popularity=250, team="Poséidon Scans"))
    s = db.get_series_by_id(sid)
    assert (s["platform"], s["popularity"], s["team"]) == ("Webtoons", 250, "Poséidon Scans")
