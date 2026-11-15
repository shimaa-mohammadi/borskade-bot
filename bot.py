"""TSETMC Watchlist Telegram Bot — entry point & handlers."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import (BotCommand, InlineKeyboardButton,
                      InlineKeyboardMarkup, Update)
from telegram.constants import ChatAction
from telegram.error import BadRequest, TelegramError
from telegram.ext import (Application, CallbackQueryHandler,
                          CommandHandler, ConversationHandler,
                          ContextTypes, MessageHandler, filters)

import httpx

import texts
from analytics import (growth_quarterly, growth_yearly, norm_fa,
                       pick_statements)
from storage import Storage, MAX_SYMBOLS
from tsetmc import TsetmcClient

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s | %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

TEHRAN = ZoneInfo("Asia/Tehran")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

store = Storage(DATA_DIR)
# TSETMC/Codal are reachable from Iran directly; only Telegram needs a proxy
tsetmc = TsetmcClient()

# conversation state
WAIT_SYMBOL = 0

WEEKDAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def tehran_now() -> datetime:
    return datetime.now(TEHRAN)


# ------------------------------------------------------------------ helpers

async def answer(q, text: str | None = None, show_alert: bool = False):
    try:
        await q.answer(text=text, show_alert=show_alert)
    except TelegramError:
        pass


async def send(bot, chat_id: int, text: str,
               keyboard: InlineKeyboardMarkup | None = None) -> None:
    """Send text split into <=4000-char chunks."""
    parts, cur = [], ""
    for block in text.split("\n"):
        if len(cur) + len(block) + 1 > 3900:
            parts.append(cur)
            cur = block
        else:
            cur = f"{cur}\n{block}" if cur else block
    if cur:
        parts.append(cur)
    for i, part in enumerate(parts):
        kb = keyboard if i == len(parts) - 1 else None
        try:
            await bot.send_message(chat_id=chat_id, text=part, reply_markup=kb)
        except TelegramError as exc:
            log.warning("send failed: %s", exc)


async def edit(query, text: str, keyboard: InlineKeyboardMarkup):
    try:
        await query.edit_message_text(text=text, reply_markup=keyboard)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


def watchlist_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for i, s in enumerate(items):
        rows.append([InlineKeyboardButton(f"✨ {s['symbol']}", callback_data=f"sym:{i}")])
    rows.append([
        InlineKeyboardButton("➕ افزودن نماد", callback_data="add"),
        InlineKeyboardButton("➖ حذف نماد", callback_data="remove"),
    ])
    return InlineKeyboardMarkup(rows)


def panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 نرخ رشد نسبت به سال گذشته", callback_data="gr:y")],
        [InlineKeyboardButton("📉 نرخ رشد نسبت به سه‌ماهه", callback_data="gr:q")],
        [InlineKeyboardButton("🎛 وضعیت سهم", callback_data="st")],
        [InlineKeyboardButton("🆕 گزارش‌های جدید", callback_data="rep")],
        [InlineKeyboardButton("📢 اطلاعیه ناظر بازار", callback_data="sup")],
        [InlineKeyboardButton("↩️ بازگشت به واچ‌لیست", callback_data="back:l")],
    ])


def status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 d RSI", callback_data="stx:d"),
         InlineKeyboardButton("📊 w RSI", callback_data="stx:w")],
        [InlineKeyboardButton("💰 قیمت پایانی", callback_data="stx:p"),
         InlineKeyboardButton("📐 سقف/کف ماه و هفته", callback_data="stx:e")],
        [InlineKeyboardButton("🧠 پول هوشمند", callback_data="stx:s"),
         InlineKeyboardButton("📆 درصد تغییر ماهیانه", callback_data="stx:m")],
        [InlineKeyboardButton("👥 سهامداران عمده", callback_data="stx:h"),
         InlineKeyboardButton("📖 عمق بازار (۵ سطح)", callback_data="stx:b")],
        [InlineKeyboardButton("🧾 نمایش همه", callback_data="stx:a")],
        [InlineKeyboardButton("↩️ بازگشت", callback_data="back:p")],
    ])


def find_item(chat_id: int, index: int) -> dict | None:
    items = store.symbols(chat_id)
    if 0 <= index < len(items):
        return items[index]
    return None


async def fetch_panel_data(item: dict) -> tuple[dict, list[dict]]:
    info, rows = await asyncio.gather(
        tsetmc.instrument_info(item["insCode"]),
        tsetmc.daily_list(item["insCode"]),
        return_exceptions=True,
    )
    if isinstance(info, Exception):
        info = {}
    if isinstance(rows, Exception):
        rows = []
    return info or {}, rows or []


# ------------------------------------------------------------------- /start

WELCOME = (
    "🤖 <b>دسته کوچک بازار</b>\n"
    "\U0001F4CB <b>ربات واچ‌لیست بورس تهران</b> (TSETMC)\n\n"
    "\u2022 \u2795 <b>/add</b> \u2014 اضافه کردن نماد به واچ لیست (حداکثر ۱۵ نماد)\n"
    "\u2022 \u2796 <b>/remove</b> \u2014 حذف نماد از واچ ایست\n"
    "\u2022 \U0001F4CB <b>/mylist</b> \u2014 واچ ایست من\n\n"
    "\U0001F4C8 نرخ رشد بنیادی (سالانه/سه‌ماهه از کدال)\n"
    "\U0001F3AE وضعیت سهم: RSI روزانه/هفتگی، قیمت پایانی، سقف‌وکف ماه و هفته،\n"
    "   پول هوشمند، تغییر ماهیانه، سهامداران عمده، عمق بازار ۵ سطح\n"
    "\U0001F6A8 هشدار گزارش جدید کدال و اطلاعیه ناظر بازار (هر ۱۰ دقیقه در ساعات بازار)\n"
    "\U0001F3C1 گزارش پایانی هر روز ساعت ۱۲:۴۰\n\n"
    "\u2728 برای شروع، از منوی پایین (/) استفاده کنید یا /add را بزنید."
)


async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("add", "اضافه کردن نماد به واچ لیست"),
        BotCommand("remove", "حذف نماد از واچ ایست"),
        BotCommand("mylist", "واچ ایست من"),
        BotCommand("start", "منوی اصلی"),
        BotCommand("alerts", "روشن/خاموش کردن هشدارها"),
    ])
    log.info("Bot commands registered.")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    alerts_on = store.chat(chat_id).get("alerts", True)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔔 هشدارها: روشن" if alerts_on else "🔕 هشدارها: خاموش",
                             callback_data="alerts")]])
    await update.message.reply_text(WELCOME, reply_markup=kb)


async def cmd_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    on = store.toggle_alerts(update.effective_chat.id)
    await update.message.reply_text(
        "🔔 هشدارها روشن شد." if on else "🔕 هشدارها خاموش شد.")


# ----------------------------------------------------------------- watchlist

async def cmd_mylist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    items = store.symbols(update.effective_chat.id)
    await update.message.reply_text(
        texts.watchlist_text(items), reply_markup=watchlist_keyboard(items))


async def show_watchlist(query) -> None:
    items = store.symbols(query.message.chat_id)
    await edit(query, texts.watchlist_text(items), watchlist_keyboard(items))


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_message(
        update.effective_chat.id,
        "✍️ نام نماد را بنویسید (مثال: دامین)\n"
        "یا برای انصراف /cancel را بزنید.")
    return WAIT_SYMBOL


async def cb_add_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Entry into the add-conversation via the ➕ inline button."""
    await answer(update.callback_query)
    await ctx.bot.send_message(
        update.effective_chat.id,
        "✍️ نام نماد را بنویسید (مثال: دامین)\n"
        "یا برای انصراف /cancel را بزنید.")
    return WAIT_SYMBOL


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ انصراف داده شد.")
    return ConversationHandler.END


