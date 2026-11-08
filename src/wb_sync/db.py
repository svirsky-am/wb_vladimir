"""SQLite через SQLAlchemy: orders, sales, fbs_orders, cards. Апсерт по ключу."""
from datetime import date, datetime, timezone

from sqlalchemy import (Boolean, Column, Date, Float, Integer, String, create_engine, select)
from sqlalchemy.orm import Session, declarative_base

Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"
    srid = Column(String, primary_key=True)
    date = Column(Date, index=True)
    article = Column(String, index=True)
    name = Column(String)
    price_rub = Column(Float)
    is_cancel = Column(Boolean, default=False)
    raw = Column(String)


class Sale(Base):
    __tablename__ = "sales"
    sale_id = Column(String, primary_key=True)
    srid = Column(String, index=True)
    date = Column(Date, index=True)
    article = Column(String, index=True)
    finished_price_rub = Column(Float)
    is_cancel = Column(Boolean, default=False)
    raw = Column(String)


class FbsOrder(Base):
    __tablename__ = "fbs_orders"
    srid = Column(String, primary_key=True)
    created_at = Column(Date, index=True)
    article = Column(String, index=True)
    price_rub = Column(Float)
    supplier_status = Column(String)
    status = Column(String)
    is_cancel = Column(Boolean, default=False)
    raw = Column(String)


class Card(Base):
    __tablename__ = "cards"
    nm_id = Column(Integer, primary_key=True)
    article = Column(String, index=True)
    title = Column(String)
    category = Column(String)
    brand = Column(String)
    raw = Column(String)


def make_engine(config) -> object:
    engine = create_engine(f"sqlite:///{config.database_path}")
    Base.metadata.create_all(engine)
    return engine


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date()
    return date.fromisoformat(str(value)[:10])


def upsert_orders(engine, rows: list) -> int:
    added = 0
    with Session(engine) as s:
        for r in rows:
            srid = str(r.get("srid") or r.get("rid") or "")
            if not srid:
                continue
            obj = s.get(Order, srid)
            if obj is None:
                obj = Order(srid=srid)
                s.add(obj)
                added += 1
            obj.date = _parse_date(r.get("date"))
            obj.article = r.get("supplierArticle")
            obj.name = r.get("goodsName") or obj.name
            obj.price_rub = (r.get("finishedPrice") or 0) / 100  # копейки -> рубли
            obj.is_cancel = bool(r.get("isCancel", False))
            s.flush()
        s.commit()
    return added


def upsert_sales(engine, rows: list) -> int:
    added = 0
    with Session(engine) as s:
        for r in rows:
            sid = str(r.get("saleID") or "")
            if not sid:
                continue
            obj = s.get(Sale, sid)
            if obj is None:
                obj = Sale(sale_id=sid)
                s.add(obj)
                added += 1
            obj.srid = str(r.get("srid") or "")
            obj.date = _parse_date(r.get("date"))
            obj.article = r.get("supplierArticle")
            obj.finished_price_rub = (r.get("finishedPrice") or 0) / 100  # копейки -> рубли
            obj.is_cancel = bool(r.get("isCancel", False))
            s.flush()
        s.commit()
    return added


def upsert_fbs_orders(engine, rows: list, client) -> int:
    added = 0
    with Session(engine) as s:
        for r in rows:
            srid = str(r.get("rid") or "")
            if not srid:
                continue
            st = r.get("statuses") or {}
            status = status_to_ru_obj(st.get("supplierStatus"), bool(st.get("isCancel", False)))
            obj = s.get(FbsOrder, srid)
            if obj is None:
                obj = FbsOrder(srid=srid)
                s.add(obj)
                added += 1
            obj.created_at = _parse_date(r.get("createdAt"))
            obj.article = r.get("article")
            obj.price_rub = r.get("price")  # v3 уже в рублях
            obj.supplier_status = st.get("supplierStatus")
            obj.status = status
            obj.is_cancel = bool(st.get("isCancel", False))
            s.flush()
        s.commit()
    return added


def upsert_cards(engine, rows: list) -> int:
    added = 0
    with Session(engine) as s:
        for r in rows:
            nm = r.get("nmID")
            if not nm:
                continue
            obj = s.get(Card, nm)
            if obj is None:
                obj = Card(nm_id=nm)
                s.add(obj)
                added += 1
            obj.article = r.get("vendorCode")
            obj.title = (r.get("title") or "").strip()
            obj.category = r.get("category") or ((r.get("parentName") or [None])[0])
            obj.brand = r.get("brand")
            s.flush()
        s.commit()
    return added


def status_to_ru_obj(status: str, is_cancel: bool) -> str:
    ru = {"new": "Ожидает сборки", "confirm": "Готов к отгрузке",
          "complete": "Доставляется", "sent_to_carrier": "Доставляется",
          "delivered": "Доставлен", "cancel": "Отменен", "cancellation": "Отменен",
          }.get((status or "").lower(), status or "неизвестно")
    if is_cancel:
        ru = "Отменен"
    return ru


def load_orders(engine, date_from: date, date_to: date) -> list[dict]:
    out = []
    with Session(engine) as s:
        for o in s.scalars(select(Order).where(Order.date.between(date_from, date_to))):
            out.append({"srid": o.srid, "date": o.date, "article": o.article, "name": o.name,
                        "finishedPrice": int((o.price_rub or 0) * 100), "isCancel": o.is_cancel})
    return out


def load_sales(engine, date_from: date, date_to: date) -> list[dict]:
    out = []
    with Session(engine) as s:
        for x in s.scalars(select(Sale).where(Sale.date.between(date_from, date_to))):
            out.append({"saleID": x.sale_id, "srid": x.srid, "date": x.date, "article": x.article,
                        "finished_price": x.finished_price_rub, "isCancel": x.is_cancel})
    return out


def load_fbs_orders(engine, date_from: date, date_to: date) -> list[dict]:
    out = []
    with Session(engine) as s:
        for o in s.scalars(select(FbsOrder).where(FbsOrder.created_at.between(date_from, date_to))):
            out.append({"srid": o.srid, "status": o.status, "article": o.article,
                        "price_rub": o.price_rub, "isCancel": o.is_cancel})
    return out
