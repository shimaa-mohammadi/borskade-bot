"""Persian message rendering (plain text, modern emoji styling)."""
from __future__ import annotations

from typing import Any

from analytics import (METRICS, fmt_num, fmt_vol, month_week_extremes,
                       monthly_change, pct_text, rsi, closes_from_rows,
                       weekly_closes, smart_money_day, smart_money_week)

JALALI_MONTHS = ["", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                 "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def watchlist_text(items: list[dict]) -> str:
    if not items:
        return ("🔳 لیست نمادهای موجود در #واچ_لیست:\n"
                "— لیست خالی است —\n\n"
                "برای افزودن، دستور /add را بزنید یا نام نماد را ارسال کنید.")
    lines = ["🔳 لیست نمادهای موجود در #واچ_لیست:"]
    for i, s in enumerate(items, 1):
        lines.append(f"{i}: {s['symbol']}")
    lines.append("")
    lines.append("👇 برای دیدن جزئیات، یک نماد را انتخاب کنید:")
    return "\n".join(lines)


def panel_header(item: dict, info: dict, rows: list[dict]) -> str:
    sym = item["symbol"]
    eps = (info.get("eps") or {})
    lines = [
        f"✨ {sym} | {item.get('name', '')}",
        f"🏛 بازار: {info.get('flowTitle') or item.get('market') or '—'}"
        f" | {info.get('cgrValCotTitle') or ''}".rstrip(),
    ]
    if rows:
        r = rows[0]
        chg = float(r.get("priceChange") or 0)
        prev = float(r.get("priceYesterday") or 0)
        pct = (chg / prev * 100) if prev else 0
        sign = "+" if pct >= 0 else ""
        arrow = "🔺" if pct >= 0 else "🔻"
        lines.append(
            f"📊 قیمت پایانی: {fmt_num(r.get('pClosing'))} "
            f"({arrow}{sign}{pct:.2f}%)"
        )
        lines.append(
            f"📦 حجم: {fmt_vol(r.get('qTotTran5J'))} | "
            f"ارزش: {fmt_vol(r.get('qTotCap'))} ریال"
        )
    if eps.get("estimatedEPS"):
        lines.append(f"💵 EPS: {fmt_num(eps['estimatedEPS'])} | PE گروه: {fmt_num(eps.get('sectorPE'))}")
    return "\n".join(lines)


def growth_text(kind: str, caption: str, growth: dict[str, float | None]) -> str:
    title = ("📌نرخ رشد نسبت به سال گذشته:"
             if kind == "yearly"
             else "📌نرخ رشد نسبت به سه ماه گذشته:")
    lines = [f"✨ {title} ✨", f"🗓 {caption}" if caption else ""]
    for key, label in METRICS.items():
        lines.append(f"🏷 {label} 👈 {pct_text(growth.get(key))}")
    if growth and all(v is None for v in growth.values()):
        lines.append("⚠️ داده‌ای از کدال برای این نماد یافت نشد.")
    return "\n".join(l for l in lines if l != "")


def rsi_text(item: dict, rows: list[dict], period: str) -> str:
    closes = closes_from_rows(rows)
    if period == "d":
        val = rsi(closes, 14)
        label = "RSI روزانه (۱۴)"
    else:
        val = rsi(weekly_closes(rows), 14)
        label = "RSI هفتگی (۱۴)"
    lines = [f"🎛 {label} — {item['symbol']}"]
    if val is None:
        lines.append("⚠️ داده کافی برای محاسبه موجود نیست.")
    else:
        zone = ("اشباع خرید 🔴" if val >= 70 else
                "اشباع فروش 🟢" if val <= 30 else "نرمال ⚪")
        lines.append(f"📈 مقدار: {val:.1f} — {zone}")
        if val >= 70:
            lines.append("⚠️ احتمال اصلاح نزولی")
        elif val <= 30:
            lines.append("✨ احتمال بازگشت صعودی")
    return "\n".join(lines)


def price_text(item: dict, rows: list[dict], info: dict) -> str:
    lines = [f"📊 قیمت — {item['symbol']}"]
    if not rows:
        lines.append("⚠️ داده‌ای یافت نشد.")
        return "\n".join(lines)
    r = rows[0]
    prev = float(r.get("priceYesterday") or 0)
    chg = float(r.get("priceChange") or 0)
    pct = (chg / prev * 100) if prev else 0
    thr = info.get("staticThreshold") or {}
    lines += [
        f"💰 قیمت پایانی: {fmt_num(r.get('pClosing'))}",
        f"⚡ آخرین معامله: {fmt_num(r.get('pDrCotVal'))}",
        f"🕒 آخرین به‌روزرسانی: {r.get('dEven')} - {r.get('hEven')}",
        f"↔️ تغییر: {fmt_num(chg)} ({pct:+.2f}%)",
        f"💰 قیمت دیروز: {fmt_num(prev)}",
        f"📈 بازه امروز: {fmt_num(r.get('priceMin'))} — {fmt_num(r.get('priceMax'))}",
    ]
    if thr.get("psGelStaMax"):
        lines.append(f"🚧 سقف/کف مجاز: {fmt_num(thr.get('psGelStaMin'))} — {fmt_num(thr.get('psGelStaMax'))}")
    lines.append(f"🔁 تعداد معاملات: {fmt_num(r.get('zTotTran'))}")
    return "\n".join(lines)


def extremes_text(item: dict, rows: list[dict], info: dict,
                  today) -> str:
    ext = month_week_extremes(rows, info, today)
    lines = [f"📐 بیشترین و کمترین قیمت — {item['symbol']}", ""]
    pairs = [
        ("این ماه", ext["month_high"], ext["month_low"]),
        ("این هفته", ext["week_high"], ext["week_low"]),
        ("یک سال گذشته", ext["year_high"], ext["year_low"]),
    ]
    for label, hi, lo in pairs:
        hi_s = fmt_num(hi) if hi else "—"
        lo_s = fmt_num(lo) if lo else "—"
        lines.append(f"🏷 {label}: سقف {hi_s} | کف {lo_s}")
    return "\n".join(lines)


def smart_money_text(item: dict, ct_rows: list[dict]) -> str:
    lines = [f"🧠 پول هوشمند — {item['symbol']}", ""]
    if not ct_rows:
        lines.append("⚠️ داده‌ای یافت نشد.")
        return "\n".join(lines)
    today = smart_money_day(ct_rows[0])
    lines.append(f"📅 امروز: {today['signal']}")
    lines.append(f"🏷 خالص خرید حقوقی: {fmt_vol(today['net_legal'])} سهم")
    lines.append(f"🏷 خالص خرید حقیقی: {fmt_vol(today['net_individual'])} سهم")
    lines.append(f"💰 خرید حقوقی: {fmt_vol(today['buy_n_val'])} | فروش حقوقی: {fmt_vol(today['sell_n_val'])} ریال")
    week = smart_money_week(ct_rows)
    if week:
        lines += ["", f"🗓 ۵ روز اخیر: {week['signal']}"]
        lines.append(f"🏷 خالص حقوقی: {fmt_vol(week['net_legal'])} | خالص حقیقی: {fmt_vol(week['net_individual'])} سهم")
        flow = " ← ".join(week["days"])
        lines.append(f"📊 روند روزها (جدید→قدیم): {flow}")
    lines += ["", "ℹ️ سیگنال: خرید حقوقی هم‌زمان با فروش حقیقی = ورود پول هوشمند"]
    return "\n".join(lines)


def monthly_change_text(item: dict, rows: list[dict], today) -> str:
    pct = monthly_change(rows, today)
    lines = [f"📆 درصد تغییر ماهیانه — {item['symbol']}"]
    lines.append(f"🏷 نسبت به ماه گذشته: {pct_text(pct) if pct is None else f'{pct:+.2f}%'}")
    return "\n".join(lines)


def holders_text(item: dict, holders: list[dict]) -> str:
    lines = [f"👥 سهامداران عمده — {item['symbol']}", ""]
    if not holders:
        lines.append("⚠️ داده‌ای یافت نشد.")
        return "\n".join(lines)
    for h in holders[:8]:
        name = (h.get("shareHolderName") or "—").strip()
        per = float(h.get("perOfShares") or 0)
        amt = float(h.get("changeAmount") or 0)
        if amt > 0:
            delta = f" (+{amt:,.0f} 🔺)"
        elif amt < 0:
            delta = f" ({amt:,.0f} 🔻)"
        else:
            delta = ""
        lines.append(f"🏷 {per:.2f}% | {name}{delta}")
    return "\n".join(lines)


def depth_text(item: dict, limits: list[dict]) -> str:
    lines = [f"📖 عمق بازار (۵ سطح) — {item['symbol']}", ""]
    if not limits:
        lines.append("⚠️ داده‌ای یافت نشد (خارج از ساعت معاملات؟).")
        return "\n".join(lines)
    lines.append("خرید 👈 قیمت | حجم      قیمت 👉 فروش")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    for lvl in range(1, 6):
        row = next((r for r in limits if r.get("number") == lvl), None)
        if not row:
            continue
        buy_p = fmt_num(row.get("pMeDem"))
        buy_v = fmt_vol(row.get("qTitMeDem"))
        buy_o = fmt_num(row.get("zOrdMeDem"))
        sell_p = fmt_num(row.get("pMeOf"))
        sell_v = fmt_vol(row.get("qTitMeOf"))
        sell_o = fmt_num(row.get("zOrdMeOf"))
        if float(row.get("pMeDem") or 0) == 0:
            buy_s = "     —      "
        else:
            buy_s = f"{buy_v}|{buy_o} @ {buy_p}"
        if float(row.get("pMeOf") or 0) == 0:
            sell_s = "     —      "
        else:
            sell_s = f"{sell_v}|{sell_o} @ {sell_p}"
        lines.append(f"🟩 {buy_s}  ⬜ {lvl}  🟥 {sell_s}")
    lines.append("")
    lines.append("ℹ️ حجم|تعداد سفارش @ قیمت (ریال)")
    return "\n".join(lines)


def reports_text(item: dict, reports: list[dict], limit: int = 8) -> str:
    lines = [f"🆕 آخرین گزارش‌های کدال — {item['symbol']}", ""]
    if not reports:
        lines.append("⚠️ گزارشی یافت نشد.")
        return "\n".join(lines)
    for r in reports[:limit]:
        title = (r.get("title") or "").strip()
        if len(title) > 90:
            title = title[:90] + "…"
        pub = str(r.get("publishDateTime_Gregorian") or "")[:16].replace("T", " ")
        lines.append(f"📄 {title}")
        lines.append(f"   🕒 {pub}")
    return "\n".join(lines)


def supervisor_text(item: dict, msgs: list[dict], limit: int = 5) -> str:
    lines = [f"📢 اطلاعیه‌های ناظر بازار — {item['symbol']}", ""]
    if not msgs:
        lines.append("⚠️ اطلاعیه‌ای یافت نشد.")
        return "\n".join(lines)
    for m in msgs[:limit]:
        title = (m.get("tseTitle") or "").strip()
        desc = (m.get("tseDesc") or "").strip().replace("\r", "")
        if len(desc) > 350:
            desc = desc[:350] + "…"
        d = str(m.get("dEven") or "")
        lines.append(f"📣 {title}")
        if desc:
            lines.append(f"{desc}")
        lines.append(f"🕒 {d}")
        lines.append("―――――――――")
    return "\n".join(lines)


def new_report_alert(item: dict, r: dict) -> str:
    title = (r.get("title") or "").strip()
    pub = str(r.get("publishDateTime_Gregorian") or "")[:16].replace("T", " ")
    return (f"🚨 گزارش جدید کدال\n"
            f"🏷 نماد: {item['symbol']}\n"
            f"📄 {title}\n"
            f"🕒 انتشار: {pub}")


def supervisor_alert(item: dict, m: dict) -> str:
    title = (m.get("tseTitle") or "").strip()
    desc = (m.get("tseDesc") or "").strip()
    if len(desc) > 600:
        desc = desc[:600] + "…"
    return (f"📣 اطلاعیه ناظر بازار\n"
            f"🏷 نماد: {item['symbol']}\n"
            f"📌 {title}\n\n{desc}")


def final_report_text(entries: list[dict], date_str: str) -> str:
    lines = [f"🏁 گزارش پایانی بازار — {date_str} (ساعت ۱۲:۴۰)", ""]
    if not entries:
        lines.append("واچ‌لیست خالی است.")
        return "\n".join(lines)
    for e in entries:
        sym, row = e["item"]["symbol"], e.get("row")
        if not row:
            lines.append(f"🏷 {sym}: ⚠️ داده‌ای دریافت نشد")
            continue
        prev = float(row.get("priceYesterday") or 0)
        chg = float(row.get("priceChange") or 0)
        pct = (chg / prev * 100) if prev else 0
        arrow = "🔺" if pct >= 0 else "🔻"
        sm = e.get("smart")
        sm_s = f" | پول هوشمند: {sm['signal']}" if sm else ""
        lines.append(
            f"🏷 {sym}: {fmt_num(row.get('pClosing'))} {arrow}{pct:+.2f}%"
            f" | حجم {fmt_vol(row.get('qTotTran5J'))}{sm_s}"
        )
        if e.get("news"):
            for t in e["news"][:2]:
                lines.append(f"   📰 {t}")
    lines += ["", "🏭 تا بازار فردا، بدرود! 🤖"]
    return "\n".join(lines)