def pick_candidates(query: str, results: list[dict]) -> list[dict]:
    q = norm_fa(query)
    exact = [r for r in results if norm_fa(r["lVal18AFC"]) == q]
    if exact:
        return exact[:8]
    prefix = [r for r in results if norm_fa(r["lVal18AFC"]).startswith(q)]
    if prefix:
        return prefix[:8]
    return [r for r in results if q in norm_fa(r["lVal30"])][:8]


async def receive_symbol(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    raw = (update.message.text or "").strip()
    if not raw or len(raw) > 40:
        await update.message.reply_text("⚠️ نام نماد معتبر نیست. دوباره تلاش کنید:")
        return WAIT_SYMBOL
    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        results = await tsetmc.search(raw)
    except Exception:
        await update.message.reply_text("🚫 خطا در ارتباط با TSETMC، دوباره تلاش کنید:")
        return WAIT_SYMBOL
    cands = pick_candidates(raw, results)
    if not cands:
        await update.message.reply_text(
            f"❌ نماد «{raw}» پیدا نشد. املای نماد را بررسی کنید:\n"
            "✍️ دوباره بنویسید یا /cancel را بزنید.")
        return WAIT_SYMBOL
    if len(cands) == 1:
        await _add_symbol(update.effective_chat, chat_id, cands[0])
        return ConversationHandler.END
    rows = [[InlineKeyboardButton(
        f"✨ {c['lVal18AFC']} — {(c.get('cgrValCotTitle') or c.get('flowTitle') or '').strip()}",
        callback_data=f"cand:{i}")] for i, c in enumerate(cands)]
    ctx.user_data["cands"] = cands
    await update.message.reply_text(
        "🤔 چند نماد مطابقت دارد، کدام را می‌خواهید؟",
        reply_markup=InlineKeyboardMarkup(rows))
    return ConversationHandler.END


async def _add_symbol(chat, chat_id: int, cand: dict) -> None:
    item = {
        "insCode": str(cand["insCode"]),
        "symbol": cand["lVal18AFC"],
        "name": cand.get("lVal30") or "",
        "market": cand.get("flowTitle") or "",
    }
    ok, err = store.add_symbol(chat_id, item)
    if not ok and err == "duplicate":
        await chat.send_message(f"⚠️ نماد {item['symbol']} قبلاً در واچ‌لیست است.")
    elif not ok and err == "limit":
        await chat.send_message(
            f"⛔ ظرفیت واچ‌لیست پر است (حداکثر {MAX_SYMBOLS} نماد).\n"
            "برای افزودن نماد جدید، اول یکی را حذف کنید: /remove")
    else:
        items = store.symbols(chat_id)
        await chat.send_message(
            f"✅ نماد {item['symbol']} به واچ‌لیست اضافه شد.\n\n"
            + texts.watchlist_text(items), reply_markup=watchlist_keyboard(items))


# ------------------------------------------------------------------- remove

async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    items = store.symbols(update.effective_chat.id)
    if not items:
        await update.message.reply_text("📭 واچ‌لیست خالی است.")
        return
    rows = [[InlineKeyboardButton(f"❌ {s['symbol']}", callback_data=f"rm:{i}")]
            for i, s in enumerate(items)]
    rows.append([InlineKeyboardButton("↩️ انصراف", callback_data="back:l")])
    await update.message.reply_text(
        "➖ کدام نماد حذف شود؟", reply_markup=InlineKeyboardMarkup(rows))


# ----------------------------------------------------------------- callbacks

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = update.effective_chat.id
    data = q.data or ""
    udata = ctx.user_data

    if data == "alerts":
        on = store.toggle_alerts(chat_id)
        await answer(q, "هشدارها روشن شد ✅" if on else "هشدارها خاموش شد 🔕")
        await edit(q, WELCOME, InlineKeyboardMarkup([[
            InlineKeyboardButton("🔔 هشدارها: روشن" if on else "🔕 هشدارها: خاموش",
                                 callback_data="alerts")]]))
        return

    if data == "remove":
        await answer(q)
        items = store.symbols(chat_id)
        if not items:
            await edit(q, "📭 واچ‌لیست خالی است.", None)
            return
        rows = [[InlineKeyboardButton(f"❌ {s['symbol']}", callback_data=f"rm:{i}")]
                for i, s in enumerate(items)]
        rows.append([InlineKeyboardButton("↩️ انصراف", callback_data="back:l")])
        await edit(q, "➖ کدام نماد حذف شود؟", InlineKeyboardMarkup(rows))
        return

    if data == "back:l":
        await answer(q)
        await show_watchlist(q)
        return

    if data.startswith("cand:"):
        idx = int(data.split(":")[1])
        cands = udata.get("cands") or []
        if idx >= len(cands):
            await answer(q, "منقضی شده — دوباره /add را بزنید.")
            return
        await answer(q)
        await _add_symbol(q.message.chat, chat_id, cands[idx])
        return

    if data.startswith("rm:"):
        idx = int(data.split(":")[1])
        items = store.symbols(chat_id)
        if idx >= len(items):
            await answer(q, "لیست تغییر کرده است.")
            await show_watchlist(q)
            return
        removed = items[idx]["symbol"]
        store.remove_symbol(chat_id, items[idx]["insCode"])
        await answer(q, f"حذف شد ✅")
        items = store.symbols(chat_id)
        await edit(q, f"✅ نماد {removed} حذف شد.\n\n" + texts.watchlist_text(items),
                   watchlist_keyboard(items))
        return

    if data.startswith("sym:"):
        idx = int(data.split(":")[1])
        item = find_item(chat_id, idx)
        if not item:
            await answer(q, "لیست تغییر کرده است.")
            await show_watchlist(q)
            return
        await answer(q)
        udata["sym_idx"] = idx
        udata["cur_sym"] = item["symbol"]
        info, rows = await fetch_panel_data(item)
        udata["panel"] = {"info": info, "rows": rows}
        await edit(q, texts.panel_header(item, info, rows), panel_keyboard())
        return

    if data in ("gr:y", "gr:q", "st", "rep", "sup", "back:p") or data.startswith("stx:"):
        idx = udata.get("sym_idx")
        item = find_item(chat_id, idx if idx is not None else -1)
        if not item:
            await answer(q, "ابتدا از واچ‌لیست یک نماد انتخاب کنید.")
            await show_watchlist(q)
            return
        await answer(q, "در حال دریافت…")
        await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)

        if data == "back:p":
            info = udata.get("panel", {}).get("info") or {}
            rows = udata.get("panel", {}).get("rows") or []
            await edit(q, texts.panel_header(item, info, rows), panel_keyboard())
            return

        if data in ("gr:y", "gr:q"):
            try:
                raw = await tsetmc.statement_content(item["insCode"])
            except Exception:
                raw = []
            st = pick_statements(raw)
            if data == "gr:y":
                cap, g = growth_yearly(st)
                kind = "yearly"
            else:
                cap, g = growth_quarterly(st)
                kind = "quarterly"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📈 نرخ رشد سالانه", callback_data="gr:y"),
                 InlineKeyboardButton("📉 نرخ رشد سه‌ماهه", callback_data="gr:q")],
                [InlineKeyboardButton("↩️ بازگشت", callback_data="back:p")]])
            await edit(q, texts.growth_text(kind, cap, g), kb)
            return

        if data == "st":
            kb = status_keyboard()
            await edit(q, f"🎛 وضعیت سهم — {item['symbol']}\n"
                          "👇 یکی از موارد را انتخاب کنید:", kb)
            return

        if data == "rep":
            try:
                reports = await tsetmc.codal_reports(item["insCode"], top=20)
            except Exception:
                reports = []
            reports = [r for r in reports if r.get("symbol") == item["symbol"]]
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="back:p")]])
            await edit(q, texts.reports_text(item, reports), kb)
            return

        if data == "sup":
            try:
                msgs = await tsetmc.messages(item["insCode"])
            except Exception:
                msgs = []
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="back:p")]])
            await edit(q, texts.supervisor_text(item, msgs), kb)
            return

        # ---- status detail buttons
        which = data.split(":")[1]
        info, rows = await fetch_panel_data(item)
        udata["panel"] = {"info": info, "rows": rows}
        now = tehran_now()
        try:
            if which in ("d", "w"):
                body = texts.rsi_text(item, rows, which)
            elif which == "p":
                body = texts.price_text(item, rows, info)
            elif which == "e":
                body = texts.extremes_text(item, rows, info, now.date())
            elif which == "s":
                ct = await tsetmc.client_type_history(item["insCode"])
                body = texts.smart_money_text(item, ct)
            elif which == "m":
                body = texts.monthly_change_text(item, rows, now.date())
            elif which == "h":
                holders = await tsetmc.share_holders(item["insCode"])
                body = texts.holders_text(item, holders)
            elif which == "b":
                limits = await tsetmc.best_limits(item["insCode"])
                body = texts.depth_text(item, limits)
            elif which == "a":
                body = await _full_status(item, info, rows, now)
            else:
                body = "؟"
        except Exception as exc:
            log.exception("status failed")
            body = f"🚫 خطا در دریافت داده: {exc}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت به وضعیت", callback_data="st")]])
        await edit(q, body, kb)


