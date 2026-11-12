# -*- coding: utf-8 -*-
"""Smoke test of the full data layer with real symbols."""
import asyncio, sys, datetime
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8")

import tsetmc, texts
from analytics import (growth_quarterly, growth_yearly, norm_fa,
                       pick_statements, pick_statements as _ps)

TEHRAN = ZoneInfo("Asia/Tehran")
today = datetime.datetime.now(TEHRAN).date()


async def dump(sym_name: str):
    print("=" * 60)
    print("SYMBOL:", sym_name)
    res = await tsetmc_client.search(sym_name)
    print(f"search results: {len(res)}")
    q = norm_fa(sym_name)
    cand = [r for r in res if norm_fa(r["lVal18AFC"]) == q] or res[:1]
    c = cand[0]
    print("picked:", c["lVal18AFC"], "|", c["lVal30"], "| insCode:", c["insCode"])
    ins = str(c["insCode"])
    item = {"insCode": ins, "symbol": c["lVal18AFC"], "name": c["lVal30"], "market": c.get("flowTitle")}

    info = await tsetmc_client.instrument_info(ins)
    print("info: sector=%s maxWeek=%s minWeek=%s" % (info.get("sector", {}).get("lSecVal"),
                                                     info.get("maxWeek"), info.get("minWeek")))
    rows = await tsetmc_client.daily_list(ins)
    print("daily rows:", len(rows), "| newest dEven:", rows[0]["dEven"] if rows else None)

    print("\n--- panel ---")
    print(texts.panel_header(item, info, rows))
    print("\n--- RSI d/w ---")
    print(texts.rsi_text(item, rows, "d"))
    print(texts.rsi_text(item, rows, "w"))
    print("\n--- extremes ---")
    print(texts.extremes_text(item, rows, info, today))
    print("\n--- monthly change ---")
    print(texts.monthly_change_text(item, rows, today))
    print("\n--- smart money ---")
    ct = await tsetmc_client.client_type_history(ins)
    print(texts.smart_money_text(item, ct))
    print("\n--- depth ---")
    lim = await tsetmc_client.best_limits(ins)
    print(texts.depth_text(item, lim))
    print("\n--- holders ---")
    hs = await tsetmc_client.share_holders(ins)
    print(texts.holders_text(item, hs[:8]))
    print("\n--- growth ---")
    raw = await tsetmc_client.statement_content(ins)
    st = pick_statements(raw)
    print("statements parsed:", len(st))
    cap, g = growth_yearly(st)
    print(texts.growth_text("yearly", cap, g))
    cap, g = growth_quarterly(st)
    print()
    print(texts.growth_text("quarterly", cap, g))
    print("\n--- codal reports ---")
    reps = [r for r in await tsetmc_client.codal_reports(ins, top=10) if r.get("symbol") == c["lVal18AFC"]]
    print(texts.reports_text(item, reps, limit=3))
    print("\n--- supervisor msgs ---")
    ms = await tsetmc_client.messages(ins)
    print(texts.supervisor_text(item, ms, limit=2))


async def main():
    global tsetmc_client
    tsetmc_client = tsetmc.TsetmcClient()
    try:
        await dump("دامین")
        await dump("فولاد")
    finally:
        await tsetmc_client.close()

asyncio.run(main())
