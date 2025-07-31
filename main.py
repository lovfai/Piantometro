import json
import os
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.constants import ChatMemberStatus
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# === CONFIG ===
TOKEN = "8349278486:AAEmkSGmlH71pbRjGlEd3sQcNwxgm5CEN90"
SOGLIA_INIZIALE = 20
DATA_DIR = "dati_gruppi"


def path_file(chat_id):
    return os.path.join(DATA_DIR, f"{chat_id}.json")


def carica_dati(chat_id):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    file_path = path_file(chat_id)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    else:
        return {}


def salva_dati(chat_id, dati):
    with open(path_file(chat_id), "w") as f:
        json.dump(dati, f)


def fibonacci(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


async def is_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    member = await update.effective_chat.get_member(user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Ciao! Sono il Piantometro, il bot che tiene traccia dei pianti nel gruppo.\n"
        "Usa /pianto per punire i lamenti inutili.\n"
        "Solo gli admin possono usarlo. Buona stagione dei pianti!"
    )


async def pianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Usa /pianto rispondendo a un messaggio.")
        return

    user = update.message.reply_to_message.from_user
    if user.is_bot:
        return

    user_id = str(user.id)
    nome = user.first_name
    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    if user_id not in dati:
        dati[user_id] = {
            "pianti": 0,
            "soglia": SOGLIA_INIZIALE,
            "fib_step": 0,
            "stagione_zerata": False
        }

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
            messaggio += f" Ha superato il limite stagionale. Sarà muto per {durata_ore} ora{'e' if durata_ore != 1 else ''}."
        except:
            messaggio += " ⚠️ Non è stato possibile applicare il mute (forse il bot non è admin?)."

    salva_dati(chat_id, dati)
    await update.message.reply_text(messaggio)


async def annullapianto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Usa /annullapianto rispondendo a un messaggio.")
        return

    user = update.message.reply_to_message.from_user
    if user.is_bot:
        return

    user_id = str(user.id)
    nome = user.first_name
    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    if user_id not in dati:
        dati[user_id] = {
            "pianti": 0,
            "soglia": SOGLIA_INIZIALE,
            "fib_step": 0,
            "stagione_zerata": False
        }

    dati[user_id]["pianti"] = max(0, dati[user_id]["pianti"] - 1)
    pianti_rimanenti = dati[user_id]["pianti"]
    soglia = dati[user_id]["soglia"]

    salva_dati(chat_id, dati)
    await update.message.reply_text(
        f"Pianto annullato per {nome}. Ora ha {pianti_rimanenti} pianto{'i' if pianti_rimanenti != 1 else ''} su {soglia}."
    )


async def impostasoglia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
        return

    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Usa /impostasoglia [numero] in risposta a un messaggio.")
        return

    user = update.message.reply_to_message.from_user
    if user.is_bot:
        return

    try:
        nuova_soglia = int(context.args[0])
    except:
        await update.message.reply_text("Devi specificare un numero intero dopo il comando.")
        return

    user_id = str(user.id)
    chat_id = str(update.effective_chat.id)
    dati = carica_dati(chat_id)

    if user_id not in dati:
        dati[user_id] = {
            "pianti": 0,
            "soglia": nuova_soglia,
            "fib_step": 0,
            "stagione_zerata": False
        }
    else:
        dati[user_id]["soglia"] = nuova_soglia

    salva_dati(chat_id, dati)
    await update.message.reply_text(f"✅ Soglia aggiornata per {user.first_name}: ora ha {nuova_soglia} pianti a disposizione.")


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
        await update.message.reply_text("Solo gli admin possono usare questo comando.")
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
            messaggio += f"\n➡️ <b>{user_id}</b> riparte con soglia 20 (recupero dopo stagione a 0)."
            dati[user_id] = {
                "pianti": 0,
                "soglia": nuova_soglia,
                "fib_step": 0,
                "stagione_zerata": False
            }
        else:
            nuova_soglia = max(SOGLIA_INIZIALE + diff, 0)
            if nuova_soglia == 0:
                messaggio += f"\n❌ <b>{user_id}</b> ha terminato la stagione in negativo: per questa stagione non avrà pianti a disposizione."
                dati[user_id] = {
                    "pianti": 0,
                    "soglia": 0,
                    "fib_step": 0,
                    "stagione_zerata": True
                }
            else:
                messaggio += f"\n✔️ <b>{user_id}</b> riparte con soglia {nuova_soglia}."
                dati[user_id] = {
                    "pianti": 0,
                    "soglia": nuova_soglia,
                    "fib_step": 0,
                    "stagione_zerata": False
                }

    salva_dati(chat_id, dati)
    await update.message.reply_text(messaggio, parse_mode="HTML")


# === BOOT ===
import asyncio
import logging
from keep_alive import keep_alive

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pianto", pianto))
    app.add_handler(CommandHandler("annullapianto", annullapianto))
    app.add_handler(CommandHandler("impostasoglia", impostasoglia))
    app.add_handler(CommandHandler("riepilogopianti", riepilogopianti))
    app.add_handler(CommandHandler("resetpianti", resetpianti))

    await app.initialize()
    await app.start()
    print("🤖 Piantometro attivo!")
    await asyncio.Event().wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    keep_alive()
    asyncio.run(main())