async def _full_status(item: dict, info: dict, rows: list[dict], now) -> str:
    parts = [texts.price_text(item, rows, info), "",
             texts.rsi_text(item, rows, "d"), "",
             texts.rsi_text(item, rows, "w"), "",
             texts.extremes_text(item, rows, info, now.date()), "",
             texts.monthly_change_text(item, rows, now.date()), ""]
    try:
        ct = await tsetmc.client_type_history(item["insCode"])
        parts += [texts.smart_money_text(item, ct), ""]
    except Exception:
        pass
    try:
        limits = await tsetmc.best_limits(item["insCode"])
        parts += [texts.depth_text(item, limits)]
    except Exception:
        pass
    return "\n".join(parts)


# ------------------------------------------------------------------ alerts

async def alert_tick(ctx: ContextTypes.DEFAULT_TYPE):
    """Runs every 10 minutes: intraday alerts + 12:40 final report."""
    now = tehran_now()
    wd = now.weekday()  # Mon=0 … Sat=5, Sun=6
    is_trading_day = wd >= 5 or wd <= 2  # Sat, Sun, Mon, Tue, Wed
    if not is_trading_day:
        return
    t = now.hour * 60 + now.minute

    for chat_id, data in list(store.all_chats().items()):
        if not data.get("alerts", True):
            continue
        items = data.get("symbols") or []
        if not items:
            continue
        try:
            if 8 * 60 + 30 <= t < 12 * 60 + 30:
                await _check_new_reports(int(chat_id), items)
            if t >= 12 * 60 + 40 and store.last_final_date(chat_id) != now.strftime("%Y-%m-%d"):
                await _final_report(int(chat_id), items, now)
                store.set_final_date(chat_id, now.strftime("%Y-%m-%d"))
        except Exception:
            log.exception("alert tick failed for %s", chat_id)


