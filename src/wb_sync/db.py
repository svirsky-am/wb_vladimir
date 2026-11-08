"""SQLite-хранилище (SQLAlchemy 2.0). Апсерт по уникальному ключу."""

from datetime import date, datetime

from .app_config import AppConfig

try:
    from sqlalchemy import create_engine, select, String, Float, Boolean
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
except ImportError as exc:  # pragma: no cover
    raise ImportError("SQLAlchemy не установлена: uv sync") from exc


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    srid: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[str] = mapped_column(String, index=True)
    article: Mapped[str] = mapped_column(String, index=True)
    goods_name: Mapped[str] = mapped_column(String, default="")
    warehouse: Mapped[str] = mapped_column(String, default="")
    office: Mapped[str] = mapped_column(String, default="")
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
    finished_price: Mapped[float] = mapped_column(Float, default=0.0)
    is_cancel: Mapped[bool] = mapped_column(Boolean, default=False)


class Sale(Base):
    __tablename__ = "sales"

    sale_id: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[str] = mapped_column(String, index=True)
    srid: Mapped[str] = mapped_column(String, index=True, default="")
    article: Mapped[str] = mapped_column(String, index=True)
    goods_name: Mapped[str] = mapped_column(String, default="")
    warehouse: Mapped[str] = mapped_column(String, default="")
    finished_price: Mapped[float] = mapped_column(Float, default=0.0)
    is_cancel: Mapped[bool] = mapped_column(Boolean, default=False)


class FbsOrder(Base):
    __tablename__ = "fbs_orders"

    srid: Mapped[str] = mapped_column(String, primary_key=True)
    nm_id: Mapped[int] = mapped_column(default=0)
    article: Mapped[str] = mapped_column(String, default="", index=True)
    status: Mapped[str] = mapped_column(String, default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[str] = mapped_column(String, default="", index=True)


def create_engine_for(app_config: AppConfig):
    return create_engine(f"sqlite:///{app_config.database_file}")


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def _upsert(session: Session, model, pk_name: str, values: dict) -> bool:
    pk_value = values[pk_name]
    if not pk_value:
        return False
    existing = session.execute(
        select(model).where(getattr(model, pk_name) == pk_value)
    ).scalar_one_or_none()
    if existing is not None:
        for key, val in values.items():
            setattr(existing, key, val)
        return False
    session.add(model(**values))
    return True


def upsert_orders(engine, rows: list[dict]) -> int:
    inserted = 0
    with Session(engine) as session:
        for row in rows:
            values = {
                "srid": str(row.get("srid", "")),
                "date": (row.get("date") or "")[:10],
                "article": row.get("supplierArticle") or "",
                "goods_name": row.get("goodsName") or "",
                "warehouse": row.get("warehouseName") or "",
                "office": row.get("officeName") or "",
                "total_price": row.get("totalPrice") or 0.0,
                "discount_percent": row.get("discountPercent") or 0.0,
                "finished_price": row.get("finishedPrice") or 0.0,
                "is_cancel": bool(row.get("isCancel")),
            }
            inserted += _upsert(session, Order, "srid", values)
        session.commit()
    return inserted


def upsert_sales(engine, rows: list[dict]) -> int:
    inserted = 0
    with Session(engine) as session:
        for row in rows:
            values = {
                "sale_id": str(row.get("saleID", "")),
                "date": (row.get("date") or "")[:10],
                "srid": str(row.get("srid", "")),
                "article": row.get("supplierArticle") or "",
                "goods_name": row.get("goodsName") or "",
                "warehouse": row.get("warehouseName") or "",
                "finished_price": row.get("finishedPrice") or 0.0,
                "is_cancel": bool(row.get("isCancel")),
            }
            inserted += _upsert(session, Sale, "sale_id", values)
        session.commit()
    return inserted


def upsert_fbs_orders(engine, rows: list[dict], client) -> int:
    inserted = 0
    with Session(engine) as session:
        for row in rows:
            price = row.get("price") or 0
            # v3 отдаёт копейки
            values = {
                "srid": str(row.get("rid", "")),
                "nm_id": int(row.get("nmId") or 0),
                "article": row.get("article") or "",
                "status": client.normalize_fbs_status(row),
                "price": client.rub_from_kopecks(price),
                "created_at": datetime.utcfromtimestamp(
                    (row.get("createdAt") or 0) / 1000
                ).strftime("%Y-%m-%d"),
            }
            inserted += _upsert(session, FbsOrder, "srid", values)
        session.commit()
    return inserted


def load_orders(engine, date_from: date, date_to: date) -> list[dict]:
    with Session(engine) as session:
        rows = session.execute(
            select(Order).where(Order.date.between(_iso(date_from), _iso(date_to)))
        ).scalars().all()
        return [
            {
                "srid": r.srid,
                "date": r.date,
                "article": r.article,
                "goods_name": r.goods_name,
                "warehouse": r.warehouse,
                "finished_price": r.finished_price,
                "total_price": r.total_price,
                "is_cancel": r.is_cancel,
            }
            for r in rows
        ]


def load_sales(engine, date_from: date, date_to: date) -> list[dict]:
    with Session(engine) as session:
        rows = session.execute(
            select(Sale).where(Sale.date.between(_iso(date_from), _iso(date_to)))
        ).scalars().all()
        return [
            {
                "saleID": r.sale_id,
                "date": r.date,
                "srid": r.srid,
                "article": r.article,
                "goods_name": r.goods_name,
                "warehouse": r.warehouse,
                "finished_price": r.finished_price,
                "is_cancel": r.is_cancel,
            }
            for r in rows
        ]


def load_fbs_orders(engine, date_from: date, date_to: date) -> list[dict]:
    with Session(engine) as session:
        rows = session.execute(
            select(FbsOrder).where(FbsOrder.created_at.between(_iso(date_from), _iso(date_to)))
        ).scalars().all()
        return [
            {"srid": r.srid, "article": r.article, "status": r.status, "price": r.price}
            for r in rows
        ]


def _iso(d: date) -> str:
    return d.isoformat()
