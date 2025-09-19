#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DIFFYE-CTF Bot - Bot de Telegram para CTF de Búsqueda y Captura de Fugitivos
Versión completa con keep-alive para UptimeRobot
"""

import threading
import http.server
import socketserver
import os
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from dotenv import load_dotenv
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

# Variables para keep-alive
RENDER_URL = os.getenv('RENDER_URL')
KEEP_ALIVE_INTERVAL = int(os.getenv('KEEP_ALIVE_INTERVAL', '840'))
PORT = int(os.getenv('PORT', 10000))

# Fechas del evento
START_DATE = datetime.strptime(os.getenv('START_DATE', '2024-09-15'), '%Y-%m-%d').replace(tzinfo=TZ)
END_DATE = datetime.strptime(os.getenv('END_DATE', '2024-09-19'), '%Y-%m-%d').replace(tzinfo=TZ)

# Estados de conversación
WAITING_NAME, WAITING_FLAG = range(2)

# ====================================================================
# ========= EXPLICACIÓN DEL SISTEMA DE KEEP-ALIVE INTEGRADO ==========
# ====================================================================
#
# El código ya tiene dos mecanismos para mantener el bot activo:
#
# 1.  **Servidor Web Externo**:
#     -   Crea un pequeño servidor web que se ejecuta en paralelo a tu bot.
#     -   Plataformas como Render ponen en "suspensión" los servicios que no reciben tráfico.
#     -   Este servidor expone endpoints (como `/health`) que pueden ser monitoreados por
#         servicios externos como **UptimeRobot**.
#     -   Al configurar UptimeRobot para que haga una petición a tu `RENDER_URL/health`
#         cada 5-15 minutos, mantienes el servicio activo y evitas que se suspenda.
#
# 2.  **Servicio de Keep-Alive Interno**:
#     -   Como respaldo, el bot también se hace "auto-pings" a sí mismo cada 14 minutos.
#     -   Utiliza la `RENDER_URL` para hacer una petición a su propio endpoint `/ping`.
#     -   Esto asegura que, incluso si UptimeRobot falla, el bot intentará mantenerse
#         activo por su cuenta.
#
# Para que funcione, solo necesitas configurar la variable de entorno `RENDER_URL`.
#

# ==================== SERVIDOR WEB CON KEEP-ALIVE ====================
class KeepAliveHandler(http.server.SimpleHTTPRequestHandler):
    """Servidor HTTP mejorado para UptimeRobot y monitoreo"""
    
    def log_message(self, format, *args):
        """Suprimir logs del servidor web para evitar spam"""
        return
        
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'status': 'healthy', 'service': 'diffye-ctf-bot', 'timestamp': datetime.now(TZ).isoformat()}
            self.wfile.write(str(response).replace("'", '"').encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html_content = """
            <!DOCTYPE html><html lang="es"><head><title>🔍 DIFFYE-CTF Bot</title></head>
            <body><h1>🔍 DIFFYE-CTF Bot</h1><p>Estado: 🟢 ACTIVO</p>
            <p><small>🤖 Servidor funcionando correctamente.</small></p></body></html>
            """
            self.wfile.write(html_content.encode('utf-8'))

def start_web_server():
    """Inicia el servidor web para keep-alive"""
    try:
        httpd = socketserver.TCPServer(("", PORT), KeepAliveHandler)
        logger.info(f"🌐 Servidor web iniciado en puerto {PORT}")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"❌ Error en servidor web: {e}")

# ==================== KEEP-ALIVE INTERNO ====================
class KeepAliveService:
    """Servicio interno complementario para keep-alive (auto-ping)"""

    def __init__(self):
        self.running = False
        self.session = None

    async def start(self):
        """Inicia el servicio de keep-alive interno"""
        if not RENDER_URL:
            logger.warning("⚠️ RENDER_URL no configurada, keep-alive interno deshabilitado")
            return

        self.running = True
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )

        # Iniciar el loop de ping interno
        asyncio.create_task(self._ping_loop())
        logger.info(f"🔥 Keep-alive interno iniciado - ping cada {KEEP_ALIVE_INTERVAL} segundos")

    async def stop(self):
        """Detiene el servicio de keep-alive"""
        self.running = False
        if self.session:
            await self.session.close()

    async def _ping_loop(self):
        """Loop principal de ping interno (backup)"""
        while self.running:
            try:
                await asyncio.sleep(KEEP_ALIVE_INTERVAL)
                await self._ping_self()
            except Exception as e:
                logger.error(f"❌ Error en keep-alive ping: {e}")
                await asyncio.sleep(120)  # Esperar 2 minutos antes de reintentar

    async def _ping_self(self):
        """Hace ping al propio servicio (backup de UptimeRobot)"""
        if not self.session or not RENDER_URL:
            return

        try:
            ping_url = f"{RENDER_URL.rstrip('/')}/ping"
            async with self.session.get(ping_url) as response:
                if response.status == 200:
                    logger.info(f"✅ Keep-alive ping interno exitoso - {datetime.now(TZ).strftime('%H:%M:%S')}")
                else:
                    logger.warning(f"⚠️ Keep-alive ping falló - Status: {response.status}")

        except asyncio.TimeoutError:
            logger.warning("⚠️ Keep-alive ping - Timeout")
        except Exception as e:
            logger.error(f"❌ Keep-alive ping error: {e}")

# Instancia global del servicio
keep_alive_service = KeepAliveService()

# ==================== MONITOR DE ACTIVIDAD ====================
class ActivityMonitor:
    """Monitor de actividad del bot"""

    def __init__(self):
        self.last_activity = datetime.now(TZ)
        self.message_count = 0
        self.start_time = datetime.now(TZ)

    def record_activity(self):
        """Registra actividad del bot"""
        self.last_activity = datetime.now(TZ)
        self.message_count += 1

        if self.message_count % 25 == 0:
            logger.info(f"📈 Actividad del bot - Mensajes procesados: {self.message_count}")

    def get_status(self):
        """Obtiene el estado de actividad"""
        current_time = datetime.now(TZ)
        inactive_minutes = (current_time - self.last_activity).total_seconds() / 60
        uptime_hours = (current_time - self.start_time).total_seconds() / 3600

        return {
            'last_activity': self.last_activity.isoformat(),
            'message_count': self.message_count,
            'inactive_minutes': round(inactive_minutes, 2),
            'uptime_hours': round(uptime_hours, 2)
        }

activity_monitor = ActivityMonitor()

# ==================== FUNCIONES DEL BOT ====================

def sanitize_text(text):
    """Sanitiza texto de usuario para evitar problemas con caracteres especiales"""
    if not text:
        return "Sin nombre"
    sanitized = str(text).replace('_', ' ').replace('*', ' ').replace('[', '(').replace(']', ')')
    sanitized = sanitized.replace('`', "'").replace('~', '-').replace('>', ' ').replace('<', ' ')
    return sanitized[:50]

def get_challenge_availability_date(challenge_id):
    """Calcula la fecha de disponibilidad de cada desafío"""
    if challenge_id == 0:
        return START_DATE - timedelta(days=1)  # Tutorial disponible antes
    else:
        return START_DATE + timedelta(days=challenge_id - 1)

def is_challenge_available(challenge_id):
    """Verifica si un desafío está disponible en la fecha actual"""
    current_time = datetime.now(TZ)
    challenge_date = get_challenge_availability_date(challenge_id)
    return current_time >= challenge_date

def get_time_until_unlock(challenge_id):
    """Obtiene el tiempo restante hasta que se desbloquee un desafío"""
    current_time = datetime.now(TZ)
    challenge_date = get_challenge_availability_date(challenge_id)
    
    if current_time >= challenge_date:
        return None
    
    time_diff = challenge_date - current_time
    
    if time_diff.days > 0:
        return f"{time_diff.days} día(s)"
    elif time_diff.seconds > 3600:
        hours = time_diff.seconds // 3600
        return f"{hours} hora(s)"
    elif time_diff.seconds > 60:
        minutes = time_diff.seconds // 60
        return f"{minutes} minuto(s)"
    else:
        return "menos de 1 minuto"

def track_activity(func):
    """Decorator para registrar actividad del bot"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        activity_monitor.record_activity()
        return await func(update, context)
    return wrapper

