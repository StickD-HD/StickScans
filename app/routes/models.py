"""Corps des requêtes reçues par l'API (validés par pydantic)."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str
    next: str | None = None


class AddSeriesRequest(BaseModel):
    url: str
    category_ids: list[int] = []


class ChangeUrlRequest(BaseModel):
    url: str


class MarkReadUpToRequest(BaseModel):
    number: str


class ToggleReadRequest(BaseModel):
    is_read: bool


class BulkReadRequest(BaseModel):
    chapter_ids: list[int]
    is_read: bool


class HistoryRemoveRequest(BaseModel):
    chapter_ids: list[int]


class BulkSeriesRequest(BaseModel):
    series_ids: list[int] = Field(min_length=1, max_length=1000)
    action: str
    category_id: int | None = None


class BulkIdsRequest(BaseModel):
    series_ids: list[int] = Field(max_length=1000)


class CategoryRequest(BaseModel):
    name: str


class AnilistTokenRequest(BaseModel):
    token: str


class AnilistClientIdRequest(BaseModel):
    client_id: str


class AnilistLinkRequest(BaseModel):
    anilist_id: int
    title: str


class AnilistUpdateRequest(BaseModel):
    status: str | None = None
    progress: int | None = None
    score: float | None = None
    # AAAA-MM-JJ, ou "" pour effacer la date sur AniList ; absent (None) = date inchangée
    start_date: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    end_date: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    notes: str | None = Field(default=None, max_length=500)  # "" = effacer la note


class UpdateSettingsRequest(BaseModel):
    auto_enabled: bool | None = None
    skip_completed: bool | None = None
    skip_unread: bool | None = None
    skip_never_read: bool | None = None


class BackupSettingsRequest(BaseModel):
    enabled: bool | None = None
    keep: int | None = Field(default=None, ge=1, le=30)
