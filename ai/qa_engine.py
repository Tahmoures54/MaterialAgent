# ai/qa_engine.py
"""
Offline Q&A engine for the iMat warehouse management system.
Supports: Persian/English
Answers natural language questions about: stock, locations, shortages, summaries, transactions, item search.
"""
import re
import html
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, List, Callable
from datetime import date, timedelta

from sqlalchemy import func
from db.database import SessionLocal
from db.models import Product, Stock, Transaction

logger = logging.getLogger(__name__)


# ======================================================================
# Text normalization
# ======================================================================
class TextNormalizer:
    """Normalize Persian/Arabic text and digits for more stable searching."""

    _ARABIC_TO_PERSIAN = str.maketrans({
        "ي": "ی", "ك": "ک", "ﻻ": "لا", "ة": "ه",
        "إ": "ا", "أ": "ا", "آ": "ا", "ؤ": "و", "ئ": "ی",
    })
    _DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

    @classmethod
    def normalize(cls, text: str) -> str:
        if not text:
            return ""
        text = text.translate(cls._ARABIC_TO_PERSIAN)
        text = text.translate(cls._DIGIT_MAP)
        text = text.replace("\u200c", " ").replace("ـ", "")
        text = re.sub(r"\s+", " ", text).strip()
        return text


# ======================================================================
# Intent detection result structure
# ======================================================================
@dataclass
class IntentMatch:
    handler: Callable
    score: float
    params: dict