# ==================== DESAFÍOS (MODIFICADO) ====================
CHALLENGES = {
    0: {
        'title': '🔍 Desafío Tutorial',
        'description': '''📱 DESAFÍO DE EJEMPLO

La División INVESTIGACIÓN FEDERAL DE FUGITIVOS Y EXTRADICIONES es la encargada del dictado del curso: LA INVESTIGACIÓN FEDERAL EN LA BÚSQUEDA Y CAPTURA DE FUGITIVOS.

🧠 Tu misión: Indicar la sigla de la fuerza a la que pertenece esta división.

📦 Envía la flag en el siguiente formato: `FLAG{PALABRA}` o `FLAG{PALABRA_PALABRA}`.

💡 Pista: La fuerza tiene jurisdicción nacional, viste de azul y su nombre completo incluye la palabra "Argentina".

''',
        'flag': ['FLAG{PFA}'],
        'material_link': None
    },
    1: {
        'title': '📸 Desafío 1 - Redes Sociales',
        'description': '''📱 ANÁLISIS DE INSTAGRAM

Contexto: Se monitorea el perfil de Instagram de un joven que reside en la Ciudad de Buenos Aires.
Sus publicaciones contienen múltiples referencias a su barrio de residencia.

Material disponible: Ver perfil desde el botón de abajo

Tu misión: Analiza las publicaciones y ubicaciones para determinar:
¿En qué barrio reside el joven?

Formato de respuesta: `FLAG{BARRIO}` o `FLAG{BARRIO_BARRIO}`

💡 Pista: Los fondos de las fotos y los hashtags pueden revelar la ubicación.
''',
        'flag': ['FLAG{VILLA_URQUIZA}'],
        'material_link': 'https://www.instagram.com/gian.francomh/'
    },
    2: {
        'title': '🚗 Desafío 2 - Cámaras de Tránsito',
        'description': '''🎥 ANÁLISIS DE MOVIMIENTOS VEHICULARES

Contexto: Un vehículo de interés repite siempre los mismos recorridos,
excepto en fechas específicas cuando se desvía de su ruta tradicional.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Identifica el patrón anómalo y determina:
¿Cuál es la calle principal donde el vehículo se desvía de su ruta habitual?

Formato de respuesta: `FLAG{CALLE}` o `FLAG{CALLE_CALLE}`.

💡 Pista: Busca cambios en el patrón regular de movimiento.
''',
        'flag': ['FLAG{AV_ALVAREZ_THOMAS}'],
        'material_link': 'https://docs.google.com/spreadsheets/d/1Vb3RNY0fa3pxY-QToCg1zIo539L0jfCG/edit?usp=drive_link&ouid=100147836674076127083&rtpof=true&sd=true'
    },
    3: {
        'title': '📞 Desafío 3 - Registros Telefónicos',
        'description': '''📱 ANÁLISIS DE REGISTROS DE LLAMADAS

Contexto: Tenemos la tarea de analizar un registro de llamadas. Sabemos que es importante para la causa pero no tenemos más precisiones. 
Los movimientos de antenas podrían permitir identificar su domicilio y recorridos regulares.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Analiza los patrones de conexión y determina:
¿En qué barrio se encuentra el domicilio de la persona investigada?

Formato de respuesta: `FLAG{BARRIO}` o `FLAG{BARRIO_BARRIO}`.

💡 Pista: Las conexiones nocturnas suelen indicar el lugar de residencia.
''',
        'flag': ['FLAG{CABALLITO}'],
        'material_link': 'https://docs.google.com/spreadsheets/d/1iz4hu39zfQT21QBRJudHi7_sHBt8-pCr/edit?usp=drive_link&ouid=100147836674076127083&rtpof=true&sd=true'
    },
    4: {
        'title': '📦 Desafío 4 - Análisis de E-commerce',
        'description': '''🛒 ANÁLISIS DE REGISTROS DE E-COMMERCE

Contexto: Un usuario realiza numerosas compras en un portal de e-commerce.
Varios ítems podrían corresponder a artículos comúnmente vinculados con actividades ilícitas. Debemos analizar en profundidad el registro.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Analiza los registros de compras y determina:
¿Qué actividad ilegal puede inferirse a partir de las compras realizadas?

Formato de respuesta: `FLAG{ACTIVIDAD}` o `FLAG{ACTIVIDAD_ACTIVIDAD}`.

💡 Pista: Presta atención a los patrones de compra y las cantidades de ciertos artículos.
''',
        'flag': ['FLAG{DROGAS}', 'FLAG{DROGA}', 'FLAG{VENTA_DE_ESTUPEFACIENTES}', 'FLAG{ESTUPEFACIENTES}'],
        'material_link': 'https://docs.google.com/spreadsheets/d/17stE1_x1FrUj08-oyAcvbDmYe9zB8C6tX_MyANgRF44/edit?usp=drive_link'
    },
    5: {
        'title': '🔗 Desafío 5 - La Conexión Final',
        'description': '''🎯 INTEGRACIÓN DE FUENTES

Contexto: Los análisis previos han revelado vínculos entre los actores investigados. Nuevos requerimientos judiciales aportaron información clave, incluyendo:
- Registro de llamadas del prófugo.
- Historial de compras de su principal colaborador.
- Imágenes de tránsito vinculadas a un socio del buscado.
- Perfil de Instagram del hermano del requerido, disponible para análisis complementario.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Integra toda la información y determina:
¿Cuál es el nombre del depósito utilizado por los investigados?

Formato de respuesta: `FLAG{DEPOSITO}` o `FLAG{DEPOSITO_DEPOSITO}`

💡 Pista: El depósito aparece mencionado en múltiples fuentes.
''',
        'flag': ['FLAG{MAHALO_HERMANOS}','FLAG{HERMANOS_MAHALO}','FLAG{MAHALO}'],
        'material_link': 'https://docs.google.com/spreadsheets/d/1LRWdPC1SgzmW47BWOnnWM0FmI2opxc4T33J5FxQN78w/edit?usp=drive_link'
    }
}

