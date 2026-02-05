import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackContext

# 1) Справочник валют (MVP)
CURRENCY_DB = {
    "USD": ("✅ USD", "Свободно обменивается в большинстве банков."),
    "EUR": ("✅ EUR", "Свободно обменивается в большинстве банков."),
    "RUB": ("✅ RUB", "Обычно обменивается в большинстве банков."),

    "GBP": ("⚠️ GBP", "Обменивается ограниченно. Часто только в отдельных банках/отделениях."),
    "CHF": ("⚠️ CHF", "Обменивается ограниченно. Лучше уточнять заранее по отделениям."),
    "JPY": ("⚠️ JPY", "Обменивается ограниченно. Возможен обмен по предварительному запросу."),
    "CNY": ("⚠️ CNY", "Обменивается ограниченно. Зависит от наличия."),

    "AUD": ("❌ AUD", "Как правило, в банках не обменивается (низкий спрос / нет наличия)."),
    "CAD": ("❌ CAD", "Как правило, в банках не обменивается (низкий спрос / нет наличия)."),
    "NOK": ("❌ NOK", "Как правило, в банках не обменивается (низкий спрос / нет наличия)."),
}

HELP_TEXT = (
    "Введите код валюты (например: USD, EUR, AUD, JPY).\n"
    "Я отвечу, обменивается ли она в банках и насколько это доступно."
)

def normalize(text: str) -> str:
    return text.strip().upper()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = normalize(update.message.text)
    # разрешим ввод типа "usd" или "USD?"
    query = "".join(ch for ch in query if ch.isalpha())

    if len(query) != 3:
        await update.message.reply_text("Пожалуйста, введите 3-буквенный код валюты (например: USD).")
        return

    if query in CURRENCY_DB:
        title, desc = CURRENCY_DB[query]
        await update.message.reply_text(f"{title}\n\n{desc}")
    else:
        await update.message.reply_text(
            f"🤷‍♂️ {query}\n\nПока нет в базе. Напишите код валюты — добавлю."
        )

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужно установить переменную окружения BOT_TOKEN с токеном от BotFather.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()