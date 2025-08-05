import os
from typing import Dict, List, Any
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

class Config:
    """
    Clase principal de configuraciones del sistema de SPAM.
    
    Esta clase centraliza todas las configuraciones del sistema:
    - Configuraciones de base de datos
    - Configuraciones de servidores de correo
    - Configuraciones de modelos de ML
    - Configuraciones de la interfaz web
    """
    
    # ========================================
    # CONFIGURACIONES DE BASE DE DATOS
    # ========================================
    
    # Ruta de la base de datos SQLite
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'spam_detector.db')
    
    # Configuraciones de conexión a base de datos
    DATABASE_CONFIG = {
        'timeout': 30,              # Timeout de conexión en segundos
        'check_same_thread': False,  # Permitir múltiples hilos
        'isolation_level': None      # Autocommit
    }
    
    # ========================================
    # CONFIGURACIONES DE SERVIDORES DE CORREO
    # ========================================
    
    # Configuraciones por defecto para servidores comunes
    EMAIL_SERVERS = {
        'gmail.com': {
            'imap_server': 'imap.gmail.com',
            'imap_port': 993,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'requires_ssl': True
        },
        'outlook.com': {
            'imap_server': 'outlook.office365.com',
            'imap_port': 993,
            'smtp_server': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'requires_ssl': True
        },
        'yahoo.com': {
            'imap_server': 'imap.mail.yahoo.com',
            'imap_port': 993,
            'smtp_server': 'smtp.mail.yahoo.com',
            'smtp_port': 587,
            'requires_ssl': True
        },
        'hotmail.com': {
            'imap_server': 'outlook.office365.com',
            'imap_port': 993,
            'smtp_server': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'requires_ssl': True
        }
    }
    
    # Configuraciones de monitoreo de correo
    EMAIL_MONITORING = {
        'default_check_interval': 15,    # Minutos entre revisiones
        'max_emails_per_check': 50,      # Máximo correos por revisión
        'connection_timeout': 30,         # Timeout de conexión en segundos
        'max_retries': 3,                # Máximo intentos de conexión
        'retry_delay': 5                 # Segundos entre intentos
    }
    
    # ========================================
    # CONFIGURACIONES DE MODELOS DE ML
    # ========================================
    
    # Configuraciones del modelo de detección de SPAM
    SPAM_MODEL = {
        'algorithm': 'naive_bayes',      # Algoritmo por defecto
        'confidence_threshold': 0.7,      # Umbral de confianza (0.0-1.0)
        'min_training_examples': 100,    # Mínimo ejemplos para entrenar
        'max_training_examples': 10000,  # Máximo ejemplos para entrenar
        'retrain_interval': 24,          # Horas entre reentrenamientos
        'feature_weights': {
            'urgent_words': 1.5,
            'money_words': 1.3,
            'free_words': 1.2,
            'caps_ratio': 1.4,
            'exclamation_count': 1.3,
            'link_count': 1.2,
            'suspicious_domain': 2.0,
            'attachment_type': 1.8,
            'sender_reputation': 1.6,
            'content_length': 1.1
        }
    }
    
    # Configuraciones de características de SPAM
    SPAM_FEATURES = {
        'urgent_words': [
            'URGENTE', 'INMEDIATO', 'CRÍTICO', 'ACCIÓN REQUERIDA',
            'SUSPENDIDO', 'BLOQUEADO', 'VERIFICAR', 'CONFIRMAR'
        ],
        'money_words': [
            'DINERO', 'GANAR', 'MILLONES', 'DÓLARES', 'EUROS',
            'HERENCIA', 'INVERSIÓN', 'GANANCIA', 'FORTUNA'
        ],
        'free_words': [
            'GRATIS', 'FREE', 'SIN COSTO', 'SIN CARGO',
            'REGALO', 'PREMIO', 'OPORTUNIDAD'
        ],
        'suspicious_domains': [
            'spam.com', 'malware.net', 'scam.org',
            'free-money.com', 'lottery-win.com'
        ]
    }
    
    # ========================================
    # CONFIGURACIONES DE LA INTERFAZ WEB
    # ========================================
    
    # Configuraciones de Streamlit
    STREAMLIT_CONFIG = {
        'page_title': 'CL_guardmail - Detector de SPAM',
        'page_icon': '🛡️',
        'layout': 'wide',                # Layout ancho
        'initial_sidebar_state': 'expanded',
        'theme': {
            'primaryColor': '#FF4B4B',
            'backgroundColor': '#FFFFFF',
            'secondaryBackgroundColor': '#F0F2F6',
            'textColor': '#262730'
        }
    }
    
    # Configuraciones del dashboard
    DASHBOARD_CONFIG = {
        'refresh_interval': 30,          # Segundos entre actualizaciones
        'max_display_emails': 100,       # Máximo correos a mostrar
        'chart_height': 400,             # Altura de gráficos
        'enable_real_time': True         # Actualización en tiempo real
    }
    
    # ========================================
    # CONFIGURACIONES DE LOGGING
    # ========================================
    
    # Configuraciones de logging
    LOGGING_CONFIG = {
        'level': 'INFO',                 # Nivel de logging
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': 'spam_detector.log',     # Archivo de log
        'max_size': 10 * 1024 * 1024,   # 10MB máximo
        'backup_count': 5                # Número de backups
    }
    
    # ========================================
    # CONFIGURACIONES DE SEGURIDAD
    # ========================================
    
    # Configuraciones de seguridad
    SECURITY_CONFIG = {
        'encrypt_passwords': True,       # Encriptar contraseñas
        'session_timeout': 3600,         # Timeout de sesión en segundos
        'max_login_attempts': 5,         # Máximo intentos de login
        'password_min_length': 8,        # Longitud mínima de contraseña
        'enable_2fa': False              # Autenticación de dos factores
    }
    
    # ========================================
    # CONFIGURACIONES DE NOTIFICACIONES
    # ========================================
    
    # Configuraciones de notificaciones
    NOTIFICATION_CONFIG = {
        'enable_email_notifications': True,
        'enable_dashboard_alerts': True,
        'spam_threshold': 0.8,           # Umbral para alertas de SPAM
        'notification_interval': 60       # Segundos entre notificaciones
    }
    
    # ========================================
    # CONFIGURACIONES DE EXPORTACIÓN
    # ========================================
    
    # Configuraciones de exportación de datos
    EXPORT_CONFIG = {
        'enable_csv_export': True,
        'enable_json_export': True,
        'enable_pdf_reports': True,
        'max_export_size': 10000,        # Máximo registros para exportar
        'export_path': 'exports/'        # Carpeta de exportaciones
    }
    
    # ========================================
    # CONFIGURACIONES DE DESARROLLO
    # ========================================
    
    # Configuraciones de desarrollo
    DEVELOPMENT_CONFIG = {
        'debug_mode': os.getenv('DEBUG', 'False').lower() == 'true',
        'enable_profiling': False,
        'enable_testing': True,
        'test_database': 'test_spam_detector.db'
    }
    
    @classmethod
    def get_email_server_config(cls, email_domain: str) -> Dict[str, Any]:
        """
        Obtiene la configuración del servidor de correo para un dominio.
        
        Args:
            email_domain (str): Dominio del correo (ej: gmail.com)
            
        Returns:
            Dict: Configuración del servidor
        """
        # Extraer dominio del email completo
        domain = email_domain.split('@')[-1].lower()
        
        # Buscar configuración específica
        if domain in cls.EMAIL_SERVERS:
            return cls.EMAIL_SERVERS[domain]
        
        # Configuración por defecto para dominios desconocidos
        return {
            'imap_server': f'imap.{domain}',
            'imap_port': 993,
            'smtp_server': f'smtp.{domain}',
            'smtp_port': 587,
            'requires_ssl': True
        }
    
    @classmethod
    def get_model_config(cls, algorithm: str = None) -> Dict[str, Any]:
        """
        Obtiene la configuración del modelo de ML.
        
        Args:
            algorithm (str): Algoritmo específico (opcional)
            
        Returns:
            Dict: Configuración del modelo
        """
        config = cls.SPAM_MODEL.copy()
        if algorithm:
            config['algorithm'] = algorithm
        return config
    
    @classmethod
    def get_feature_weights(cls) -> Dict[str, float]:
        """
        Obtiene los pesos de las características para el modelo.
        
        Returns:
            Dict: Pesos de características
        """
        return cls.SPAM_MODEL['feature_weights']
    
    @classmethod
    def is_development_mode(cls) -> bool:
        """
        Verifica si el sistema está en modo desarrollo.
        
        Returns:
            bool: True si está en modo desarrollo
        """
        return cls.DEVELOPMENT_CONFIG['debug_mode']

# Instancia global de configuración
config = Config()

# Función helper para obtener configuraciones
def get_config() -> Config:
    """
    Obtiene la instancia global de configuración.
    
    Returns:
        Config: Instancia de configuración
    """
    return config

if __name__ == "__main__":
    # Test de configuraciones
    print("✅ Configuraciones cargadas exitosamente")
    print(f"📧 Servidores configurados: {len(config.EMAIL_SERVERS)}")
    print(f"🤖 Algoritmo por defecto: {config.SPAM_MODEL['algorithm']}")
    print(f"🛡️ Umbral de confianza: {config.SPAM_MODEL['confidence_threshold']}")
    print(f"🌐 Modo desarrollo: {config.is_development_mode()}") 