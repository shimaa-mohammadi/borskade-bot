# 📄 متن آماده پورت‌فولیو (کپی کنید در پونیشا / کارلنسر)

## نسخه فارسی

**🤖 ربات تلگرامی واچ‌لیست بورس تهران (BorsKade)**

ربات هوشمند پیگیری سهام برای بازار سرمایه ایران که مستقیماً به APIهای رسمی
TSETMC (سایت tsetmc.ir) و سامانه کدال متصل می‌شود — بدون هیچ سرویس واسط.

**امکانات:**
- ✅ واچ‌لیست تا ۱۵ نماد با جستجوی هوشمند نام فارسی
- 📈 نرخ رشد بنیادی (درآمد عملیاتی، سود ناخالص، سود عملیاتی، سود خالص، EPS)
  به‌صورت سالانه و سه‌ماهه — استخراج و محاسبه از صورت‌های مالی کدال
- 🎛 وضعیت لحظه‌ای سهم: RSI روزانه/هفتگی، قیمت پایانی، سقف و کف ماه/هفته/سال،
  پول هوشمند (تحلیل حقیقی/حقوقی)، درصد تغییر ماهیانه، سهامداران عمده،
  عمق بازار ۵ سطح
- 🚨 هشدار خودکار هر ۱۰ دقیقه در ساعات بازار (شنبه تا چهارشنبه ۸:۳۰–۱۲:۳۰)
  برای گزارش‌های جدید کدال و اطلاعیه‌های ناظر بازار
- 🏁 گزارش پایانی روزانه ساعت ۱۲:۴۰
- 🛡 مقاوم در برابر قطعی اینترنت/پروکسی (تلاش مجدد خودکار، مسیریابی هوشمند)

**تکنولوژی:** Python 3.12، asyncio، python-telegram-bot، httpx، APScheduler،
Reverse-Engineering unofficial APIs، معماری supervisor با restart خودکار

**سورس کد:** github.com/shimaa-mohammadi/borskade-bot
**تست زنده:** t.me/BorsKade_bot

---

## English Version (برای کارفرمای بین‌المللی)

**🤖 BorsKade — Tehran Stock Exchange Watchlist Telegram Bot**

A smart stock-tracking Telegram bot for Iran's capital market, consuming
official TSETMC (tsetmc.ir) and Codal disclosure APIs directly — no third-party
data providers.

**Features:**
- Watchlist (up to 15 symbols) with intelligent Persian symbol search
- Fundamental growth rates (revenue, gross/operating/net profit, EPS) — yearly
  & quarter-over-quarter, parsed & computed from Codal financial statements
- Live instrument status: daily/weekly RSI, closing price, month/week/year
  high-low, smart-money flow (retail vs institutional), monthly change,
  major shareholders, 5-level market depth
- Automated 10-minute intraday alerts for new Codal filings & market-supervisor
  announcements during trading hours (Sat–Wed 8:30–12:30) + daily 12:40 recap
- Resilient: auto-retry on network/proxy failures, smart proxy/direct routing

**Stack:** Python 3.12, asyncio, python-telegram-bot, httpx, APScheduler,
reverse-engineered undocumented APIs, supervisor architecture with auto-restart

**Source:** github.com/shimaa-mohammadi/borskade-bot · **Live:** t.me/BorsKade_bot

---

## 📸 اسکرین‌شات‌هایی که بگیرید (به این ترتیب)

1. پیام خوش‌آمد + دکمه «هشدارها» → نمای منوی اصلی
2. خروجی «واچ ایست من» (لیست شماره‌دار + دکمه‌های نمادها)
3. پنل یک نماد (مثلاً دامین) با دکمه‌های نرخ رشد
4. خروجی «📈 نرخ رشد نسبت به سال گذشته» — جدول بنیادی
5. زیرمنوی «🎛 وضعیت سهم» — ۹ دکمه
6. خروجی «🧠 پول هوشمند» یا «📖 عمق بازار (۵ سطح)»
7. یک پیام هشدار «🚨 گزارش جدید کدال» (اگر اتفاق افتاد)

💡 اسکرین‌شات‌ها را از **پنجره تلگرام دسکتاپ** بگیرید (تمیزتر از موبایل).
برای هر اسکرین‌شات: Win+Shift+S → انتخاب ناحیه چت.

## 🔓 عمومی کردن ریپو (۲ دقیقه)

1. بروید به github.com/shimaa-mohammadi/borskade-bot
2. Settings → پایین صفحه Danger Zone → **Change visibility** → Make public
3. تایپ کنید borskade-bot و تأیید

(کد امن است: توکن ربات و داده‌های شخصی در .gitignore هستند و هرگز push نشده‌اند)
