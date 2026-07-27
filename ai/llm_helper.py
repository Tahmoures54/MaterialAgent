# ai/llm_helper.py
"""
AI Assistant for iMat – Intelligent Inventory Insights.
Offline-first: uses local QA engine + local rule-based analysis.
No external API keys required.
"""

import html
from datetime import datetime
from typing import List, Dict, Optional

from db.database import SessionLocal
from db.models import Stock, Product, Location, Transaction
from ai.optimizer import InventoryOptimizer  # kept for future integrations
from ai.qa_engine import QAEngine


class LLMHelper:
    """
    Offline inventory assistant with multilingual Q&A and local analytics.

    Features:
    - Answers questions via local QAEngine (fa/en)
    - Fallback local guidance for unmatched questions
    - Inventory snapshot + local analysis
    - HTML report generation (fa/en)
    """

    MESSAGES = {
        "en": {
            "answer_prefix": "<b>📦 Smart Inventory Answer:</b><br><br>{body}",
            "fallback_stock": (
                "Please check the <b>Live Stock Dashboard</b> or "
                "<b>Inventory Summary</b> reports for current stock levels."
            ),
            "fallback_qc": (
                "QC status is tracked per item. Use the Live Stock Dashboard to filter by QC status."
            ),
            "fallback_expiry": (
                "Check the Expiry Date Monitor (Material Control menu) for approaching expirations."
            ),
            "fallback_reorder": (
                "Use the Reorder Point Calculator (Tools menu) to compute optimal order quantities."
            ),
            "fallback_location": (
                "Warehouse locations are managed via Material Control → Warehouse & Locations."
            ),
            "fallback_generic": (
                "I am an offline assistant. I can answer questions about items, stock levels, "
                "locations, transactions, and low-stock alerts. Please try a different question."
            ),
            "no_data": "No inventory data available.",
            "analysis_title": "📊 Local Inventory Analysis",
            "total_items": "Total Items",
            "total_qty": "Total Quantity",
            "available": "Available",
            "qc_status": "QC Status",
            "critical": "⚠️ Critically Low Stock",
            "high_alloc": "⚠️ Highly Allocated Items",
            "reorder_yes": (
                "<b>📊 Local Recommendation:</b><br>"
                "✅ <b>Yes, reorder</b> approximately <b>{qty:.0f} units</b>.<br>"
                "Current stock ({current_stock:.0f}) is below reorder point ({rp:.0f})."
            ),
            "reorder_no": (
                "<b>📊 Local Recommendation:</b><br>"
                "❌ <b>No reorder needed</b>. Stock ({current_stock:.0f}) is sufficient."
            ),
            "bad_lead_time": "Lead time must be greater than zero.",
            "report_title_default": "Inventory Analysis",
            "generated_at": "Generated",
            "critical_items_table": "🔴 Critical Items",
            "item_code": "Item Code",
            "description": "Description",
            "qty_col": "Available",
        },
        "fa": {
            "answer_prefix": "<b>📦 پاسخ هوشمند انبار:</b><br><br>{body}",
            "fallback_stock": (
                "لطفاً برای بررسی موجودی از <b>داشبورد موجودی لحظه‌ای</b> یا "
                "<b>گزارش خلاصه انبار</b> استفاده کنید."
            ),
            "fallback_qc": (
                "وضعیت QC برای هر قلم ثبت می‌شود. از داشبورد موجودی برای فیلتر بر اساس QC استفاده کنید."
            ),
            "fallback_expiry": (
                "برای اقلام نزدیک انقضا از بخش مانیتور تاریخ انقضا در منوی کنترل متریال استفاده کنید."
            ),
            "fallback_reorder": (
                "برای محاسبه سفارش بهینه از ابزار محاسبه نقطه سفارش (منوی ابزارها) استفاده کنید."
            ),
            "fallback_location": (
                "مدیریت مکان‌ها از مسیر «کنترل متریال ← انبار و مکان‌ها» انجام می‌شود."
            ),
            "fallback_generic": (
                "من دستیار آفلاین هستم. می‌توانم درباره کالاها، موجودی، مکان‌ها، "
                "تراکنش‌ها و هشدار کمبود پاسخ بدهم. لطفاً سوال را دقیق‌تر بپرسید."
            ),
            "no_data": "داده‌ای برای تحلیل موجود نیست.",
            "analysis_title": "📊 تحلیل محلی انبار",
            "total_items": "تعداد اقلام",
            "total_qty": "مجموع تعداد",
            "available": "قابل دسترس",
            "qc_status": "وضعیت QC",
            "critical": "⚠️ اقلام بحرانی کم‌موجودی",
            "high_alloc": "⚠️ اقلام با تخصیص بالا",
            "reorder_yes": (
                "<b>📊 پیشنهاد محلی:</b><br>"
                "✅ <b>بله، سفارش‌گذاری شود</b> حدود <b>{qty:.0f} واحد</b>.<br>"
                "موجودی فعلی ({current_stock:.0f}) کمتر از نقطه سفارش ({rp:.0f}) است."
            ),
            "reorder_no": (
                "<b>📊 پیشنهاد محلی:</b><br>"
                "❌ <b>نیازی به سفارش نیست</b>. موجودی ({current_stock:.0f}) کافی است."
            ),
            "bad_lead_time": "Lead Time باید بزرگ‌تر از صفر باشد.",
            "report_title_default": "تحلیل موجودی انبار",
            "generated_at": "تاریخ تولید",
            "critical_items_table": "🔴 اقلام بحرانی",
            "item_code": "کد کالا",
            "description": "شرح",
            "qty_col": "قابل دسترس",
        },
    }

    def __init__(self):
        self._offline_mode = True
        self.qa = QAEngine()

    # ------------------------------------------------------------------
    # i18n helpers
    # ------------------------------------------------------------------
    def _resolve_lang(self, query: str = "", lang: Optional[str] = None) -> str:
        if lang in ("fa", "en"):
            return lang
        detected = self.qa.detect_language(query or "")
        return detected if detected in ("fa", "en") else "en"

    def _msg(self, lang: str, key: str, **kwargs) -> str:
        template = self.MESSAGES.get(lang, self.MESSAGES["en"]).get(key, key)
        try:
            return template.format(**kwargs) if kwargs else template
        except Exception:
            return template

    # ==================================================================
    # پاسخ‌دهی اصلی
    # ==================================================================
    def answer_query(self, query: str, context: str = "", lang: Optional[str] = None) -> str:
        """
        پاسخ به سوال کاربر با QAEngine محلی؛ در صورت عدم تشخیص، fallback محلی.

        Args:
            query: سوال کاربر
            context: فعلاً استفاده نمی‌شود (برای backward compatibility)
            lang: 'fa' یا 'en' (اختیاری). اگر None باشد خودکار تشخیص داده می‌شود.
        """
        ui_lang = self._resolve_lang(query, lang)

        # 1) تلاش با QAEngine
        answer = self.qa.answer(query, lang=ui_lang, strict=False)
        if answer:
            return self._msg(ui_lang, "answer_prefix", body=answer)

        # 2) fallback rule-based
        local = self._local_query_handler(query, ui_lang)
        if local:
            return local

        # 3) fallback نهایی
        return self.local_fallback(query, ui_lang)

    # ==================================================================
    # snapshot + analysis
    # ==================================================================
    def get_inventory_snapshot(self, session=None) -> List[Dict]:
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True
        try:
            results = (
                session.query(
                    Stock.item_code,
                    Product.description,
                    Product.discipline,
                    Stock.quantity,
                    Stock.allocated_qty,
                    Stock.qc_status,
                    Location.code.label("location"),
                )
                .join(Product, Stock.item_code == Product.item_code)
                .join(Location, Stock.location_id == Location.id)
                .filter(Stock.quantity > 0)
                .all()
            )

            snapshot = []
            for row in results:
                q = float(row.quantity or 0)
                a = float(row.allocated_qty or 0)
                snapshot.append({
                    "item_code": row.item_code,
                    "description": row.description or "",
                    "discipline": row.discipline or "",
                    "quantity": q,
                    "allocated": a,
                    "available": q - a,
                    "qc_status": row.qc_status or "UNKNOWN",
                    "location": row.location or "-",
                })
            return snapshot
        finally:
            if close_session:
                session.close()

    def _local_inventory_analysis(self, data: List[Dict]) -> Dict:
        total_items = len(data)
        total_qty = sum(d.get("quantity", 0) for d in data)
        total_allocated = sum(d.get("allocated", 0) for d in data)
        total_available = sum(d.get("available", 0) for d in data)

        qc_counts = {"QUARANTINE": 0, "ACCEPTED": 0, "REJECTED": 0}
        for d in data:
            qc = d.get("qc_status", "UNKNOWN")
            if qc in qc_counts:
                qc_counts[qc] += 1

        critical = [d for d in data if d.get("available", 0) < 10 and d.get("quantity", 0) > 0]

        high_alloc = []
        for d in data:
            qty = d.get("quantity", 0) or 0
            if qty > 0:
                ratio = (d.get("allocated", 0) or 0) / qty
                if ratio > 0.8:
                    high_alloc.append(d)

        return {
            "total_items": total_items,
            "total_qty": total_qty,
            "total_allocated": total_allocated,
            "total_available": total_available,
            "qc_counts": qc_counts,
            "critical_items": critical[:5],
            "high_allocation_items": high_alloc[:5],
        }

    def generate_inventory_summary(self, inventory_data: List[Dict], lang: str = "en") -> str:
        lang = self._resolve_lang(lang=lang)
        if not inventory_data:
            return self._msg(lang, "no_data")

        insights = self._local_inventory_analysis(inventory_data)
        return self._format_local_analysis(insights, lang)

    def _format_local_analysis(self, insights: Dict, lang: str) -> str:
        title = self._msg(lang, "analysis_title")
        html_out = (
            "<div style=\"font-family:'Segoe UI',Arial;color:#263238;line-height:1.8;\">"
            f"<h3 style=\"color:#004D40;margin-bottom:8px;\">{title}</h3>"
        )
        html_out += (
            f"<p><b>{self._msg(lang,'total_items')}:</b> {insights['total_items']} | "
            f"<b>{self._msg(lang,'total_qty')}:</b> {insights['total_qty']:.0f} | "
            f"<b>{self._msg(lang,'available')}:</b> {insights['total_available']:.0f}</p>"
        )

        html_out += f"<p><b>{self._msg(lang,'qc_status')}:</b> "
        for status, count in insights["qc_counts"].items():
            color = {"ACCEPTED": "#2E7D32", "QUARANTINE": "#F57F17", "REJECTED": "#C62828"}.get(status, "#666")
            html_out += f'<span style="color:{color}; margin-right:12px;">● {status}: {count}</span>'
        html_out += "</p>"

        if insights["critical_items"]:
            html_out += f'<p style="color:#C62828;"><b>{self._msg(lang,"critical")}:</b></p><ul>'
            for item in insights["critical_items"]:
                html_out += (
                    f"<li>{html.escape(str(item.get('item_code','?')))} – "
                    f"{html.escape(str(item.get('description','')))} "
                    f"({self._msg(lang,'available')}: {float(item.get('available',0)):.0f})</li>"
                )
            html_out += "</ul>"

        if insights["high_allocation_items"]:
            html_out += f'<p style="color:#E65100;"><b>{self._msg(lang,"high_alloc")}:</b></p><ul>'
            for item in insights["high_allocation_items"]:
                qty = float(item.get("quantity", 0) or 0)
                alloc = float(item.get("allocated", 0) or 0)
                pct = (alloc / qty * 100) if qty > 0 else 0
                html_out += f"<li>{html.escape(str(item.get('item_code','?')))} – {pct:.0f}% allocated</li>"
            html_out += "</ul>"

        html_out += "</div>"
        return html_out

    # ==================================================================
    # fallback
    # ==================================================================
    def _local_query_handler(self, query: str, lang: str) -> Optional[str]:
        q = (query or "").lower()
        if any(word in q for word in ["stock", "inventory", "level", "موجودی", "انبار"]):
            return self._msg(lang, "fallback_stock")
        if "qc" in q or "quality" in q or "کنترل کیفی" in q:
            return self._msg(lang, "fallback_qc")
        if "expir" in q or "انقضا" in q:
            return self._msg(lang, "fallback_expiry")
        if "reorder" in q or "order" in q or "سفارش" in q:
            return self._msg(lang, "fallback_reorder")
        if "location" in q or "where" in q or "مکان" in q:
            return self._msg(lang, "fallback_location")
        return None

    def local_fallback(self, query: str, lang: Optional[str] = None) -> str:
        lang = self._resolve_lang(query=query, lang=lang)
        q = (query or "").lower()
        if "stock" in q or "موجودی" in q:
            return self._msg(lang, "fallback_stock")
        return self._msg(lang, "fallback_generic")

    # ==================================================================
    # reorder suggestion
    # ==================================================================
    def suggest_reorder(
        self,
        item_name: str,
        current_stock: float,
        demand_forecast: float,
        lead_time_days: int,
        lang: str = "en",
    ) -> str:
        lang = self._resolve_lang(lang=lang)

        if lead_time_days <= 0:
            return f"<span style='color:#C62828;'><b>{self._msg(lang, 'bad_lead_time')}</b></span>"

        # ساده و شفاف
        safety_stock = demand_forecast * 0.2
        daily_demand = demand_forecast / lead_time_days
        reorder_point = (daily_demand * lead_time_days) + safety_stock  # == demand_forecast + safety_stock

        if current_stock <= reorder_point:
            qty = (reorder_point - current_stock) + safety_stock
            return self._msg(
                lang, "reorder_yes",
                qty=max(qty, 0),
                current_stock=current_stock,
                rp=reorder_point,
            )
        return self._msg(lang, "reorder_no", current_stock=current_stock)

    # ==================================================================
    # report generation
    # ==================================================================
    def generate_html_report(
        self,
        inventory_data: List[Dict],
        title: Optional[str] = None,
        lang: str = "en"
    ) -> str:
        lang = self._resolve_lang(lang=lang)
        report_title = title or self._msg(lang, "report_title_default")
        local_data = self._local_inventory_analysis(inventory_data or [])
        summary_html = self.generate_inventory_summary(inventory_data or [], lang=lang)

        html_doc = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(report_title)}</title>
    <style>
        body {{ font-family:'Segoe UI',Arial; background:#F5F7FA; padding:20px; }}
        .container {{ max-width:900px; margin:0 auto; background:white; border-radius:12px; padding:30px; box-shadow:0 4px 20px rgba(0,0,0,0.06); }}
        h1 {{ color:#004D40; border-bottom:3px solid #E0F2F1; padding-bottom:10px; }}
        .summary {{ background:#E0F2F1; padding:20px; border-radius:8px; margin:20px 0; }}
        .metrics {{ display:flex; gap:20px; margin:20px 0; }}
        .metric-card {{ flex:1; background:#F9FAFB; padding:16px; border-radius:8px; text-align:center; border-left:4px solid #004D40; }}
        .metric-value {{ font-size:24px; font-weight:bold; color:#004D40; }}
        .metric-label {{ font-size:12px; color:#607D8B; }}
        table {{ width:100%; border-collapse:collapse; margin:15px 0; }}
        th {{ background:#004D40; color:white; padding:10px; text-align:left; }}
        td {{ padding:8px 10px; border-bottom:1px solid #E0E0E0; }}
        tr:nth-child(even) {{ background:#f9fafb; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {html.escape(report_title)}</h1>
        <p>{self._msg(lang,'generated_at')}: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

        <div class="metrics">
            <div class="metric-card"><div class="metric-value">{local_data['total_items']}</div><div class="metric-label">{self._msg(lang,'total_items')}</div></div>
            <div class="metric-card"><div class="metric-value">{local_data['total_qty']:.0f}</div><div class="metric-label">{self._msg(lang,'total_qty')}</div></div>
            <div class="metric-card"><div class="metric-value">{local_data['total_available']:.0f}</div><div class="metric-label">{self._msg(lang,'available')}</div></div>
            <div class="metric-card"><div class="metric-value">{local_data['qc_counts']['ACCEPTED']}</div><div class="metric-label">QC Accepted</div></div>
        </div>

        <div class="summary">{summary_html}</div>

        <h3>{self._msg(lang,'critical_items_table')}</h3>
        <table>
            <tr>
                <th>{self._msg(lang,'item_code')}</th>
                <th>{self._msg(lang,'description')}</th>
                <th>{self._msg(lang,'qty_col')}</th>
            </tr>
        """

        for item in local_data.get("critical_items", []):
            html_doc += (
                f"<tr><td>{html.escape(str(item.get('item_code','?')))}</td>"
                f"<td>{html.escape(str(item.get('description','')))}</td>"
                f"<td>{float(item.get('available',0)):.0f}</td></tr>"
            )

        html_doc += "</table></div></body></html>"
        return html_doc

    def save_html_report(
        self,
        inventory_data: List[Dict],
        filepath: str,
        title: Optional[str] = None,
        lang: str = "en",
    ) -> str:
        html_content = self.generate_html_report(inventory_data, title=title, lang=lang)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        return filepath


# ------------------------------------------------------------------
# Singleton instance
# ------------------------------------------------------------------
_llm_instance: Optional[LLMHelper] = None


def get_llm_instance() -> LLMHelper:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMHelper()
    return _llm_instance