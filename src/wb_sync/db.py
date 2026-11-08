"""SQLite через SQLAlchemy: orders, sales, fbs_orders, cards."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, Session

from .cards import normalize_card


class Base(DeclarativeBase):
    pass


class OrderRow(Base):
    __tablename__ = "orders"
    srid = Column(String, primary_key=True)
    date = Column(String, index=True)
    nm_id = Column(Integer)
    article = Column(String)
    subject = Column(String)
    brand = Column(String)
    warehouse_name = Column(String)
    total_price = Column(Float)
    discount_percent = Column(Integer)
    finished_price = Column(Float)
    is_cancel = Column(Boolean)


class SaleRow(Base):
    __tablename__ = "sales"
    sale_id = Column(String, primary_key=True)
    srid = Column(String, index=True)
    date = Column(String, index=True)
    nm_id = Column(Integer)
    article = Column(String)
    subject = Column(String)
    brand = Column(String)
    warehouse_name = Column(String)
    finished_price = Column(Float)
    is_cancel = Column(Boolean)


class FbsOrderRow(Base):
    __tablename__ = "fbs_orders"
    srid = Column(String, primary_key=True)
    created_at = Column(String, index=True)
    nm_id = Column(Integer)
    article = Column(String)
    price = Column(Float)
    status = Column(String)
    raw = Column(Text)


class CardRow(Base):
    __tablename__ = "cards"
    nm_id = Column(Integer, primary_key=True)
    imt_id = Column(Integer)
    article = Column(String, index=True)
    title = Column(String)
    brand = Column(String)
    raw = Column(Text)
    updated_at = Column(String)


def get_engine(config):
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{config.database_path}")
    Base.metadata.create_all(engine)
    return engine


def _d(s):
    return datetime.fromisoformat(s[:10]).date() if s else None


# ---------- orders ----------
def upsert_orders(engine, rows) -> int:
    n = 0
    with Session(engine) as s:
        for row in rows:
            srid = str(row.get("srid") or "")
            if not srid:
                continue
            obj = s.get(OrderRow, srid)
            if obj is None:
                obj = OrderRow(srid=srid)
                s.add(obj)
                n += 1
            obj.date = row.get("date") or ""
            obj.nm_id = row.get("nmId")
            obj.article = row.get("supplierArticle") or ""
            obj.subject = row.get("subjectName") or ""
            obj.brand = row.get("brandName") or ""
            obj.warehouse_name = row.get("warehouseName") or ""
            # v1 отдаёт цены в копейках -> конвертируем в рубли
            obj.total_price = (row.get("totalPrice") or 0) / 100
            obj.discount_percent = row.get("discountPercent") or 0
            obj.finished_price = (row.get("finishedPrice") or 0) / 100
            obj.is_cancel = bool(row.get("isCancel"))
        s.commit()
    return n


def load_orders(engine, date_from: date, date_to: date):
    out = []
    with Session(engine) as s:
        q = s.query(OrderRow).filter(OrderRow.date.is_not(None))
        for r in q.all():
            d = _d(r.date)
            if d and date_from <= d <= date_to:
                out.append(r.__dict__ | {"_sa": None} if False else {
                    "srid": r.srid, "date": r.date, "nmId": r.nm_id, "supplierArticle": r.article,
                    "subjectName": r.subject, "brandName": r.brand, "warehouseName": r.warehouse_name,
                    "totalPrice": r.total_price, "discountPercent": r.discount_percent,
                    "finishedPrice": r.finished_price, "isCancel": r.is_cancel,
                })
    return out


# ---------- sales ----------
def upsert_sales(engine, rows) -> int:
    n = 0
    with Session(engine) as s:
        for row in rows:
            sale_id = str(row.get("saleID") or "")
            if not sale_id:
                continue
            obj = s.get(SaleRow, sale_id)
            if obj is None:
                obj = SaleRow(sale_id=sale_id)
                s.add(obj)
                n += 1
            obj.srid = str(row.get("srid") or "")
            obj.date = row.get("date") or ""
            obj.nm_id = row.get("nmId")
            obj.article = row.get("supplierArticle") or ""
            obj.subject = row.get("subjectName") or ""
            obj.brand = row.get("brandName") or ""
            obj.warehouse_name = row.get("warehouseName") or ""
            # v1 отдаёт цены в копейках -> конвертируем в рубли
            obj.finished_price = (row.get("finishedPrice") or 0) / 100
            obj.is_cancel = bool(row.get("isCancel"))
        s.commit()
    return n


def load_sales(engine, date_from: date, date_to: date):
    out = []
    with Session(engine) as s:
        for r in s.query(SaleRow).all():
            d = _d(r.date)
            if d and date_from <= d <= date_to:
                out.append({
                    "saleID": r.sale_id, "srid": r.srid, "date": r.date, "nmId": r.nm_id,
                    "supplierArticle": r.article, "subjectName": r.subject, "brandName": r.brand,
                    "warehouseName": r.warehouse_name, "finishedPrice": r.finished_price,
                    "isCancel": r.is_cancel,
                })
    return out


# ---------- fbs_orders ----------
def upsert_fbs_orders(engine, rows, client) -> int:
    n = 0
    with Session(engine) as s:
        for row in rows:
            srid = str(row.get("rid") or "")
            if not srid:
                continue
            obj = s.get(FbsOrderRow, srid)
            if obj is None:
                obj = FbsOrderRow(srid=srid)
                s.add(obj)
                n += 1
            ms = row.get("createdAt") or 0
            obj.created_at = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
            obj.nm_id = row.get("nmId")
            obj.article = str(row.get("skus", [""])[0]) if row.get("skus") else ""
            obj.price = row.get("price") or 0  # v3 отдаёт цену сразу в рублях
            obj.status = client.normalize_status(row)
            obj.raw = json.dumps(row, ensure_ascii=False)
        s.commit()
    return n


def load_fbs_orders(engine, date_from: date, date_to: date):
    out = []
    with Session(engine) as s:
        for r in s.query(FbsOrderRow).all():
            d = _d(r.created_at)
            if d and date_from <= d <= date_to:
                out.append({
                    "srid": r.srid, "createdAt": r.created_at, "nmId": r.nm_id,
                    "article": r.article, "price": r.price, "status": r.status, "raw": r.raw,
                })
    return out


# ---------- cards ----------
def upsert_cards(engine, cards) -> int:
    n = 0
    with Session(engine) as s:
        for card in cards:
            nm_id = card.get("nmID")
            if nm_id is None:
                continue
            obj = s.get(CardRow, nm_id)
            if obj is None:
                obj = CardRow(nm_id=nm_id)
                s.add(obj)
                n += 1
            norm = normalize_card(card)
            obj.imt_id = norm["imt_id"]
            obj.article = norm["article"] or ""
            obj.title = norm["title"]
            obj.brand = norm["brand"]
            obj.raw = json.dumps(card, ensure_ascii=False)
            obj.updated_at = datetime.now(tz=timezone.utc).isoformat()
        s.commit()
    return n


def load_cards(engine, article: str | None = None):
    out = []
    with Session(engine) as s:
        q = s.query(CardRow)
        if article:
            q = q.filter(CardRow.article == article)
        for r in q.all():
            out.append({
                "nmID": r.nm_id, "imtID": r.imt_id, "vendorCode": r.article,
                "title": r.title, "brand": r.brand, "raw": r.raw, "updated_at": r.updated_at,
            })
    return out
