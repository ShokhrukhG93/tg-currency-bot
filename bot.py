import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest
import os
# =========================
# CONFIG
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SHEET_CSV_URL = os.environ.get("SHEET_CSV_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not SHEET_CSV_URL:
    raise RuntimeError("SHEET_CSV_URL is not set")

COL_BANK = "Наименование банка"
COL_CURR = "Валюта"
COL_BUY = "Харид"
COL_SELL = "Сотув"
COL_DATE = "Дата"  # если нет — просто не покажем

PAGE_SIZE = 18
DEFAULT_SORT = "bank"  # bank | buy | sell

# =========================
# DATA CACHE
# =========================
DF = None
CURRENCIES = None


# =========================
# LOAD DATA
# =========================
def load_df() -> pd.DataFrame:
    df = pd.read_csv(SHEET_CSV_URL)
    df.columns = [c.strip() for c in df.columns]

    # numbers clean
    for col in [COL_BUY, COL_SELL]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("\u00A0", "", regex=False)
            .str.replace(" ", "", regex=False)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # strings clean
    df[COL_CURR] = df[COL_CURR].astype(str).str.strip()
    df[COL_BANK] = df[COL_BANK].astype(str).str.strip()
    return df


def get_currencies(df: pd.DataFrame) -> list[str]:
    return sorted(
        df[COL_CURR]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )


def get_table_date(df: pd.DataFrame) -> str | None:
    if COL_DATE not in df.columns:
        return None
    s = df[COL_DATE].dropna().astype(str).str.strip()
    if s.empty:
        return None
    return s.value_counts().index[0]


# =========================
# CORE LOGIC
# =========================
def filter_banks(df_sub: pd.DataFrame) -> pd.DataFrame:
    """Не показываем банки, где Харид=0 и Сотув=0 (или оба пустые)."""
    buy = pd.to_numeric(df_sub[COL_BUY], errors="coerce").fillna(0)
    sell = pd.to_numeric(df_sub[COL_SELL], errors="coerce").fillna(0)
    return df_sub[(buy > 0) | (sell > 0)].copy()


def sort_df(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == "buy":
        return df.sort_values(by=[COL_BUY, COL_BANK], ascending=[False, True])
    if mode == "sell":
        return df.sort_values(by=[COL_SELL, COL_BANK], ascending=[True, True])
    return df.sort_values(by=[COL_BANK], ascending=[True])


def truncate(text: str, n: int) -> str:
    t = (text or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def build_summary(df_sub: pd.DataFrame) -> str:
    # best buy: max Харид, best sell: min Сотув
    lines = []

    if df_sub[COL_BUY].notna().any():
        r = df_sub.loc[df_sub[COL_BUY].idxmax()]
        lines.append(f"🟢 <b>Лучшая покупка</b>: {int(r[COL_BUY])} — {truncate(str(r[COL_BANK]), 45)}")
    else:
        lines.append("🟢 <b>Лучшая покупка</b>: нет данных")

    if df_sub[COL_SELL].notna().any():
        r = df_sub.loc[df_sub[COL_SELL].idxmin()]
        lines.append(f"🔴 <b>Лучшая продажа</b>: {int(r[COL_SELL])} — {truncate(str(r[COL_BANK]), 45)}")
    else:
        lines.append("🔴 <b>Лучшая продажа</b>: нет данных")

    return "\n".join(lines)


def build_table(df_page: pd.DataFrame) -> str:
    # аккуратно под телефон
    bank_w = 24
    buy_w = 7
    sell_w = 7

    header = f"{'Банк'.ljust(bank_w)} {'Харид'.rjust(buy_w)} {'Сотув'.rjust(sell_w)}"
    sep = "-" * len(header)
    rows = [header, sep]

    for _, r in df_page.iterrows():
        bank = truncate(str(r[COL_BANK]), bank_w)
        buy = "-" if pd.isna(r[COL_BUY]) else str(int(r[COL_BUY]))
        sell = "-" if pd.isna(r[COL_SELL]) else str(int(r[COL_SELL]))
        rows.append(f"{bank.ljust(bank_w)} {buy.rjust(buy_w)} {sell.rjust(sell_w)}")

    return "<pre>" + "\n".join(rows) + "</pre>"


# =========================
# UI BUILDERS
# =========================
def currency_keyboard(currencies: list[str]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for i, c in enumerate(currencies, 1):
        row.append(InlineKeyboardButton(c, callback_data=f"CURR|{c}|0|{DEFAULT_SORT}"))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def controls(cur: str, page: int, total_pages: int, sort_mode: str) -> InlineKeyboardMarkup:
    prev_page = max(page - 1, 0)
    next_page = min(page + 1, total_pages - 1)

    sort_row = [
        InlineKeyboardButton("🏦 Банк", callback_data=f"CURR|{cur}|{page}|bank"),
        InlineKeyboardButton("🟢 Buy", callback_data=f"CURR|{cur}|{page}|buy"),
        InlineKeyboardButton("🔴 Sell", callback_data=f"CURR|{cur}|{page}|sell"),
    ]
    nav_row = [
        InlineKeyboardButton("◀️", callback_data=f"CURR|{cur}|{prev_page}|{sort_mode}"),
        InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="NOOP"),
        InlineKeyboardButton("▶️", callback_data=f"CURR|{cur}|{next_page}|{sort_mode}"),
    ]
    bottom_row = [
        InlineKeyboardButton("⬅️ Валюты", callback_data="BACK"),
    ]
    return InlineKeyboardMarkup([sort_row, nav_row, bottom_row])


async def safe_edit(q, text: str, kb=None):
    try:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DF, CURRENCIES
    DF = load_df()
    CURRENCIES = get_currencies(DF)
    await update.message.reply_text("Выбери валюту 👇", reply_markup=currency_keyboard(CURRENCIES))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    if data == "NOOP":
        return

    if data == "BACK":
        await safe_edit(q, "Выбери валюту 👇", currency_keyboard(CURRENCIES))
        return

    if data.startswith("CURR|"):
        _, cur, page, sort_mode = data.split("|")
        page = int(page)

        df_sub = DF[DF[COL_CURR] == cur].copy()
        df_sub = filter_banks(df_sub)

        if df_sub.empty:
            await safe_edit(q, f"По валюте «{cur}» нет банков с обменом.")
            return

        # summary computed on full (filtered) set
        summary = build_summary(df_sub)

        # sorting + paging
        df_sub = sort_df(df_sub, sort_mode)
        total_pages = max(1, (len(df_sub) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        df_page = df_sub.iloc[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

        date_str = get_table_date(DF)
        date_line = f"📅 {date_str}\n" if date_str else ""

        table = build_table(df_page)
        text = f"{date_line}💱 <b>{cur}</b>\n{summary}\n\n{table}"

        await safe_edit(q, text, controls(cur, page, total_pages, sort_mode))


# =========================
# MAIN
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))
    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