async def _check_new_reports(chat_id: int, items: list[dict]):
    codal_seen = store.seen_ids(chat_id, "codal")
    msg_seen = store.seen_ids(chat_id, "msg")
    new_codal, new_msg = [], []
    first_run = not codal_seen and not msg_seen

    for item in items:
        ins = item["insCode"]
        try:
            reports = [r for r in await tsetmc.codal_reports(ins, top=15)
                       if r.get("symbol") == item["symbol"]]
            msgs = await tsetmc.messages(ins)
        except Exception:
            continue
        for r in reports[:3]:
            tid = str(r.get("tracingNo") or "")
            if tid and tid not in codal_seen:
                new_codal.append((item, r, tid))
        for m in msgs[:3]:
            mid = str(m.get("tseMsgIdn") or "")
            if mid and mid not in msg_seen:
                new_msg.append((item, m, mid))

    if first_run:
        # seed seen-ids without spamming the user on first run
        store.mark_seen(chat_id, "codal", [t for _, _, t in new_codal])
        store.mark_seen(chat_id, "msg", [t for _, _, t in new_msg])
        return

    for item, r, tid in new_codal:
        kb = None
        if tid:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                "📄 مشاهده گزارش (PDF)",
                url=f"https://cdn.tsetmc.com/api/Codal/GetContentFileByTracingNo/{tid}/1")]])
        await send(ctx_bot(), chat_id, texts.new_report_alert(item, r), kb)
    for item, m, mid in new_msg:
        await send(ctx_bot(), chat_id, texts.supervisor_alert(item, m))

    if new_codal:
        store.mark_seen(chat_id, "codal", [t for _, _, t in new_codal])
    if new_msg:
        store.mark_seen(chat_id, "msg", [t for _, _, t in new_msg])


