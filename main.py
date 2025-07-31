import json
import os
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ChatMemberStatus
from keep_alive import keep_alive

TOKEN = "8349278486:AAEmkSGmlH71pbRjGlEd3sQcNwxgm5CEN90"
SOGLIA_INIZIALE = 20
STATS_DIR = "dati_gruppi"

os.makedirs(STATS_DIR, exist_ok=True)

# === FUNZIONI DI GESTIONE FILE ===

def get_stats_file(chat_id):
    return os.path.join(STATS_DIR, f"{chat_id}.json")

def salva_dati(chat_id, dati):
    with open(get_stats_file(chat_id), "w") as f:
        json.dump(dati, f)

def carica_dati(chat_id):
    path = get_stats_file(chat_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def fibonacci(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a

async def is_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    member = await update.effective_chat.get_member(user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

def è_bot(update: Update):
    user = update.message.reply_to_message.from_user
    return user.is_bot

# === COMANDI ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Ciao! Sono il Piantometro. Conteggio i pianti e gestisco le soglie nel gruppo. Scrivi /riepilogopianti per iniziare!")

async def pianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update) or not update.message.reply_to_message or è_bot(update):
        return

    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    user = update.message.reply_to_message.from_user
    user_id = str(user.id)
    nome = user.first_name

    if user_id not in dati:
        dati[user_id] = {"pianti": 0, "soglia": SOGLIA_INIZIALE, "fib_step": 0, "stagione_zerata": False}

    dati[user_id]["pianti"] += 1
    pianti = dati[user_id]["pianti"]
    soglia = dati[user_id]["soglia"]

    messaggio = f"{nome} ha pianto {pianti} volta{'e' if pianti != 1 else ''}."

    if pianti == soglia:
        messaggio += f" {nome} ha terminato i pianti a disposizione."
    elif pianti > soglia:
        step = dati[user_id]["fib_step"]
        durata_ore = fibonacci(step)
        dati[user_id]["fib_step"] += 1

        until_date = datetime.utcnow() + timedelta(hours=durata_ore)
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )
            messaggio += f" Sarà muto per {durata_ore} ora{'e' if durata_ore != 1 else ''}."
        except:
            messaggio += " ⚠️ Non è stato possibile applicare il mute."

    salva_dati(chat_id, dati)
    await update.message.reply_text(messaggio)

async def annullapianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update) or not update.message.reply_to_message or è_bot(update):
        return

    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    user = update.message.reply_to_message.from_user
    user_id = str(user.id)
    nome = user.first_name

    if user_id not in dati:
        dati[user_id] = {"pianti": 0, "soglia": SOGLIA_INIZIALE, "fib_step": 0, "stagione_zerata": False}

    if dati[user_id]["pianti"] > 0:
        dati[user_id]["pianti"] -= 1
    else:
        dati[user_id]["pianti"] = 0

    salva_dati(chat_id, dati)

    await update.message.reply_text(
        f"Pianto annullato per {nome}. Ora ha {dati[user_id]['pianti']} pianto{'i' if dati[user_id]['pianti'] != 1 else ''} su {dati[user_id]['soglia']}."
    )

async def riepilogopianti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    if not dati:
        await update.message.reply_text("Nessuno ha ancora pianto.")
        return

    riepilogo = "📊 Riepilogo Pianti Attuali:\n"
    for user_id, info in dati.items():
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, int(user_id))
            nome = user.user.first_name
        except:
            nome = "Utente sconosciuto"
        riepilogo += f"{nome}: {info['pianti']} pianto{'i' if info['pianti'] != 1 else ''} (soglia {info['soglia']})\n"

    await update.message.reply_text(riepilogo)

async def resetpianti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return

    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    messaggio = "🔄 Nuova stagione iniziata:\n"

    for user_id, info in dati.items():
        pianti_fatti = info["pianti"]
        soglia = info["soglia"]
        diff = soglia - pianti_fatti

        if info.get("stagione_zerata", False):
            nuova_soglia = SOGLIA_INIZIALE
            messaggio += f"\n➡️ <b>{user_id}</b> riparte con soglia 20."
            dati[user_id] = {"pianti": 0, "soglia": nuova_soglia, "fib_step": 0, "stagione_zerata": False}
        else:
            nuova_soglia = max(SOGLIA_INIZIALE + diff, 0)
            if nuova_soglia == 0:
                messaggio += f"\n❌ <b>{user_id}</b> ha terminato la stagione in negativo: ripartirà con soglia 0."
                dati[user_id] = {"pianti": 0, "soglia": 0, "fib_step": 0, "stagione_zerata": True}
            else:
                messaggio += f"\n✔️ <b>{user_id}</b> riparte con soglia {nuova_soglia}."
                dati[user_id] = {"pianti": 0, "soglia": nuova_soglia, "fib_step": 0, "stagione_zerata": False}

    salva_dati(chat_id, dati)
    await update.message.reply_text(messaggio, parse_mode="HTML")

async def impostasoglia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update) or not update.message.reply_to_message or è_bot(update):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Devi specificare una nuova soglia numerica. Esempio: /impostasoglia 25")
        return

    nuova_soglia = int(context.args[0])
    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    user = update.message.reply_to_message.from_user
    user_id = str(user.id)
    nome = user.first_name

    if user_id not in dati:
        dati[user_id] = {"pianti": 0, "soglia": nuova_soglia, "fib_step": 0, "stagione_zerata": False}
    else:
        dati[user_id]["soglia"] = nuova_soglia

    salva_dati(chat_id, dati)
    await update.message.reply_text(f"Nuova soglia impostata per {nome}: {nuova_soglia} pianto{'i' if nuova_soglia != 1 else ''}.")

# === AVVIO BOT ===

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    keep_alive()  # Avvia il server Flask per Render
    asyncio.run(main())  # Avvia il bot Telegram