# ==================== COMANDOS PRINCIPALES ====================
@track_activity
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Muestra el menú principal con botones"""
    user = update.effective_user
    user_name = sanitize_text(user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")],
        [InlineKeyboardButton("📊 Mi Progreso", callback_data="my_progress")],
        [InlineKeyboardButton("🏆 Ranking", callback_data="leaderboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔍 ¡Hola {user_name}! Bienvenido al DIFFYE-CTF Bot 🤖\n\n"
        "Selecciona una opción para comenzar.\n\n"
        "Si es tu primera vez, asegúrate de inscribirte con el comando /register.",
        reply_markup=reply_markup
    )

@track_activity
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /register - Registro de usuario"""
    user = update.effective_user
    
    success = await Database.register_user(
        user.id,
        user.username or f"user_{user.id}",
        user.full_name
    )
    
    if success:
        keyboard = [
            [InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")],
            [InlineKeyboardButton("📊 Mi Progreso", callback_data="my_progress")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "✅ ¡Registro exitoso!\n\nYa puedes empezar a resolver los desafíos. ¡Buena suerte! 🕵️",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "⚠️ Ya estabas registrado. Puedes continuar con los desafíos usando los botones o el comando /challenges."
        )

@track_activity
async def view_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    message = query.message if query else update.message
    user_id = update.effective_user.id
    progress = await Database.get_user_progress(user_id)
    completed = progress['completed_challenges'] if progress else []
    text = "📋 DESAFÍOS DISPONIBLES\n" + "="*30 + "\n\n"
    keyboard = []
    for challenge_id, challenge in CHALLENGES.items():
        is_available = is_challenge_available(challenge_id)
        is_completed = challenge_id in completed
        if is_completed: status = "✅ Completado"
        elif not is_available: status = f"🔒 Disponible el {get_challenge_availability_date(challenge_id).strftime('%d/%m')}"
        else: status = "🔓 Disponible ahora"
        text += f"{'✅' if is_completed else '🔒' if not is_available else '🔓'} {challenge['title']} - {status}\n"
        if is_available and not is_completed:
            keyboard.append([InlineKeyboardButton(f"🎯 Ir al Desafío {challenge_id}", callback_data=f"challenge_{challenge_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Menú Principal", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if query: await query.edit_message_text(text=text, reply_markup=reply_markup)
    else: await message.reply_text(text=text, reply_markup=reply_markup)

@track_activity
async def show_challenge_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await query.edit_message_text(text=challenge['description'], reply_markup=reply_markup)

@track_activity
async def start_submit_with_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    challenge_id = int(query.data.split('_')[1])
    context.user_data['submitting_challenge'] = challenge_id
    await query.edit_message_text(
        f"🚩 Enviar Flag para {CHALLENGES[challenge_id]['title']}.\n"
        f"Formato: `FLAG{{PALABRA}}`\n"
        f"Envía /cancel para cancelar."
    )
    return WAITING_FLAG

@track_activity
async def start_submit_from_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for cid, c in CHALLENGES.items():
        if is_challenge_available(cid):
            keyboard.append([InlineKeyboardButton(f"🎯 {c['title']}", callback_data=f"submit_{cid}")])
    if not keyboard:
        await update.message.reply_text("No hay desafíos disponibles para enviar flags.")
    else:
        await update.message.reply_text("Selecciona el desafío:", reply_markup=InlineKeyboardMarkup(keyboard))

@track_activity
async def process_flag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    flag = update.message.text.strip()
    challenge_id = context.user_data.get('submitting_challenge')
    
    if challenge_id is None:
        await update.message.reply_text("⚠️ Sesión expirada. Usa /submit de nuevo.")
        return ConversationHandler.END
    
    # MODIFICACIÓN: Verificar flag contra lista de opciones válidas
    challenge = CHALLENGES[challenge_id]
    flag_list = challenge['flag'] if isinstance(challenge['flag'], list) else [challenge['flag']]

    is_correct = flag.upper() in [f.upper() for f in flag_list]

    if is_correct:
        result = await Database.check_flag(user_id, challenge_id, flag_list[0])
        
        keyboard = [[InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if result == 'correct':
            # MODIFICACIÓN: Verificar si completó todos los desafíos (6to desafío)
            if challenge_id == 5:  # Desafío 5 es el último (índice 5)
                # Verificar si ahora tiene todos los desafíos completados
                progress = await Database.get_user_progress(user_id)
                if progress and len(progress['completed_challenges']) == 6:
                    # Enviar mensaje especial y foto
                    congratulations_text = (
                        f"✅ ¡FLAG CORRECTA! Has completado {CHALLENGES[challenge_id]['title']}.\n\n"
                        "🎉 ¡Bien hecho, investigador 🕵️! Tu análisis ha permitido lograr la detención del fugitivo. 🎉"
                    )
                    
                    # Primero enviar el texto
                    await update.message.reply_text(congratulations_text, reply_markup=reply_markup)
                                        
                    # Luego intentar enviar la imagen desde Google Drive
                    try:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo="https://drive.google.com/uc?export=download&id=1NKbaR4tDGRTb25kpwH6DxlL37aAV9tot",
                            caption="🚔 FUGITIVO CAPTURADO 🚔"
                        )
                    except Exception as e:
                        logger.error(f"Error enviando imagen desde Drive: {e}")
                        # Si falla el envío, mostrar mensaje alternativo
                        await update.message.reply_text(
                            "🚔 FUGITIVO CAPTURADO 🚔\n"
                            "(No se pudo cargar la imagen desde Drive)"
                        )
                else:
                    await update.message.reply_text(
                        f"✅ ¡FLAG CORRECTA! Has completado {CHALLENGES[challenge_id]['title']}.",
                        reply_markup=reply_markup
                    )
            else:
                await update.message.reply_text(
                    f"✅ ¡FLAG CORRECTA! Has completado {CHALLENGES[challenge_id]['title']}.",
                    reply_markup=reply_markup
                )
        elif result == 'already_completed':
            await update.message.reply_text("ℹ️ Ya has completado este desafío.", reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ FLAG INCORRECTA. Intenta de nuevo.", reply_markup=reply_markup)
    else:
        # Registrar intento fallido usando check_flag que ya maneja los intentos
        await Database.check_flag(user_id, challenge_id, flag)
        keyboard = [[InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ FLAG INCORRECTA. Intenta de nuevo.", reply_markup=reply_markup)
    
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
    """Muestra el ranking de usuarios - Ordenado por desafíos completados y menor cantidad de intentos"""
    query = update.callback_query if update.callback_query else None
    message = query.message if query else update.message
    
    ranking = await Database.get_leaderboard()
    
    # MODIFICACIÓN: Ordenar por desafíos completados (desc) y luego por intentos (asc)
    if ranking:
        ranking.sort(key=lambda x: (-x['challenges_completed'], x['total_attempts']))
    
    text = "🏆 RANKING TOP 10\n" + "="*30 + "\n\n"
    
    if not ranking:
        text += "Aún no hay usuarios en el ranking.\n"
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, user in enumerate(ranking[:10]):  # Limitar a top 10
            medal = medals[i] if i < 3 else f"{i+1}."
            full_name = sanitize_text(user['full_name']) 
            text += f"{medal} {full_name}\n"  
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

• /admin_stats • Ver estadísticas (solo admins)
• /broadcast • Enviar mensaje circular (solo admins)

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
    """Comando admin para ver estadísticas MODIFICADO"""
    user_id = str(update.effective_user.id)
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ No tienes permisos para usar este comando.")
        return
    
    try:
        stats = await Database.get_admin_stats()
        
        text = "📊 ESTADÍSTICAS ADMINISTRATIVAS\n" + "="*40 + "\n\n"
        text += f"👥 Usuarios Totales: {stats['total_users']}\n"
        text += f"🔥 Activos (24h): {stats['active_users']}\n\n"
        
        text += "📈 COMPLETADOS POR DESAFÍO:\n" + "-"*30 + "\n"
        
        # MODIFICACIÓN: Ordenar estadísticas por ID de desafío
        challenge_stats = sorted(stats['challenge_stats'], key=lambda x: x['challenge_id'])
        
        for stat in challenge_stats:
            challenge_name = CHALLENGES[stat['challenge_id']]['title']
            completion_rate = (stat['completions'] / stats['total_users'] * 100) if stats['total_users'] > 0 else 0
            text += f"• {challenge_name}:\n"
            text += f"  Completados: {stat['completions']} usuarios ({completion_rate:.1f}%)\n\n"
        
        # MODIFICACIÓN: Agregar estadísticas adicionales
        if stats.get('completion_stats'):
            text += "🏆 ESTADÍSTICAS DE FINALIZACIÓN:\n" + "-"*30 + "\n"
            text += f"• Usuarios que completaron todos: {stats['completion_stats'].get('all_completed', 0)}\n"
            text += f"• Promedio de desafíos por usuario: {stats['completion_stats'].get('avg_challenges', 0):.1f}\n"
            text += f"• Promedio de intentos por usuario: {stats['completion_stats'].get('avg_attempts', 0):.1f}\n"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas admin: {e}")
        await update.message.reply_text("⚠️ Error obteniendo estadísticas.")


@track_activity
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando admin para enviar mensajes circulares a todos los usuarios"""
    user_id = str(update.effective_user.id)
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ No tienes permisos para usar este comando.")
        return
    
    # Verificar si hay un mensaje para enviar
    if not context.args:
        await update.message.reply_text(
            "📢 ENVÍO DE MENSAJE CIRCULAR\n\n"
            "Uso: `/broadcast Tu mensaje aquí`\n\n"
            "Ejemplo: `/broadcast El sistema estará en mantenimiento el domingo de 2:00 a 4:00 AM`\n\n"
            "⚠️ Este mensaje se enviará a TODOS los usuarios registrados."
        )
        return
    
    # Construir el mensaje
    broadcast_text = " ".join(context.args)
    admin_name = update.effective_user.first_name or "Admin"
    
    # Mensaje formateado
    formatted_message = (
        f"📢 MENSAJE DEL ADMINISTRADOR\n"
        f"{'='*35}\n\n"
        f"{broadcast_text}\n\n"
        f"— {admin_name}\n"
        f"🕐 {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')}"
    )
    
    try:
        # Obtener todos los usuarios registrados
        all_users = await Database.get_all_users()
        
        if not all_users:
            await update.message.reply_text("❌ No hay usuarios registrados para enviar el mensaje.")
            return
        
        # Confirmar antes de enviar
        keyboard = [
            [InlineKeyboardButton("✅ Confirmar Envío", callback_data=f"confirm_broadcast")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_broadcast")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Guardar el mensaje en el contexto para el callback
        context.user_data['broadcast_message'] = formatted_message
        context.user_data['broadcast_users'] = all_users
        
        await update.message.reply_text(
            f"📋 VISTA PREVIA DEL MENSAJE:\n\n{formatted_message}\n\n"
            f"👥 Se enviará a {len(all_users)} usuarios registrados.\n\n"
            "¿Confirmas el envío?",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error preparando broadcast: {e}")
        await update.message.reply_text("❌ Error preparando el mensaje circular.")

@track_activity
async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirma y ejecuta el envío del mensaje circular"""
    query = update.callback_query
    user_id = str(update.effective_user.id)
    
    if user_id not in ADMIN_IDS:
        await query.answer("⛔ No tienes permisos.", show_alert=True)
        return
    
    if query.data == "cancel_broadcast":
        context.user_data.clear()
        await query.edit_message_text("❌ Envío de mensaje cancelado.")
        return
    
    if query.data == "confirm_broadcast":
        message_to_send = context.user_data.get('broadcast_message')
        users_list = context.user_data.get('broadcast_users', [])
        
        if not message_to_send or not users_list:
            await query.edit_message_text("❌ Error: Datos del mensaje no encontrados.")
            return
        
        await query.edit_message_text("📤 Enviando mensaje circular... Por favor espera.")
        
        success_count = 0
        failed_count = 0
        
        # Enviar mensaje a cada usuario
        for user in users_list:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=message_to_send
                )
                success_count += 1
                # Pequeña pausa para evitar límites de rate
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed_count += 1
                logger.warning(f"No se pudo enviar mensaje a usuario {user['user_id']}: {e}")
        
        # Reporte final
        report = (
            f"📊 REPORTE DE ENVÍO COMPLETADO\n\n"
            f"✅ Enviados exitosamente: {success_count}\n"
            f"❌ Fallos: {failed_count}\n"
            f"👥 Total intentos: {len(users_list)}\n\n"
            f"El mensaje ha sido distribuido."
        )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=report
        )
        
        # Limpiar datos del contexto
        context.user_data.clear()


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los errores del bot"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Ha ocurrido un error. Por favor, intenta nuevamente más tarde."
        )


async def post_init_tasks(application: Application):
    """Función de inicialización asíncrona para la base de datos"""
    await db_manager.initialize()
    await Database.init_db()
    logger.info("Base de datos inicializada correctamente")
    
    # Iniciar el servicio de keep-alive
    await keep_alive_service.start()
    
async def post_shutdown_tasks(application: Application):
    """Función para cerrar la conexión de la base de datos"""
    await keep_alive_service.stop()
    await db_manager.close()
    logger.info("Conexión de la base de datos cerrada")

def main() -> None:
    """Función principal del bot"""

    # Iniciar el servidor web en un hilo separado para el keep-alive
    web_server_thread = threading.Thread(target=start_web_server)
    web_server_thread.daemon = True
    web_server_thread.start()
    
    # Crear la aplicación del bot
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init_tasks)
        .post_shutdown(post_shutdown_tasks)
        .build()
    )
    
    # Manejador de conversación para envío de flags
    submit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_submit_with_id, pattern=r"^submit_\d+$"),
            CommandHandler('submit', start_submit_from_command)
        ],
        states={
            WAITING_FLAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_flag)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )
    
    # Asegurar que TODOS los manejadores estén registrados
    
    # 1. Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("challenges", view_challenges))
    application.add_handler(CommandHandler("progress", my_progress))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin_stats", admin_stats))
    # Comando de broadcast para admins
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    
    # 2. Botones (CallbackQueryHandlers)
    application.add_handler(CallbackQueryHandler(view_challenges, pattern="^view_challenges$"))
    application.add_handler(CallbackQueryHandler(show_challenge_detail, pattern="^challenge_\d+$"))
    application.add_handler(CallbackQueryHandler(my_progress, pattern="^my_progress$"))
    application.add_handler(CallbackQueryHandler(leaderboard, pattern="^leaderboard$"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    # Callback para confirmación de broadcast
    application.add_handler(CallbackQueryHandler(confirm_broadcast, pattern="^(confirm_broadcast|cancel_broadcast)$"))
    
    # 3. Conversación de /submit
    application.add_handler(submit_handler)
    
    # 4. Manejador de errores
    application.add_error_handler(error_handler)
    
    # Iniciar el bot
    logger.info("🤖 Iniciando el bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()