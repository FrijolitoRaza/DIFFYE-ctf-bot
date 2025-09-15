#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DIFFYE-CTF Bot - Bot de Telegram para CTF de Búsqueda y Captura de Fugitivos
"""

import threading
import http.server
import socketserver

import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
import pytz
from database_manager import db_manager, Database

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables de entorno
BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',')
TZ = pytz.timezone(os.getenv('TIMEZONE', 'America/Argentina/Buenos_Aires'))

# Fechas del evento (modificables via variables de entorno)
START_DATE = datetime.strptime(os.getenv('START_DATE', '2024-09-15'), '%Y-%m-%d').replace(tzinfo=TZ)
END_DATE = datetime.strptime(os.getenv('END_DATE', '2024-09-19'), '%Y-%m-%d').replace(tzinfo=TZ)

# Estados de conversación
WAITING_NAME, WAITING_FLAG = range(2)

# Función auxiliar para sanitizar texto de usuarios
def sanitize_text(text):
    """Sanitiza texto de usuario para evitar problemas con caracteres especiales"""
    if not text:
        return "Sin nombre"
    # Reemplazar caracteres problemáticos
    sanitized = str(text).replace('_', ' ').replace('*', ' ').replace('[', '(').replace(']', ')')
    sanitized = sanitized.replace('`', "'").replace('~', '-').replace('>', ' ').replace('<', ' ')
    return sanitized[:50]  # Limitar longitud

# Desafíos y sus flags (simplificadas a una palabra)
CHALLENGES = {
    0: {
        'title': '🔍 Desafío Tutorial',
        'description': '''📱 DESAFÍO DE EJEMPLO

La División INVESTIGACIÓN FEDERAL DE FUGITIVOS Y EXTRADICIONES es la escargada del dictado del curso: LA INVESTIGACIÓN FEDERAL EN LA BÚSQUEDA Y CAPTURA DE FUGITIVOS.

🧠 Tu misión: Tu misión: Indicar la sigla de la fuerza a la que pertenece esta división.

📦 Envía la flag en el siguiente formato: `FLAG{PALABRA}` o `FLAG{PALABRA_PALABRA}`.

💡 Pista: La fuerza tiene jurisdicción nacional, viste de azul y su nombre completo incluye la palabra “Argentina”.

''',
        'flag': 'FLAG{PFA}',
        'available_date': START_DATE - timedelta(days=1),  # Disponible antes del evento
        'material_link': None
    },
    1: {
        'title': '📦 Desafío 1 - Análisis de E-commerce',
        'description': '''🛒 ANÁLISIS DE REGISTROS DE E-COMMERCE

Contexto: Un usuario realiza compras sospechosas en un portal de e-commerce.
Varios ítems podrían corresponder a artículos comúnmente vinculados con actividades ilícitas.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Analiza los registros de compras y determina:
¿Qué actividad ilegal puede inferirse a partir de las compras realizadas?

Formato de respuesta: `FLAG{ACTIVIDAD}` o `FLAG{ACTIVIDAD_ACTIVIDAD}`.

💡 Pista: Presta atención a los patrones de compra y las cantidades de ciertos artículos.
''',
        'flag': 'FLAG{DROGAS}',
        'available_date': START_DATE,
        'material_link': 'https://ejemplo.com/desafio1.xlsx'
    },
    2: {
        'title': '📞 Desafío 2 - Registros Telefónicos',
        'description': '''📱 ANÁLISIS DE REGISTROS DE LLAMADAS

Contexto: Se han obtenido los registros de llamadas de la esposa del prófugo.
Los movimientos de antenas podrían permitir identificar su domicilio y recorridos regulares.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Analiza los patrones de conexión y determina:
¿En qué barrio se encuentra el domicilio de la esposa del prófugo?

Formato de respuesta: `FLAG{BARRIO}` o `FLAG{BARRIO_BARRIO}`.

💡 Pista: Las conexiones nocturnas suelen indicar el lugar de residencia.
''',
        'flag': 'FLAG{CABALLITO}',
        'available_date': START_DATE + timedelta(days=1),
        'material_link': 'https://ejemplo.com/desafio2.xlsx'
    },
    3: {
        'title': '🚗 Desafío 3 - Cámaras de Tránsito',
        'description': '''🎥 ANÁLISIS DE MOVIMIENTOS VEHICULARES

Contexto: Un vehículo de interés repite siempre los mismos recorridos,
excepto en fechas específicas cuando se desvía de su ruta tradicional.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Identifica el patrón anómalo y determina:
¿Cuál es la calle principal donde el vehículo se desvía de su ruta habitual?

Formato de respuesta: `FLAG{CALLE}` o `FLAG{CALLE_CALLE}`.

💡 Pista: Busca cambios en el patrón regular de movimiento.
''',
        'flag': 'FLAG{AV_ÁLVAREZ_THOMAS}',
        'available_date': START_DATE + timedelta(days=2),
        'material_link': 'https://ejemplo.com/desafio3.xlsx'
    },
    4: {
        'title': '📸 Desafío 4 - Redes Sociales',
        'description': '''📱 ANÁLISIS DE INSTAGRAM

Contexto: Se monitorea el perfil de Instagram del hermano del prófugo.
Sus publicaciones contienen múltiples referencias a su barrio de residencia.

Material disponible: Ver perfil desde el botón de abajo

Tu misión: Analiza las publicaciones y ubicaciones para determinar:
¿En qué barrio reside el hermano del prófugo?

Formato de respuesta: `FLAG{BARRIO}` o `FLAG{BARRIO_BARRIO}`

💡 Pista: Los fondos de las fotos y los hashtags pueden revelar la ubicación.
''',
        'flag': 'FLAG{URQUIZA}',
        'available_date': START_DATE + timedelta(days=3),
        'material_link': 'https://www.instagram.com/gian.francomh/'
    },
    5: {
        'title': '🔗 Desafío 5 - La Conexión Final',
        'description': '''🎯 INTEGRACIÓN DE FUENTES

Contexto: Los análisis previos han revelado conexiones entre los distintos actores.
Nuevos requerimientos judiciales proporcionaron información adicional crucial.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Integra toda la información y determina:
¿Cuál es el nombre del depósito utilizado por los investigados?

Formato de respuesta: `FLAG{DEPOSITO}` o `FLAG{DEPOSITO_DEPOSITO}`

💡 Pista: El depósito aparece mencionado en múltiples fuentes.
''',
        'flag': 'FLAG{MAHALO_HERMANOS}',
        'available_date': START_DATE + timedelta(days=4),
        'material_link': 'https://ejemplo.com/desafio5.xlsx'
    }
}

# Funciones del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Inicio del bot"""
    user = update.effective_user
    user_name = sanitize_text(user.first_name)
    
    await update.message.reply_text(
        f"🔍 ¡Bienvenido al DIFFYE-CTF Bot! 🔍\n\n"
        f"Hola {user_name}, soy el bot oficial del CTF de Búsqueda y Captura de Fugitivos.\n\n"
        f"📅 Evento: {START_DATE.strftime('%d/%m')} al {END_DATE.strftime('%d/%m/%Y')}\n"
        f"🎯 Objetivo: Resolver 5 desafíos de análisis de información\n\n"
        f"Para comenzar, necesito registrarte en el sistema.\n"
        f"Por favor, usa el comando /register para inscribirte."
        f"Si ya estás inscrito, elige el desafío disponible para hoy con el comando /challenges."
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /register - Registro de usuario"""
    user = update.effective_user
    
    # Registrar en la base de datos
    success = await Database.register_user(
        user.id,
        user.username or f"user_{user.id}",
        user.full_name
    )
    
    if success:
        keyboard = [
            [InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")],
            [InlineKeyboardButton("📊 Mi Progreso", callback_data="my_progress")],
            [InlineKeyboardButton("🏆 Ranking", callback_data="leaderboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ ¡Registro exitoso!\n\n"
            f"Ya estás inscrito en el CTF. Aquí tienes las opciones disponibles:\n\n"
            f"• 📋 /challenges • Ver los desafíos disponibles\n"
            f"• 🚩 /submit • Enviar una flag\n"
            f"• 📊 /progress • Ver tu progreso\n"
            f"• 🏆 /leaderboard • Ver el ranking\n"
            f"• ❓ /help • Ayuda y comandos\n\n"
            f"¡Buena suerte en la investigación! 🕵️",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "⚠️ Hubo un problema con el registro. Por favor, contacta a un administrador."
        )

async def view_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los desafíos disponibles"""
    query = update.callback_query if update.callback_query else None
    message = query.message if query else update.message
    user_id = update.effective_user.id
    
    # Obtener progreso del usuario
    progress = await Database.get_user_progress(user_id)
    completed = progress['completed_challenges'] if progress else []
    
    current_date = datetime.now(TZ)
    
    text = "📋 DESAFÍOS DISPONIBLES\n" + "="*30 + "\n\n"
    
    for challenge_id, challenge in CHALLENGES.items():
        # Verificar disponibilidad
        is_available = current_date >= challenge['available_date']
        is_completed = challenge_id in completed
        
        # Determinar el estado
        if is_completed:
            status = "✅ Completado"
            emoji = "✅"
        elif not is_available:
            unlock_date = challenge['available_date'].strftime('%d/%m %H:%M')
            status = f"🔒 Disponible: {unlock_date}"
            emoji = "🔒"
        else:
            status = "🔓 Disponible"
            emoji = "🔓"
        
        text += f"{emoji} {challenge['title']}\n"
        text += f"   Estado: {status}\n\n"
    
    keyboard = []
    
    # Agregar botones para desafíos disponibles
    for challenge_id, challenge in CHALLENGES.items():
        is_available = current_date >= challenge['available_date']
        is_completed = challenge_id in completed
        
        if is_available and not is_completed:
            keyboard.append([
                InlineKeyboardButton(
                    f"🎯 Desafío {challenge_id}", 
                    callback_data=f"challenge_{challenge_id}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Menú Principal", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup
        )
    else:
        await message.reply_text(
            text=text,
            reply_markup=reply_markup
        )

async def show_challenge_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el detalle de un desafío específico"""
    query = update.callback_query
    challenge_id = int(query.data.split('_')[1])
    
    challenge = CHALLENGES[challenge_id]
    
    keyboard = [
        [InlineKeyboardButton("🚩 Enviar Flag", callback_data=f"submit_{challenge_id}")],
        [InlineKeyboardButton("🔙 Ver Desafíos", callback_data="view_challenges")]
    ]
    
    if challenge['material_link']:
        keyboard.insert(1, [InlineKeyboardButton("📥 Descargar Material", url=challenge['material_link'])])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.answer()
    await query.edit_message_text(
        text=challenge['description'],
        reply_markup=reply_markup
    )

async def start_submit_with_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de envío de flag desde un callback con ID"""
    query = update.callback_query
    challenge_id = int(query.data.split('_')[1])
    
    context.user_data['submitting_challenge'] = challenge_id
    
    await query.answer()
    await query.edit_message_text(
        f"🚩 Enviar Flag - {CHALLENGES[challenge_id]['title']}\n\n"
        f"Por favor, envía tu flag en el siguiente formato:\n"
        f"`FLAG{{PALABRA}}`\n\n"
        f"Ejemplo: `FLAG{{EJEMPLO}}`\n\n"
        f"Envía /cancel para cancelar."
    )
    
    return WAITING_FLAG

async def start_submit_from_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de envío de flag desde el comando /submit"""
    current_date = datetime.now(TZ)
    
    keyboard = []
    text = "🚩 ENVIAR FLAG\n\nSelecciona el desafío al que quieres enviar una flag:\n\n"
    
    for challenge_id, challenge in CHALLENGES.items():
        is_available = current_date >= challenge['available_date']
        if is_available:
            keyboard.append([
                InlineKeyboardButton(
                    f"🎯 Desafío {challenge_id}", 
                    callback_data=f"submit_{challenge_id}"
                )
            ])
    
    if not keyboard:
        text = "No hay desafíos disponibles para enviar flags en este momento."
    else:
        keyboard.append([InlineKeyboardButton("🔙 Menú Principal", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=text,
        reply_markup=reply_markup
    )

async def process_flag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la flag enviada"""
    user_id = update.effective_user.id
    flag = update.message.text.strip()
    challenge_id = context.user_data.get('submitting_challenge')
    
    if challenge_id is None:
        await update.message.reply_text(
            "⚠️ Sesión expirada. Por favor, selecciona un desafío para enviar la flag.\n"
            "Puedes hacerlo con el comando /submit."
        )
        return ConversationHandler.END
    
    # Verificar la flag
    result = await Database.check_flag(user_id, challenge_id, flag)
    
    keyboard = [[InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if result == 'correct':
        await update.message.reply_text(
            f"✅ ¡FLAG CORRECTA!\n\n"
            f"¡Excelente trabajo! Has completado el {CHALLENGES[challenge_id]['title']}.\n\n"
            f"🎯 Continúa con el siguiente desafío.",
            reply_markup=reply_markup
        )
    elif result == 'already_completed':
        await update.message.reply_text(
            f"ℹ️ Ya has completado este desafío anteriormente.",
            reply_markup=reply_markup
        )
    elif result == 'incorrect':
        await update.message.reply_text(
            f"❌ FLAG INCORRECTA\n\n"
            f"La flag enviada no es correcta. Revisa el desafío e intenta nuevamente.\n\n"
            f"💡 Recuerda verificar el formato: `FLAG{{PALABRA}}`",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "⚠️ Hubo un error al procesar tu flag. Por favor, intenta nuevamente.",
            reply_markup=reply_markup
        )
    
    context.user_data.pop('submitting_challenge', None)
    return ConversationHandler.END

async def my_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el progreso del usuario"""
    query = update.callback_query if update.callback_query else None
    message = query.message if query else update.message
    user_id = update.effective_user.id
    
    progress = await Database.get_user_progress(user_id)
    
    if not progress or not progress['stats']:
        text = "📊 MI PROGRESO\n\n⚠️ No estás registrado. Usa /register para inscribirte."
    else:
        stats = progress['stats']
        completed = progress['completed_challenges']
        
        username = sanitize_text(stats['username'])
        last_activity = stats['last_activity'].strftime('%d/%m %H:%M')
        
        text = f"📊 MI PROGRESO\n" + "="*30 + "\n\n"
        text += f"👤 Usuario: {username}\n"
        text += f"✅ Desafíos Completados: {stats['challenges_completed']}/6\n"
        text += f"🎯 Intentos Totales: {stats['total_attempts']}\n"
        text += f"📅 Última Actividad: {last_activity}\n\n"
        
        text += "Desafíos Completados:\n"
        for c_id in completed:
            text += f"• {CHALLENGES[c_id]['title']}\n"
        
        if stats['challenges_completed'] == 6:
            text += "\n🏆 ¡FELICITACIONES! Has completado todos los desafíos."
    
    keyboard = [
        [InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")],
        [InlineKeyboardButton("🏆 Ver Ranking", callback_data="leaderboard")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await message.reply_text(text=text, reply_markup=reply_markup)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el ranking de usuarios"""
    query = update.callback_query if update.callback_query else None
    message = query.message if query else update.message
    
    ranking = await Database.get_leaderboard()
    
    text = "🏆 RANKING TOP 10\n" + "="*30 + "\n\n"
    
    if not ranking:
        text += "Aún no hay usuarios en el ranking.\n"
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, user in enumerate(ranking):
            medal = medals[i] if i < 3 else f"{i+1}."
            username = sanitize_text(user['username'])
            text += f"{medal} {username}\n"
            text += f"   ✅ Desafíos: {user['challenges_completed']}/6\n"
            text += f"   🎯 Intentos: {user['total_attempts']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 Mi Progreso", callback_data="my_progress")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await message.reply_text(text=text, reply_markup=reply_markup)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú principal"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")],
        [InlineKeyboardButton("📊 Mi Progreso", callback_data="my_progress")],
        [InlineKeyboardButton("🏆 Ranking", callback_data="leaderboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.answer()
    await query.edit_message_text(
        "🔍 DIFFYE-CTF Bot\n\n"
        "Selecciona una opción del menú:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Muestra ayuda"""
    help_text = """
❓ AYUDA - DIFFYE-CTF Bot

Comandos disponibles:
• /start • Iniciar el bot
• /register • Registrarse en el CTF
• /challenges • Ver desafíos disponibles
• /submit • Enviar una flag
• /progress • Ver tu progreso
• /leaderboard • Ver el ranking
• /help • Ver esta ayuda

¿Cómo participar?
1. Regístrate con /register
2. Revisa los desafíos con /challenges
3. Descarga y analiza el material
4. Envía las flags con /submit
5. ¡Completa todos los desafíos!

Formato de flags:
Todas las flags siguen el formato: `FLAG{PALABRA}` o `FLAG{PALABRA_PALABRA}`

¡Buena suerte! 🕵️
"""
    await update.message.reply_text(help_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la operación actual"""
    context.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando admin para ver estadísticas"""
    user_id = str(update.effective_user.id)
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ No tienes permisos para usar este comando.")
        return
    
    try:
        stats = await Database.get_admin_stats()
        
        text = "📊 ESTADÍSTICAS ADMINISTRATIVAS\n" + "="*30 + "\n\n"
        text += f"👥 Usuarios Totales: {stats['total_users']}\n"
        text += f"🔥 Activos (24h): {stats['active_users']}\n\n"
        text += "Completados por Desafío:\n"
        
        for stat in stats['challenge_stats']:
            challenge_name = CHALLENGES[stat['challenge_id']]['title']
            text += f"• {challenge_name}: {stat['completions']} usuarios\n"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas admin: {e}")
        await update.message.reply_text("⚠️ Error obteniendo estadísticas.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los errores del bot"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Ha ocurrido un error. Por favor, intenta nuevamente más tarde."
        )

# Funciones de inicialización y cierre
async def post_init_tasks(application: Application):
    """Función de inicialización asíncrona para la base de datos"""
    await db_manager.initialize()
    await Database.init_db()
    logger.info("Base de datos inicializada correctamente")
    
async def post_shutdown_tasks(application: Application):
    """Función para cerrar la conexión de la base de datos"""
    await db_manager.close()
    logger.info("Conexión de la base de datos cerrada")

def main():
    """Función principal"""
    # Crear la aplicación
    application = Application.builder().token(BOT_TOKEN).post_init(post_init_tasks).post_shutdown(post_shutdown_tasks).build()
    
    # Manejador de conversación para envío de flags
    submit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_submit_with_id, pattern=r"^submit_\d+$"),
            CommandHandler('submit', start_submit_from_command)
        ],
        states={
            WAITING_FLAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_flag)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Agregar manejadores
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("challenges", view_challenges))
    application.add_handler(CommandHandler("progress", my_progress))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin_stats", admin_stats))
    
    # Manejadores de callback
    application.add_handler(CallbackQueryHandler(view_challenges, pattern="^view_challenges$"))
    application.add_handler(CallbackQueryHandler(show_challenge_detail, pattern="^challenge_\d+$"))
    application.add_handler(CallbackQueryHandler(my_progress, pattern="^my_progress$"))
    application.add_handler(CallbackQueryHandler(leaderboard, pattern="^leaderboard$"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    
    # Agregar el manejador de conversación
    application.add_handler(submit_handler)
    
    # Manejador de errores
    application.add_error_handler(error_handler)
    
    # Iniciar el bot
    logger.info("Bot iniciado correctamente")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# Agregar al final de bot.py, antes de if __name__ == "__main__":

def start_dummy_server():
    """Servidor HTTP dummy para Render Web Service"""
    port = int(os.getenv('PORT', 10000))
    try:
        handler = http.server.SimpleHTTPRequestHandler
        httpd = socketserver.TCPServer(("", port), handler)
        logger.info(f"Servidor dummy iniciado en puerto {port}")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"Error en servidor dummy: {e}")

def main():
    """Función principal modificada"""
    # Iniciar servidor dummy en hilo separado para Render
    if os.getenv('RENDER'):  # Solo en producción
        server_thread = threading.Thread(target=start_dummy_server)
        server_thread.daemon = True
        server_thread.start()
    
    # Crear la aplicación (tu código existente)
    application = Application.builder().token(BOT_TOKEN).post_init(post_init_tasks).post_shutdown(post_shutdown_tasks).build()
    
    # ... resto de tu código igual ...
    
    # Iniciar el bot
    logger.info("Bot iniciado correctamente")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()