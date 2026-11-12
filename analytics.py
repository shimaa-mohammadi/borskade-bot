"""Analytics: RSI (daily/weekly), month/week extremes, smart money,
Codal income-statement parsing and YoY / QoQ growth rates."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

# --------------------------------------------------------------------- util

def norm_fa(text: str) -> str:
    """Normalize Arabic/Persian look-alikes for comparisons."""
    if not text:
        return ""
    table = str.maketrans({
        "ي": "ی", "ى": "ی", "ك": "ک", "ٱ": "ا", "أ": "ا", "إ": "ا",
        "\u200c": "", "\u200f": "", "\u200e": "",
        "ة": "ه",
    })
    return text.translate(table).strip()


def fmt_num(value: Any) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value or "—")
    if f == int(f) and abs(f) < 1e15:
        return f"{int(f):,}"
    return f"{f:,.2f}"


def fmt_vol(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v >= 1e9:
        return f"{v / 1e9:,.2f} میلیارد"
    if v >= 1e6:
        return f"{v / 1e6:,.2f} میلیون"
    return fmt_num(v)


def pct_text(pct: float | None) -> str:
    if pct is None:
        return "نامشخص"
    if pct >= 0:
        return f"{abs(pct):,.0f}% افزایش"
    return f"{abs(pct):,.0f}% کاهش"


def day_weekday(d: int) -> int:
    """weekday() of Gregorian yyyymmdd int: Mon=0 … Sat=5, Sun=6."""
    return date(d // 10000, d // 100 % 100, d % 100).weekday()


def saturday_of(d: int) -> int:
    """Gregorian yyyymmdd of the Saturday starting this Iranian week."""
    dd = date(d // 10000, d // 100 % 100, d % 100)
    sat = dd.fromordinal(dd.toordinal() - ((dd.weekday() - 5) % 7))
    return sat.year * 10000 + sat.month * 100 + sat.day


# ---------------------------------------------------------------------- RSI

def rsi(closes_old_to_new: list[float], period: int = 14) -> float | None:
    """Wilder's RSI."""
    if len(closes_old_to_new) < period + 1:
        return None
    deltas = [closes_old_to_new[i] - closes_old_to_new[i - 1]
              for i in range(1, len(closes_old_to_new))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - 100.0 / (1.0 + rs)


def closes_from_rows(rows: list[dict]) -> list[float]:
    """Daily rows (newest first) → closes oldest→newest."""
    return [float(r["pClosing"]) for r in reversed(rows) if r.get("pClosing")]


def weekly_closes(rows: list[dict]) -> list[float]:
    """Weekly closes (last session of each week, week starts Saturday),
    oldest→newest."""
    by_week: dict[int, tuple[int, float]] = {}  # sat -> (max_dEven, close)
    for r in rows:
        d = r.get("dEven")
        if not d or r.get("pClosing") is None:
            continue
        sat = saturday_of(int(d))
        cur = by_week.get(sat)
        if cur is None or int(d) > cur[0]:
            by_week[sat] = (int(d), float(r["pClosing"]))
    return [close for _, (_d, close) in sorted(by_week.items(), key=lambda kv: kv[0])]


# ------------------------------------------------------- price / extremes

def month_week_extremes(rows: list[dict], info: dict, today: date) -> dict:
    ym = today.year * 100 + today.month
    month_rows = [r for r in rows if r.get("dEven") and int(r["dEven"]) // 100 == ym]
    today_weekday = today.weekday()
    # Saturday of the current Iranian week as a date → yyyymmdd int
    sat_date = today.fromordinal(today.toordinal() - ((today_weekday - 5) % 7))
    sat = sat_date.year * 10000 + sat_date.month * 100 + sat_date.day
    week_rows = [r for r in rows if r.get("dEven") and int(r["dEven"]) >= sat]

    def hi(rs): return max((float(r["priceMax"]) for r in rs if r.get("priceMax")), default=None)
    def lo(rs): return min((float(r["priceMin"]) for r in rs if r.get("priceMin")), default=None)

    return {
        "month_high": hi(month_rows) or info.get("maxYear"),
        "month_low": lo(month_rows) or info.get("minYear"),
        "week_high": hi(week_rows) or info.get("maxWeek"),
        "week_low": lo(week_rows) or info.get("minWeek"),
        "year_high": info.get("maxYear"),
        "year_low": info.get("minYear"),
    }


def monthly_change(rows: list[dict], today: date) -> float | None:
    """% change of latest close vs last close of previous month."""
    if not rows:
        return None
    ym = today.year * 100 + today.month
    latest = rows[0]
    prev = next((r for r in rows if r.get("dEven") and int(r["dEven"]) // 100 < ym), None)
    if not prev:
        return None
    base = float(prev["pClosing"])
    if base == 0:
        return None
    return (float(latest["pClosing"]) - base) / base * 100.0


# ------------------------------------------------------------- smart money

def smart_money_day(ct: dict) -> dict:
    """Client-type row → individual/legal net volumes & smart-money signal.

    I = حقیقی (individual), N = حقوقی (legal/non-individual).
    """
    buy_i = float(ct.get("buy_I_Volume") or 0)
    sell_i = float(ct.get("sell_I_Volume") or 0)
    buy_n = float(ct.get("buy_N_Volume") or 0)
    sell_n = float(ct.get("sell_N_Volume") or 0)
    net_i, net_n = buy_i - sell_i, buy_n - sell_n
    if net_n > 0 and net_i < 0:
        signal = "ورودی ✅"
    elif net_n < 0 and net_i > 0:
        signal = "خروجی ⛔"
    elif net_n > 0:
        signal = "ورودی احتمالی 🔶"
    elif net_n < 0:
        signal = "خروجی احتمالی 🔻"
    else:
        signal = "خنثی ⚪"
    return {
        "signal": signal,
        "net_individual": net_i,
        "net_legal": net_n,
        "buy_i_vol": buy_i, "sell_i_vol": sell_i,
        "buy_n_vol": buy_n, "sell_n_vol": sell_n,
        "buy_i_val": float(ct.get("buy_I_Value") or 0),
        "sell_i_val": float(ct.get("sell_I_Value") or 0),
        "buy_n_val": float(ct.get("buy_N_Value") or 0),
        "sell_n_val": float(ct.get("sell_N_Value") or 0),
        "buy_i_count": ct.get("buy_I_Count"), "sell_i_count": ct.get("sell_I_Count"),
    }


def smart_money_week(ct_rows: list[dict]) -> dict:
    """Aggregate the last 5 sessions (rows newest-first)."""
    rows = ct_rows[:5]
    if not rows:
        return {}
    total = {
        "buy_i_vol": sum(float(r.get("buy_I_Volume") or 0) for r in rows),
        "sell_i_vol": sum(float(r.get("sell_I_Volume") or 0) for r in rows),
        "buy_n_vol": sum(float(r.get("buy_N_Volume") or 0) for r in rows),
        "sell_n_vol": sum(float(r.get("sell_N_Volume") or 0) for r in rows),
        "buy_i_val": sum(float(r.get("buy_I_Value") or 0) for r in rows),
        "sell_i_val": sum(float(r.get("sell_I_Value") or 0) for r in rows),
        "buy_n_val": sum(float(r.get("buy_N_Value") or 0) for r in rows),
        "sell_n_val": sum(float(r.get("sell_N_Value") or 0) for r in rows),
    }
    per_day = [smart_money_day(r)["signal"].split()[0] for r in rows]
    net_n = total["buy_n_vol"] - total["sell_n_vol"]
    net_i = total["buy_i_vol"] - total["sell_i_vol"]
    if net_n > 0 and net_i < 0:
        signal = "ورودی ✅"
    elif net_n < 0 and net_i > 0:
        signal = "خروجی ⛔"
    elif net_n > 0:
        signal = "ورودی احتمالی 🔶"
    elif net_n < 0:
        signal = "خروجی احتمالی 🔻"
    else:
        signal = "خنثی ⚪"
    return {"signal": signal, "days": per_day,
            "net_individual": net_i, "net_legal": net_n, **total}


# ------------------------------------------- Codal statements & growth rate

METRICS = {
    "operating_revenue": "درآمد عملیاتی",
    "gross_profit": "سود ناخالص",
    "operating_profit": "سود عملیاتی",
    "net_profit": "سود خالص",
    "eps": "سود هر سهم",
}


def _match_metric(label: str) -> str | None:
    lab = norm_fa(label)
    lab = re.sub(r"\s+", "", lab)
    if "هرسهم" in lab and "سود" in lab:
        return "eps"
    if "ناخالص" in lab and "سود" in lab:
        return "gross_profit"
    if "خالص" in lab and "سود" in lab and "تداوم" not in lab and "عملیات" not in lab:
        return "net_profit"
    if "عملیات" in lab and "سود" in lab and "خالص" not in lab and "تداوم" not in lab:
        return "operating_profit"
    if "درآمد" in lab and "عملیات" in lab and "غیر" not in lab and "سایر" not in lab:
        return "operating_revenue"
    return None


def _parse_td_content(content: str) -> list[list[tuple[int | None, str]]]:
    """Parse the XML-ish `<Root><table>…` into rows of (td_Id, text).

    Phantom empty cells (`<td />`) carry no Id — keeping the Id lets us
    separate label / values / change-cell reliably even when the change
    cell itself is empty.
    """
    trs = re.findall(r"<tr>(.*?)</tr>", content or "", re.S)
    parsed = []
    for tr in trs:
        cells = []
        for m in re.finditer(r"<td([^>]*)(?:>(.*?)</td>|/>)", tr, re.S):
            attrs = m.group(1) or ""
            text = re.sub(r"<[^>]+>", "", m.group(2) or "").strip()
            idm = re.search(r'Id="(\d+)"', attrs)
            cells.append((int(idm.group(1)) if idm else None, text))
        parsed.append(cells)
    return parsed


def parse_statement(stmt: dict) -> dict | None:
    """One Codal statement → {period, period_end, year_end, audited, metrics}.

    metrics: {metric_key: {"values": [v_current, v_prev…], "change": pct}}
    """
    content = stmt.get("content") or ""
    rows = _parse_td_content(content)
    if len(rows) < 2:
        return None
    header_cells = rows[0]
    header_texts = [norm_fa(t) for _i, t in header_cells]
    change_confirmed = any("درصد" in h and "تغییر" in h for h in header_texts)
    ncols = sum(1 for _i, t in header_cells[1:] if t != "")

    m = re.search(r"<Period>(\d+)</Period>", content)
    period_len = int(m.group(1)) if m else None
    m = re.search(r"<PeriodEndToDate>([^<]+)</PeriodEndToDate>", content)
    period_end = m.group(1).strip() if m else ""
    m = re.search(r"<YearEndToDate>([^<]+)</YearEndToDate>", content)
    year_end = m.group(1).strip() if m else ""
    m = re.search(r"<IsAudited>([^<]+)</IsAudited>", content)
    audited = norm_fa(m.group(1)) if m else ""
    pub = int(stmt.get("publishDateTime_DEven") or 0)

    metrics: dict[str, dict] = {}
    for cells in rows[1:]:
        if len(cells) < 2:
            continue
        label = cells[0][1]
        key = _match_metric(label)
        if not key:
            continue
        # data cells: keep every NON-EMPTY cell after the label — Codal puts
        # values in both numbered and unnumbered <td>s, so Id-based
        # filtering would misalign columns.
        ndata = [t for _i, t in cells[1:] if t != ""]
        change = None
        values_raw = ndata
        if change_confirmed and ndata and len(ndata) == ncols:
            try:
                change = float(ndata[-1].replace(",", ""))
                values_raw = ndata[:-1]
            except ValueError:
                values_raw = ndata
        elif change_confirmed and ndata and len(ndata) > ncols:
            try:
                change = float(ndata[-1].replace(",", ""))
            except ValueError:
                change = None
            values_raw = ndata[:ncols - 1] if change is not None else ndata
        values: list[float] = []
        for v in values_raw:
            try:
                values.append(float(v.replace(",", "")))
            except ValueError:
                values.append(0.0)
        if not values:
            continue
        if key not in metrics or len(values) > len(metrics[key]["values"]):
            metrics[key] = {"values": values, "change": change, "label": label}
    if not metrics:
        return None
    return {
        "period_len": period_len,
        "period_end": period_end,
        "year_end": year_end,
        "audited": audited,
        "published": pub,
        "metrics": metrics,
    }


def _metric_value(st: dict, key: str) -> float | None:
    vals = st["metrics"].get(key, {}).get("values")
    if vals:
        return vals[0]
    return None


def _prev_period_match(cur: dict, statements: list[dict], key: str, v1: float) -> bool:
    """True if v1 (2nd column of the current report) matches the current-
    period value of an earlier report → it is the same-period-last-year."""
    for s2 in statements:
        if s2 is cur:
            continue
        if (s2.get("period_end") or "") >= (cur.get("period_end") or ""):
            continue
        v0s = (s2["metrics"].get(key) or {}).get("values")
        if v0s and v0s[0] and abs(v0s[0] - v1) <= max(1.0, 0.02 * abs(v0s[0])):
            return True
    return False


def growth_yearly(statements: list[dict]) -> tuple[str, dict[str, float | None]]:
    """Year-over-year growth of the newest statement's metrics.

    The Codal درصد تغییر column is unreliable across companies, so growth
    is recomputed: (1) validated prev-period column, (2) change column
    only when it matches the recomputed value, (3) annual-vs-annual.
    """
    if not statements:
        return "", {}
    cur = max(statements, key=lambda s: (s["published"], s["period_end"]))
    annuals = sorted([s for s in statements
                      if s.get("period_len") == 12 and s is not cur],
                     key=lambda s: s["year_end"])
    out: dict[str, float | None] = {}
    for key in METRICS:
        cell = cur["metrics"].get(key)
        pct = None
        if cell:
            vs = cell["values"]
            v0 = vs[0] if vs else None
            v1 = vs[1] if len(vs) >= 2 else None
            chg = cell.get("change")
            # (1) prev column cross-validated against an earlier report
            if v0 is not None and v1 not in (None, 0) and \
                    _prev_period_match(cur, statements, key, v1):
                pct = (v0 - v1) / abs(v1) * 100
            # (2) change column accepted only when recomputation agrees
            elif v0 is not None and v1 not in (None, 0) and chg is not None:
                comp = (v0 - v1) / abs(v1) * 100
                if abs(comp - chg) <= 2.0:
                    pct = chg
            # (3) annual vs previous annual
            if pct is None and cur.get("period_len") == 12 and v0 is not None and annuals:
                pv = (annuals[-1]["metrics"].get(key) or {}).get("values")
                if pv and pv[0]:
                    pct = (v0 - pv[0]) / abs(pv[0]) * 100
        out[key] = pct
    pl = cur.get("period_len")
    pl_fa = "۱۲ماهه" if pl == 12 else f"{pl}ماهه"
    caption = (f"دوره {pl_fa} منتهی به {cur['period_end']} "
               f"نسبت به دوره مشابه سال گذشته ({cur['audited']})")
    return caption, out


def _discrete_quarters(statements: list[dict]) -> list[dict]:
    """Cumulative Codal periods → discrete quarter values per metric."""
    by_period: dict[str, dict[int, dict]] = {}  # year_end -> {3|6|9|12: stmt}
    for s in statements:
        pl = s.get("period_len")
        if pl in (3, 6, 9, 12) and s.get("year_end"):
            prev = by_period.setdefault(s["year_end"], {})
            cur = prev.get(pl)
            if cur is None or s["published"] >= cur["published"]:
                prev[pl] = s
    quarters: list[tuple[str, int, dict, str]] = []
    # (year_end, quarter#, {metric: val}, period_end)
    for year_end, cum in by_period.items():
        vals = {}
        for pl in (3, 6, 9, 12):
            st = cum.get(pl)
            if not st:
                continue
            vals[pl] = st
        prev_cum = None
        for pl in (3, 6, 9, 12):
            st = vals.get(pl)
            if not st:
                continue
            qvals = {}
            for key in METRICS:
                v = _metric_value(st, key)
                if v is None:
                    qvals[key] = None
                    continue
                if pl == 3:
                    qvals[key] = v
                else:
                    base = _metric_value(prev_cum, key) if prev_cum else None
                    qvals[key] = (v - base) if base is not None else None
            quarters.append((year_end, pl // 3, qvals, st["period_end"]))
            prev_cum = st
    quarters.sort(key=lambda q: (q[0], q[1]))
    return quarters


FA_QUARTERS = {1: "اول", 2: "دوم", 3: "سوم", 4: "چهارم"}


def growth_quarterly(statements: list[dict]) -> tuple[str, dict[str, float | None]]:
    """Latest discrete quarter vs previous quarter → growth %."""
    quarters = _discrete_quarters(statements)
    if not quarters:
        return "", {}
    cur_y, cur_q, cur_vals, cur_period_end = quarters[-1]
    prev_vals = quarters[-2][2] if len(quarters) >= 2 else {}
    out: dict[str, float | None] = {}
    for key in METRICS:
        c, p = cur_vals.get(key), prev_vals.get(key)
        if c is None or p in (None, 0):
            out[key] = None
        else:
            out[key] = (c - p) / abs(p) * 100
    caption = (f"سه‌ماهه {FA_QUARTERS.get(cur_q, cur_q)} سال مالی {cur_y} "
               f"(دوره منتهی به {cur_period_end}) نسبت به ربع قبل")
    return caption, out


def pick_statements(raw: list[dict]) -> list[dict]:
    """Parse & dedupe statements (keep latest publish per period_end)."""
    parsed = []
    for s in raw:
        p = parse_statement(s)
        if p:
            parsed.append(p)
    dedup: dict[str, dict] = {}
    for p in parsed:
        key = f"{p['year_end']}|{p['period_len']}|{p['period_end']}"
        old = dedup.get(key)
        if old is None or p["published"] >= old["published"]:
            dedup[key] = p
    return list(dedup.values())
