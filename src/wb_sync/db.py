"""SQLite через SQLAlchemy 2.0: orders, sales, fbs_orders, cards."""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date, UniqueConstraint, select,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger("wb_sync.db")


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    srid: Mapped[str] = mapped_column(String, unique=True)
    date: Mapped[str] = mapped_column(String)
    article: Mapped[str] = mapped_column(String)
    article_name: Mapped[str] = mapped_column(String, default="")
    warehouse: Mapped[str] = mapped_column(String, default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="")
    is_cancel: Mapped[bool] = mapped_column(Boolean, default=False)


class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[str] = mapped_column(String, unique=True)
    date: Mapped[str] = mapped_column(String)
    srid: Mapped[str] = mapped_column(String, default="")
    article: Mapped[str] = mapped_column(String)
    article_name: Mapped[str] = mapped_column(String, default="")
    finished_price: Mapped[float] = mapped_column(Float, default=0.0)
    is_cancel: Mapped[bool] = mapped_column(Boolean, default=False)


class FbsOrder(Base):
    __tablename__ = "fbs_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rid: Mapped[str] = mapped_column(String, unique=True)
    nm_id: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="")
    is_cancel: Mapped[bool] = mapped_column(Boolean, default=False)


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nm_id: Mapped[int] = mapped_column(Integer, unique=True)
    article: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String, default="")
    brand: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")
    raw: Mapped[str] = mapped_column(String, default="{}")


def make_engine(config):
    return create_engine(f"sqlite:///{config.database_path}")


def init_db(engine):
    Base.metadata.create_all(engine)


# ----- апсерты: идемпотентны, дубли исключены -----
def _upsert(session, model, unique_attr, unique_value, values: dict):
    obj = session.execute(
        select(model).where(getattr(model, unique_attr) == unique_value)
    ).scalar_one_or_none()
    if obj is None:
        session.add(model(**values))
        return 1
    for k, v in values.items():
        setattr(obj, k, v)
    return 0


def upsert_orders(engine, rows):
    added = 0
    with sessionmaker(engine)() as s:
        for r in rows:
            added += _upsert(s, Order, "srid", r["srid"], {
                "srid": r["srid"],
                "date": r.get("date", ""),
                "article": r.get("article", "") or r.get("supplierArticle", ""),
                "article_name": r.get("article_name", ""),
                "warehouse": r.get("warehouseName", ""),
                "quantity": int(r.get("quantity", 1) or 1),
                "price": r.get("price", 0.0),
                "status": r.get("status", ""),
                "is_cancel": bool(r.get("isCancel", False)),
            })
        s.commit()
    logger.info("orders: %d новых записей из %d", added, len(rows))
    return added


def upsert_sales(engine, rows):
    added = 0
    with sessionmaker(engine)() as s:
        for r in rows:
            added += _upsert(s, Sale, "sale_id", r["saleID"], {
                "sale_id": r["saleID"],
                "date": r.get("date", ""),
                "srid": r.get("srid", ""),
                "article": r.get("article", "") or r.get("supplierArticle", ""),
                "article_name": r.get("article_name", ""),
                "finished_price": r.get("finishedPrice", 0) / 100.0,  # копейки -> рубли
                "is_cancel": bool(r.get("isCancel", False)),
            })
        s.commit()
    logger.info("sales: %d новых записей из %d", added, len(rows))
    return added


def upsert_fbs_orders(engine, rows, client):
    added = 0
    with sessionmaker(engine)() as s:
        for r in rows:
            ts = r.get("createdAt")
            created = (
                datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
                if isinstance(ts, (int, float)) else str(ts or "")
            )
            added += _upsert(s, FbsOrder, "rid", r["rid"], {
                "rid": r["rid"],
                "nm_id": int(r.get("nmId", 0) or 0),
                "created_at": created,
                "price": r.get("price", 0.0),  # v3 отдаёт рубли
                "status": client.normalize_v3_status(r) if hasattr(client, "normalize_v3_status") else normalize_v3_status(r),
                "is_cancel": bool((r.get("statuses") or {}).get("isCancel", False)),
            })
        s.commit()
    logger.info("fbs_orders: %d новых записей из %d", added, len(rows))
    return added


def upsert_cards(engine, cards):
    import json as _json
    added = 0
    with sessionmaker(engine)() as s:
        for c in cards:
            added += _upsert(s, Card, "nm_id", c.get("nmID"), {
                "nm_id": c.get("nmID"),
                "article": c.get("vendorCode", ""),
                "title": c.get("title", ""),
                "brand": c.get("brand", ""),
                "category": c.get("category", ""),
                "updated_at": c.get("updatedAt", ""),
                "raw": _json.dumps(c, ensure_ascii=False),
            })
        s.commit()
    logger.info("cards: %d новых карточек из %d", added, len(cards))
    return added


def load_orders(engine, d_from: date, d_to: date):
    with sessionmaker(engine)() as s:
        rows = s.execute(select(Order).where(Order.date >= d_from.isoformat(),
                                             Order.date <= d_to.isoformat())).scalars().all()
        return [dict(srid=r.srid, date=r.date, article=r.article,
                     article_name=r.article_name, warehouseName=r.warehouse,
                     quantity=r.quantity, price=r.price, status=r.status,
                     isCancel=r.is_cancel) for r in rows]


def load_sales(engine, d_from: date, d_to: date):
    with sessionmaker(engine)() as s:
        rows = s.execute(select(Sale).where(Sale.date >= d_from.isoformat(),
                                            Sale.date <= d_to.isoformat())).scalars().all()
        return [dict(saleID=r.sale_id, date=r.date, srid=r.srid, article=r.article,
                     article_name=r.article_name, finished_price=r.finished_price,
                     isCancel=r.is_cancel) for r in rows]


def load_fbs_orders(engine, d_from: date, d_to: date):
    with sessionmaker(engine)() as s:
        rows = s.execute(select(FbsOrder).where(FbsOrder.created_at >= d_from.isoformat(),
                                                FbsOrder.created_at <= d_to.isoformat())).scalars().all()
        return [dict(rid=r.rid, nmId=r.nm_id, createdAt=r.created_at,
                     price=r.price, status=r.status, isCancel=r.is_cancel) for r in rows]


def load_cards(engine):
    with sessionmaker(engine)() as s:
        rows = s.execute(select(Card)).scalars().all()
        return [dict(nmID=r.nm_id, article=r.article, title=r.title,
                     brand=r.brand, category=r.category, updatedAt=r.updated_at) for r in rows]
