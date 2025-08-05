# 🛡️ CL_guardmail - Sistema de Detección de SPAM

Un sistema avanzado de detección de SPAM con interfaz web moderna, monitoreo automático de múltiples cuentas de correo y aprendizaje continuo.

## 📋 Características Principales

### 🔍 Detección Inteligente
- **Múltiples algoritmos**: Naive Bayes, SVM, Random Forest
- **Análisis de características**: Palabras clave, patrones, dominios sospechosos
- **Categorización**: Phishing, Scam, Malware, Spam Comercial, etc.
- **Confianza dinámica**: Puntuación de confianza para cada detección

### 📧 Monitoreo Automático
- **Múltiples cuentas**: Gmail, Outlook, Yahoo, Hotmail y más
- **Revisión automática**: Cada 5-60 minutos (configurable)
- **IMAP seguro**: Conexiones SSL/TLS
- **Gestión de errores**: Reintentos automáticos

### 🌐 Interfaz Web Moderna
- **Dashboard interactivo**: Estadísticas en tiempo real
- **Configuración fácil**: Agregar/editar cuentas sin código
- **Análisis manual**: Probar correos individualmente
- **Sistema de entrenamiento**: Marcar correos como SPAM/HAM

### 📊 Análisis y Reportes
- **Estadísticas detalladas**: Tendencias, categorías, precisión
- **Gráficos interactivos**: Plotly para visualizaciones
- **Exportación**: CSV, JSON, PDF
- **Alertas**: Notificaciones de SPAM crítico

## 🚀 Instalación Rápida

### Prerrequisitos
- Python 3.8+
- pip (gestor de paquetes)

### Paso 1: Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/CL_guardmail.git
cd CL_guardmail
```

### Paso 2: Crear entorno virtual
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

### Paso 3: Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 4: Ejecutar la aplicación
```bash
streamlit run app.py
```

La aplicación estará disponible en: `http://localhost:8501`

## 📁 Estructura del Proyecto

```
CL_guardmail/
├── app.py                 # Aplicación web principal (Streamlit)
├── database.py            # Gestión de base de datos SQLite
├── config.py              # Configuraciones del sistema
├── spam_detector.py       # Modelo de detección de SPAM
├── email_monitor.py       # Monitoreo automático de correos
├── requirements.txt       # Dependencias de Python
├── README.md             # Este archivo
├── spam_detector.db      # Base de datos SQLite (se crea automáticamente)
└── exports/              # Carpeta para exportaciones
```

## 🎯 Uso del Sistema

### 1. Configurar Cuentas de Correo

1. **Abrir la aplicación web**
2. **Ir a "Configurar Cuentas"**
3. **Hacer clic en "Agregar Cuenta"**
4. **Completar el formulario:**
   - Email y contraseña
   - El sistema detecta automáticamente el servidor
   - Configurar intervalo de revisión (5-60 minutos)

### 2. Monitoreo Automático

El sistema automáticamente:
- ✅ Se conecta a las cuentas configuradas
- ✅ Descarga correos nuevos
- ✅ Analiza cada correo con el modelo de SPAM
- ✅ Guarda resultados en la base de datos
- ✅ Actualiza estadísticas en tiempo real

### 3. Análisis Manual

Para probar correos individualmente:
1. **Ir a "Análisis Manual"**
2. **Pegar contenido del correo**
3. **Hacer clic en "Analizar"**
4. **Ver resultados detallados**

### 4. Entrenamiento del Modelo

Para mejorar la detección:
1. **Ir a "Entrenamiento"**
2. **Marcar correos como SPAM/HAM**
3. **Agregar patrones personalizados**
4. **Ver métricas de rendimiento**

## 🔧 Configuración Avanzada

### Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# Base de datos
DATABASE_PATH=spam_detector.db

# Modo desarrollo
DEBUG=True

# Configuraciones de logging
LOG_LEVEL=INFO
LOG_FILE=spam_detector.log

# Configuraciones de seguridad
ENCRYPT_PASSWORDS=True
SESSION_TIMEOUT=3600
```

### Configuraciones de Servidores de Correo

El sistema incluye configuraciones predefinidas para:

- **Gmail**: imap.gmail.com:993
- **Outlook**: outlook.office365.com:993
- **Yahoo**: imap.mail.yahoo.com:993
- **Hotmail**: outlook.office365.com:993

Para servidores personalizados, editar `config.py`.

## 📊 Base de Datos

### Tablas Principales

1. **email_accounts**: Cuentas de correo configuradas
2. **analyzed_emails**: Correos analizados
3. **spam_categories**: Tipos de SPAM (Phishing, Scam, etc.)
4. **spam_features**: Características para detección
5. **training_examples**: Ejemplos para entrenamiento
6. **spam_patterns**: Patrones de detección
7. **user_feedback**: Feedback del usuario

### Consultas Útiles

```sql
-- Ver estadísticas por cuenta
SELECT email, total_emails_checked, total_spam_detected 
FROM email_accounts;

