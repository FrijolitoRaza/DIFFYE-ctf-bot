#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de configuración optimizado para DIFFYE-CTF Bot
Incluye configuración de pool de conexiones PostgreSQL
"""

import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from database_manager import db_manager, Database

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def setup_database():
    """Configura la base de datos con optimizaciones"""
    try:
        # Inicializar pool de conexiones
        logger.info("Inicializando pool de conexiones...")
        await db_manager.initialize()
        
        # Crear tablas
        logger.info("Creando tablas de base de datos...")
        success = await Database.init_db()
        
        if success:
            logger.info("✅ Base de datos configurada correctamente")
            return True
        else:
            logger.error("❌ Error configurando base de datos")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error en configuración: {e}")
        return False

async def test_connections():
    """Prueba las conexiones a la base de datos"""
    try:
        logger.info("Probando conexiones...")
        
        # Probar conexión asíncrona
        async with db_manager.get_connection() as conn:
            result = await conn.fetchval("SELECT 1")
            logger.info(f"✅ Conexión asíncrona exitosa. Resultado: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error probando conexiones: {e}")
        return False

async def create_sample_data():
    """Crea datos de ejemplo para testing"""
    try:
        logger.info("Creando datos de ejemplo...")
        
        # Usuario de prueba
        await Database.register_user(123456789, "test_user", "Usuario de Prueba")
        
        # Progreso de prueba
        await db_manager.execute_command('''
            INSERT INTO progress (user_id, challenge_id, flag_submitted, is_correct)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, challenge_id, flag_submitted) DO NOTHING
        ''', 123456789, 0, 'FLAG{INICIO_INVESTIGACION}', True)
        
        logger.info("✅ Datos de ejemplo creados")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creando datos de ejemplo: {e}")
        return False

def check_environment():
    """Verifica las variables de entorno"""
    required_vars = [
        'BOT_TOKEN',
        'DATABASE_URL',
        'ADMIN_IDS'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Variables de entorno faltantes: {', '.join(missing_vars)}")
        logger.info("Crea un archivo .env basado en env.example")
        return False
    
    logger.info("✅ Variables de entorno configuradas")
    return True

def create_directories():
    """Crea directorios necesarios"""
    directories = ['logs', 'data', 'backups']
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"✅ Directorio creado: {directory}")

async def main():
    """Función principal de configuración"""
    logger.info("🚀 Iniciando configuración optimizada de DIFFYE-CTF Bot")
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Verificar entorno
    if not check_environment():
        return False
    
    # Crear directorios
    create_directories()
    
    # Configurar base de datos
    if not await setup_database():
        return False
    
    # Probar conexiones
    if not await test_connections():
        return False
    
    # Crear datos de ejemplo (opcional)
    if os.getenv('CREATE_SAMPLE_DATA', 'false').lower() == 'true':
        await create_sample_data()
    
    logger.info("🎉 Configuración completada exitosamente!")
    logger.info("📋 Próximos pasos:")
    logger.info("   1. Asegúrate de que tu archivo .env esté completo")
    logger.info("   2. Ejecuta: python bot.py")
    logger.info("   3. Prueba el bot con /start")
    
    # Cerrar conexiones
    await db_manager.close()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)