def ctx_bot():
    """The job-queue callback context stores the bot on app; use module ref."""
    return BOT_REF[0]


BOT_REF: list = []


async def _final_report(chat_id: int, items: list[dict], now):
    date_str = f"{WEEKDAYS_FA[(now.weekday() + 1) % 7]} {now.strftime('%Y-%m-%d')}"
    entries = []
    for item in items:
        try:
            rows = await tsetmc.daily_list(item["insCode"])
            ct = await tsetmc.client_type_history(item["insCode"])
            sm = smart_money_day(ct[0]) if ct else None
            news = []
            for m in (await tsetmc.messages(item["insCode"]))[:2]:
                tt = (m.get("tseTitle") or "").strip()
                if tt:
                    news.append(tt)
            for r in (await tsetmc.codal_reports(item["insCode"], top=5))[:2]:
                if r.get("symbol") == item["symbol"]:
                    news.append("کدال: " + (r.get("title") or "")[:70])
            entries.append({"item": item, "row": rows[0] if rows else None,
                            "smart": sm, "news": news})
        except Exception:
            entries.append({"item": item, "row": None})
        await asyncio.sleep(0.3)
    await send(ctx_bot(), chat_id, texts.final_report_text(entries, date_str))


# -------------------------------------------------------------------- main

def _pick_telegram_route():
    """Choose how to reach api.telegram.org: configured proxy, direct, or none.

    Returns the proxy URL, None (= direct works) or "dead" (no route).
    """
    proxy = os.environ.get("BOT_PROXY")
    if proxy:
        try:
            with httpx.Client(proxy=proxy, timeout=6) as c:
                if c.get("https://api.telegram.org/").status_code < 500:
                    return proxy
        except Exception:
            log.warning("Configured proxy %s unreachable — trying direct…", proxy)
    try:
        with httpx.Client(timeout=6) as c:
            if c.get("https://api.telegram.org/").status_code < 500:
                return None
    except Exception:
        pass
    return "dead"