-- Ver correos SPAM recientes
SELECT subject, sender, confidence, analyzed_at 
FROM analyzed_emails 
WHERE is_spam = 1 
ORDER BY analyzed_at DESC;

-- Ver categorías de SPAM más comunes
SELECT sc.name, COUNT(*) as count
FROM email_spam_categories esc
JOIN spam_categories sc ON esc.category_id = sc.id
GROUP BY sc.name
ORDER BY count DESC;
```

## 🤖 Modelo de Machine Learning

### Algoritmos Soportados

1. **Naive Bayes**: Rápido y efectivo para texto
2. **Support Vector Machine (SVM)**: Alta precisión
3. **Random Forest**: Robusto y interpretable

### Características Extraídas

- **Palabras urgentes**: URGENTE, INMEDIATO, CRÍTICO
- **Palabras de dinero**: DINERO, GANAR, MILLONES
- **Proporción de mayúsculas**: Indicador de SPAM
- **Número de exclamaciones**: Urgencia falsa
- **Dominios sospechosos**: Lista negra de dominios
- **Longitud del contenido**: SPAM suele ser largo

### Entrenamiento Continuo

El modelo mejora automáticamente:
- ✅ Con feedback del usuario
- ✅ Con nuevos patrones agregados
- ✅ Con ejemplos de entrenamiento
- ✅ Reentrenamiento automático cada 24 horas

## 📈 Dashboard y Estadísticas

### Métricas Principales

- **Cuentas activas**: Número de cuentas monitoreadas
- **Correos analizados**: Total de correos procesados
- **SPAM detectado**: Correos marcados como SPAM
- **Tasa de SPAM**: Porcentaje de SPAM vs HAM
- **Precisión**: Efectividad del modelo

### Gráficos Disponibles

- **Tendencias temporales**: SPAM por día/semana
- **Distribución por categoría**: Tipos de SPAM más comunes
- **Precisión del modelo**: Evolución de la precisión
- **Actividad por cuenta**: Correos por cuenta

## 🔒 Seguridad

### Protección de Datos

- ✅ **Contraseñas encriptadas**: Almacenamiento seguro
- ✅ **Conexiones SSL**: IMAP/SMTP seguro
- ✅ **Sesiones temporales**: Timeout automático
- ✅ **Logs seguros**: Sin información sensible

### Configuraciones de Seguridad

```python
# En config.py
SECURITY_CONFIG = {
    'encrypt_passwords': True,
    'session_timeout': 3600,
    'max_login_attempts': 5,
    'password_min_length': 8
}
```

## 🐛 Solución de Problemas

### Errores Comunes

#### 1. Error de conexión IMAP
```
Error: [SSL: CERTIFICATE_VERIFY_FAILED]
```
**Solución**: Verificar configuración SSL en `config.py`

#### 2. Base de datos no encontrada
```
Error: no such table: email_accounts
```
**Solución**: Ejecutar `python database.py` para crear tablas

#### 3. Librerías faltantes
```
ModuleNotFoundError: No module named 'streamlit'
```
**Solución**: `pip install -r requirements.txt`

### Logs y Debugging

Los logs se guardan en:
- **Archivo**: `spam_detector.log`
- **Nivel**: INFO por defecto
- **Rotación**: 10MB máximo, 5 backups

Para debug avanzado:
```bash
export DEBUG=True
streamlit run app.py
```

## 🚀 Despliegue

### Desarrollo Local
```bash
streamlit run app.py
```

### Producción con Docker
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501"]
```

### Servidor Web
```bash
# Con Nginx
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

## 🤝 Contribución

### Cómo Contribuir

1. **Fork** el repositorio
2. **Crear** una rama para tu feature
3. **Commit** tus cambios
4. **Push** a la rama
5. **Crear** un Pull Request

### Estándares de Código

- **Python**: PEP 8
- **Documentación**: Docstrings completos
- **Tests**: pytest para nuevas funcionalidades
- **Logging**: Usar logger en lugar de print

### Estructura de Commits

```
feat: agregar nueva categoría de SPAM
fix: corregir error de conexión IMAP
docs: actualizar README
test: agregar tests para spam_detector
```

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 🙏 Agradecimientos

- **Streamlit**: Interfaz web moderna
- **scikit-learn**: Algoritmos de ML
- **SQLite**: Base de datos ligera
- **Plotly**: Gráficos interactivos

## 📞 Soporte

### Contacto
- **Email**: tu-email@ejemplo.com
- **GitHub**: https://github.com/tu-usuario/CL_guardmail
- **Issues**: https://github.com/tu-usuario/CL_guardmail/issues

### Documentación Adicional
- **Wiki**: https://github.com/tu-usuario/CL_guardmail/wiki
- **API Docs**: https://github.com/tu-usuario/CL_guardmail/docs

---

**⭐ Si te gusta este proyecto, ¡dale una estrella en GitHub!**

**🛡️ CL_guardmail - Protegiendo tu bandeja de entrada desde 2025** 