import os
import base64
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import openai

# 🔐 Clés API depuis les variables d'environnement
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# 🔁 Mémoire de l'analyse
last_analysis = {}

# 🔍 Prompt d'analyse complet
ANALYSE_PROMPT = (
    "Tu es un expert de l'achat-revente sur Vinted. Ton rôle est d'aider un vendeur à décider rapidement si un produit en photo vaut la peine d'être acheté et revendu.\n\n"
    "À partir de la photo fournie, effectue une analyse détaillée et directe comprenant :\n"
    "🏡 Marque + type de vêtement\n"
    "🧼 État estimé (visuellement)\n"
    "📊 Popularité du produit (modèle rare ou courant ?)\n"
    "💶 Prix moyen constaté sur Vinted\n"
    "💸 Prix d'achat conseillé\n"
    "💰 Prix de revente réaliste\n"
    "⏳ Temps moyen estimé pour vendre\n"
    "📈 Marge estimée + feu vert (🟢) ou feu rouge (🔴)\n"
    "❗ Conseil final : Vaut-il le coup d’être acheté ? Oui / Non + justification.\n\n"
    "Utilise des emojis, une mise en page claire, et structure comme une fiche de revente professionnelle."
)

# 📝 Prompt titre + description
GEN_TITRE_PROMPT = (
    "Génère un titre Vinted professionnel pour ce produit à revendre (30–80 caractères max). "
    "Puis écris une description claire, rassurante et vendeuse avec des emojis (3-4 lignes max). "
    "Mentionne l'état, la taille si visible, et incite à l'achat sans mentionner de prix."
)

# 📸 Réception photo
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
        await file.download_to_drive(tf.name)
        image_path = tf.name

    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    await update.message.reply_text("🧠 Analyse IA en cours...")

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANALYSE_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Voici la photo :"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]}
            ],
            max_tokens=700
        )

        result = response.choices[0].message.content
        last_analysis[update.effective_user.id] = result

        keyboard = [
            [InlineKeyboardButton("📌 Générer description Vinted", callback_data="gen_description")],
            [InlineKeyboardButton("💾 Sauvegarder dans log.txt", callback_data="save_log")],
            [InlineKeyboardButton("🔄 Reanalyser", callback_data="reanalyze")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(f"🔍 Résultat IA :\n\n{result}", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text("❌ Erreur lors de l'analyse IA.")

# 🎛️ Boutons interactifs
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    analysis = last_analysis.get(user_id, "Aucune analyse disponible.")

    if query.data == "gen_description":
        await query.edit_message_text("📝 Génération titre + description...")
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": GEN_TITRE_PROMPT},
                    {"role": "user", "content": analysis}
                ],
                max_tokens=300
            )
            content = response.choices[0].message.content
            await query.edit_message_text(f"📌 Titre & Description Vinted :\n\n{content}")
        except Exception:
            await query.edit_message_text("❌ Impossible de générer la description.")

    elif query.data == "save_log":
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open("log.txt", "a") as log_file:
            log_file.write(f"\n[{now}] - {analysis}\n{'-'*50}\n")
        await query.edit_message_text("💾 Analyse sauvegardée dans log.txt.")

    elif query.data == "reanalyze":
        await query.edit_message_text("🔄 Renvoie une nouvelle photo pour recommencer !")

# 📨 Réception texte
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Envoie-moi une photo pour une analyse IA complète 🔍")

# 🚀 Démarrage bot
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(CallbackQueryHandler(handle_button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.run_polling()
