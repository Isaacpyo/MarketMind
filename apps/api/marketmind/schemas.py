"""Request/response models. Everything crossing the API boundary is validated here."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

ProductId = Annotated[str, StringConstraints(pattern=r"^[0-9]{5}[A-Z]?$")]
"""Online Retail stock codes: five digits plus an optional variant letter."""

ClientEventType = Literal["view", "rec_click"]
EventType = Literal["view", "rec_click", "add_to_cart", "purchase"]
SortOption = Literal["popular", "price_asc", "price_desc", "name"]
Strategy = Literal["popularity", "cold_start", "hybrid"]
RecSource = Literal["popularity", "content", "als"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Catalogue -------------------------------------------------------------------------------


class Product(ApiModel):
    id: str
    title: str
    description: str
    category: str
    price: float
    popularity: int


class ProductPage(ApiModel):
    items: list[Product]
    total: int
    page: int
    page_size: int


class Category(ApiModel):
    name: str
    count: int


# --- Auth ------------------------------------------------------------------------------------


class RegisterIn(ApiModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class LoginIn(ApiModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class User(ApiModel):
    id: str
    email: str
    name: str
    role: Literal["customer", "admin"]
    is_demo: bool


class AuthOut(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: User


# --- Events ----------------------------------------------------------------------------------


class EventIn(ApiModel):
    product_id: ProductId
    type: ClientEventType
    # Where the interaction came from, e.g. "for_you" or "similar"; used for analytics only.
    context: Annotated[str, StringConstraints(pattern=r"^[a-z_]{1,32}$")] | None = None


class EventAck(ApiModel):
    accepted: bool
    deduplicated: bool = False


# --- Recommendations -------------------------------------------------------------------------


class Recommendation(ApiModel):
    product: Product
    score: float
    reason: str
    source: RecSource


class RecommendationList(ApiModel):
    strategy: Strategy
    model_version: str | None
    items: list[Recommendation]


# --- Cart & orders ---------------------------------------------------------------------------


class CartAddIn(ApiModel):
    product_id: ProductId
    quantity: int = Field(default=1, ge=1, le=20)


class CartSetIn(ApiModel):
    quantity: int = Field(ge=1, le=20)


class CartLine(ApiModel):
    product: Product
    quantity: int
    line_total: float


class Cart(ApiModel):
    items: list[CartLine]
    item_count: int
    subtotal: float


class OrderLine(ApiModel):
    product_id: str
    title: str
    unit_price: float
    quantity: int
    line_total: float


class Order(ApiModel):
    id: str
    created_at: datetime
    status: Literal["placed"]
    lines: list[OrderLine]
    total: float


# --- Admin -----------------------------------------------------------------------------------


class AlsParams(ApiModel):
    factors: int = Field(default=64, ge=8, le=256)
    regularization: float = Field(default=0.05, ge=1e-4, le=10.0)
    alpha: float = Field(default=1.0, ge=0.05, le=100.0)
    iterations: int = Field(default=20, ge=1, le=50)
    hybrid_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Weight of ALS (vs content) in the hybrid feed"
    )


class ModelMetrics(ApiModel):
    precision: float
    recall: float
    coverage: float


class EvaluationReport(ApiModel):
    k: int
    users_evaluated: int
    holdout_fraction: float
    models: dict[str, ModelMetrics]


class DatasetStats(ApiModel):
    users: int
    items: int
    interactions: int
    train_interactions: int
    test_interactions: int


class TrainingRun(ApiModel):
    id: str
    status: Literal["running", "succeeded", "failed"]
    trigger: Literal["startup", "admin"]
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    params: AlsParams
    dataset: DatasetStats | None
    evaluation: EvaluationReport | None
    error: str | None


class ModelInfo(ApiModel):
    version: str
    trained_at: datetime
    params: AlsParams
    items: int


class AdminOverview(ApiModel):
    products: int
    registered_users: int
    demo_users: int
    events_by_type: dict[str, int]
    live_events_last_24h: int
    live_events_since_model: int
    model: ModelInfo | None
    latest_run: TrainingRun | None
    retrain_available_in_seconds: int


class Health(ApiModel):
    status: Literal["ok"]
    ready: bool = Field(description="True once the catalogue is loaded and recommendations work")
    seeded: bool
    model_version: str | None
