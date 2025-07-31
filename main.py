import json
import os
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ChatMemberStatus
from datetime import datetime, timedelta
from keep_alive import keep_alive

# === CONFIGURAZIONE BASE ===
TOKEN = "8349278486:AAEmkSGmlH71pbRjGlEd3sQcNwxgm5CEN90"
SOGLIA_INIZIALE = 20
STATS_FILE = "dati_pianti.json"

dati_utenti = {}

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

async def is_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    member = await update.effective_chat.get_member(user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

async def pianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Usa /pianto rispondendo a un messaggio.")
        return

    user = update.message.reply_to_message.from_user
    user_id = str(user.id)
    nome = user.first_name

    if user_id not in dati_utenti:
        dati_utenti[user_id] = {
            "pianti": 0,
            "soglia": SOGLIA_INIZIALE,
            "fib_step": 0,
            "stagione_zerata": False
        }

    dati_utenti[user_id]["pianti"] += 1
    pianti = dati_utenti[user_id]["pianti"]
    soglia = dati_utenti[user_id]["soglia"]

    messaggio = f"{nome} ha pianto {pianti} volta{'e' if pianti != 1 else ''}."

    if pianti == soglia:
        messaggio += f" {nome} ha terminato i pianti a disposizione."
    elif pianti > soglia:
        step = dati_utenti[user_id]["fib_step"]
        durata_ore = fibonacci(step)
        dati_utenti[user_id]["fib_step"] += 1

        until_date = datetime.utcnow() + timedelta(hours=durata_ore)
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )
            messaggio += f" Ha superato il limite stagionale. Sarà muto per {durata_ore} ora{'e' if durata_ore > 1 else ''}."
        except:
            messaggio += " ⚠️ Non è stato possibile applicare il mute (forse il bot non è admin?)."

    salva_dati()
    await update.message.reply_text(messaggio)

async def annullapianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Usa /annullapianto rispondendo al messaggio da annullare.")
        return

    user = update.message.reply_to_message.from_user
    user_id = str(user.id)
    nome = user.first_name

    if user_id in dati_utenti and dati_utenti[user_id]["pianti"] > 0:
        dati_utenti[user_id]["pianti"] -= 1
        pianti_rimanenti = dati_utenti[user_id]["pianti"]
        soglia = dati_utenti[user_id]["soglia"]
        await update.message.reply_text(
            f"Pianto annullato per {nome}. Ora ha {pianti_rimanenti} pianto{'i' if pianti_rimanenti != 1 else ''} su {soglia}."
        )
    else:
        await update.message.reply_text(f"{nome} non ha pianti da annullare.")

    salva_dati()

async def riepilogopianti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not dati_utenti:
        await update.message.reply_text("Nessuno ha ancora pianto.")
        return

    riepilogo = "📊 Riepilogo Pianti Attuali:\n"
    for user_id, info in dati_utenti.items():
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, int(user_id))
            nome = user.user.first_name
        except:
            nome = "Utente sconosciuto"

        riepilogo += f"{nome}: {info['pianti']} pianto{'i' if info['pianti'] != 1 else ''} (soglia {info['soglia']})\n"

    await update.message.reply_text(riepilogo)

async def resetpianti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    messaggio = "🔄 Nuova stagione iniziata:\n"

    for user_id, info in dati_utenti.items():
        pianti_fatti = info["pianti"]
        soglia = info["soglia"]
        diff = soglia - pianti_fatti

        if info.get("stagione_zerata", False):
            nuova_soglia = SOGLIA_INIZIALE
            messaggio += f"\n➡️ <b>{user_id}</b> riparte con soglia 20 (recupero dopo stagione a 0)."
            dati_utenti[user_id] = {
                "pianti": 0,
                "soglia": nuova_soglia,
                "fib_step": 0,
                "stagione_zerata": False
            }
        else:
            nuova_soglia = max(SOGLIA_INIZIALE + diff, 0)
            if nuova_soglia == 0:
                messaggio += f"\n❌ <b>{user_id}</b> ha terminato la stagione in negativo: per questa stagione non avrà pianti a disposizione."
                dati_utenti[user_id] = {
                    "pianti": 0,
                    "soglia": 0,
                    "fib_step": 0,
                    "stagione_zerata": True
                }
            else:
                messaggio += f"\n✔️ <b>{user_id}</b> riparte con soglia {nuova_soglia}."
                dati_utenti[user_id] = {
                    "pianti": 0,
                    "soglia": nuova_soglia,
                    "fib_step": 0,
                    "stagione_zerata": False
                }

    salva_dati()
    await update.message.reply_text(messaggio, parse_mode="HTML")

# === AVVIO BOT ===
import asyncio
import logging
from keep_alive import keep_alive

async def main():
    carica_dati()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("pianto", pianto))
    app.add_handler(CommandHandler("annullapianto", annullapianto))
    app.add_handler(CommandHandler("riepilogopianti", riepilogopianti))
    app.add_handler(CommandHandler("resetpianti", resetpianti))

    print("Piantometro in esecuzione...")
    await app.initialize()
    await app.start()

    # Mantiene il bot attivo finché il processo è in vita
    await asyncio.Event().wait()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    keep_alive()  # Avvia il server Flask per Render + UptimeRobot

    loop = asyncio.get_event_loop()
    loop.create_task(main())   # Avvia il bot
    loop.run_forever()         # Mantiene il processo attivo
