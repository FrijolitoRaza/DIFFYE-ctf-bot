# DIFFYE-CTF Bot 🔍

Bot de Telegram para el CTF (Capture The Flag) de Búsqueda y Captura de Fugitivos.

## 📋 Descripción

Este bot gestiona un CTF temático donde los participantes deben resolver 5 desafíos relacionados con análisis de información para simular la captura de un fugitivo. Los desafíos incluyen análisis de:
- Registros de E-commerce
- Registros telefónicos
- Cámaras de tránsito
- Redes sociales
- Integración de fuentes

## 🚀 Características

- **Gestión de usuarios**: Registro y seguimiento de participantes
- **Sistema de desafíos**: 5 desafíos + 1 tutorial, liberados por día
- **Validación de flags**: Sistema robusto de verificación de respuestas
- **Ranking en tiempo real**: Tabla de posiciones actualizada
- **Estadísticas detalladas**: Para usuarios y administradores
- **Base de datos PostgreSQL**: Almacenamiento persistente con **pool de conexiones**
- **Operaciones asíncronas**: Mejor rendimiento y escalabilidad
- **Rate limiting**: Protección contra spam y ataques
- **Logging avanzado**: Sistema de logs rotativo y estructurado
- **Health checks**: Monitoreo automático del sistema
- **Variables de entorno**: Configuración flexible
- **Docker ready**: Despliegue containerizado optimizado

## 📅 Fechas del Evento

Por defecto: **15/09 al 19/09**
(Modificables via variables de entorno para pruebas)

## 🛠️ Requisitos

