#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database Manager con Pool de Conexiones PostgreSQL
Optimizado para DIFFYE-CTF Bot
"""

import asyncpg
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Tuple, AsyncGenerator
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manejador de base de datos con pool de conexiones"""

    def __init__(self, database_url: str, min_connections: int = 1, max_connections: int = 2):
        self.database_url = database_url
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Inicializa el pool de conexiones asíncrono"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=30,
                statement_cache_size=0,
                server_settings={
                    'application_name': 'diffye_ctf_bot',
                    'timezone': 'America/Argentina/Buenos_Aires'
                }
            )
            logger.info(f"✅ Pool de conexiones asíncrono inicializado: {self.min_connections}-{self.max_connections}")
        except Exception as e:
            logger.error(f"❌ Error inicializando pool asíncrono: {e}")
            raise

    async def close(self):
        """Cierra el pool de conexiones"""
        if self.pool:
            await self.pool.close()
            logger.info("✅ Pool de conexiones asíncrono cerrado")
            self.pool = None

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Context manager para obtener una conexión del pool"""
        if not self.pool:
            raise RuntimeError("Pool no inicializado. Llama a initialize() primero.")
        
        connection = await self.pool.acquire()
        try:
            yield connection
        finally:
            await self.pool.release(connection)

    async def execute_query(self, query: str, *args) -> List[Dict]:
        """Ejecuta una consulta SELECT y retorna los resultados"""
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error ejecutando consulta: {e}")
            raise

    async def execute_one(self, query: str, *args) -> Optional[Dict]:
        """Ejecuta una consulta SELECT y retorna un solo resultado"""
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error ejecutando consulta: {e}")
            raise

    async def execute_command(self, query: str, *args) -> str:
        """Ejecuta un comando (INSERT, UPDATE, DELETE) y retorna el resultado"""
        try:
            async with self.get_connection() as conn:
                result = await conn.execute(query, *args)
                return result
        except Exception as e:
            logger.error(f"Error ejecutando comando: {e}")
            raise

    async def execute_transaction(self, queries: List[Tuple[str, tuple]]) -> bool:
        """Ejecuta múltiples consultas en una transacción"""
        try:
            async with self.get_connection() as conn:
                async with conn.transaction():
                    for query, args in queries:
                        await conn.execute(query, *args)
                return True
        except Exception as e:
            logger.error(f"Error en transacción: {e}")
            return False

# Instancia global del manejador de base de datos
db_manager = DatabaseManager(
    database_url=os.getenv('DATABASE_URL'),
    min_connections=int(os.getenv('DB_MIN_CONNECTIONS', '1')),
    max_connections=int(os.getenv('DB_MAX_CONNECTIONS', '3'))
)

class Database:
    """Clase de compatibilidad con el código existente"""
    
    @staticmethod
    async def init_db():
        """Inicializa las tablas de la base de datos"""
        queries = [
            # ... (Tus consultas SQL para crear tablas)
            ('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    full_name VARCHAR(255),
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    organization VARCHAR(255)
                )
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)
            ''', ()),
            ('''
                CREATE TABLE IF NOT EXISTS progress (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    challenge_id INTEGER NOT NULL,
                    flag_submitted VARCHAR(255) NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address INET,
                    attempt_number INTEGER DEFAULT 1,
                    UNIQUE(user_id, challenge_id, flag_submitted)
                )
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_progress_user ON progress(user_id)
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_progress_challenge ON progress(challenge_id)
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_progress_correct ON progress(is_correct)
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_progress_date ON progress(submission_date)
            ''', ()),
            ('''
                CREATE TABLE IF NOT EXISTS statistics (
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    challenges_completed INTEGER DEFAULT 0,
                    total_attempts INTEGER DEFAULT 0,
                    correct_attempts INTEGER DEFAULT 0,
                    incorrect_attempts INTEGER DEFAULT 0,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_time_minutes INTEGER DEFAULT 0,
                    average_attempts_per_challenge DECIMAL(5,2) DEFAULT 0,
                    PRIMARY KEY (user_id)
                )
            ''', ()),
            ('''
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    action VARCHAR(100) NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address INET
                )
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_logs(user_id)
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_logs(timestamp)
            ''', ()),
            ('''
                CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_logs(action)
            ''', ())
        ]
        
        success = await db_manager.execute_transaction(queries)
        if success:
            logger.info("Base de datos inicializada correctamente")
        else:
            logger.error("Error inicializando base de datos")
        return success
    
    @staticmethod
    async def register_user(user_id: int, username: str, full_name: str) -> bool:
        """Registra un nuevo usuario"""
        queries = [
            ('''
                INSERT INTO users (user_id, username, full_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE
                SET username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    is_active = TRUE
            ''', (user_id, username, full_name)),
            ('''
                INSERT INTO statistics (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id,))
        ]
        
        return await db_manager.execute_transaction(queries)
    
    @staticmethod
    async def check_flag(user_id: int, challenge_id: int, flag: str) -> str:
        """Verifica una flag enviada por el usuario"""
        try:
            # Verificar si ya completó este desafío
            existing = await db_manager.execute_one('''
                SELECT * FROM progress 
                WHERE user_id = $1 AND challenge_id = $2 AND is_correct = TRUE
            ''', user_id, challenge_id)
            
            if existing:
                return 'already_completed'
            
            # Obtener la flag correcta (esto debería venir de una configuración)
            # Por ahora usamos una lógica simple
            from bot import CHALLENGES
            challenge_flags = CHALLENGES[challenge_id]['flag']

            # Manejar tanto listas como strings
            if isinstance(challenge_flags, list):
                is_correct = flag.upper() in [f.upper() for f in challenge_flags]
            else:
                is_correct = challenge_flags.upper() == flag.upper()
            #is_correct = CHALLENGES[challenge_id]['flag'].upper() == flag.upper()
            
            # Registrar el intento
            await db_manager.execute_command('''
                INSERT INTO progress (user_id, challenge_id, flag_submitted, is_correct)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, challenge_id, flag_submitted) DO NOTHING
            ''', user_id, challenge_id, flag, is_correct)
            
            # Actualizar estadísticas
            if is_correct:
                await db_manager.execute_command('''
                    UPDATE statistics 
                    SET challenges_completed = (
                        SELECT COUNT(DISTINCT challenge_id) 
                        FROM progress 
                        WHERE user_id = $1 AND is_correct = TRUE
                    ),
                    total_attempts = total_attempts + 1,
                    correct_attempts = correct_attempts + 1,
                    last_activity = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                ''', user_id)
            else:
                await db_manager.execute_command('''
                    UPDATE statistics 
                    SET total_attempts = total_attempts + 1,
                        incorrect_attempts = incorrect_attempts + 1,
                        last_activity = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                ''', user_id)
            
            return 'correct' if is_correct else 'incorrect'
            
        except Exception as e:
            logger.error(f"Error verificando flag: {e}")
            return 'error'
    
    @staticmethod
    async def get_user_progress(user_id: int) -> Dict:
        """Obtiene el progreso del usuario"""
        try:
            stats = await db_manager.execute_one('''
                SELECT s.*, u.username, u.full_name
                FROM statistics s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.user_id = $1
            ''', user_id)
            
            completed = await db_manager.execute_query('''
                SELECT DISTINCT challenge_id
                FROM progress
                WHERE user_id = $1 AND is_correct = TRUE
                ORDER BY challenge_id
            ''', user_id)
            
            return {
                'stats': stats,
                'completed_challenges': [row['challenge_id'] for row in completed]
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo progreso: {e}")
            return {'stats': None, 'completed_challenges': []}
    
    @staticmethod
    async def get_leaderboard() -> List[Dict]:
        """Obtiene el ranking de usuarios"""
        try:
            return await db_manager.execute_query('''
                SELECT u.full_name, s.challenges_completed, s.total_attempts,
                        MIN(p.submission_date) as first_completion
                FROM users u
                JOIN statistics s ON u.user_id = s.user_id
                LEFT JOIN progress p ON u.user_id = p.user_id AND p.is_correct = TRUE
                WHERE s.challenges_completed > 0
                GROUP BY u.full_name, s.challenges_completed, s.total_attempts
                ORDER BY s.challenges_completed DESC, first_completion ASC
                LIMIT 10
            ''')
        except Exception as e:
            logger.error(f"Error obteniendo leaderboard: {e}")
            return []
    
    
    @staticmethod
    async def get_admin_stats() -> Dict:
        """Obtiene estadísticas para administradores"""
        try:
            total_users = await db_manager.execute_one(
                "SELECT COUNT(*) as total FROM users WHERE is_active = TRUE"
            )
            
            active_users = await db_manager.execute_one('''
                SELECT COUNT(DISTINCT user_id) as active 
                FROM progress 
                WHERE submission_date > CURRENT_TIMESTAMP - INTERVAL '24 hours'
            ''')
            
            challenge_stats = await db_manager.execute_query('''
                SELECT challenge_id, COUNT(DISTINCT user_id) as completions
                FROM progress
                WHERE is_correct = TRUE
                GROUP BY challenge_id
                ORDER BY challenge_id
            ''')
            
            return {
                'total_users': total_users['total'] if total_users else 0,
                'active_users': active_users['active'] if active_users else 0,
                'challenge_stats': challenge_stats
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas admin: {e}")
            return {'total_users': 0, 'active_users': 0, 'challenge_stats': []}


@staticmethod
async def get_all_users():
    """Obtiene todos los usuarios registrados para mensajes circulares"""
    try:
        query = "SELECT user_id, username, full_name FROM users ORDER BY registration_date"
        result = await db_manager.execute_query(query)
        return result
    except Exception as e:
        logger.error(f"Error obteniendo todos los usuarios: {e}")
        return []# Ejemplo de uso en un script
async def main():
    """Función principal para inicializar y usar el manejador"""
    try:
        await db_manager.initialize()
        
        # Aquí puedes llamar a las funciones que usan la base de datos
        # Por ejemplo:
        # await Database.init_db()
        # await Database.register_user(12345, 'testuser', 'Test User')
        
        logger.info("✅ Pruebas de conexión exitosas y operaciones de ejemplo terminadas.")
    except Exception as e:
        logger.error(f"⚠️ Un error crítico ocurrió: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())