def build_app(token: str, proxy: str | None = None) -> Application:
    builder = Application.builder().token(token).post_init(post_init)
    if proxy:
        from telegram.request import HTTPXRequest
        try:
            tg_req = HTTPXRequest(proxy=proxy, connection_pool_size=16)
            tg_upd = HTTPXRequest(proxy=proxy, connection_pool_size=4)
        except TypeError:  # older PTB signature
            tg_req = HTTPXRequest(proxy_url=proxy, connection_pool_size=16)
            tg_upd = HTTPXRequest(proxy_url=proxy, connection_pool_size=4)
        builder = builder.request(tg_req).get_updates_request(tg_upd)
        log.info("Telegram traffic routed via proxy: %s", proxy)
    app = builder.build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("add", cmd_add),
                      CallbackQueryHandler(cb_add_entry, pattern="^add$")],
        states={WAIT_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                             receive_symbol)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True, allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("mylist", cmd_mylist))
    app.add_handler(CommandHandler("list", cmd_mylist))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CallbackQueryHandler(on_button))
    return app


async def _poll_forever(app: Application):
    """Manual lifecycle with a fresh event loop per attempt."""
    async with app:
        await post_init(app)
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"])
        await asyncio.Event().wait()


def main() -> None:
    token = None
    if len(sys.argv) > 1:
        token = sys.argv[1]
    token = token or os.environ.get("BOT_TOKEN")
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not token and os.path.exists(cfg_path):
        import json
        token = json.load(open(cfg_path, encoding="utf-8")).get("token")
    tok_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
    if not token and os.path.exists(tok_path):
        token = open(tok_path, encoding="utf-8").read().strip() or None
    if not token:
        print("استفاده: python bot.py <TELEGRAM_TOKEN>  یا متغیر محیطی BOT_TOKEN")
        sys.exit(1)

    import time as _time
    log.info("BorsKade starting…")
    while True:
        route = _pick_telegram_route()
        if route == "dead":
            log.warning("هیچ مسیری به api.telegram.org نیست "
                        "(پراکسی و اتصال مستقیم هر دو قطع‌اند) — تلاش مجدد بعد از ۲۰ ثانیه")
            _time.sleep(20)
            continue
        if route:
            log.info("Telegram route: proxy %s", route)
        else:
            log.info("Telegram route: direct")
        try:
            app = build_app(token, proxy=route)
            BOT_REF[0] = app.bot
            asyncio.run(_poll_forever(app))
            break  # clean exit
        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break
        except Exception as exc:  # noqa: BLE001
            log.warning("Polling failed (%s) — retrying in 15s…", exc)
            _time.sleep(15)


if __name__ == "__main__":
    main()