- Python 3.9+
- PostgreSQL 12+
- Token de Bot de Telegram (obtener de [@BotFather](https://t.me/botfather))
- Docker y Docker Compose (opcional, para despliegue containerizado)

## ⚡ Optimizaciones Implementadas

Este bot ha sido **completamente optimizado** para mejor rendimiento y escalabilidad:

### 🚀 Mejoras de Rendimiento
- **Pool de conexiones PostgreSQL**: Reutilización eficiente de conexiones (5-20 por defecto)
- **Operaciones asíncronas**: Todas las operaciones de BD son no bloqueantes
- **Context managers**: Gestión automática de recursos
- **Health checks**: Monitoreo automático del sistema

### 🛡️ Mejoras de Seguridad
- **Sanitización de input**: Prevención de inyecciones SQL
- **Rate limiting configurable**: Protección contra spam
- **Validación robusta**: Verificación de formato de flags
- **Logging estructurado**: Trazabilidad completa de operaciones

### 📊 Monitoreo Avanzado
- **Métricas detalladas**: Estadísticas en tiempo real
- **Logs rotativos**: Gestión automática de archivos de log
- **Alertas de salud**: Detección temprana de problemas

Para más detalles, consulta [OPTIMIZATIONS.md](OPTIMIZATIONS.md).

## 📦 Instalación

### Opción 1: Instalación Local Optimizada

1. **Clonar el repositorio**
```bash
git clone https://github.com/FrijolitoRaza/DIFFYE-ctf-bot.git
cd diffye-ctf-bot
```

2. **Crear entorno virtual**
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. **Configuración optimizada automática**
```bash
# Copiar archivo de configuración
cp env.example .env

# Editar configuración (opcional)
nano .env

# Ejecutar configuración optimizada
python setup_optimized.py
```

4. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

5. **Configurar PostgreSQL**
```bash
# La configuración se hace automáticamente con setup_optimized.py
# Si necesitas configuración manual:
createdb diffye_ctf
psql -d diffye_ctf -f database_schema.sql
```

6. **Probar optimizaciones (opcional)**
```bash
python test_optimizations.py
```

7. **Ejecutar el bot optimizado**
```bash
python bot.py
```

### Opción 2: Usando Docker

1. **Clonar el repositorio**
```bash
git clone https://github.com/FrijolitoRaza/DIFFYE-ctf-bot.git
cd diffye-ctf-bot
```

2. **Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus valores
```

3. **Construir y ejecutar con Docker Compose**
```bash
# Modo producción
docker-compose up -d

# Modo desarrollo (incluye PgAdmin)
docker-compose --profile dev up -d
```

## 🤖 Comandos del Bot

### Comandos de Usuario
- `/start` - Iniciar el bot
- `/register` - Registrarse en el CTF
- `/challenges` - Ver desafíos disponibles
- `/submit` - Enviar una flag
- `/progress` - Ver tu progreso personal
- `/leaderboard` - Ver el ranking general
- `/help` - Mostrar ayuda

### Comandos de Admin
- `/admin_stats` - Ver estadísticas generales (solo admins)
- `/broadcast` - Enviar mensaje circular (solo admins)

## 🏁 Flags y Desafíos

### Formato de Flags
Todas las flags siguen el formato: `FLAG{RESPUESTA}`

### Desafíos Disponibles

1. **Desafío 0 (Tutorial)**
   - Flag: `FLAG{INICIO_INVESTIGACION}`
   - Disponible: Siempre

2. **Desafío 4**: Redes Sociales
   - Flag: `FLAG{VILLA_URQUIZA}`
   - Disponible: Día 4 (18/09)

3. **Desafío 3**: Cámaras de Tránsito
   - Flag: `FLAG{TRIUNVIRATO_OLAZABAL}`
   - Disponible: Día 3 (17/09)

4. **Desafío 2**: Registros Telefónicos
   - Flag: `FLAG{CABALLITO}`
   - Disponible: Día 2 (16/09)

5. **Desafío 1**: Análisis de E-commerce
   - Flag: `FLAG{VENTA_ESTUPEFACIENTES}`
   - Disponible: Día 1 (15/09)

6. **Desafío 5**: La Conexión Final
   - Flag: `FLAG{MAHALO_HERMANOS}`
   - Disponible: Día 5 (19/09)

## 🔧 Configuración

### Variables de Entorno Principales

```env
# Bot de Telegram
BOT_TOKEN=tu_token_aqui

# Base de datos
DATABASE_URL=postgresql://user:pass@localhost:5432/diffye_ctf

# Administradores (IDs de Telegram)
ADMIN_IDS=123456789,987654321

# Fechas del evento (formato YYYY-MM-DD)
START_DATE=2024-09-15
END_DATE=2024-09-19

# Timezone
TIMEZONE=America/Argentina/Buenos_Aires

# Fechas del evento (formato: YYYY-MM-DD)
START_DATE=2024-09-15
END_DATE=2024-09-19

# Configuración de logging
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# Configuración de rate limiting
RATE_LIMIT_MAX_CALLS=10
RATE_LIMIT_PERIOD=60


# Link de material para desafios
DESAFIO1= 

DESAFIO2=

DESAFIO3=

DESAFIO4=

DESAFIO5=

IMGFINAL=
```

## 📊 Base de Datos

### Esquema Principal

- **users**: Información de usuarios registrados
- **progress**: Intentos y flags enviadas
- **statistics**: Estadísticas agregadas por usuario
- **activity_logs**: Log de todas las actividades
- **sessions**: Sesiones de participación

### Vistas Útiles

- **leaderboard_view**: Ranking con estadísticas
- **challenge_statistics**: Estadísticas por desafío

## 🐳 Docker

### Servicios Incluidos

- **postgres**: Base de datos PostgreSQL
- **bot**: Aplicación del bot
- **pgadmin**: Interfaz web para PostgreSQL (perfil dev)
- **redis**: Cache y rate limiting (perfil production)
- **nginx**: Servidor web para archivos estáticos (perfil production)

### Comandos Docker Útiles

```bash
# Ver logs del bot
docker-compose logs -f bot

# Acceder a la base de datos
docker-compose exec postgres psql -U diffye_user -d diffye_ctf

# Reiniciar el bot
docker-compose restart bot

# Backup de la base de datos
docker-compose exec postgres pg_dump -U diffye_user diffye_ctf > backup.sql
```

## 🔒 Seguridad

### Mejores Prácticas

1. **Nunca commitear el archivo `.env`** con credenciales reales
2. **Usar contraseñas fuertes** para la base de datos
3. **Limitar IDs de admin** solo a usuarios confiables
4. **Configurar HTTPS** para nginx en producción
5. **Realizar backups regulares** de la base de datos
6. **Monitorear logs** para detectar actividad sospechosa

### Rate Limiting

El bot incluye protección contra spam:
- Máximo 10 intentos por desafío por usuario
- Cooldown de 5 minutos entre intentos fallidos múltiples

## 📈 Monitoreo y Estadísticas

### Para Administradores

El comando `/admin_stats` muestra:
- Total de usuarios registrados
- Usuarios activos en las últimas 24h
- Completados por desafío
- Tasa de éxito general

### Logs

Los logs se almacenan en:
- `./logs/` - Logs de aplicación
- PostgreSQL - Logs de actividad en `activity_logs`

## 🧪 Testing

### Modo de Prueba

Para realizar pruebas fuera de las fechas oficiales:

1. Modificar las fechas en `.env`:
```env
START_DATE=2024-01-01
END_DATE=2024-12-31
```

2. Usar el Desafío 0 (Tutorial) que siempre está disponible

### Tests Automatizados

```bash
# Ejecutar tests
pytest tests/

# Con coverage
pytest --cov=. tests/
```

## 📝 Personalización

### Modificar Desafíos

Editar el diccionario `CHALLENGES` en `bot.py`:

```python
CHALLENGES = {
    1: {
        'title': 'Nuevo Desafío',
        'description': 'Descripción...',
        'flag': 'FLAG{RESPUESTA}',
        'available_date': START_DATE,
        'material_link': 'https://...'
    }
}
```

### Agregar Materiales

1. Colocar archivos en `./materials/`
2. Actualizar `material_link` en el desafío correspondiente
3. Si usas nginx, los archivos estarán disponibles en `http://tu-servidor/materials/`

## 🚨 Troubleshooting

### Problemas Comunes

**Bot no responde:**
- Verificar token en `.env`
- Verificar conexión a Internet
- Revisar logs: `docker-compose logs bot`

**Error de base de datos:**
- Verificar credenciales en `DATABASE_URL`
- Verificar que PostgreSQL esté ejecutándose
- Revisar permisos de usuario

**Desafíos no disponibles:**
- Verificar fechas en `.env`
- Verificar timezone configurado
- Verificar fecha/hora del sistema

**Rate limit exceeded:**
- Esperar el tiempo de cooldown
- Verificar configuración en `.env`

## 📚 Estructura del Proyecto

```
diffye-ctf-bot/
├── bot.py                 # Aplicación principal
├── requirements.txt       # Dependencias Python
├── .env.example          # Ejemplo de configuración
├── .gitignore           # Archivos ignorados por git
├── database_schema.sql  # Esquema de base de datos
├── docker-compose.yml   # Configuración Docker
├── Dockerfile          # Imagen Docker del bot
├── README.md          # Este archivo
├── logs/             # Logs de aplicación
├── materials/        # Archivos para desafíos
└── backups/         # Backups de base de datos
```

## 🤝 Contribuciones

Las contribuciones son bienvenidas! Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 👥 Créditos

- **Desarrollo**: [Tu nombre]
- **Concepto**: Curso de Búsqueda y Captura de Fugitivos
- **Framework**: python-telegram-bot

## 📞 Soporte

Para soporte y consultas:
- Crear un issue en GitHub
- Contactar a los administradores del CTF
- Telegram: @tu_usuario

## 🎯 Roadmap

### Versión 1.0 (Actual)
- ✅ Sistema básico de desafíos
- ✅ Registro y tracking de usuarios
- ✅ Validación de flags
- ✅ Ranking en tiempo real
- ✅ Docker support

### Versión 2.0 (Futuro)
- [ ] Sistema de hints (pistas) con penalización
- [ ] Desafíos dinámicos por equipo
- [ ] Dashboard web para administradores
- [ ] Integración con plataforma CTF externa
- [ ] Notificaciones automáticas
- [ ] Exportación de reportes en PDF
- [ ] Sistema de badges/logros
- [ ] Multi-idioma support

---

**¡Buena suerte en la investigación!** 🕵️‍♂️🔍
**¡Buena suerte en la investigación!** 🕵️‍♂️🔍