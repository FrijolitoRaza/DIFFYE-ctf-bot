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
RENDER_URL = os.getenv('RENDER_URL')  # https://tu-app.onrender.com
KEEP_ALIVE_INTERVAL = int(os.getenv('KEEP_ALIVE_INTERVAL', '840'))  # 14 minutos
PORT = int(os.getenv('PORT', 10000))

# Fechas del evento
START_DATE = datetime.strptime(os.getenv('START_DATE', '2024-09-15'), '%Y-%m-%d').replace(tzinfo=TZ)
END_DATE = datetime.strptime(os.getenv('END_DATE', '2024-09-19'), '%Y-%m-%d').replace(tzinfo=TZ)

# Estados de conversación
WAITING_NAME, WAITING_FLAG = range(2)

# ==================== SERVIDOR WEB CON KEEP-ALIVE ====================
class KeepAliveHandler(http.server.SimpleHTTPRequestHandler):
    """Servidor HTTP mejorado para UptimeRobot y monitoreo"""
    
    def log_message(self, format, *args):
        """Suprimir logs del servidor web para evitar spam"""
        return
        
    def do_GET(self):
        if self.path == '/health':
            # Endpoint principal para UptimeRobot
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                'status': 'healthy',
                'service': 'diffye-ctf-bot',
                'timestamp': datetime.now(TZ).isoformat(),
                'uptime': 'running',
                'challenges_available': sum(1 for i in range(6) if is_challenge_available(i)),
                'last_activity': activity_monitor.last_activity.isoformat() if activity_monitor.last_activity else None
            }
            self.wfile.write(str(response).replace("'", '"').encode())
            
        elif self.path == '/ping':
            # Endpoint simple para ping/pong
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'pong')
            
        elif self.path == '/status':
            # Endpoint detallado de estado
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            activity_status = activity_monitor.get_status()
            response = {
                'bot_status': 'active',
                'timestamp': datetime.now(TZ).isoformat(),
                'activity': activity_status,
                'event_dates': {
                    'start': START_DATE.isoformat(),
                    'end': END_DATE.isoformat(),
                    'current': datetime.now(TZ).isoformat()
                }
            }
            self.wfile.write(str(response).replace("'", '"').encode())
            
        else:
            # Página principal con auto-refresh
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            current_time = datetime.now(TZ)
            available_challenges = sum(1 for i in range(6) if is_challenge_available(i))
            activity_status = activity_monitor.get_status()
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>🔍 DIFFYE-CTF Bot</title>
                <meta http-equiv="refresh" content="30">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .status {{ color: green; font-weight: bold; }}
                    .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                    .endpoint {{ background: #f3e5f5; padding: 10px; margin: 5px 0; border-radius: 3px; font-family: monospace; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🔍 DIFFYE-CTF Bot</h1>
                    <p>Estado: <span class="status">🟢 ACTIVO</span></p>
                    
                    <div class="info">
                        <h3>📊 Información del Sistema</h3>
                        <p><strong>Última actualización:</strong> {current_time.strftime('%d/%m/%Y %H:%M:%S %Z')}</p>
                        <p><strong>Desafíos disponibles:</strong> {available_challenges}/6</p>
                        <p><strong>Mensajes procesados:</strong> {activity_status['message_count']}</p>
                        <p><strong>Última actividad:</strong> {activity_status['inactive_minutes']:.1f} min atrás</p>
                        <p><strong>Evento:</strong> {START_DATE.strftime('%d/%m')} al {END_DATE.strftime('%d/%m/%Y')}</p>
                    </div>
                    
                    <h3>🔗 Endpoints Disponibles</h3>
                    <div class="endpoint">/health - Health check para UptimeRobot</div>
                    <div class="endpoint">/ping - Ping simple</div>
                    <div class="endpoint">/status - Estado detallado</div>
                    
                    <p><small>🤖 Servidor funcionando correctamente - Auto-refresh cada 30 segundos</small></p>
                </div>
                
                <script>
                    // Auto-refresh cada 30 segundos
                    setTimeout(function() {{ 
                        location.reload(); 
                    }}, 30000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode('utf-8'))

def start_web_server():
    """Inicia el servidor web para keep-alive"""
    try:
        httpd = socketserver.TCPServer(("", PORT), KeepAliveHandler)
        logger.info(f"🌐 Servidor web iniciado en puerto {PORT}")
        logger.info(f"📡 Endpoints para UptimeRobot:")
        logger.info(f"   - {RENDER_URL}/health (recomendado)")
        logger.info(f"   - {RENDER_URL}/ping")
        logger.info(f"   - {RENDER_URL}/status")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"❌ Error en servidor web: {e}")

# ==================== KEEP-ALIVE INTERNO ====================
class KeepAliveService:
    """Servicio interno complementario para keep-alive"""
    
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
        logger.info(f"🔄 Keep-alive interno iniciado - ping cada {KEEP_ALIVE_INTERVAL} segundos")
        
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
        
        # Log cada 25 mensajes para no llenar los logs
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

# Función auxiliar para sanitizar texto
def sanitize_text(text):
    """Sanitiza texto de usuario para evitar problemas con caracteres especiales"""
    if not text:
        return "Sin nombre"
    sanitized = str(text).replace('_', ' ').replace('*', ' ').replace('[', '(').replace(']', ')')
    sanitized = sanitized.replace('`', "'").replace('~', '-').replace('>', ' ').replace('<', ' ')
    return sanitized[:50]

# Funciones de fechas y disponibilidad
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

# Decorator para registrar actividad
def track_activity(func):
    """Decorator para registrar actividad del bot"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        activity_monitor.record_activity()
        return await func(update, context)
    return wrapper

# ==================== DESAFÍOS ====================
CHALLENGES = {
    0: {
        'title': '🔍 Desafío Tutorial',
        'description': '''📱 DESAFÍO DE EJEMPLO

La División INVESTIGACIÓN FEDERAL DE FUGITIVOS Y EXTRADICIONES es la escargada del dictado del curso: LA INVESTIGACIÓN FEDERAL EN LA BÚSQUEDA Y CAPTURA DE FUGITIVOS.

🧠 Tu misión: Indicar la sigla de la fuerza a la que pertenece esta división.

📦 Envía la flag en el siguiente formato: `FLAG{PALABRA}` o `FLAG{PALABRA_PALABRA}`.

💡 Pista: La fuerza tiene jurisdicción nacional, viste de azul y su nombre completo incluye la palabra "Argentina".

''',
        'flag': 'FLAG{PFA}',
        'material_link': None
    },
    1: {
        'title': '📸 Desafío 1 - Redes Sociales',
        'description': '''📱 ANÁLISIS DE INSTAGRAM

Contexto: Se monitorea el perfil de Instagram de un joven que reside en la Ciudad de Buenos Aires.
Sus publicaciones contienen múltiples referencias a su barrio de residencia.

Material disponible: Ver perfil desde el botón de abajo

Tu misión: Analiza las publicaciones y ubicaciones para determinar:
¿En qué barrio reside el jovén?

Formato de respuesta: `FLAG{BARRIO}` o `FLAG{BARRIO_BARRIO}`

💡 Pista: Los fondos de las fotos y los hashtags pueden revelar la ubicación.
''',
        'flag': 'FLAG{VILLA_URQUIZA}',
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
        'flag': 'FLAG{AV_ÁLVAREZ_THOMAS}',
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
        'flag': 'FLAG{CABALLITO}',
        'material_link': 'https://docs.google.com/spreadsheets/d/1iz4hu39zfQT21QBRJudHi7_sHBt8-pCr/edit?usp=drive_link&ouid=100147836674076127083&rtpof=true&sd=true'
    },
    4: {
        'title': '🔦 Desafío 4 - Análisis de E-commerce',
        'description': '''🛒 ANÁLISIS DE REGISTROS DE E-COMMERCE

Contexto: Un usuario realiza numerosas compras en un portal de e-commerce.
Varios ítems podrían corresponder a artículos comúnmente vinculados con actividades ilícitas. Debemos analizar en profundidad el registro.

Material disponible: Descargar archivo Excel desde el botón de abajo

Tu misión: Analiza los registros de compras y determina:
¿Qué actividad ilegal puede inferirse a partir de las compras realizadas?

Formato de respuesta: `FLAG{ACTIVIDAD}` o `FLAG{ACTIVIDAD_ACTIVIDAD}`.

💡 Pista: Presta atención a los patrones de compra y las cantidades de ciertos artículos.
''',
        'flag': 'FLAG{DROGAS}',
        'material_link': 'https://docs.google.com/spreadsheets/d/17stE1_x1FrUj08-oyAcvbDmYe9zB8C6tX_MyANgRF44/edit?usp=drive_link'
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
        'material_link': 'https://docs.google.com/spreadsheets/d/1LRWdPC1SgzmW47BWOnnWM0FmI2opxc4T33J5FxQN78w/edit?usp=drive_link'
    }
}

# ==================== COMANDOS PRINCIPALES ====================

@track_activity
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Inicio del bot"""
    user = update.effective_user
    user_name = sanitize_text(user.first_name)
    
    current_time = datetime.now(TZ)
    available_challenges = sum(1 for i in range(6) if is_challenge_available(i))
    
    await update.message.reply_text(
        f"🔍 ¡Bienvenido al DIFFYE-CTF Bot! 🔍\n\n"
        f"Hola {user_name}, soy el bot oficial del CTF de Búsqueda y Captura de Fugitivos.\n\n"
        f"📅 Evento: {START_DATE.strftime('%d/%m')} al {END_DATE.strftime('%d/%m/%Y')}\n"
        f"🎯 Objetivo: Resolver 6 desafíos de análisis de información\n"
        f"📊 Desafíos disponibles: {available_challenges}/6\n\n"
        f"Los desafíos se habilitan día a día durante el evento.\n\n"
        f"Para comenzar, necesito registrarte en el sistema.\n"
        f"Por favor, usa el comando /register para inscribirte.\n"
        f"Si ya estás inscrito, elige el desafío disponible para hoy con el comando /challenges."
    )

@track_activity
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
        available_count = sum(1 for i in range(6) if is_challenge_available(i))
        
        keyboard = [
            [InlineKeyboardButton("📋 Ver Desafíos", callback_data="view_challenges")],
            [InlineKeyboardButton("📊 Mi Progreso", callback_data="my_progress")],
            [InlineKeyboardButton("🏆 Ranking", callback_data="leaderboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ ¡Registro exitoso!\n\n"
            f"Ya estás inscrito en el CTF. Aquí tienes las opciones disponibles:\n\n"
            f"• 📋 /challenges • Ver los desafíos disponibles ({available_count}/6)\n"
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

@track_activity
async def view_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los desafíos disponibles"""
    query = update.callback_query if update.callback_query else None
    message = query.message if query else update.message
    user_id = update.effective_user.id
    
    # Obtener progreso del usuario
    progress = await Database.get_user_progress(user_id)
    completed = progress['completed_challenges'] if progress else []
    
    current_time = datetime.now(TZ)
    
    text = "📋 DESAFÍOS DISPONIBLES\n" + "="*30 + "\n\n"
    text += f"📅 Fecha actual: {current_time.strftime('%d/%m/%Y %H:%M')}\n\n"
    
    keyboard = []
    
    for challenge_id, challenge in CHALLENGES.items():
        # Verificar disponibilidad
        is_available = is_challenge_available(challenge_id)
        is_completed = challenge_id in completed
        availability_date = get_challenge_availability_date(challenge_id)
        
        # Determinar el estado
        if is_completed:
            status = "✅ Completado"
            emoji = "✅"
        elif not is_available:
            time_left = get_time_until_unlock(challenge_id)
            unlock_date = availability_date.strftime('%d/%m %H:%M')
            status = f"🔒 Disponible: {unlock_date}"
            if time_left:
                status += f" (en {time_left})"
            emoji = "🔒"
        else:
            status = "🔓 Disponible ahora"
            emoji = "🔓"
        
        text += f"{emoji} {challenge['title']}\n"
        text += f"   📅 Fecha: {availability_date.strftime('%d/%m')}\n"
        text += f"   Estado: {status}\n\n"
        
        # Agregar botón si está disponible y no completado
        if is_available and not is_completed:
            keyboard.append([
                InlineKeyboardButton(
                    f"🎯 Desafío {challenge_id}", 
                    callback_data=f"challenge_{challenge_id}"
                )
            ])
    
    # Agregar información adicional sobre el cronograma
    text += "\n📅 CRONOGRAMA DE LIBERACIÓN:\n"
    text += f"• Tutorial: {get_challenge_availability_date(0).strftime('%d/%m')} (Pre-evento)\n"
    for i in range(1, 6):
        date = get_challenge_availability_date(i)
        text += f"• Desafío {i}: {date.strftime('%d/%m')} (Día {i})\n"
    
    keyboard.append([InlineKeyboardButton("🔙 Menú Principal", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await message.reply_text(text=text, reply_markup=reply_markup)

@track_activity
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

@track_activity
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

@track_activity
async def start_submit_from_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de envío de flag desde el comando /submit"""
    current_date = datetime.now(TZ)
    
    keyboard = []
    text = "🚩 ENVIAR FLAG\n\nSelecciona el desafío al que quieres enviar una flag:\n\n"
    
    for challenge_id, challenge in CHALLENGES.items():
        is_available = is_challenge_available(challenge_id)
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
    
    await update.message.reply_text(text=text, reply_markup=reply_markup)

@track_activity
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
    ####################################################################################################################################################################
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
    """Función principal modificada"""
    # Iniciar servidor dummy en hilo separado para Render
    if os.getenv('RENDER') or os.getenv('PORT'):  # Detectar si estamos en Render
        server_thread = threading.Thread(target=start_dummy_server)
        server_thread.daemon = True
        server_thread.start()
        logger.info("Servidor dummy iniciado en hilo separado")
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

if __name__ == "__main__":
    main()