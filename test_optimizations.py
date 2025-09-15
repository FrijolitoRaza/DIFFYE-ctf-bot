#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar las optimizaciones implementadas
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Configurar el event loop para Windows
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Prueba la conexión a la base de datos"""
    try:
        from database_manager import db_manager
        
        logger.info("🔌 Probando conexión a base de datos...")
        
        # Inicializar pool asíncrono
        await db_manager.initialize()
        
        # Probar conexión asíncrona
        async with db_manager.get_connection() as conn:
            result = await conn.fetchval("SELECT 1 as test")
            logger.info(f"✅ Conexión asíncrona: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en conexión a BD: {e}")
        return False

async def test_database_operations():
    """Prueba las operaciones de base de datos"""
    try:
        from database_manager import Database
        
        logger.info("📊 Probando operaciones de base de datos...")
        
        # Crear tablas
        success = await Database.init_db()
        if not success:
            logger.error("❌ Error inicializando BD")
            return False
        
        # Probar registro de usuario
        user_id = 999999999
        success = await Database.register_user(user_id, "test_user", "Usuario de Prueba")
        if not success:
            logger.error("❌ Error registrando usuario")
            return False
        logger.info("✅ Usuario registrado correctamente")
        
        # Probar verificación de flag
        result = await Database.check_flag(user_id, 0, "FLAG{INICIO_INVESTIGACION}")
        if result not in ["correct", "already_completed"]:
            logger.error(f"❌ Error verificando flag: {result}")
            return False
        logger.info(f"✅ Flag verificada correctamente. Resultado: {result}")
        
        # Probar obtención de progreso
        progress = await Database.get_user_progress(user_id)
        if not progress or not progress['stats']:
            logger.error("❌ Error obteniendo progreso")
            return False
        logger.info("✅ Progreso obtenido correctamente")
        
        # Probar leaderboard
        leaderboard = await Database.get_leaderboard()
        logger.info(f"✅ Leaderboard obtenido: {len(leaderboard)} usuarios")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en operaciones de BD: {e}")
        return False

def test_utilities():
    """Prueba las utilidades"""
    try:
        from utils_file import (
            validate_flag_format, sanitize_input, hash_flag,
            calculate_score, format_time_remaining, generate_progress_bar
        )
        
        logger.info("🛠️ Probando utilidades...")
        
        # Probar validación de flags
        valid_flag = "FLAG{TEST}"
        invalid_flag = "invalid_flag"
        
        if not validate_flag_format(valid_flag):
            logger.error("❌ Error validando flag válida")
            return False
        if validate_flag_format(invalid_flag):
            logger.error("❌ Error validando flag inválida")
            return False
        logger.info("✅ Validación de flags funciona correctamente")
        
        # Probar sanitización
        dirty_input = "<script>alert('xss')</script>"
        clean_input = sanitize_input(dirty_input)
        if "<script>" in clean_input:
            logger.error("❌ Error en sanitización")
            return False
        logger.info("✅ Sanitización funciona correctamente")
        
        # Probar hash
        flag_hash = hash_flag(valid_flag)
        if not flag_hash or len(flag_hash) != 64:
            logger.error("❌ Error generando hash")
            return False
        logger.info("✅ Hash generado correctamente")
        
        # Probar cálculo de puntaje
        score = calculate_score(1, 3, 120)
        if score <= 0:
            logger.error("❌ Error calculando puntaje")
            return False
        logger.info(f"✅ Puntaje calculado: {score}")
        
        # Probar formateo de tiempo
        now = datetime.now()
        future = datetime(now.year, now.month, now.day + 1, now.hour, now.minute)
        time_str = format_time_remaining(future, now)
        if not time_str:
            logger.error("❌ Error formateando tiempo")
            return False
        logger.info(f"✅ Tiempo formateado: {time_str}")
        
        # Probar barra de progreso
        progress_bar = generate_progress_bar(3, 5, 10)
        if not progress_bar or "🟩" not in progress_bar:
            logger.error("❌ Error generando barra de progreso")
            return False
        logger.info(f"✅ Barra de progreso: {progress_bar}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en utilidades: {e}")
        return False

async def test_bot_functions():
    """Prueba las funciones del bot"""
    try:
        from bot import CHALLENGES, START_DATE, END_DATE
        
        logger.info("🤖 Probando funciones del bot...")
        
        # Verificar configuración de desafíos
        if not CHALLENGES or len(CHALLENGES) != 6:
            logger.error("❌ Error en configuración de desafíos")
            return False
        logger.info(f"✅ {len(CHALLENGES)} desafíos configurados")
        
        # Verificar fechas
        if START_DATE >= END_DATE:
            logger.error("❌ Error en fechas del evento")
            return False
        logger.info(f"✅ Fechas del evento: {START_DATE.strftime('%d/%m/%Y')} - {END_DATE.strftime('%d/%m/%Y')}")
        
        # Verificar estructura de desafíos
        for challenge_id, challenge in CHALLENGES.items():
            required_fields = ['title', 'description', 'flag', 'available_date']
            for field in required_fields:
                if field not in challenge:
                    logger.error(f"❌ Campo {field} faltante en desafío {challenge_id}")
                    return False
        logger.info("✅ Estructura de desafíos correcta")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en funciones del bot: {e}")
        return False

async def test_performance():
    """Prueba el rendimiento del pool de conexiones"""
    try:
        from database_manager import db_manager
        
        logger.info("⚡ Probando rendimiento del pool...")
        
        # Probar múltiples conexiones concurrentes
        async def test_connection():
            async with db_manager.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                return result
        
        # Ejecutar 10 conexiones concurrentes
        tasks = [test_connection() for _ in range(10)]
        start_time = datetime.now()
        results = await asyncio.gather(*tasks)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        logger.info(f"✅ 10 conexiones concurrentes en {duration:.2f} segundos")
        
        # Verificar que todas las conexiones funcionaron
        if not all(result == 1 for result in results):
            logger.error("❌ Error en conexiones concurrentes")
            return False
        
        logger.info("✅ Pool de conexiones funciona correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en prueba de rendimiento: {e}")
        return False

async def main():
    """Función principal de pruebas"""
    logger.info("🧪 Iniciando pruebas de optimizaciones...")
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Verificar variables de entorno requeridas
    required_vars = ['DATABASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Variables de entorno faltantes: {missing_vars}")
        logger.info("Configura las variables en tu archivo .env")
        return False
    
    tests = [
        ("Conexión a BD", test_database_connection),
        ("Operaciones de BD", test_database_operations),
        ("Utilidades", test_utilities),
        ("Funciones del Bot", test_bot_functions),
        ("Rendimiento", test_performance)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Ejecutando: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                logger.info(f"✅ {test_name}: PASÓ")
                passed += 1
            else:
                logger.error(f"❌ {test_name}: FALLÓ")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
    
    logger.info(f"\n📊 Resultados: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        logger.info("🎉 ¡Todas las optimizaciones funcionan correctamente!")
        return True
    else:
        logger.error("⚠️ Algunas pruebas fallaron. Revisa los logs.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)