import json
import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ChatMemberStatus
from keep_alive import keep_alive

# === CONFIG ===
TOKEN = "INSERISCI_IL_TUO_TOKEN"
SOGLIA_INIZIALE = 20
STATS_FILE = "dati_pianti.json"
dati_utenti = {}

# === UTILS ===
def salva_dati():
    with open(STATS_FILE, "w") as f:
        json.dump(dati_utenti, f)

def carica_dati():
    global dati_utenti
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            dati_utenti = json.load(f)

def fibonacci(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a

def is_bot(user):
    return user.is_bot

async def is_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    member = await update.effective_chat.get_member(user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

# === COMANDI ===
async def pianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Usa /pianto rispondendo a un messaggio.")
        return

    user = update.message.reply_to_message.from_user
    if is_bot(user):
        await update.message.reply_text("Non puoi assegnare pianti a un bot.")
        return

    chat_id = str(update.effective_chat.id)
    user_id = str(user.id)
    nome = user.first_name

    if chat_id not in dati_utenti:
        dati_utenti[chat_id] = {}

    if user_id not in dati_utenti[chat_id]:
        dati_utenti[chat_id][user_id] = {
            "pianti": 0,
            "soglia": SOGLIA_INIZIALE,
            "fib_step": 0,
            "stagione_zerata": False
        }

    dati_utenti[chat_id][user_id]["pianti"] += 1
    pianti = dati_utenti[chat_id][user_id]["pianti"]
    soglia = dati_utenti[chat_id][user_id]["soglia"]

    messaggio = f"{nome} ha pianto {pianti} volt{'e' if pianti != 1 else 'a'}."

    if pianti == soglia:
        messaggio += f" {nome} ha terminato i pianti a disposizione."
    elif pianti > soglia:
        step = dati_utenti[chat_id][user_id]["fib_step"]
        durata_ore = fibonacci(step)
        dati_utenti[chat_id][user_id]["fib_step"] += 1

        until_date = datetime.utcnow() + timedelta(hours=durata_ore)
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )
            messaggio += f" Ha superato il limite stagionale. Sarà muto per {durata_ore} or{'e' if durata_ore != 1 else 'a'}."
        except:
            messaggio += " ⚠️ Non è stato possibile applicare il mute (forse il bot non è admin?)."

    salva_dati()
    await update.message.reply_text(messaggio)

async def annullapianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Usa /annullapianto rispondendo al messaggio.")
        return

    user = update.message.reply_to_message.from_user
    if is_bot(user):
        await update.message.reply_text("Non puoi annullare un pianto a un bot.")
        return

    chat_id = str(update.effective_chat.id)
    user_id = str(user.id)
    nome = user.first_name

    if chat_id not in dati_utenti:
        dati_utenti[chat_id] = {}

    if user_id not in dati_utenti[chat_id]:
        dati_utenti[chat_id][user_id] = {
            "pianti": 0,
            "soglia": SOGLIA_INIZIALE,
            "fib_step": 0,
            "stagione_zerata": False
        }

    if dati_utenti[chat_id][user_id]["pianti"] > 0:
        dati_utenti[chat_id][user_id]["pianti"] -= 1

    pianti_rimanenti = dati_utenti[chat_id][user_id]["pianti"]
    soglia = dati_utenti[chat_id][user_id]["soglia"]
    salva_dati()

    await update.message.reply_text(
        f"Pianto annullato per {nome}. Ora ha {pianti_rimanenti} piant{'i' if pianti_rimanenti != 1 else 'o'} su {soglia}."
    )

async def riepilogopianti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)

    if chat_id not in dati_utenti or not dati_utenti[chat_id]:
        await update.message.reply_text("Nessuno ha ancora pianto.")
        return

    riepilogo = "📊 Riepilogo Pianti Attuali:\n"
    for user_id, info in dati_utenti[chat_id].items():
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, int(user_id))
            nome = user.user.first_name
        except:
            nome = "Utente sconosciuto"

        riepilogo += f"{nome}: {info['pianti']} piant{'i' if info['pianti'] != 1 else 'o'} (soglia {info['soglia']})\n"

    await update.message.reply_text(riepilogo)

async def resetpianti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    chat_id = str(update.effective_chat.id)
    if chat_id not in dati_utenti:
        dati_utenti[chat_id] = {}

    messaggio = "🔄 Nuova stagione iniziata:\n"

    for user_id, info in dati_utenti[chat_id].items():
        pianti_fatti = info["pianti"]
        soglia = info["soglia"]
        diff = soglia - pianti_fatti

        if info.get("stagione_zerata", False):
            nuova_soglia = SOGLIA_INIZIALE
            messaggio += f"\n➡️ <b>{user_id}</b> riparte con soglia 20 (recupero dopo stagione a 0)."
        else:
            nuova_soglia = max(SOGLIA_INIZIALE + diff, 0)
            if nuova_soglia == 0:
                messaggio += f"\n❌ <b>{user_id}</b> ha terminato la stagione in negativo: per questa stagione non avrà pianti a disposizione."
            else:
                messaggio += f"\n✔️ <b>{user_id}</b> riparte con soglia {nuova_soglia}."

        dati_utenti[chat_id][user_id] = {
            "pianti": 0,
            "soglia": nuova_soglia,
            "fib_step": 0,
            "stagione_zerata": nuova_soglia == 0
        }

    salva_dati()
    await update.message.reply_text(messaggio, parse_mode="HTML")

async def impostasoglia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Usa /impostasoglia [numero] rispondendo a un messaggio dell’utente.")
        return

    try:
        nuova_soglia = int(context.args[0])
        if nuova_soglia < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Inserisci un numero valido e positivo per la soglia.")
        return

    user = update.message.reply_to_message.from_user
    if is_bot(user):
        await update.message.reply_text("Non puoi impostare la soglia a un bot.")
        return

    chat_id = str(update.effective_chat.id)
    user_id = str(user.id)
    nome = user.first_name

    if chat_id not in dati_utenti:
        dati_utenti[chat_id] = {}

    if user_id not in dati_utenti[chat_id]:
        dati_utenti[chat_id][user_id] = {
            "pianti": 0,
            "soglia": nuova_soglia,
            "fib_step": 0,
            "stagione_zerata": False
        }
    else:
        dati_utenti[chat_id][user_id]["soglia"] = nuova_soglia

    salva_dati()
    await update.message.reply_text(
        f"La soglia dei pianti per {nome} è stata impostata a {nuova_soglia}."
    )

# === AVVIO BOT ===
async def main():
    carica_dati()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("pianto", pianto))
    app.add_handler(CommandHandler("annullapianto", annullapianto))
    app.add_handler(CommandHandler("riepilogopianti", riepilogopianti))
    app.add_handler(CommandHandler("resetpianti", resetpianti))
    app.add_handler(CommandHandler("impostasoglia", impostasoglia))

    print("Piantometro in esecuzione...")
    await app.initialize()
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    keep_alive()
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
