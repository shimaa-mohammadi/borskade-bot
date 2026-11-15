# -*- coding: utf-8 -*-
"""Offline reproduction: feed a synthetic /start through the real app dispatch."""
import asyncio, sys, logging
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

import bot  # noqa: E402
import telegram._bot as _tbot  # noqa: E402
from telegram import Update, Message, MessageEntity, Chat, User  # noqa: E402

CHAT_ID = 118941571


async def fake_get_me(self, *a, **k):
    u = User(id=9143272064, is_bot=True, first_name="BorsKade",
             username="BorsKade_bot", can_join_groups=True)
    self._bot_user = u
    return u


_tbot.Bot.get_me = fake_get_me  # class-level patch → no network


async def main():
    app = bot.build_app("9143272064:FAKE-TOKEN-FOR-DISPATCH-TEST")
    await app.initialize()

    print("=" * 70)
    print("bot.username =", repr(app.bot.username))
    msg = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(CHAT_ID, "private"),
        from_user=User(CHAT_ID, False, "Shima", username="shima_test"),
        text="/start",
        entities=[MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=6)],
    )
    update = Update(update_id=99999, message=msg)
    update._bot = app.bot
    msg.set_bot(app.bot)  # message shortcuts (get_bot) need this

    # direct handler checks
    conv = None
    for handlers in app.handlers.values():
        for h in handlers:
            name = type(h).__name__
            try:
                check = h.check_update(update)
            except Exception as exc:
                check = f"RAISED {exc!r}"
            print(f"CHECK {name:<22} → {check}")
    print("=" * 70)
    await app.process_update(update)
    print("process_update finished.")


if __name__ == "__main__":
    asyncio.run(main())