# ======================================================================
# Main engine
# ======================================================================
class QAEngine:
    """Local (offline) – answers warehouse questions in Persian/English."""

    TRANSLATIONS = {
        "en": {
            "list_title": "📦 Items matching '{keyword}'",
            "no_item": "No items found matching '{keyword}'.",
            "stock_line": "<b>{item_code}</b> – {description} | Available: {qty:.0f} {unit}",
            "stock_detail_title": "📋 Stock Details for {item_code}",
            "stock_detail_line": "Location: {loc}, Heat: {heat}, Qty: {qty:.0f}, Allocated: {alloc:.0f}, QC: {qc}",
            "low_stock_title": "⚠️ Items with critically low stock (available < {threshold:.0f})",
            "low_stock_line": "{item_code} – {desc} – Available: {avail:.0f}",
            "no_low_stock": "No items below {threshold:.0f} units.",
            "location_title": "📍 Location of '{item_code}'",
            "location_line": "{item_code} is at {loc} (Qty: {qty:.0f})",
            "summary_title": "📊 Warehouse Summary",
            "summary_line": "Distinct items: {items} | Stock rows: {records} | Total qty: {qty:.0f}",
            "recent_tx_title": "🔄 Recent Transactions (last {days} days)",
            "recent_tx_line": "{date} | {ttype} | {item_code} | Qty: {qty:.0f}",
            "no_tx": "No transactions found in the last {days} days.",
            "top_stock_title": "🏆 Top {limit} items by available quantity",
            "top_stock_line": "{rank}. {item_code} – {desc} – Available: {avail:.0f}",
            "unknown": "I didn't understand that. Try items, stock, location, low stock, summary, or transactions.",
        },
        "fa": {
            "list_title": "📦 لیست کالاهای شامل '{keyword}'",
            "no_item": "هیچ کالایی با عبارت '{keyword}' پیدا نشد.",
            "stock_line": "<b>{item_code}</b> – {description} | موجودی در دسترس: {qty:.0f} {unit}",
            "stock_detail_title": "📋 جزئیات موجودی {item_code}",
            "stock_detail_line": "مکان: {loc}، شماره گداخت: {heat}، تعداد: {qty:.0f}، تخصیص‌یافته: {alloc:.0f}، QC: {qc}",
            "low_stock_title": "⚠️ اقلام با موجودی بحرانی (موجودی کمتر از {threshold:.0f})",
            "low_stock_line": "{item_code} – {desc} – موجودی: {avail:.0f}",
            "no_low_stock": "هیچ کالایی با موجودی کمتر از {threshold:.0f} یافت نشد.",
            "location_title": "📍 محل نگهداری '{item_code}'",
            "location_line": "{item_code} در {loc} (تعداد: {qty:.0f}) موجود است.",
            "summary_title": "📊 خلاصه وضعیت انبار",
            "summary_line": "اقلام متمایز: {items} | ردیف‌های موجودی: {records} | مجموع تعداد: {qty:.0f}",
            "recent_tx_title": "🔄 تراکنش‌های اخیر ({days} روز گذشته)",
            "recent_tx_line": "{date} | {ttype} | {item_code} | تعداد: {qty:.0f}",
            "no_tx": "هیچ تراکنشی در {days} روز گذشته یافت نشد.",
            "top_stock_title": "🏆 {limit} قلم با بیشترین موجودی در دسترس",
            "top_stock_line": "{rank}. {item_code} – {desc} – موجودی: {avail:.0f}",
            "unknown": "متوجه نشدم. لطفاً درباره کالا، موجودی، مکان، کمبود، خلاصه یا تراکنش بپرسید.",
        },
    }

    def __init__(self, lang: str = "en", default_low_threshold: float = 10.0):
        self.lang = lang if lang in self.TRANSLATIONS else "en"
        self.default_low_threshold = default_low_threshold

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @contextmanager
    def _session(self):
        session = SessionLocal()
        try:
            yield session
        except Exception:
            logger.exception("Database error inside QAEngine session")
            raise
        finally:
            session.close()

    def detect_language(self, query: str) -> str:
        return "fa" if re.search(r"[\u0600-\u06FF]", query or "") else "en"

    def t(self, key: str, **kwargs) -> str:
        template = self.TRANSLATIONS.get(self.lang, {}).get(key, key)
        try:
            return template.format(**kwargs) if kwargs else template
        except Exception:
            return template

    @staticmethod
    def _safe(s: Optional[str]) -> str:
        return html.escape((s or "").strip())

    @staticmethod
    def _wrap_list(title: str, lines: List[str]) -> str:
        body = "".join(f"<li>{ln}</li>" for ln in lines)
        return f"<h3>{title}</h3><ul>{body}</ul>"

    @staticmethod
    def _looks_like_code(term: str) -> bool:
        return bool(re.match(r"^[A-Za-z]{1,6}[-_]?\d[\w\-]*$", term.strip()))

    @staticmethod
    def _extract_number(text: str, default: float) -> float:
        m = re.search(r"\d+(?:\.\d+)?", text or "")
        return float(m.group()) if m else default

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------
    def _detect_intent(self, q: str) -> Optional[IntentMatch]:
        candidates: List[IntentMatch] = []

        # summary
        if re.search(r"(خلاصه|وضعیت\s+انبار|summary|overview|total\s+stock)", q):
            candidates.append(IntentMatch(self.warehouse_summary, 0.60, {}))

        # recent transactions
        if re.search(r"(تراکنش|ورود\s+و\s+خروج|transactions?|recent\s+activity)", q):
            days = int(self._extract_number(q, 7))
            days = max(1, min(days, 365))
            candidates.append(IntentMatch(self.recent_transactions, 0.70, {"days": days}))

        # low stock
        if re.search(r"(کمبود|موجودی\s+کم|کم\s+موجود|low\s+stock|running\s+low|shortage)", q):
            threshold = self._extract_number(q, self.default_low_threshold)
            threshold = max(0.0, threshold)
            candidates.append(IntentMatch(self.low_stock_report, 0.75, {"threshold": threshold}))

        # top available
        if re.search(r"(بیشترین\s+موجودی|top\s+stock|top\s+\d+|highest\s+stock)", q):
            limit = int(self._extract_number(q, 10))
            limit = max(1, min(limit, 50))
            candidates.append(IntentMatch(self.top_available_items, 0.76, {"limit": limit}))

        # location
        m = re.search(r"(?:where\s+is\s+(?P<en>[\w\-]+)|(?P<fa>[\w\-آ-ی]+)\s+کجا(?:ست| است|\s+قرار دارد))", q)
        if m:
            term = (m.group("en") or m.group("fa") or "").strip()
            if term:
                candidates.append(IntentMatch(self.item_location, 0.80, {"term": term}))

        # explicit code in question
        m = re.search(r"(?P<code>[A-Za-z]{1,6}[-_]?\d[\w\-]*)", q)
        if m and self._looks_like_code(m.group("code")):
            candidates.append(IntentMatch(self.check_item_stock, 0.85, {"item_code": m.group("code").upper()}))

        # list by keyword
        m = re.search(r"(?:چه|چی)\s+(?P<fa>.+?)\s+(?:داریم|موجوده?)|list\s+(?:of\s+)?(?P<en>.+)", q)
        if m:
            keyword = (m.group("fa") or m.group("en") or "").strip().rstrip("?؟")
            if keyword:
                candidates.append(IntentMatch(self.list_items_by_type, 0.50, {"keyword": keyword}))

        # do we have ...
        m = re.search(r"do\s+we\s+have\s+(?P<term>.+)", q)
        if m and not candidates:
            term = m.group("term").strip().rstrip("?")
            if self._looks_like_code(term):
                candidates.append(IntentMatch(self.check_item_stock, 0.55, {"item_code": term.upper()}))
            else:
                candidates.append(IntentMatch(self.list_items_by_type, 0.55, {"keyword": term}))

        return max(candidates, key=lambda c: c.score) if candidates else None

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def answer(self, query: str, lang: Optional[str] = None, strict: bool = False) -> Optional[str]:
        """
        strict=False: returns None if no intent found (for fallback)
        strict=True : returns unknown message if no intent found
        """
        if not query or not query.strip():
            return self.t("unknown") if strict else None

        self.lang = lang if lang in self.TRANSLATIONS else (lang or self.detect_language(query))
        if self.lang not in self.TRANSLATIONS:
            self.lang = "en"

        q = TextNormalizer.normalize(query.strip()).lower()
        intent = self._detect_intent(q)

        if intent is None:
            logger.info("QAEngine: no intent matched query=%r", query)
            return self.t("unknown") if strict else None

        try:
            return intent.handler(**intent.params)
        except Exception:
            logger.exception("QAEngine handler failed: %s", intent.handler.__name__)
            return self.t("unknown") if strict else None

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def list_items_by_type(self, keyword: str, limit: int = 30) -> str:
        keyword = keyword.strip()
        limit = max(1, min(limit, 100))

        with self._session() as session:
            products = (
                session.query(Product)
                .filter(
                    (Product.description.ilike(f"%{keyword}%")) |
                    (Product.item_code.ilike(f"%{keyword}%"))
                )
                .limit(limit)
                .all()
            )

            if not products:
                return self.t("no_item", keyword=self._safe(keyword))

            codes = [p.item_code for p in products]
            avail_map = dict(
                session.query(
                    Stock.item_code,
                    func.coalesce(func.sum(Stock.quantity - Stock.allocated_qty), 0.0)
                )
                .filter(Stock.item_code.in_(codes), Stock.qc_status == "ACCEPTED")
                .group_by(Stock.item_code)
                .all()
            )

            lines = []
            for p in products:
                lines.append(self.t(
                    "stock_line",
                    item_code=self._safe(p.item_code),
                    description=self._safe(p.description or ""),
                    qty=float(avail_map.get(p.item_code, 0.0)),
                    unit=self._safe(p.unit_of_measure or ("عدد" if self.lang == "fa" else "EA"))
                ))
            return self._wrap_list(self.t("list_title", keyword=self._safe(keyword)), lines)

    def check_item_stock(self, item_code: str) -> str:
        item_code = (item_code or "").upper().strip()

        with self._session() as session:
            product = session.query(Product).filter_by(item_code=item_code).first()
            if not product:
                return self.t("no_item", keyword=self._safe(item_code))

            stocks = (
                session.query(Stock)
                .filter(Stock.item_code == item_code, Stock.quantity > 0)
                .all()
            )
            if not stocks:
                return self.t("no_item", keyword=self._safe(item_code))

            lines = []
            for s in stocks:
                lines.append(self.t(
                    "stock_detail_line",
                    loc=self._safe(s.location.code if s.location else "?"),
                    heat=self._safe(s.heat_no or "-"),
                    qty=float(s.quantity or 0),
                    alloc=float(s.allocated_qty or 0),
                    qc=self._safe(s.qc_status or "-")
                ))
            return self._wrap_list(self.t("stock_detail_title", item_code=self._safe(item_code)), lines)

    def low_stock_report(self, threshold: Optional[float] = None) -> str:
        threshold = self.default_low_threshold if threshold is None else max(0.0, float(threshold))

        with self._session() as session:
            low_items = (
                session.query(
                    Product.item_code,
                    Product.description,
                    func.sum(Stock.quantity - Stock.allocated_qty).label("avail")
                )
                .join(Stock, Stock.item_code == Product.item_code)
                .filter(Stock.qc_status == "ACCEPTED")
                .group_by(Product.item_code, Product.description)
                .having(func.sum(Stock.quantity - Stock.allocated_qty) < threshold)
                .order_by(func.sum(Stock.quantity - Stock.allocated_qty).asc())
                .all()
            )

            if not low_items:
                return f"<p>{self.t('no_low_stock', threshold=threshold)}</p>"

            lines = [
                self.t(
                    "low_stock_line",
                    item_code=self._safe(item.item_code),
                    desc=self._safe(item.description or ""),
                    avail=float(item.avail or 0)
                )
                for item in low_items
            ]
            return self._wrap_list(self.t("low_stock_title", threshold=threshold), lines)

    def item_location(self, term: str) -> str:
        term = term.strip()
        with self._session() as session:
            products = (
                session.query(Product)
                .filter(
                    (Product.item_code.ilike(f"%{term}%")) |
                    (Product.description.ilike(f"%{term}%"))
                )
                .limit(20)
                .all()
            )
            if not products:
                return self.t("no_item", keyword=self._safe(term))

            lines = []
            for p in products:
                stocks = (
                    session.query(Stock)
                    .filter(Stock.item_code == p.item_code, Stock.quantity > 0)
                    .all()
                )
                for s in stocks:
                    lines.append(self.t(
                        "location_line",
                        item_code=self._safe(p.item_code),
                        loc=self._safe(s.location.code if s.location else "?"),
                        qty=float(s.quantity or 0)
                    ))

            if not lines:
                return self.t("no_item", keyword=self._safe(term))
            return self._wrap_list(self.t("location_title", item_code=self._safe(term)), lines)

    def warehouse_summary(self) -> str:
        with self._session() as session:
            items = session.query(func.count(func.distinct(Stock.item_code))).scalar() or 0
            records = session.query(func.count(Stock.id)).scalar() or 0
            total_qty = session.query(func.coalesce(func.sum(Stock.quantity), 0.0)).scalar() or 0.0

            line = self.t("summary_line", items=int(items), records=int(records), qty=float(total_qty))
            return f"<h3>{self.t('summary_title')}</h3><p>{line}</p>"

    def recent_transactions(self, days: int = 7) -> str:
        """Show recent transactions (fixed: uses Transaction.date instead of transaction_date)."""
        days = max(1, min(int(days), 365))
        with self._session() as session:
            since = date.today() - timedelta(days=days)
            txs = (
                session.query(Transaction)
                .filter(Transaction.date >= since)                     # fixed column name
                .order_by(Transaction.date.desc())                     # fixed column name
                .limit(30)
                .all()
            )

            if not txs:
                return f"<p>{self.t('no_tx', days=days)}</p>"

            lines = [
                self.t(
                    "recent_tx_line",
                    date=self._safe(str(getattr(t, "date", "-"))),     # fixed attribute access
                    ttype=self._safe(str(getattr(t, "transaction_type", "-"))),
                    item_code=self._safe(str(getattr(t, "item_code", "-"))),
                    qty=float(getattr(t, "quantity", 0) or 0)
                )
                for t in txs
            ]
            return self._wrap_list(self.t("recent_tx_title", days=days), lines)

    def top_available_items(self, limit: int = 10) -> str:
        """Items with the highest available quantity (ACCEPTED - allocated)."""
        limit = max(1, min(int(limit), 50))
        with self._session() as session:
            rows = (
                session.query(
                    Product.item_code,
                    Product.description,
                    func.coalesce(func.sum(Stock.quantity - Stock.allocated_qty), 0.0).label("avail")
                )
                .join(Stock, Stock.item_code == Product.item_code)
                .filter(Stock.qc_status == "ACCEPTED")
                .group_by(Product.item_code, Product.description)
                .order_by(func.sum(Stock.quantity - Stock.allocated_qty).desc())
                .limit(limit)
                .all()
            )

            if not rows:
                return self.t("no_item", keyword="-")

            lines = []
            for idx, r in enumerate(rows, start=1):
                lines.append(self.t(
                    "top_stock_line",
                    rank=idx,
                    item_code=self._safe(r.item_code),
                    desc=self._safe(r.description or ""),
                    avail=float(r.avail or 0)
                ))
            return self._wrap_list(self.t("top_stock_title", limit=limit), lines)