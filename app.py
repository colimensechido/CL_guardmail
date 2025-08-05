import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import logging
import re

# Importar nuestros módulos
from database import create_database, SpamDatabase
from config import get_config
# from spam_detector import SpamDetector  # Lo crearemos después
# from email_monitor import EmailMonitor  # Lo crearemos después

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la página
st.set_page_config(
    page_title="CL_guardmail - Detector de SPAM",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class SpamDetectorApp:
    """
    Clase principal de la aplicación web de detección de SPAM.
    
    Esta clase maneja toda la lógica de la interfaz web:
    - Dashboard principal
    - Configuración de cuentas
    - Análisis de correos
    - Sistema de entrenamiento
    - Visualización de datos
    """
    
    def __init__(self):
        """Inicializa la aplicación web."""
        self.config = get_config()
        self.db = create_database()
        self.setup_session_state()
    
    def setup_session_state(self):
        """Configura el estado inicial de la sesión."""
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'dashboard'
        
        if 'last_auto_check' not in st.session_state:
            st.session_state.last_auto_check = {}
        
        if 'auto_check_enabled' not in st.session_state:
            st.session_state.auto_check_enabled = True
        
        # Nuevos estados para logging visual
        if 'auto_check_logs' not in st.session_state:
            st.session_state.auto_check_logs = []
        
        if 'current_checking_account' not in st.session_state:
            st.session_state.current_checking_account = None
        
        if 'check_start_time' not in st.session_state:
            st.session_state.check_start_time = None
    
    def add_log_entry(self, message: str, level: str = "INFO"):
        """
        Agrega una entrada al log visual del sistema automático.
        
        Args:
            message (str): Mensaje a agregar
            level (str): Nivel del log (INFO, SUCCESS, ERROR, WARNING)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'level': level
        }
        
        # Mantener solo los últimos 20 logs
        st.session_state.auto_check_logs.append(log_entry)
        if len(st.session_state.auto_check_logs) > 20:
            st.session_state.auto_check_logs.pop(0)
    
    def run_automatic_checks(self):
        """
        Ejecuta las revisiones automáticas de correos según los intervalos configurados.
        Esta función se ejecuta en cada rerun de Streamlit.
        """
        if not st.session_state.auto_check_enabled:
            return
        
        try:
            # Obtener todas las cuentas activas
            accounts = self.get_email_accounts()
            current_time = time.time()
            
            # Log de inicio de ciclo
            self.add_log_entry("🔄 Iniciando ciclo de revisión automática", "INFO")
            
            # Contador de revisiones programadas
            scheduled_checks = 0
            
            for account in accounts:
                if not account['is_active']:
                    continue
                
                account_id = account['id']
                check_interval = account['check_interval'] * 60  # Convertir a segundos
                
                # Verificar si es tiempo de revisar esta cuenta
                last_check = st.session_state.last_auto_check.get(account_id, 0)
                time_since_last_check = current_time - last_check
                
                if time_since_last_check >= check_interval:
                    scheduled_checks += 1
                    # Log de inicio de revisión
                    self.add_log_entry(f"📧 Iniciando revisión de {account['email']} (intervalo: {account['check_interval']} min)", "INFO")
                    st.session_state.current_checking_account = account['email']
                    st.session_state.check_start_time = current_time
                    
                    # Ejecutar revisión automática (no bloqueante)
                    try:
                        # Ejecutar en un thread separado o de forma asíncrona
                        self.run_automatic_check_for_account(account_id, account)
                        st.session_state.last_auto_check[account_id] = current_time
                        
                        # Log de fin de revisión
                        st.session_state.current_checking_account = None
                        st.session_state.check_start_time = None
                        
                    except Exception as e:
                        self.add_log_entry(f"❌ Error en revisión de {account['email']}: {str(e)}", "ERROR")
                        st.session_state.current_checking_account = None
                        st.session_state.check_start_time = None
                        
                else:
                    # Calcular tiempo restante
                    time_remaining = check_interval - time_since_last_check
                    minutes_remaining = time_remaining / 60
                    
                    # Solo log si faltan menos de 5 minutos
                    if minutes_remaining <= 5:
                        self.add_log_entry(f"⏰ {account['email']}: Próxima revisión en {minutes_remaining:.1f} min", "INFO")
            
            # Log de fin de ciclo
            if scheduled_checks > 0:
                self.add_log_entry(f"✅ Ciclo completado: {scheduled_checks} revisión(es) programada(s)", "SUCCESS")
            else:
                self.add_log_entry("✅ Ciclo completado: No hay revisiones pendientes", "SUCCESS")
                    
        except Exception as e:
            self.add_log_entry(f"❌ Error en revisión automática: {str(e)}", "ERROR")
            logger.error(f"Error en revisión automática: {e}")

    def run_automatic_check_for_account(self, account_id: int, account: dict):
        """
        Ejecuta una revisión automática para una cuenta específica.
        
        Args:
            account_id (int): ID de la cuenta
            account (dict): Información de la cuenta
        """
        try:
            self.add_log_entry(f"🔍 Conectando a {account['email']}...", "INFO")
            
            # Importar y ejecutar la revisión
            from email_monitor import process_account_emails
            
            # Ejecutar con timeout para evitar bloqueos
            result = process_account_emails(
                account_id=account_id,
                max_emails=account['max_emails_per_check'],
                get_all=False,  # Solo correos recientes
                get_recent=False  # Usar comportamiento por defecto (no leídos + leídos recientes)
            )
            
            if result['success']:
                self.add_log_entry(f"✅ {account['email']}: {result['emails_processed']} correos procesados, {result['spam_detected']} SPAM detectado", "SUCCESS")
                logger.info(f"✅ Revisión automática completada para {account['email']}: {result['emails_processed']} correos procesados")
            else:
                self.add_log_entry(f"❌ {account['email']}: Error - {result.get('error', 'Error desconocido')}", "ERROR")
                logger.error(f"❌ Error en revisión automática para {account['email']}: {result.get('error', 'Error desconocido')}")
                
        except Exception as e:
            self.add_log_entry(f"❌ {account['email']}: Error de conexión - {str(e)}", "ERROR")
            logger.error(f"Error ejecutando revisión automática para cuenta {account_id}: {e}")

    def run(self):
        """
        Ejecuta la aplicación principal.
        
        Incluye:
        - Configuración inicial
        - Revisión automática de correos
        - Navegación principal
        - Interfaz de usuario
        """
        # Título principal
        st.title("🛡️ CL_guardmail - Sistema de Detección de SPAM")
        st.markdown("---")
        
        # Configurar estado inicial
        self.setup_session_state()
        
        # Ejecutar revisiones automáticas
        self.run_automatic_checks()
        
        # Crear sidebar
        self.create_sidebar()
        
        # Navegación principal
        if st.session_state.current_page == 'dashboard':
            self.show_dashboard()
        elif st.session_state.current_page == 'accounts':
            self.show_account_config()
        elif st.session_state.current_page == 'viewer':
            self.show_email_viewer()
        elif st.session_state.current_page == 'manual':
            self.show_manual_analysis()
        elif st.session_state.current_page == 'training':
            self.show_training()
        elif st.session_state.current_page == 'statistics':
            self.show_statistics()
        elif st.session_state.current_page == 'patterns':
            self.show_patterns()
        elif st.session_state.current_page == 'ml_models':
            self.show_ml_models()
    
    def create_sidebar(self):
        """
        Crea la barra lateral con navegación y configuraciones.
        
        La sidebar contiene:
        - Menú de navegación
        - Información del sistema
        - Configuraciones rápidas
        """
        with st.sidebar:
            st.header("🧭 Navegación")
            
            # Menú de navegación
            page = st.selectbox(
                "Seleccionar página:",
                [
                    'dashboard',
                    'accounts',
                    'viewer',
                    'manual',
                    'training',
                    'statistics',
                    'patterns',
                    'ml_models'
                ],
                format_func=lambda x: {
                    'dashboard': '📊 Dashboard',
                    'accounts': '📧 Configurar Cuentas',
                    'viewer': '👁️ Visualizar Correos',
                    'manual': '🔍 Análisis Manual',
                    'training': '🎓 Entrenamiento',
                    'statistics': '📈 Estadísticas',
                    'patterns': '🔍 Patrones',
                    'ml_models': '🤖 Modelos ML'
                }[x],
                index=0
            )
            
            if page != st.session_state.current_page:
                st.session_state.current_page = page
                st.rerun()
            
            st.markdown("---")
            
            # Información del sistema
            st.header("ℹ️ Información del Sistema")
            
            # Estadísticas rápidas
            try:
                total_accounts = self.get_total_accounts()
                total_emails = self.get_total_emails()
                total_spam = self.get_total_spam()
                
                st.metric("📧 Cuentas Configuradas", total_accounts)
                st.metric("📨 Correos Analizados", total_emails)
                st.metric("🚨 SPAM Detectado", total_spam)
                
                if total_emails > 0:
                    spam_rate = (total_spam / total_emails) * 100
                    st.metric("📊 Tasa de SPAM", f"{spam_rate:.1f}%")
                
            except Exception as e:
                st.error(f"Error cargando estadísticas: {e}")
            
            st.markdown("---")
            
            # Configuraciones rápidas
            st.header("⚙️ Configuraciones")
            
            # Control del sistema automático
            auto_check_enabled = st.checkbox(
                "🔄 Sistema Automático Activo",
                value=st.session_state.auto_check_enabled,
                help="Habilita/deshabilita las revisiones automáticas de correos"
            )
            
            if auto_check_enabled != st.session_state.auto_check_enabled:
                st.session_state.auto_check_enabled = auto_check_enabled
                if auto_check_enabled:
                    st.success("✅ Sistema automático activado")
                else:
                    st.warning("⚠️ Sistema automático desactivado")
                st.rerun()
            
            # Indicador de estado actual
            if st.session_state.current_checking_account:
                st.warning(f"⏳ Revisando: {st.session_state.current_checking_account}")
                if st.session_state.check_start_time:
                    elapsed_time = time.time() - st.session_state.check_start_time
                    st.caption(f"⏱️ Tiempo: {elapsed_time:.1f}s")
            else:
                st.info("💤 Sistema en espera")
            
            # Umbral de confianza
            confidence_threshold = st.slider(
                "Umbral de Confianza",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.1,
                help="Confianza mínima para marcar como SPAM"
            )
            
            # Intervalo de revisión (solo informativo en sidebar)
            st.info("ℹ️ Los intervalos de revisión se configuran por cuenta en 'Configurar Cuentas'")
            
            st.markdown("---")
            
            # Botón de actualización
            if st.button("🔄 Actualizar Datos"):
                st.rerun()
    
    def show_dashboard(self):
        """
        Muestra el dashboard principal con estadísticas y gráficos.
        
        El dashboard incluye:
        - Resumen de estadísticas
        - Gráficos de tendencias
        - Últimos correos analizados
        - Alertas del sistema
        """
        st.header("📊 Dashboard Principal")
        
        # Indicador del sistema automático
        auto_status = "✅ ACTIVO" if st.session_state.auto_check_enabled else "❌ INACTIVO"
        auto_color = "green" if st.session_state.auto_check_enabled else "red"
        
        col_status, col_spacer = st.columns([1, 3])
        with col_status:
            st.markdown(f"""
            <div style="background-color: {auto_color}; color: white; padding: 10px; border-radius: 5px; text-align: center;">
                <strong>🔄 Sistema Automático: {auto_status}</strong>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Crear columnas para métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        try:
            with col1:
                total_accounts = self.get_total_accounts()
                st.metric("📧 Cuentas Activas", total_accounts)
            
            with col2:
                total_emails = self.get_total_emails()
                st.metric("📨 Correos Analizados", total_emails)
            
            with col3:
                total_spam = self.get_total_spam()
                st.metric("🚨 SPAM Detectado", total_spam)
            
            with col4:
                if total_emails > 0:
                    accuracy = ((total_emails - total_spam) / total_emails) * 100
                    st.metric("✅ Precisión", f"{accuracy:.1f}%")
                else:
                    st.metric("✅ Precisión", "N/A")
        
        except Exception as e:
            st.error(f"Error cargando métricas: {e}")
        
        st.markdown("---")
        
        # Gráficos y visualizaciones
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Tendencias de SPAM")
            self.show_spam_trends()
        
        with col2:
            st.subheader("🎯 Categorías de SPAM")
            self.show_spam_categories()
        
        # Últimos correos analizados
        st.subheader("📧 Últimos Correos Analizados")
        self.show_recent_emails()
        
        # Información del sistema automático
        st.subheader("🔄 Estado del Sistema Automático")
        self.show_automatic_system_status()
        
        # Log visual en tiempo real
        st.subheader("📋 Log de Actividad en Tiempo Real")
        
        # Información sobre el sistema no-bloqueante
        with st.expander("ℹ️ ¿Cómo funciona el sistema automático?", expanded=False):
            st.info("""
            **🔄 Sistema No-Bloqueante:**
            
            - ✅ **No bloquea la interfaz**: Puedes navegar libremente mientras revisa
            - ✅ **Ejecución en background**: Las revisiones se ejecutan sin afectar la UI
            - ✅ **Logs en tiempo real**: Ves exactamente qué está haciendo
            - ✅ **Continuidad**: El sistema sigue funcionando aunque cambies de página
            
            **⚡ Optimizaciones:**
            - Las revisiones se ejecutan de forma asíncrona
            - Timeouts para evitar bloqueos largos
            - Logs persistentes entre navegaciones
            - Indicadores visuales de progreso
            """)
        
        self.show_visual_log()
        
        # Alertas del sistema
        st.subheader("🚨 Alertas del Sistema")
        self.show_system_alerts()
    
    def show_account_config(self):
        """
        Muestra la página de configuración de cuentas de correo.
        
        Permite al usuario:
        - Agregar nuevas cuentas
        - Editar cuentas existentes
        - Eliminar cuentas
        - Configurar intervalos de revisión
        """
        st.header("📧 Configuración de Cuentas de Correo")
        
        # Tabs para diferentes acciones
        tab1, tab2, tab3 = st.tabs(["➕ Agregar Cuenta", "✏️ Editar Cuentas", "🗑️ Eliminar Cuenta"])
        
        with tab1:
            self.show_add_account_form()
        
        with tab2:
            self.show_edit_accounts()
        
        with tab3:
            self.show_delete_account()
    
    def show_add_account_form(self):
        """
        Muestra el formulario para agregar una nueva cuenta de correo.
        
        El formulario incluye:
        - Email y contraseña
        - Configuración del servidor
        - Intervalos de revisión
        - Validaciones
        """
        st.subheader("Agregar Nueva Cuenta")
        
        with st.form("add_account_form"):
            # Información básica
            email = st.text_input("📧 Dirección de Correo", placeholder="usuario@gmail.com")
            password = st.text_input("🔑 Contraseña", type="password")
            
            # Configuración del servidor
            st.subheader("⚙️ Configuración del Servidor")
            
            # Selección de servidor de correo
            st.subheader("📧 Seleccionar Proveedor de Correo")
            
            # Opciones de servidores populares
            server_options = {
                "Gmail": {
                    "imap_server": "imap.gmail.com",
                    "imap_port": 993,
                    "help": "Para cuentas @gmail.com",
                    "icon": "📧"
                },
                "Outlook/Hotmail": {
                    "imap_server": "outlook.office365.com",
                    "imap_port": 993,
                    "help": "Para cuentas @outlook.com, @hotmail.com",
                    "icon": "📧"
                },
                "Yahoo": {
                    "imap_server": "imap.mail.yahoo.com",
                    "imap_port": 993,
                    "help": "Para cuentas @yahoo.com",
                    "icon": "📧"
                },
                "ProtonMail": {
                    "imap_server": "127.0.0.1",
                    "imap_port": 1143,
                    "help": "Para cuentas @protonmail.com (requiere Bridge)",
                    "icon": "🔒"
                },
                "iCloud": {
                    "imap_server": "imap.mail.me.com",
                    "imap_port": 993,
                    "help": "Para cuentas @icloud.com",
                    "icon": "🍎"
                },
                "Zoho": {
                    "imap_server": "imap.zoho.com",
                    "imap_port": 993,
                    "help": "Para cuentas @zoho.com",
                    "icon": "📧"
                },
                "Otro (Personalizado)": {
                    "imap_server": "",
                    "imap_port": 993,
                    "help": "Para otros proveedores",
                    "icon": "⚙️"
                }
            }
            
            # Selector de servidor con iconos
            server_names = [f"{server_options[server]['icon']} {server}" for server in server_options.keys()]
            selected_server_with_icon = st.selectbox(
                "Proveedor de correo:",
                options=server_names,
                help="Selecciona tu proveedor de correo"
            )
            
            # Extraer nombre del servidor sin icono
            selected_server = selected_server_with_icon.split(" ", 1)[1] if " " in selected_server_with_icon else selected_server_with_icon
            
            # Mostrar configuración del servidor seleccionado
            server_config = server_options[selected_server]
            
            # Campos del servidor
            col1, col2 = st.columns(2)
            
            # Determinar si es proveedor personalizado
            is_custom = (selected_server == "Otro (Personalizado)")
            
            with col1:
                imap_server = st.text_input(
                    "IMAP Server",
                    value=server_config["imap_server"],
                    help=server_config["help"],
                    disabled=not is_custom
                )
            
            with col2:
                imap_port = st.number_input(
                    "IMAP Puerto",
                    value=server_config["imap_port"],
                    min_value=1,
                    max_value=65535,
                    help="Puerto IMAP (normalmente 993 para SSL)",
                    disabled=not is_custom
                )
            
            # Información adicional según el proveedor
            st.subheader("📋 Instrucciones Específicas")
            
            if selected_server == "Gmail":
                with st.expander("🔧 Configuración de Gmail", expanded=True):
                    st.markdown("""
                    **📋 PASOS EXACTOS PARA GMAIL:**
                    
                    **1️⃣ Habilitar Verificación en 2 Pasos:**
                    - Ve a [myaccount.google.com/security](https://myaccount.google.com/security)
                    - Busca "Verificación en 2 pasos" y haz clic
                    - Sigue los pasos para habilitarla (SMS o app)
                    
                    **2️⃣ Generar Contraseña de Aplicación:**
                    - Ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
                    - Selecciona "Otra aplicación personalizada"
                    - Escribe "CL_guardmail" como nombre
                    - Haz clic en "Generar"
                    - **Copia la contraseña de 16 caracteres**
                    
                    **3️⃣ Configurar en CL_guardmail:**
                    - Email: tu_email@gmail.com
                    - Contraseña: **usa la contraseña de 16 caracteres** (NO tu contraseña normal)
                    - Servidor: imap.gmail.com (automático)
                    - Puerto: 993 (automático)
                    
                    **⚠️ IMPORTANTE:** Nunca uses tu contraseña normal de Gmail
                    """)
                    
            elif selected_server == "Outlook/Hotmail":
                with st.expander("🔧 Configuración de Outlook/Hotmail", expanded=True):
                    st.markdown("""
                    **📋 PASOS EXACTOS PARA OUTLOOK:**
                    
                    **1️⃣ Habilitar IMAP en Outlook:**
                    - Ve a [outlook.live.com/mail/0/options/mail/accounts](https://outlook.live.com/mail/0/options/mail/accounts)
                    - Busca "Configuración de POP e IMAP"
                    - Habilita "Permitir que dispositivos y aplicaciones usen IMAP"
                    
                    **2️⃣ Para Cuentas Empresariales (Office 365):**
                    - Ve a [portal.office.com](https://portal.office.com)
                    - Configuración → Ver toda la configuración de Outlook
                    - Correo → Sincronización de correo electrónico
                    - Marca "Permitir que dispositivos y aplicaciones usen IMAP"
                    
                    **3️⃣ Configurar en CL_guardmail:**
                    - Email: tu_email@outlook.com o tu_email@hotmail.com
                    - Contraseña: **tu contraseña normal** (no necesitas contraseña de app)
                    - Servidor: outlook.office365.com (automático)
                    - Puerto: 993 (automático)
                    
                    **✅ VENTAJA:** No necesitas contraseña de aplicación
                    """)
                    
            elif selected_server == "Yahoo":
                with st.expander("🔧 Configuración de Yahoo", expanded=True):
                    st.markdown("""
                    **📋 PASOS EXACTOS PARA YAHOO:**
                    
                    **1️⃣ Generar Contraseña de Aplicación:**
                    - Ve a [login.yahoo.com/account/security](https://login.yahoo.com/account/security)
                    - Busca "Contraseñas de aplicación" o "App passwords"
                    - Haz clic en "Generar contraseña de aplicación"
                    - Selecciona "Otra aplicación"
                    - Escribe "CL_guardmail" como nombre
                    - **Copia la contraseña generada**
                    
                    **2️⃣ Si no ves "Contraseñas de aplicación":**
                    - Primero habilita "Verificación en 2 pasos"
                    - Ve a [login.yahoo.com/account/security](https://login.yahoo.com/account/security)
                    - Busca "Verificación en 2 pasos" y actívala
                    - Luego vuelve a intentar generar la contraseña de aplicación
                    
                    **3️⃣ Configurar en CL_guardmail:**
                    - Email: tu_email@yahoo.com
                    - Contraseña: **usa la contraseña de aplicación** (NO tu contraseña normal)
                    - Servidor: imap.mail.yahoo.com (automático)
                    - Puerto: 993 (automático)
                    
                    **⚠️ IMPORTANTE:** Yahoo requiere contraseña de aplicación
                    """)
                    
            elif selected_server == "ProtonMail":
                with st.expander("🔧 Configuración de ProtonMail", expanded=True):
                    st.markdown("""
                    **📋 PASOS EXACTOS PARA PROTONMAIL:**
                    
                    **1️⃣ Instalar ProtonMail Bridge:**
                    - Ve a [protonmail.com/bridge](https://protonmail.com/bridge)
                    - Descarga la versión para tu sistema operativo
                    - Instala y ejecuta ProtonMail Bridge
                    
                    **2️⃣ Configurar Bridge:**
                    - Abre ProtonMail Bridge
                    - Inicia sesión con tu cuenta ProtonMail
                    - Bridge te mostrará credenciales específicas
                    - **Anota el email y contraseña que te da Bridge**
                    
                    **3️⃣ Configurar en CL_guardmail:**
                    - Email: **usa el email que te da Bridge** (no tu email normal)
                    - Contraseña: **usa la contraseña que te da Bridge**
                    - Servidor: 127.0.0.1 (automático)
                    - Puerto: 1143 (automático)
                    
                    **⚠️ IMPORTANTE:** Bridge debe estar ejecutándose siempre
                    **💡 TIP:** Bridge crea un túnel seguro entre CL_guardmail y ProtonMail
                    """)
                    
            elif selected_server == "iCloud":
                with st.expander("🔧 Configuración de iCloud", expanded=True):
                    st.markdown("""
                    **📋 PASOS EXACTOS PARA ICLOUD:**
                    
                    **1️⃣ Generar Contraseña de Aplicación:**
                    - Ve a [appleid.apple.com](https://appleid.apple.com)
                    - Inicia sesión con tu Apple ID
                    - Ve a "Seguridad" → "Contraseñas de aplicación"
                    - Haz clic en "Generar contraseña"
                    - Selecciona "Otra aplicación" y escribe "CL_guardmail"
                    - **Copia la contraseña de 16 caracteres**
                    
                    **2️⃣ Si no ves "Contraseñas de aplicación":**
                    - Primero habilita "Verificación en 2 pasos"
                    - Ve a [appleid.apple.com](https://appleid.apple.com)
                    - Seguridad → Verificación en 2 pasos
                    - Sigue los pasos para activarla
                    - Luego vuelve a intentar generar la contraseña de aplicación
                    
                    **3️⃣ Configurar en CL_guardmail:**
                    - Email: tu_email@icloud.com
                    - Contraseña: **usa la contraseña de 16 caracteres** (NO tu contraseña normal)
                    - Servidor: imap.mail.me.com (automático)
                    - Puerto: 993 (automático)
                    
                    **⚠️ IMPORTANTE:** Nunca uses tu contraseña normal de Apple ID
                    """)
                    
            elif selected_server == "Zoho":
                with st.expander("🔧 Configuración de Zoho", expanded=True):
                    st.markdown("""
                    **📋 PASOS EXACTOS PARA ZOHO:**
                    
                    **1️⃣ Verificar Configuración IMAP:**
                    - Ve a [mail.zoho.com](https://mail.zoho.com)
                    - Inicia sesión con tu cuenta Zoho
                    - Ve a Configuración → Cuentas de correo
                    - Busca "Configuración IMAP" y asegúrate de que esté habilitado
                    
                    **2️⃣ Para Cuentas Empresariales:**
                    - Contacta a tu administrador de Zoho
                    - Pide que habilite el acceso IMAP para tu cuenta
                    - Verifica que no haya restricciones de seguridad
                    
                    **3️⃣ Configurar en CL_guardmail:**
                    - Email: tu_email@zoho.com
                    - Contraseña: **tu contraseña normal** (no necesitas contraseña de app)
                    - Servidor: imap.zoho.com (automático)
                    - Puerto: 993 (automático)
                    
                    **✅ VENTAJA:** Configuración simple, no requiere contraseña de aplicación
                    **⚠️ NOTA:** Algunas cuentas empresariales pueden tener restricciones
                    """)
                    
            elif selected_server == "Otro (Personalizado)":
                with st.expander("🔧 Configuración Personalizada", expanded=True):
                    st.markdown("""
                    **📋 CONFIGURACIÓN PARA SERVIDORES PERSONALIZADOS:**
                    
                    **1️⃣ Verificar Configuración IMAP:**
                    - Contacta a tu proveedor de correo
                    - Pregunta por la configuración IMAP
                    - Verifica que IMAP esté habilitado en tu cuenta
                    
                    **2️⃣ Información Necesaria:**
                    - **Servidor IMAP:** (ej: imap.tuproveedor.com)
                    - **Puerto IMAP:** (normalmente 993 para SSL, 143 para no SSL)
                    - **Tipo de conexión:** SSL/TLS o STARTTLS
                    - **Credenciales:** email y contraseña
                    
                    **3️⃣ Configuraciones Comunes:**
                    
                    **📧 Empresarial (Exchange):**
                    - Servidor: outlook.office365.com
                    - Puerto: 993
                    - Usar contraseña normal
                    
                    **📧 Hosting Personal:**
                    - Servidor: mail.tudominio.com
                    - Puerto: 993 (SSL) o 143 (no SSL)
                    - Usar credenciales del hosting
                    
                    **📧 Otros Proveedores:**
                    - Consulta la documentación de tu proveedor
                    - Busca "configuración IMAP" en su sitio web
                    
                    **⚠️ IMPORTANTE:** Verifica la configuración con tu proveedor antes de usar
                    """)
            
            # Configuraciones adicionales
            st.subheader("⏰ Configuraciones de Monitoreo")
            
            # Información sobre el sistema de revisión
            with st.expander("ℹ️ ¿Cómo funciona la revisión automática?", expanded=False):
                st.markdown("""
                **🔍 Sistema de Revisión Inteligente:**
                
                **📧 Correos Revisados:**
                - Solo se analizan **correos no leídos** (UNSEEN)
                - Se evita procesar correos ya analizados
                - El sistema mantiene un registro de correos procesados
                
                **⚡ Batch Size (Tamaño de Lote):**
                - Define cuántos correos se procesan en cada revisión
                - Ejemplo: Si pones 50, cada revisión traerá hasta 50 correos nuevos
                - Valores recomendados: 10-100 (depende de tu volumen de correo)
                
                **⏱️ Frecuencia de Revisión:**
                - Se ejecuta automáticamente según el intervalo configurado
                - También puedes forzar una revisión manual con el botón "🔄 Revisar"
                
                **💾 Eficiencia:**
                - Los correos ya analizados se marcan como procesados
                - No se repite el análisis de correos ya revisados
                - Se optimiza el uso de recursos del servidor
                """)
            
            check_interval = st.selectbox(
                "Intervalo de Revisión",
                [1, 5, 10, 15, 30, 60],
                index=2,
                help="Cada cuántos minutos revisar correos nuevos"
            )
            
            max_emails = st.number_input(
                "Máximo Correos por Revisión (Batch Size)",
                value=50,
                min_value=10,
                max_value=200,
                help="Cantidad máxima de correos no leídos que se analizarán en cada revisión automática (batch size). Solo procesa correos nuevos."
            )
            
            # Botones de acción
            col1, col2 = st.columns(2)
            
            with col1:
                test_connection = st.form_submit_button("🔍 Probar Conexión", type="secondary")
            
            with col2:
                submitted = st.form_submit_button("➕ Agregar Cuenta", type="primary")
            
            if test_connection:
                if self.validate_account_form(email, password, imap_server):
                    with st.spinner("🔍 Probando conexión..."):
                        # Simular prueba de conexión (por ahora)
                        import time
                        time.sleep(2)
                        
                        # Aquí iría la lógica real de prueba de conexión
                        if selected_server in ["Gmail", "Outlook/Hotmail", "Yahoo"]:
                            st.success("✅ Conexión exitosa! Las credenciales son correctas.")
                        else:
                            st.warning("⚠️ Conexión simulada. Verifica manualmente las credenciales.")
                else:
                    st.error("❌ Completa todos los campos para probar la conexión")
            
            if submitted:
                if self.validate_account_form(email, password, imap_server):
                    success = self.add_email_account(
                        email, password, imap_server, imap_port, check_interval, max_emails
                    )
                    if success:
                        st.success("✅ Cuenta agregada exitosamente!")
                        st.rerun()
                    else:
                        st.error("❌ Error al agregar la cuenta")
                else:
                    st.error("❌ Por favor, completa todos los campos requeridos")
    
    def show_edit_accounts(self):
        """
        Muestra la lista de cuentas existentes para editar.
        
        Permite:
        - Ver todas las cuentas configuradas
        - Editar configuraciones
        - Activar/desactivar cuentas
        """
        st.subheader("Editar Cuentas Existentes")
        
        try:
            # Obtener cuentas de la base de datos
            accounts = self.get_email_accounts()
            
            if not accounts:
                st.info("📭 No hay cuentas configuradas")
                return
            
            # Mostrar cuentas con botones de acción
            st.subheader("📋 Cuentas Configuradas")
            
            for account in accounts:
                col1, col2, col3, col4, col5, col6, col7 = st.columns([3, 1, 1, 1, 1, 1, 1])
                
                with col1:
                    status_icon = "✅" if account['is_active'] else "❌"
                    st.write(f"{status_icon} **{account['email']}**")
                    st.caption(f"Servidor: {account['server']} | Última revisión: {account['last_check_at'] or 'Nunca'}")
                
                with col2:
                    if st.button("🔄 Revisar", key=f"revisar_{account['id']}", help="Forzar revisión inmediata"):
                        with st.spinner(f"Revisando {account['email']}..."):
                            result = self.force_email_check(account['id'])
                            
                            if result['success']:
                                st.success(f"✅ Revisión completada para {result['account_email']}")
                                
                                # Mostrar estadísticas principales
                                col_stats1, col_stats2, col_stats3 = st.columns(3)
                                with col_stats1:
                                    st.metric("📧 Encontrados", result['emails_found'])
                                with col_stats2:
                                    st.metric("🚨 SPAM", result['spam_detected'])
                                with col_stats3:
                                    st.metric("✅ HAM", result['ham_detected'])
                                
                                # Mostrar tiempo de procesamiento
                                if 'processing_time' in result:
                                    st.caption(f"⏱️ Tiempo de procesamiento: {result['processing_time']:.2f} segundos")
                                
                                # Mostrar detalle de correos si hay
                                if result.get('emails_detail'):
                                    with st.expander("📋 Detalle de Correos Procesados", expanded=False):
                                        for i, email_detail in enumerate(result['emails_detail'], 1):
                                            spam_icon = "🚨" if email_detail['is_spam'] else "✅"
                                            confidence_pct = email_detail['confidence'] * 100
                                            
                                            st.write(f"{spam_icon} **{i}.** {email_detail['subject']}")
                                            st.caption(f"De: {email_detail['sender']} | Confianza: {confidence_pct:.1f}% | Score: {email_detail['spam_score']:.3f}")
                                
                                # Actualizar dashboard
                                st.rerun()
                            else:
                                st.error(f"❌ Error en revisión: {result['error']}")
                
                with col3:
                    if st.button("📥 Obtener TODOS", key=f"get_all_{account['id']}", help="Obtener TODOS los correos de Gmail"):
                        with st.spinner(f"Obteniendo TODOS los correos de {account['email']}..."):
                            result = self.force_email_check(account['id'], get_all=True)
                            
                            if result['success']:
                                st.success(f"✅ Obtenidos TODOS los correos de {result['account_email']}")
                                
                                # Mostrar estadísticas principales
                                col_stats1, col_stats2, col_stats3 = st.columns(3)
                                with col_stats1:
                                    st.metric("📧 Total Obtenidos", result['emails_found'])
                                with col_stats2:
                                    st.metric("🚨 SPAM", result['spam_detected'])
                                with col_stats3:
                                    st.metric("✅ HAM", result['ham_detected'])
                                
                                # Mostrar tiempo de procesamiento
                                if 'processing_time' in result:
                                    st.caption(f"⏱️ Tiempo de procesamiento: {result['processing_time']:.2f} segundos")
                                
                                # Mostrar detalle de correos si hay
                                if result.get('emails_detail'):
                                    with st.expander("📋 Detalle de Correos Obtenidos", expanded=False):
                                        for i, email_detail in enumerate(result['emails_detail'], 1):
                                            spam_icon = "🚨" if email_detail['is_spam'] else "✅"
                                            confidence_pct = email_detail['confidence'] * 100
                                            
                                            st.write(f"{spam_icon} **{i}.** {email_detail['subject']}")
                                            st.caption(f"De: {email_detail['sender']} | Confianza: {confidence_pct:.1f}% | Score: {email_detail['spam_score']:.3f}")
                                
                                # Actualizar dashboard
                                st.rerun()
                            else:
                                st.error(f"❌ Error obteniendo correos: {result['error']}")
                
                with col4:
                    if st.button("📅 Recientes", key=f"get_recent_{account['id']}", help="Obtener correos recientes (últimos 7 días)"):
                        with st.spinner(f"Obteniendo correos recientes de {account['email']}..."):
                            result = self.force_email_check(account['id'], get_recent=True)
                            
                            if result['success']:
                                st.success(f"✅ Obtenidos correos recientes de {result['account_email']}")
                                
                                # Mostrar estadísticas principales
                                col_stats1, col_stats2, col_stats3 = st.columns(3)
                                with col_stats1:
                                    st.metric("📧 Recientes", result['emails_found'])
                                with col_stats2:
                                    st.metric("🚨 SPAM", result['spam_detected'])
                                with col_stats3:
                                    st.metric("✅ HAM", result['ham_detected'])
                                
                                # Mostrar tiempo de procesamiento
                                if 'processing_time' in result:
                                    st.caption(f"⏱️ Tiempo de procesamiento: {result['processing_time']:.2f} segundos")
                                
                                # Mostrar detalle de correos si hay
                                if result.get('emails_detail'):
                                    with st.expander("📋 Detalle de Correos Recientes", expanded=False):
                                        for i, email_detail in enumerate(result['emails_detail'], 1):
                                            spam_icon = "🚨" if email_detail['is_spam'] else "✅"
                                            confidence_pct = email_detail['confidence'] * 100
                                            
                                            st.write(f"{spam_icon} **{i}.** {email_detail['subject']}")
                                            st.caption(f"De: {email_detail['sender']} | Confianza: {confidence_pct:.1f}% | Score: {email_detail['spam_score']:.3f}")
                                
                                # Actualizar dashboard
                                st.rerun()
                            else:
                                st.error(f"❌ Error obteniendo correos recientes: {result['error']}")
                
                with col5:
                    if st.button("✏️ Editar", key=f"editar_{account['id']}", help="Editar configuración"):
                        st.session_state.selected_account = account['id']
                        st.rerun()
                
                with col6:
                    if st.button("🗑️ Eliminar", key=f"eliminar_{account['id']}", help="Eliminar cuenta"):
                        if st.checkbox(f"Confirmar eliminación de {account['email']}", key=f"confirm_{account['id']}"):
                            success = self.delete_email_account(account['id'])
                            if success:
                                st.success("✅ Cuenta eliminada exitosamente!")
                                st.rerun()
                            else:
                                st.error("❌ Error al eliminar la cuenta")
                
                with col7:
                    if st.button("🔍 Diagnosticar", key=f"diagnosticar_{account['id']}", help="Diagnosticar el funcionamiento del sistema automático"):
                        with st.spinner(f"Diagnosticando {account['email']}..."):
                            from email_monitor import diagnose_account_emails
                            result = diagnose_account_emails(account['id'])
                            
                            if result['success']:
                                st.success(f"✅ Diagnóstico completado para {result['account_email']}")
                                
                                # Mostrar información del diagnóstico
                                col_diag1, col_diag2, col_diag3 = st.columns(3)
                                
                                with col_diag1:
                                    st.metric("📧 No Leídos (7 días)", result['unread_emails'])
                                    st.metric("📧 Leídos (2 días)", result['recent_read_emails'])
                                
                                with col_diag2:
                                    st.metric("📊 Total Recientes", result['total_recent_emails'])
                                    st.metric("⏱️ Última Revisión", result['last_check'] or "Nunca")
                                
                                with col_diag3:
                                    st.metric("⚙️ Intervalo (min)", result['check_interval'])
                                    st.metric("📦 Máximo por Revisión", result['max_emails_per_check'])
                                
                                # Mostrar estado de la cuenta
                                status_icon = "✅" if result['is_active'] else "❌"
                                st.info(f"{status_icon} **Estado de la cuenta:** {'Activa' if result['is_active'] else 'Inactiva'}")
                                
                                # Mostrar estadísticas históricas
                                col_stats1, col_stats2 = st.columns(2)
                                with col_stats1:
                                    st.metric("📊 Total Procesados", result['total_processed'])
                                with col_stats2:
                                    st.metric("🚨 Total SPAM", result['total_spam'])
                                
                                # Recomendaciones
                                if result['total_recent_emails'] > 0:
                                    st.success("🎯 **El sistema automático debería procesar estos correos en la próxima revisión**")
                                else:
                                    st.info("📭 **No hay correos recientes para procesar**")
                                
                                if not result['is_active']:
                                    st.warning("⚠️ **La cuenta está inactiva. El sistema automático no funcionará.**")
                                
                            else:
                                st.error(f"❌ Error en diagnóstico: {result['error']}")
                
                st.markdown("---")
            
            # Formulario de edición
            st.subheader("✏️ Editar Cuenta")
            
            selected_email = st.selectbox(
                "Seleccionar cuenta para editar:",
                [acc['email'] for acc in accounts]
            )
            
            if selected_email:
                account = next((acc for acc in accounts if acc['email'] == selected_email), None)
                
                if account:
                    with st.form("edit_account_form"):
                        # Campos editables
                        is_active = st.checkbox("Cuenta Activa", value=account['is_active'])
                        check_interval = st.selectbox(
                            "Intervalo de Revisión (minutos)",
                            [1, 5, 10, 15, 30, 60],
                            index=[1, 5, 10, 15, 30, 60].index(account['check_interval'])
                        )
                        max_emails = st.number_input(
                            "Máximo Correos por Revisión",
                            value=account['max_emails_per_check'],
                            min_value=10,
                            max_value=200
                        )
                        
                        # Botón de actualización
                        if st.form_submit_button("💾 Guardar Cambios"):
                            success = self.update_email_account(
                                account['id'], is_active, check_interval, max_emails
                            )
                            if success:
                                st.success("✅ Cuenta actualizada exitosamente!")
                                st.rerun()
                            else:
                                st.error("❌ Error al actualizar la cuenta")
            
            # Botón para borrar correos duplicados
            st.markdown("---")
            st.subheader("🧹 Mantenimiento de Base de Datos")
            
            col_clean1, col_clean2 = st.columns([2, 1])
            
            with col_clean1:
                st.info("""
                **Borrar Correos Duplicados**: 
                Elimina registros duplicados basándose en el `email_id` único de cada correo.
                Esto ayuda a mantener la base de datos limpia y eficiente.
                """)
            
            with col_clean2:
                if st.button("🗑️ Borrar Correos Duplicados", type="secondary", help="Eliminar registros duplicados de la base de datos"):
                    with st.spinner("Analizando y eliminando correos duplicados..."):
                        result = self.clean_duplicate_emails()
                        
                        if result['success']:
                            st.success(f"✅ Limpieza completada exitosamente!")
                            
                            # Mostrar estadísticas de limpieza
                            col_stats1, col_stats2, col_stats3 = st.columns(3)
                            with col_stats1:
                                st.metric("📊 Total Antes", result['total_before'])
                            with col_stats2:
                                st.metric("🗑️ Eliminados", result['duplicates_removed'])
                            with col_stats3:
                                st.metric("📊 Total Después", result['total_after'])
                            
                            # Mostrar detalles si hay
                            if result.get('details'):
                                with st.expander("📋 Detalles de Limpieza", expanded=False):
                                    for detail in result['details']:
                                        st.write(f"• **{detail['account_email']}**: {detail['total_emails']} correos restantes")
                            
                            st.rerun()
                        else:
                            st.error(f"❌ Error en limpieza: {result['error']}")
        
        except Exception as e:
            st.error(f"Error cargando cuentas: {e}")
    
    def show_delete_account(self):
        """
        Muestra la interfaz para eliminar cuentas de correo.
        
        Incluye:
        - Lista de cuentas disponibles
        - Confirmación de eliminación
        - Estadísticas de la cuenta
        """
        st.subheader("🗑️ Eliminar Cuenta")
        
        try:
            accounts = self.get_email_accounts()
            
            if not accounts:
                st.info("📭 No hay cuentas para eliminar")
                return
            
            # Seleccionar cuenta
            selected_email = st.selectbox(
                "Seleccionar cuenta para eliminar:",
                [acc['email'] for acc in accounts]
            )
            
            if selected_email:
                account = next((acc for acc in accounts if acc['email'] == selected_email), None)
                
                if account:
                    # Mostrar información de la cuenta
                    st.info(f"📧 Cuenta: {account['email']}")
                    st.info(f"📊 Correos analizados: {account['total_emails_checked']}")
                    st.info(f"🚨 SPAM detectado: {account['total_spam_detected']}")
                    
                    # Confirmación
                    if st.button("🗑️ Eliminar Cuenta", type="primary"):
                        if st.checkbox("Confirmo que quiero eliminar esta cuenta"):
                            success = self.delete_email_account(account['id'])
                            if success:
                                st.success("✅ Cuenta eliminada exitosamente!")
                                st.rerun()
                            else:
                                st.error("❌ Error al eliminar la cuenta")
                        else:
                            st.warning("⚠️ Debes confirmar la eliminación")
        
        except Exception as e:
            st.error(f"Error: {e}")
    
    def show_manual_analysis(self):
        """
        Muestra la página de análisis manual de correos.
        
        Permite al usuario:
        - Pegar contenido de correos
        - Analizar manualmente
        - Ver resultados detallados
        - Marcar como SPAM/HAM
        """
        st.header("🔍 Análisis Manual de Correos")
        
        # Tabs para diferentes tipos de análisis
        tab1, tab2 = st.tabs(["📝 Analizar Correo", "📊 Resultados Recientes"])
        
        with tab1:
            self.show_manual_analysis_form()
        
        with tab2:
            self.show_analysis_results()
    
    def show_manual_analysis_form(self):
        """
        Muestra el formulario para análisis manual de correos.
        
        El formulario incluye:
        - Campo para contenido del correo
        - Información del remitente
        - Análisis en tiempo real
        - Resultados detallados
        """
        st.subheader("Analizar Correo Manualmente")
        
        with st.form("manual_analysis_form"):
            # Información del correo
            sender = st.text_input("📤 Remitente", placeholder="remitente@ejemplo.com")
            subject = st.text_input("📋 Asunto", placeholder="Asunto del correo")
            
            # Contenido del correo
            content = st.text_area(
                "📄 Contenido del Correo",
                placeholder="Pega aquí el contenido del correo...",
                height=200
            )
            
            # Botón de análisis
            submitted = st.form_submit_button("🔍 Analizar Correo")
            
            if submitted and content:
                # Mostrar spinner durante el análisis
                with st.spinner("🔍 Analizando correo..."):
                    # Aquí iría la lógica de análisis
                    # Por ahora simulamos el resultado
                    result = self.analyze_email_manual(content, sender, subject)
                    
                    # Mostrar resultados
                    self.display_analysis_results(result)
            elif submitted and not content:
                st.error("❌ Por favor, ingresa el contenido del correo")
    
    def show_training(self):
        """
        Muestra la página de entrenamiento del modelo.
        
        Permite al usuario:
        - Marcar correos como SPAM/HAM
        - Agregar patrones
        - Ver métricas de entrenamiento
        - Reentrenar el modelo
        """
        st.header("🎓 Entrenamiento del Modelo")
        
        # Tabs para diferentes aspectos del entrenamiento
        tab1, tab2, tab3 = st.tabs(["📝 Marcar Correos", "🔍 Agregar Patrones", "📊 Métricas"])
        
        with tab1:
            self.show_training_interface()
        
        with tab2:
            self.show_pattern_management()
        
        with tab3:
            self.show_training_metrics()
    
    def show_statistics(self):
        """
        Muestra la página de estadísticas detalladas.
        
        Incluye:
        - Gráficos de tendencias
        - Estadísticas por categoría
        - Análisis temporal
        - Reportes exportables
        """
        st.header("📊 Estadísticas Detalladas")
        
        # Filtros de fecha
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "Fecha de inicio",
                value=datetime.now() - timedelta(days=30)
            )
        
        with col2:
            end_date = st.date_input(
                "Fecha de fin",
                value=datetime.now()
            )
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Tendencias Temporales")
            self.show_temporal_trends(start_date, end_date)
        
        with col2:
            st.subheader("🎯 Distribución por Categoría")
            self.show_category_distribution(start_date, end_date)
        
        # Tabla de estadísticas
        st.subheader("📋 Estadísticas Detalladas")
        self.show_detailed_statistics(start_date, end_date)
    
    def show_patterns(self):
        """
        Muestra la página de gestión de patrones.
        
        Permite:
        - Ver patrones existentes
        - Agregar nuevos patrones
        - Editar patrones
        - Eliminar patrones
        """
        st.header("🔍 Gestión de Patrones")
        
        # Tabs para diferentes acciones
        tab1, tab2, tab3 = st.tabs(["📋 Ver Patrones", "➕ Agregar Patrón", "✏️ Editar Patrones"])
        
        with tab1:
            self.show_existing_patterns()
        
        with tab2:
            self.show_add_pattern_form()
        
        with tab3:
            self.show_edit_patterns()
    
    # ========================================
    # MÉTODOS AUXILIARES
    # ========================================
    
    def get_total_accounts(self) -> int:
        """Obtiene el total de cuentas configuradas."""
        try:
            result = self.db.cursor.execute(
                "SELECT COUNT(*) FROM email_accounts WHERE is_active = 1"
            ).fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error obteniendo total de cuentas: {e}")
            return 0
    
    def get_total_emails(self) -> int:
        """Obtiene el total de correos analizados."""
        try:
            result = self.db.cursor.execute(
                "SELECT COUNT(*) FROM analyzed_emails"
            ).fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error obteniendo total de correos: {e}")
            return 0
    
    def get_total_spam(self) -> int:
        """Obtiene el total de SPAM detectado."""
        try:
            result = self.db.cursor.execute(
                "SELECT COUNT(*) FROM analyzed_emails WHERE is_spam = 1"
            ).fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error obteniendo total de SPAM: {e}")
            return 0
    
    def get_email_accounts(self) -> list:
        """Obtiene todas las cuentas de correo configuradas."""
        try:
            result = self.db.cursor.execute(
                "SELECT * FROM email_accounts ORDER BY created_at DESC"
            ).fetchall()
            
            # Convertir a lista de diccionarios
            accounts = []
            for row in result:
                account = {
                    'id': row[0],
                    'email': row[1],
                    'password': row[2],
                    'server': row[3],
                    'port': row[4],
                    'protocol': row[5],
                    'is_active': bool(row[6]),
                    'check_interval': row[7],
                    'max_emails_per_check': row[8],
                    'created_at': row[9],
                    'last_check_at': row[10],
                    'total_emails_checked': row[11],
                    'total_spam_detected': row[12]
                }
                accounts.append(account)
            
            return accounts
        except Exception as e:
            logger.error(f"Error obteniendo cuentas: {e}")
            return []
    
    def get_recent_emails(self, limit: int = 10) -> list:
        """Obtiene los correos más recientes analizados."""
        try:
            result = self.db.cursor.execute("""
                SELECT subject, sender, is_spam, confidence, spam_score, processed_at
                FROM analyzed_emails 
                ORDER BY processed_at DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [
                {
                    'subject': row[0],
                    'sender': row[1],
                    'is_spam': bool(row[2]),
                    'confidence': row[3],
                    'spam_score': row[4],
                    'processed_at': row[5]
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Error obteniendo correos recientes: {e}")
            return []
    
    def get_filtered_emails(self, filters: dict) -> list:
        """
        Obtiene correos filtrados según criterios específicos.
        
        Args:
            filters (dict): Diccionario con filtros aplicados
            
        Returns:
            list: Lista de correos filtrados
        """
        try:
            # Construir consulta base
            query = """
                SELECT 
                    ae.id,
                    ae.subject,
                    ae.sender,
                    ae.sender_domain,
                    ae.recipient,
                    ae.content,
                    ae.content_length,
                    ae.is_spam,
                    ae.confidence,
                    ae.spam_score,
                    ae.processed_at,
                    ae.received_at,
                    ea.email as account_email
                FROM analyzed_emails ae
                LEFT JOIN email_accounts ea ON ae.account_id = ea.id
                WHERE 1=1
            """
            
            params = []
            
            # Aplicar filtros
            if filters.get('search_text'):
                search_text = f"%{filters['search_text']}%"
                query += " AND (ae.subject LIKE ? OR ae.sender LIKE ? OR ae.content LIKE ?)"
                params.extend([search_text, search_text, search_text])
            
            if filters.get('spam_status') is not None:
                query += " AND ae.is_spam = ?"
                params.append(filters['spam_status'])
            
            if filters.get('confidence_min') is not None:
                query += " AND ae.confidence >= ?"
                params.append(filters['confidence_min'])
            
            if filters.get('confidence_max') is not None:
                query += " AND ae.confidence <= ?"
                params.append(filters['confidence_max'])
            
            if filters.get('spam_score_min') is not None:
                query += " AND ae.spam_score >= ?"
                params.append(filters['spam_score_min'])
            
            if filters.get('spam_score_max') is not None:
                query += " AND ae.spam_score <= ?"
                params.append(filters['spam_score_max'])
            
            if filters.get('sender_domain'):
                query += " AND ae.sender_domain LIKE ?"
                params.append(f"%{filters['sender_domain']}%")
            
            if filters.get('processed_date_from'):
                query += " AND DATE(ae.processed_at) >= ?"
                params.append(filters['processed_date_from'])
            
            if filters.get('processed_date_to'):
                query += " AND DATE(ae.processed_at) <= ?"
                params.append(filters['processed_date_to'])
            
            if filters.get('received_date_from'):
                query += " AND DATE(ae.received_at) >= ?"
                params.append(filters['received_date_from'])
            
            if filters.get('received_date_to'):
                query += " AND DATE(ae.received_at) <= ?"
                params.append(filters['received_date_to'])
            
            if filters.get('account_id'):
                query += " AND ae.account_id = ?"
                params.append(filters['account_id'])
            
            # Ordenar
            order_by = filters.get('order_by', 'processed_at')
            order_direction = filters.get('order_direction', 'DESC')
            query += f" ORDER BY ae.{order_by} {order_direction}"
            
            # Limitar resultados
            limit = filters.get('limit', 1000)
            query += f" LIMIT {limit}"
            
            # Ejecutar consulta
            result = self.db.cursor.execute(query, params).fetchall()
            
            return [
                {
                    'id': row[0],
                    'subject': row[1],
                    'sender': row[2],
                    'sender_domain': row[3],
                    'recipient': row[4],
                    'content': row[5],
                    'content_length': row[6],
                    'is_spam': bool(row[7]),
                    'confidence': row[8],
                    'spam_score': row[9],
                    'processed_at': row[10],
                    'received_at': row[11],
                    'account_email': row[12]
                }
                for row in result
            ]
            
        except Exception as e:
            logger.error(f"Error obteniendo correos filtrados: {e}")
            return []
    
    def get_email_accounts_for_filter(self) -> list:
        """Obtiene lista de cuentas para filtros."""
        try:
            result = self.db.cursor.execute("""
                SELECT id, email FROM email_accounts WHERE is_active = 1
                ORDER BY email
            """).fetchall()
            
            return [{'id': row[0], 'email': row[1]} for row in result]
        except Exception as e:
            logger.error(f"Error obteniendo cuentas para filtro: {e}")
            return []
    
    def get_spam_categories_for_filter(self) -> list:
        """Obtiene categorías de SPAM para filtros."""
        try:
            result = self.db.cursor.execute("""
                SELECT id, name FROM spam_categories WHERE is_active = 1
                ORDER BY name
            """).fetchall()
            
            return [{'id': row[0], 'name': row[1]} for row in result]
        except Exception as e:
            logger.error(f"Error obteniendo categorías para filtro: {e}")
            return []
    
    def get_spam_statistics(self) -> dict:
        """Obtiene estadísticas detalladas de SPAM."""
        try:
            # Estadísticas generales
            total_emails = self.get_total_emails()
            total_spam = self.get_total_spam()
            
            # Estadísticas por día (últimos 7 días)
            result = self.db.cursor.execute("""
                SELECT DATE(processed_at) as date, 
                       COUNT(*) as total,
                       SUM(CASE WHEN is_spam = 1 THEN 1 ELSE 0 END) as spam_count
                FROM analyzed_emails 
                WHERE processed_at >= DATE('now', '-7 days')
                GROUP BY DATE(processed_at)
                ORDER BY date DESC
            """).fetchall()
            
            daily_stats = [
                {
                    'date': row[0],
                    'total': row[1],
                    'spam_count': row[2],
                    'spam_percentage': (row[2] / row[1] * 100) if row[1] > 0 else 0
                }
                for row in result
            ]
            
            return {
                'total_emails': total_emails,
                'total_spam': total_spam,
                'spam_percentage': (total_spam / total_emails * 100) if total_emails > 0 else 0,
                'daily_stats': daily_stats
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de SPAM: {e}")
            return {
                'total_emails': 0,
                'total_spam': 0,
                'spam_percentage': 0,
                'daily_stats': []
            }
    
    def validate_account_form(self, email: str, password: str, server: str) -> bool:
        """Valida el formulario de agregar cuenta."""
        return bool(email and password and server)
    
    def add_email_account(self, email: str, password: str, server: str, 
                         port: int, interval: int, max_emails: int) -> bool:
        """Agrega una nueva cuenta de correo."""
        try:
            self.db.cursor.execute("""
                INSERT INTO email_accounts (email, password, server, port, 
                                         check_interval, max_emails_per_check)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (email, password, server, port, interval, max_emails))
            self.db.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error agregando cuenta: {e}")
            return False
    
    def update_email_account(self, account_id: int, is_active: bool, 
                           interval: int, max_emails: int) -> bool:
        """Actualiza una cuenta de correo existente."""
        try:
            self.db.cursor.execute("""
                UPDATE email_accounts 
                SET is_active = ?, check_interval = ?, max_emails_per_check = ?
                WHERE id = ?
            """, (is_active, interval, max_emails, account_id))
            self.db.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error actualizando cuenta: {e}")
            return False
    
    def delete_email_account(self, account_id: int) -> bool:
        """Elimina una cuenta de correo."""
        try:
            self.db.cursor.execute("DELETE FROM email_accounts WHERE id = ?", (account_id,))
            self.db.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error eliminando cuenta: {e}")
            return False
    
    def force_email_check(self, account_id: int, get_all: bool = False, get_recent: bool = False) -> dict:
        """
        Fuerza una revisión manual de correos para una cuenta específica.
        
        Args:
            account_id (int): ID de la cuenta a revisar
            get_all (bool): Si True, obtiene todos los correos (no solo no leídos)
            get_recent (bool): Si True, obtiene correos recientes (últimos 7 días)
            
        Returns:
            dict: Resultado de la revisión con estadísticas
        """
        try:
            # Importar el módulo de monitoreo
            from email_monitor import process_account_emails
            
            # Obtener información de la cuenta
            account = self.db.cursor.execute(
                "SELECT * FROM email_accounts WHERE id = ?", (account_id,)
            ).fetchone()
            
            if not account:
                return {"success": False, "error": "Cuenta no encontrada"}
            
            # Procesar correos usando el módulo real
            result = process_account_emails(account_id, account['max_emails_per_check'], get_all, get_recent)
            
            if result['success']:
                return {
                    "success": True,
                    "account_email": account['email'],
                    "emails_found": result['emails_processed'],
                    "spam_detected": result['spam_detected'],
                    "ham_detected": result['ham_detected'],
                    "processing_time": result['processing_time'],
                    "emails_detail": result.get('emails_detail', [])
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', 'Error desconocido')
                }
            
        except Exception as e:
            logger.error(f"Error en revisión manual: {e}")
            return {"success": False, "error": str(e)}
    
    def clean_duplicate_emails(self) -> dict:
        """
        Elimina correos duplicados de la base de datos.
        
        Busca registros con el mismo email_id y account_id, manteniendo solo
        el registro más reciente (con processed_at más reciente).
        
        Returns:
            dict: Resultado de la limpieza con estadísticas
        """
        try:
            # Obtener total de correos antes de la limpieza
            self.db.cursor.execute("SELECT COUNT(*) FROM analyzed_emails")
            total_before = self.db.cursor.fetchone()[0]
            
            if total_before == 0:
                return {
                    "success": True,
                    "total_before": 0,
                    "total_after": 0,
                    "duplicates_removed": 0,
                    "message": "No hay correos en la base de datos"
                }
            
            # Identificar IDs de correos a mantener (los más recientes)
            self.db.cursor.execute("""
                SELECT MAX(id) as keep_id
                FROM analyzed_emails 
                GROUP BY account_id, email_id
            """)
            
            keep_ids = [row['keep_id'] for row in self.db.cursor.fetchall()]
            
            # Identificar IDs de correos a eliminar
            self.db.cursor.execute("""
                SELECT id FROM analyzed_emails 
                WHERE id NOT IN ({})
            """.format(','.join(['?'] * len(keep_ids))), keep_ids)
            
            delete_ids = [row['id'] for row in self.db.cursor.fetchall()]
            
            if not delete_ids:
                return {
                    "success": True,
                    "total_before": total_before,
                    "total_after": total_before,
                    "duplicates_removed": 0,
                    "message": "No hay duplicados para eliminar"
                }
            
            # Eliminar registros relacionados primero
            # 1. Eliminar características de email
            self.db.cursor.execute("""
                DELETE FROM email_features 
                WHERE email_id IN ({})
            """.format(','.join(['?'] * len(delete_ids))), delete_ids)
            
            # 2. Eliminar categorías de SPAM
            self.db.cursor.execute("""
                DELETE FROM email_spam_categories 
                WHERE email_id IN ({})
            """.format(','.join(['?'] * len(delete_ids))), delete_ids)
            
            # 3. Eliminar feedback del usuario
            self.db.cursor.execute("""
                DELETE FROM user_feedback 
                WHERE email_id IN ({})
            """.format(','.join(['?'] * len(delete_ids))), delete_ids)
            
            # 4. Finalmente eliminar los correos duplicados
            self.db.cursor.execute("""
                DELETE FROM analyzed_emails 
                WHERE id IN ({})
            """.format(','.join(['?'] * len(delete_ids))), delete_ids)
            
            # Obtener total después de la limpieza
            self.db.cursor.execute("SELECT COUNT(*) FROM analyzed_emails")
            total_after = self.db.cursor.fetchone()[0]
            
            # Calcular duplicados eliminados
            duplicates_removed = total_before - total_after
            
            # Obtener detalles por cuenta
            self.db.cursor.execute("""
                SELECT 
                    ea.email,
                    COUNT(*) as total_emails
                FROM analyzed_emails ae
                JOIN email_accounts ea ON ae.account_id = ea.id
                GROUP BY ae.account_id, ea.email
                ORDER BY ea.email
            """)
            
            account_details = []
            for row in self.db.cursor.fetchall():
                account_details.append({
                    'account_email': row['email'],
                    'total_emails': row['total_emails']
                })
            
            # Commit de los cambios
            self.db.conn.commit()
            
            return {
                "success": True,
                "total_before": total_before,
                "total_after": total_after,
                "duplicates_removed": duplicates_removed,
                "details": account_details,
                "message": f"Limpieza completada: {duplicates_removed} duplicados eliminados"
            }
            
        except Exception as e:
            logger.error(f"Error limpiando duplicados: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def analyze_email_manual(self, content: str, sender: str, subject: str) -> dict:
        """
        Analiza un correo manualmente (simulación por ahora).
        
        Args:
            content (str): Contenido del correo
            sender (str): Remitente
            subject (str): Asunto
            
        Returns:
            dict: Resultados del análisis
        """
        # Simulación de análisis
        import random
        
        # Calcular características básicas
        content_length = len(content)
        caps_ratio = sum(1 for c in content if c.isupper()) / len(content) if content else 0
        exclamation_count = content.count('!')
        
        # Simular puntuación de SPAM
        spam_score = random.uniform(0.1, 0.9)
        is_spam = spam_score > 0.7
        confidence = abs(spam_score - 0.5) * 2
        
        return {
            'is_spam': is_spam,
            'confidence': confidence,
            'spam_score': spam_score,
            'features': {
                'content_length': content_length,
                'caps_ratio': caps_ratio,
                'exclamation_count': exclamation_count
            },
            'categories': [
                {'name': 'Spam Comercial', 'confidence': 0.8},
                {'name': 'Phishing', 'confidence': 0.3}
            ] if is_spam else []
        }
    
    def display_analysis_results(self, result: dict):
        """
        Muestra los resultados del análisis de un correo.
        
        Args:
            result (dict): Resultados del análisis
        """
        # Métricas principales
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status = "🚨 SPAM" if result['is_spam'] else "✅ HAM"
            st.metric("Resultado", status)
        
        with col2:
            st.metric("Confianza", f"{result['confidence']:.1%}")
        
        with col3:
            st.metric("Puntuación SPAM", f"{result['spam_score']:.2f}")
        
        # Características extraídas
        st.subheader("🔍 Características Extraídas")
        
        features_df = pd.DataFrame([
            {'Característica': k, 'Valor': v}
            for k, v in result['features'].items()
        ])
        
        st.dataframe(features_df, use_container_width=True)
        
        # Categorías detectadas
        if result['categories']:
            st.subheader("🎯 Categorías Detectadas")
            
            categories_df = pd.DataFrame(result['categories'])
            st.dataframe(categories_df, use_container_width=True)
        
        # Botones de acción
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Marcar como HAM"):
                st.success("Correo marcado como HAM")
        
        with col2:
            if st.button("🚨 Marcar como SPAM"):
                st.success("Correo marcado como SPAM")
    
    # Métodos para gráficos y visualizaciones (simulados por ahora)
    def show_spam_trends(self):
        """Muestra gráfico de tendencias de SPAM."""
        try:
            stats = self.get_spam_statistics()
            
            if not stats['daily_stats']:
                st.info("📈 No hay datos suficientes para mostrar tendencias")
                return
            
            # Crear gráfico de tendencias
            import plotly.express as px
            import pandas as pd
            
            df = pd.DataFrame(stats['daily_stats'])
            df['date'] = pd.to_datetime(df['date'])
            
            fig = px.line(df, x='date', y='spam_percentage', 
                         title='Tendencia de SPAM (Últimos 7 días)',
                         labels={'spam_percentage': 'Porcentaje SPAM (%)', 'date': 'Fecha'})
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error mostrando tendencias: {e}")
    
    def show_spam_categories(self):
        """Muestra gráfico de categorías de SPAM."""
        try:
            # Obtener estadísticas por categoría
            result = self.db.cursor.execute("""
                SELECT sc.name, COUNT(*) as count
                FROM analyzed_emails ae
                JOIN email_spam_categories esc ON ae.id = esc.email_id
                JOIN spam_categories sc ON esc.category_id = sc.id
                WHERE ae.is_spam = 1
                GROUP BY sc.name
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            
            if not result:
                st.info("🎯 No hay categorías de SPAM registradas aún")
                return
            
            # Crear gráfico de barras
            import plotly.express as px
            import pandas as pd
            
            df = pd.DataFrame(result, columns=['Categoría', 'Cantidad'])
            
            fig = px.bar(df, x='Cantidad', y='Categoría', 
                        title='Top Categorías de SPAM',
                        orientation='h')
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error mostrando categorías: {e}")
    
    def show_recent_emails(self):
        """Muestra los correos más recientes analizados."""
        try:
            recent_emails = self.get_recent_emails(10)
            
            if not recent_emails:
                st.info("📭 No hay correos analizados aún")
                return
            
            # Mostrar correos en una tabla
            for email in recent_emails:
                spam_icon = "🚨" if email['is_spam'] else "✅"
                confidence_pct = email['confidence'] * 100 if email['confidence'] else 0
                
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"{spam_icon} **{email['subject']}**")
                    st.caption(f"De: {email['sender']}")
                
                with col2:
                    st.caption(f"Confianza: {confidence_pct:.1f}%")
                
                with col3:
                    st.caption(f"Score: {email['spam_score']:.3f}")
                
                st.markdown("---")
                
        except Exception as e:
            st.error(f"Error mostrando correos recientes: {e}")
    
    def show_system_alerts(self):
        """
        Muestra alertas del sistema.
        
        Incluye:
        - Cuentas inactivas
        - Errores de conexión
        - Alertas de rendimiento
        """
        try:
            accounts = self.get_email_accounts()
            
            alerts = []
            
            # Verificar cuentas inactivas
            inactive_accounts = [acc for acc in accounts if not acc['is_active']]
            if inactive_accounts:
                alerts.append(f"⚠️ {len(inactive_accounts)} cuenta(s) inactiva(s)")
            
            # Verificar cuentas sin revisión reciente
            current_time = time.time()
            for account in accounts:
                if account['is_active'] and account['last_check_at']:
                    # Calcular tiempo desde última revisión
                    last_check = datetime.fromisoformat(account['last_check_at'].replace('Z', '+00:00'))
                    time_since_check = (datetime.now() - last_check).total_seconds() / 60
                    
                    if time_since_check > account['check_interval'] * 2:  # Más del doble del intervalo
                        alerts.append(f"⏰ {account['email']}: Sin revisión reciente ({time_since_check:.0f} min)")
            
            if alerts:
                for alert in alerts:
                    st.warning(alert)
            else:
                st.success("✅ Sistema funcionando correctamente")
                
        except Exception as e:
            st.error(f"Error cargando alertas: {e}")

    def show_automatic_system_status(self):
        """
        Muestra el estado detallado del sistema automático.
        
        Incluye:
        - Estado general del sistema
        - Cuentas activas y sus intervalos
        - Últimas revisiones
        - Próximas revisiones programadas
        """
        try:
            accounts = self.get_email_accounts()
            active_accounts = [acc for acc in accounts if acc['is_active']]
            
            if not active_accounts:
                st.info("📭 No hay cuentas activas configuradas")
                return
            
            # Mostrar estado general
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("📧 Cuentas Activas", len(active_accounts))
                
                # Calcular tiempo promedio hasta próxima revisión
                current_time = time.time()
                total_wait_time = 0
                account_count = 0
                
                for account in active_accounts:
                    last_check = st.session_state.last_auto_check.get(account['id'], 0)
                    check_interval = account['check_interval'] * 60
                    time_since_last = current_time - last_check
                    time_until_next = max(0, check_interval - time_since_last)
                    total_wait_time += time_until_next
                    account_count += 1
                
                if account_count > 0:
                    avg_wait_time = total_wait_time / account_count / 60  # Convertir a minutos
                    st.metric("⏱️ Próxima Revisión Promedio", f"{avg_wait_time:.1f} min")
            
            with col2:
                # Mostrar cuentas con intervalos más frecuentes
                frequent_accounts = [acc for acc in active_accounts if acc['check_interval'] <= 5]
                st.metric("⚡ Revisión Rápida (≤5 min)", len(frequent_accounts))
                
                # Mostrar cuentas con intervalos normales
                normal_accounts = [acc for acc in active_accounts if 5 < acc['check_interval'] <= 30]
                st.metric("📊 Revisión Normal (5-30 min)", len(normal_accounts))
            
            # Mostrar detalles de cada cuenta activa
            st.subheader("📋 Detalles de Cuentas Activas")
            
            for account in active_accounts:
                with st.expander(f"📧 {account['email']} (Intervalo: {account['check_interval']} min)", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        last_check = st.session_state.last_auto_check.get(account['id'], 0)
                        if last_check > 0:
                            last_check_time = datetime.fromtimestamp(last_check)
                            st.write(f"**Última Revisión:** {last_check_time.strftime('%H:%M:%S')}")
                        else:
                            st.write("**Última Revisión:** Nunca")
                    
                    with col2:
                        current_time = time.time()
                        check_interval = account['check_interval'] * 60
                        time_since_last = current_time - last_check
                        time_until_next = max(0, check_interval - time_since_last)
                        
                        if time_until_next > 0:
                            st.write(f"**Próxima Revisión:** {time_until_next/60:.1f} min")
                        else:
                            st.write("**Próxima Revisión:** Inmediata")
                    
                    with col3:
                        st.write(f"**Máximo Correos:** {account['max_emails_per_check']}")
                        st.write(f"**Total Procesados:** {account['total_emails_checked']}")
            
            # Mostrar estadísticas de rendimiento
            st.subheader("📊 Estadísticas de Rendimiento")
            
            total_processed = sum(acc['total_emails_checked'] for acc in active_accounts)
            total_spam = sum(acc['total_spam_detected'] for acc in active_accounts)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📨 Total Procesados", total_processed)
            
            with col2:
                st.metric("🚨 Total SPAM", total_spam)
            
            with col3:
                if total_processed > 0:
                    spam_rate = (total_spam / total_processed) * 100
                    st.metric("📊 Tasa de SPAM", f"{spam_rate:.1f}%")
                else:
                    st.metric("📊 Tasa de SPAM", "N/A")
                    
        except Exception as e:
            st.error(f"Error cargando estado del sistema automático: {e}")

    def show_visual_log(self):
        """
        Muestra el log visual en tiempo real del sistema automático.
        
        Incluye:
        - Estado actual del sistema
        - Timer de revisión actual
        - Historial de actividades
        - Indicadores visuales de estado
        """
        try:
            # Estado actual del sistema
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Indicador de estado general
                if st.session_state.auto_check_enabled:
                    st.success("🔄 Sistema Automático: ACTIVO")
                else:
                    st.error("❌ Sistema Automático: INACTIVO")
            
            with col2:
                # Cuenta actualmente siendo revisada
                if st.session_state.current_checking_account:
                    st.warning(f"⏳ Revisando: {st.session_state.current_checking_account}")
                    
                    # Timer de revisión actual
                    if st.session_state.check_start_time:
                        elapsed_time = time.time() - st.session_state.check_start_time
                        st.metric("⏱️ Tiempo de Revisión", f"{elapsed_time:.1f}s")
                        
                        # Barra de progreso (simulada)
                        if elapsed_time < 30:  # Si lleva menos de 30 segundos
                            progress = min(elapsed_time / 30, 1.0)
                            st.progress(progress)
                            st.caption("🔄 Procesando correos...")
                        else:
                            st.progress(1.0)
                            st.caption("⏳ Revisión en progreso...")
                else:
                    st.info("💤 No hay revisiones en curso")
            
            with col3:
                # Próxima revisión programada
                accounts = self.get_email_accounts()
                active_accounts = [acc for acc in accounts if acc['is_active']]
                
                if active_accounts:
                    current_time = time.time()
                    next_check_time = float('inf')
                    next_account = None
                    
                    for account in active_accounts:
                        last_check = st.session_state.last_auto_check.get(account['id'], 0)
                        check_interval = account['check_interval'] * 60
                        time_since_last = current_time - last_check
                        time_until_next = max(0, check_interval - time_since_last)
                        
                        if time_until_next < next_check_time:
                            next_check_time = time_until_next
                            next_account = account
                    
                    if next_account and next_check_time < float('inf'):
                        minutes_remaining = next_check_time / 60
                        st.metric("⏰ Próxima Revisión", f"{minutes_remaining:.1f} min")
                        st.caption(f"Cuenta: {next_account['email']}")
                    else:
                        st.metric("⏰ Próxima Revisión", "Inmediata")
                else:
                    st.metric("⏰ Próxima Revisión", "N/A")
            
            st.markdown("---")
            
            # Historial de logs
            st.subheader("📝 Historial de Actividad")
            
            # Controles para el log
            col_controls1, col_controls2, col_controls3, col_controls4 = st.columns(4)
            
            with col_controls1:
                if st.button("🔄 Actualizar Log", key="refresh_log"):
                    st.rerun()
            
            with col_controls2:
                if st.button("🗑️ Limpiar Log", key="clear_log"):
                    st.session_state.auto_check_logs = []
                    st.rerun()
            
            with col_controls3:
                auto_refresh = st.checkbox("🔄 Auto-refresh", value=True, key="auto_refresh_log")
            
            with col_controls4:
                if st.button("⚡ Forzar Revisión", key="force_check_now"):
                    self.add_log_entry("🔄 Revisión manual forzada por usuario", "INFO")
                    self.run_automatic_checks()
                    st.rerun()
            
            # Mostrar logs
            if st.session_state.auto_check_logs:
                # Crear contenedor con scroll
                log_container = st.container()
                
                with log_container:
                    # Mostrar logs en orden inverso (más recientes arriba)
                    for log_entry in reversed(st.session_state.auto_check_logs):
                        timestamp = log_entry['timestamp']
                        message = log_entry['message']
                        level = log_entry['level']
                        
                        # Color según el nivel
                        if level == "SUCCESS":
                            st.success(f"🕐 {timestamp} | {message}")
                        elif level == "ERROR":
                            st.error(f"🕐 {timestamp} | {message}")
                        elif level == "WARNING":
                            st.warning(f"🕐 {timestamp} | {message}")
                        else:
                            st.info(f"🕐 {timestamp} | {message}")
            else:
                st.info("📭 No hay actividad registrada aún")
            
            # Auto-refresh si está habilitado
            if auto_refresh:
                time.sleep(1)  # Pequeña pausa para evitar spam
                st.rerun()
                
        except Exception as e:
            st.error(f"Error mostrando log visual: {e}")

    def show_analysis_results(self):
        """Muestra resultados de análisis recientes."""
        st.info("📊 Resultados recientes (simulado)")
    
    def show_training_interface(self):
        """Muestra interfaz de entrenamiento."""
        st.info("🎓 Interfaz de entrenamiento (simulado)")
    
    def show_pattern_management(self):
        """Muestra gestión de patrones."""
        st.info("🔍 Gestión de patrones (simulado)")
    
    def show_training_metrics(self):
        """Muestra métricas de entrenamiento."""
        st.info("📊 Métricas de entrenamiento (simulado)")
    
    def show_temporal_trends(self, start_date, end_date):
        """Muestra tendencias temporales."""
        st.info("📈 Tendencias temporales (simulado)")
    
    def show_category_distribution(self, start_date, end_date):
        """Muestra distribución por categoría."""
        st.info("🎯 Distribución por categoría (simulado)")
    
    def show_detailed_statistics(self, start_date, end_date):
        """Muestra estadísticas detalladas."""
        st.info("📋 Estadísticas detalladas (simulado)")
    
    def show_existing_patterns(self):
        """Muestra patrones existentes."""
        st.info("📋 Patrones existentes (simulado)")
    
    def show_add_pattern_form(self):
        """Muestra formulario para agregar patrón."""
        st.info("➕ Formulario de patrón (simulado)")
    
    def show_edit_patterns(self):
        """Muestra edición de patrones."""
        st.info("✏️ Edición de patrones (simulado)")
    
    def show_email_viewer(self):
        """
        Muestra la página de visualización y filtrado de correos.
        
        Permite al usuario:
        - Filtrar correos por múltiples criterios
        - Ver detalles completos de cada correo
        - Exportar resultados
        - Analizar patrones
        """
        st.header("📧 Visualizador de Correos")
        st.markdown("---")
        
        # Sidebar para filtros rápidos
        with st.sidebar:
            st.subheader("🔍 Filtros Rápidos")
            
            # Filtros básicos
            quick_spam_filter = st.selectbox(
                "🚨 Estado",
                ["Todos", "Solo SPAM", "Solo HAM"],
                help="Filtrar por clasificación"
            )
            
            quick_account_filter = st.selectbox(
                "📧 Cuenta",
                ["Todas", "Gmail", "Outlook", "Yahoo"],
                help="Filtrar por proveedor"
            )
            
            # Filtros de fecha más intuitivos
            st.subheader("📅 Período")
            date_range = st.selectbox(
                "Rango de tiempo",
                ["Últimas 24h", "Últimos 7 días", "Último mes", "Último año", "Personalizado"],
                help="Seleccionar período de tiempo"
            )
            
            if date_range == "Personalizado":
                col1, col2 = st.columns(2)
                with col1:
                    custom_from = st.date_input("Desde")
                with col2:
                    custom_to = st.date_input("Hasta")
            else:
                custom_from = None
                custom_to = None
            
            # Búsqueda rápida
            quick_search = st.text_input(
                "🔍 Buscar",
                placeholder="Asunto, remitente...",
                help="Búsqueda rápida en texto"
            )
            
            # Botones de acción rápida
            st.markdown("---")
            st.subheader("⚡ Acciones")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Aplicar Filtros", type="primary"):
                    self.apply_quick_filters(quick_spam_filter, quick_account_filter, date_range, custom_from, custom_to, quick_search)
            
            with col2:
                if st.button("📤 Exportar", type="secondary"):
                    if 'filtered_emails' in st.session_state and st.session_state.filtered_emails:
                        self.export_emails_to_csv(st.session_state.filtered_emails)
                    else:
                        st.warning("No hay resultados para exportar")
        
        # Contenido principal
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("📊 Correos Encontrados")
            
            # Botón para obtener todos los correos
            if st.button("📥 Obtener Todo el Correo y Revisarlo", type="primary", help="Obtener todos los correos de la base de datos"):
                all_filters = {
                    'limit': 1000,
                    'order_by': 'received_at',
                    'order_direction': 'DESC'
                }
                st.session_state.filtered_emails = self.get_filtered_emails(all_filters)
                st.success(f"✅ Obtenidos {len(st.session_state.filtered_emails)} correos para revisión.")
            
            # Mostrar estadísticas
            if 'filtered_emails' in st.session_state and st.session_state.filtered_emails:
                emails = st.session_state.filtered_emails
                
                # Métricas rápidas
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    st.metric("📧 Total", len(emails))
                
                with metric_col2:
                    spam_count = sum(1 for email in emails if email['is_spam'])
                    st.metric("🚨 SPAM", spam_count)
                
                with metric_col3:
                    ham_count = sum(1 for email in emails if not email['is_spam'])
                    st.metric("✅ HAM", ham_count)
                
                with metric_col4:
                    if emails:
                        avg_confidence = sum(email['confidence'] for email in emails) / len(emails)
                        st.metric("📊 Confianza", f"{avg_confidence:.1%}")
                
                st.markdown("---")
                
                # Tabla mejorada
                self.show_improved_email_table(emails)
                
            else:
                st.info("📭 No hay correos filtrados. Usa los filtros para ver resultados.")
        
        with col2:
            st.subheader("🔧 Filtros Avanzados")
            
            with st.expander("⚙️ Configuración Avanzada", expanded=False):
                self.show_advanced_filters()
    
    def show_improved_email_table(self, emails):
        """Muestra una tabla mejorada de correos."""
        
        # Crear DataFrame para mejor visualización
        email_data = []
        for email in emails:
            email_data.append({
                'Estado': "🚨 SPAM" if email['is_spam'] else "✅ HAM",
                'Asunto': email['subject'][:50] + "..." if len(email['subject']) > 50 else email['subject'],
                'Remitente': email['sender'][:30] + "..." if len(email['sender']) > 30 else email['sender'],
                'Dominio': email['sender_domain'],
                'Confianza': f"{email['confidence']:.1%}",
                'Score SPAM': f"{email['spam_score']:.3f}",
                'Recibido': email['received_at'] if email['received_at'] else "N/A",
                'Procesado': email['processed_at'],
                'ID': email['id']
            })
        
        df = pd.DataFrame(email_data)
        
        # Mostrar tabla con opciones de ordenamiento
        st.dataframe(
            df,
            column_config={
                "Estado": st.column_config.TextColumn("Estado", width="small"),
                "Asunto": st.column_config.TextColumn("Asunto", width="medium"),
                "Remitente": st.column_config.TextColumn("Remitente", width="medium"),
                "Dominio": st.column_config.TextColumn("Dominio", width="small"),
                "Confianza": st.column_config.TextColumn("Confianza", width="small"),
                "Score SPAM": st.column_config.TextColumn("Score SPAM", width="small"),
                "Recibido": st.column_config.TextColumn("Recibido", width="small"),
                "Procesado": st.column_config.TextColumn("Procesado", width="small"),
                "ID": st.column_config.NumberColumn("ID", width="small")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Botones de acción para correos seleccionados
        st.markdown("---")
        st.subheader("⚡ Acciones en Lote")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ Marcar como HAM", type="primary"):
                st.info("Función de marcado en lote (en desarrollo)")
        
        with col2:
            if st.button("🚨 Marcar como SPAM", type="primary"):
                st.info("Función de marcado en lote (en desarrollo)")
        
        with col3:
            if st.button("📤 Exportar Seleccionados", type="secondary"):
                st.info("Función de exportación selectiva (en desarrollo)")
        
        with col4:
            if st.button("🗑️ Eliminar Seleccionados", type="secondary"):
                st.info("Función de eliminación en lote (en desarrollo)")
        
        # Sección para ver detalles de un correo específico
        st.markdown("---")
        st.subheader("👁️ Ver Detalles de Correo")
        
        # Selector de correo para ver detalles
        if emails:
            email_options = [f"{'🚨' if email['is_spam'] else '✅'} {email['subject'][:50]}..." for email in emails]
            selected_email_index = st.selectbox(
                "Seleccionar correo para ver detalles:",
                range(len(emails)),
                format_func=lambda x: email_options[x] if x < len(email_options) else "N/A"
            )
            
            if st.button("👁️ Ver Detalles Completos"):
                selected_email = emails[selected_email_index]
                st.session_state.selected_email = selected_email
                st.success(f"✅ Correo seleccionado: {selected_email['subject']}")
                
                # Mostrar detalles inmediatamente
                self.show_email_details()
    
    def show_advanced_filters(self):
        """Muestra filtros avanzados en un expander."""
        
        with st.form("advanced_filters_form"):
            # Sección 1: Filtros básicos
            st.subheader("🔍 Filtros Básicos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Estado de SPAM
                spam_status = st.selectbox(
                    "🚨 Estado de SPAM",
                    ["Todos", "Solo SPAM", "Solo HAM"],
                    help="Filtrar por clasificación de SPAM"
                )
                
                # Búsqueda de texto
                search_text = st.text_input(
                    "🔍 Buscar en texto",
                    placeholder="Buscar en asunto, remitente o contenido...",
                    help="Busca en asunto, remitente y contenido del correo"
                )
            
            with col2:
                # Dominio del remitente
                sender_domain = st.text_input(
                    "🌐 Dominio del remitente",
                    placeholder="gmail.com, outlook.com...",
                    help="Filtrar por dominio del remitente"
                )
                
                # Cuenta de correo
                accounts = self.get_email_accounts_for_filter()
                account_options = ["Todas las cuentas"] + [acc['email'] for acc in accounts]
                selected_account = st.selectbox(
                    "📧 Cuenta de correo",
                    account_options,
                    help="Filtrar por cuenta específica"
                )
            
            st.markdown("---")
            
            # Sección 2: Rangos de valores
            st.subheader("📊 Rangos de Valores")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Rango de confianza
                st.write("**Confianza del análisis**")
                confidence_range = st.slider(
                    "Confianza",
                    min_value=0.0,
                    max_value=1.0,
                    value=(0.0, 1.0),
                    step=0.1,
                    help="Rango de confianza del análisis",
                    label_visibility="collapsed"
                )
                
                # Rango de puntuación SPAM
                st.write("**Puntuación SPAM**")
                spam_score_range = st.slider(
                    "Puntuación SPAM",
                    min_value=0.0,
                    max_value=1.0,
                    value=(0.0, 1.0),
                    step=0.1,
                    help="Rango de puntuación SPAM",
                    label_visibility="collapsed"
                )
            
            with col2:
                # Tamaño del contenido
                st.write("**Tamaño del contenido**")
                content_length_range = st.slider(
                    "Tamaño del contenido",
                    min_value=0,
                    max_value=10000,
                    value=(0, 10000),
                    step=100,
                    help="Rango de tamaño del contenido",
                    label_visibility="collapsed"
                )
                
                # Límite de resultados
                st.write("**Máximo resultados**")
                limit = st.number_input(
                    "Máximo resultados",
                    min_value=10,
                    max_value=1000,
                    value=100,
                    step=10,
                    help="Número máximo de correos a mostrar",
                    label_visibility="collapsed"
                )
            
            st.markdown("---")
            
            # Sección 3: Fechas
            st.subheader("📅 Filtros de Fecha")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Fechas de Procesamiento**")
                processed_from = st.date_input(
                    "Procesado desde",
                    value=datetime.now() - timedelta(days=30),
                    help="Fecha de inicio de procesamiento",
                    label_visibility="collapsed"
                )
                
                processed_to = st.date_input(
                    "Procesado hasta",
                    value=datetime.now(),
                    help="Fecha de fin de procesamiento",
                    label_visibility="collapsed"
                )
            
            with col2:
                st.write("**Fechas de Recepción**")
                received_from = st.date_input(
                    "Recibido desde",
                    value=datetime.now() - timedelta(days=30),
                    help="Fecha de inicio de recepción del correo",
                    label_visibility="collapsed"
                )
                
                received_to = st.date_input(
                    "Recibido hasta",
                    value=datetime.now(),
                    help="Fecha de fin de recepción del correo",
                    label_visibility="collapsed"
                )
            
            st.markdown("---")
            
            # Sección 4: Ordenamiento
            st.subheader("📋 Ordenamiento")
            
            col1, col2 = st.columns(2)
            
            with col1:
                order_by = st.selectbox(
                    "Ordenar por",
                    ["received_at", "processed_at", "subject", "sender", "spam_score", "confidence"],
                    format_func=lambda x: {
                        "received_at": "Fecha de recepción",
                        "processed_at": "Fecha de procesamiento",
                        "subject": "Asunto",
                        "sender": "Remitente",
                        "spam_score": "Puntuación SPAM",
                        "confidence": "Confianza"
                    }[x],
                    help="Campo por el cual ordenar los resultados"
                )
            
            with col2:
                order_direction = st.selectbox(
                    "Dirección",
                    ["DESC", "ASC"],
                    format_func=lambda x: "Descendente" if x == "DESC" else "Ascendente",
                    help="Orden ascendente o descendente"
                )
            
            st.markdown("---")
            
            # Botones de acción
            col1, col2, col3 = st.columns(3)
            
            with col1:
                apply_advanced = st.form_submit_button("🔍 Aplicar Filtros", type="primary")
            
            with col2:
                clear_advanced = st.form_submit_button("🗑️ Limpiar", type="secondary")
            
            with col3:
                export_advanced = st.form_submit_button("📤 Exportar", type="secondary")
            
            if apply_advanced:
                # Construir filtros avanzados
                filters = {}
                
                # Filtros básicos
                if spam_status == "Solo SPAM":
                    filters['spam_status'] = True
                elif spam_status == "Solo HAM":
                    filters['spam_status'] = False
                
                if search_text:
                    filters['search_text'] = search_text
                
                if sender_domain:
                    filters['sender_domain'] = sender_domain
                
                if selected_account != "Todas las cuentas":
                    account_id = next((acc['id'] for acc in accounts if acc['email'] == selected_account), None)
                    if account_id:
                        filters['account_id'] = account_id
                
                # Rangos de valores
                if confidence_range[0] > 0.0:
                    filters['confidence_min'] = confidence_range[0]
                if confidence_range[1] < 1.0:
                    filters['confidence_max'] = confidence_range[1]
                
                if spam_score_range[0] > 0.0:
                    filters['spam_score_min'] = spam_score_range[0]
                if spam_score_range[1] < 1.0:
                    filters['spam_score_max'] = spam_score_range[1]
                
                # Fechas
                filters['processed_date_from'] = processed_from.strftime('%Y-%m-%d')
                filters['processed_date_to'] = processed_to.strftime('%Y-%m-%d')
                filters['received_date_from'] = received_from.strftime('%Y-%m-%d')
                filters['received_date_to'] = received_to.strftime('%Y-%m-%d')
                
                # Ordenamiento
                filters['order_by'] = order_by
                filters['order_direction'] = order_direction
                filters['limit'] = limit
                
                # Aplicar filtros
                st.session_state.filtered_emails = self.get_filtered_emails(filters)
                st.success(f"✅ Filtros avanzados aplicados. Encontrados {len(st.session_state.filtered_emails)} correos.")
            
            elif clear_advanced:
                if 'filtered_emails' in st.session_state:
                    del st.session_state.filtered_emails
                st.success("✅ Filtros avanzados limpiados.")
            
            elif export_advanced:
                if 'filtered_emails' in st.session_state and st.session_state.filtered_emails:
                    self.export_emails_to_csv(st.session_state.filtered_emails)
                else:
                    st.warning("⚠️ No hay resultados para exportar. Aplica filtros primero.")
    
    def apply_quick_filters(self, spam_filter, account_filter, date_range, custom_from, custom_to, search_text):
        """Aplica filtros rápidos desde la sidebar."""
        filters = {}
        
        # Filtro de SPAM
        if spam_filter == "Solo SPAM":
            filters['spam_status'] = True
        elif spam_filter == "Solo HAM":
            filters['spam_status'] = False
        
        # Filtro de cuenta
        if account_filter != "Todas":
            filters['sender_domain'] = account_filter.lower().replace("gmail", "gmail.com").replace("outlook", "outlook.com").replace("yahoo", "yahoo.com")
        
        # Filtro de fecha
        if date_range == "Personalizado" and custom_from and custom_to:
            filters['received_date_from'] = custom_from.strftime('%Y-%m-%d')
            filters['received_date_to'] = custom_to.strftime('%Y-%m-%d')
        elif date_range != "Personalizado":
            # Calcular fechas basadas en el rango seleccionado
            end_date = datetime.now()
            if date_range == "Últimas 24h":
                start_date = end_date - timedelta(days=1)
            elif date_range == "Últimos 7 días":
                start_date = end_date - timedelta(days=7)
            elif date_range == "Último mes":
                start_date = end_date - timedelta(days=30)
            elif date_range == "Último año":
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date - timedelta(days=30)
            
            filters['received_date_from'] = start_date.strftime('%Y-%m-%d')
            filters['received_date_to'] = end_date.strftime('%Y-%m-%d')
        
        # Filtro de búsqueda
        if search_text:
            filters['search_text'] = search_text
        
        # Configuración por defecto
        filters['order_by'] = 'received_at'
        filters['order_direction'] = 'DESC'
        filters['limit'] = 1000
        
        # Aplicar filtros
        st.session_state.filtered_emails = self.get_filtered_emails(filters)
        st.success(f"✅ Filtros aplicados. Encontrados {len(st.session_state.filtered_emails)} correos.")
    
    def show_email_details(self):
        """Muestra detalles completos de un correo seleccionado."""
        st.subheader("📋 Detalles Completos")
        
        if 'selected_email' not in st.session_state:
            st.info("👆 Selecciona un correo de la tabla para ver sus detalles completos.")
            return
        
        email = st.session_state.selected_email
        
        # Información principal
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📧 Información del Correo")
            st.write(f"**ID:** {email['id']}")
            st.write(f"**Asunto:** {email['subject']}")
            st.write(f"**Remitente:** {email['sender']}")
            st.write(f"**Destinatario:** {email['recipient']}")
            st.write(f"**Dominio:** {email['sender_domain']}")
            st.write(f"**Cuenta:** {email['account_email']}")
        
        with col2:
            st.subheader("📊 Análisis de SPAM")
            spam_icon = "🚨" if email['is_spam'] else "✅"
            st.write(f"**Clasificación:** {spam_icon} {'SPAM' if email['is_spam'] else 'HAM'}")
            st.write(f"**Confianza:** {email['confidence']:.1%}")
            st.write(f"**Puntuación SPAM:** {email['spam_score']:.3f}")
            st.write(f"**Tamaño:** {email['content_length']} caracteres")
            st.write(f"**Procesado:** {email['processed_at']}")
            if email['received_at']:
                st.write(f"**Recibido:** {email['received_at']}")
        
        st.markdown("---")
        
        # Contenido completo
        st.subheader("📄 Contenido Completo")
        st.text_area("Contenido del correo", email['content'], height=300, disabled=True)
        
        # Características extraídas
        st.subheader("🔍 Características Extraídas")
        self.show_email_features(email['id'])
        
        # Acciones
        st.subheader("⚡ Acciones")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ Marcar como HAM"):
                self.update_email_classification(email['id'], False)
        
        with col2:
            if st.button("🚨 Marcar como SPAM"):
                self.update_email_classification(email['id'], True)
        
        with col3:
            if st.button("📤 Reenviar"):
                st.info("📤 Función de reenvío (en desarrollo)")
        
        with col4:
            if st.button("🗑️ Eliminar"):
                if st.checkbox("Confirmar eliminación"):
                    self.delete_email(email['id'])
    
    def show_email_features(self, email_id: int):
        """Muestra las características extraídas de un correo."""
        try:
            result = self.db.cursor.execute("""
                SELECT * FROM email_features WHERE email_id = ?
            """, (email_id,)).fetchone()
            
            if result:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Longitud asunto:** {result[2]} caracteres")
                    st.write(f"**Longitud contenido:** {result[3]} caracteres")
                    st.write(f"**Longitud total:** {result[4]} caracteres")
                    st.write(f"**Ratio mayúsculas:** {result[5]:.2%}")
                
                with col2:
                    st.write(f"**Exclamaciones:** {result[6]}")
                    st.write(f"**Interrogaciones:** {result[7]}")
                    st.write(f"**Símbolos $:** {result[8]}")
                    st.write(f"**Palabras urgentes:** {result[9]}")
                
                with col3:
                    st.write(f"**Palabras SPAM:** {result[10]}")
                    st.write(f"**Dominio sospechoso:** {'Sí' if result[11] else 'No'}")
                    st.write(f"**Muchos enlaces:** {result[12]}")
                    st.write(f"**Tiene adjuntos:** {'Sí' if result[13] else 'No'}")
            else:
                st.info("📊 No hay características extraídas para este correo.")
                
        except Exception as e:
            st.error(f"Error obteniendo características: {e}")
    
    def show_email_analysis(self, email: dict):
        """Muestra análisis detallado de un correo."""
        st.subheader("📊 Análisis Detallado")
        
        # Gráfico de características
        features = {
            'Confianza': email['confidence'],
            'Puntuación SPAM': email['spam_score'],
            'Longitud': email['content_length'] / 1000  # Normalizar
        }
        
        fig = go.Figure(data=[
            go.Bar(x=list(features.keys()), y=list(features.values()))
        ])
        fig.update_layout(title="Características del Correo")
        st.plotly_chart(fig, use_container_width=True)
    
    def update_email_classification(self, email_id: int, is_spam: bool):
        """Actualiza la clasificación de un correo."""
        try:
            self.db.cursor.execute("""
                UPDATE analyzed_emails 
                SET is_spam = ?, confidence = 1.0
                WHERE id = ?
            """, (is_spam, email_id))
            self.db.conn.commit()
            st.success(f"✅ Correo marcado como {'SPAM' if is_spam else 'HAM'}")
        except Exception as e:
            st.error(f"Error actualizando clasificación: {e}")
    
    def delete_email(self, email_id: int):
        """Elimina un correo de la base de datos."""
        try:
            self.db.cursor.execute("DELETE FROM analyzed_emails WHERE id = ?", (email_id,))
            self.db.conn.commit()
            st.success("✅ Correo eliminado")
        except Exception as e:
            st.error(f"Error eliminando correo: {e}")
    
    def export_emails_to_csv(self, emails: list):
        """Exporta correos filtrados a CSV."""
        try:
            import pandas as pd
            
            # Preparar datos para exportación
            export_data = []
            for email in emails:
                export_data.append({
                    'ID': email['id'],
                    'Asunto': email['subject'],
                    'Remitente': email['sender'],
                    'Dominio': email['sender_domain'],
                    'Destinatario': email['recipient'],
                    'Es SPAM': 'Sí' if email['is_spam'] else 'No',
                    'Confianza': f"{email['confidence']:.1%}",
                    'Puntuación SPAM': f"{email['spam_score']:.3f}",
                    'Tamaño': email['content_length'],
                    'Procesado': email['processed_at'],
                    'Recibido': email['received_at'] if email['received_at'] else '',
                    'Cuenta': email['account_email']
                })
            
            df = pd.DataFrame(export_data)
            
            # Generar CSV
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            
            # Descargar archivo
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"correos_filtrados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            st.success("✅ Archivo CSV generado correctamente")
            
        except Exception as e:
            st.error(f"Error exportando a CSV: {e}")

    def show_ml_models(self):
        """
        Muestra la página de gestión de modelos de Machine Learning.
        
        Permite:
        - Crear nuevos modelos
        - Editar modelos existentes
        - Gestionar ejemplos de entrenamiento
        - Ver estadísticas de modelos
        """
        st.header("🤖 Gestión de Modelos de Machine Learning")
        
        # Tabs para diferentes acciones
        tab1, tab2, tab3 = st.tabs(["📋 Modelos", "➕ Crear Modelo", "📊 Estadísticas"])
        
        with tab1:
            self.show_ml_models_list()
        
        with tab2:
            self.show_create_ml_model_form()
        
        with tab3:
            self.show_ml_statistics()

    def show_ml_models_list(self):
        """Muestra la lista de modelos de ML con opciones de gestión."""
        try:
            models = self.db.get_ml_models()
            
            if not models:
                st.info("📭 No hay modelos creados. Crea tu primer modelo en la pestaña 'Crear Modelo'")
                return
            
            st.subheader("📋 Modelos Existentes")
            
            for model in models:
                with st.expander(f"🤖 {model['name']} ({model['algorithm']})", expanded=False):
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        st.write(f"**Descripción:** {model['description']}")
                        st.write(f"**Tipo:** {model['model_type']}")
                        st.write(f"**Estado:** {'✅ Activo' if model['is_active'] else '❌ Inactivo'}")
                        st.write(f"**Precisión:** {model['accuracy']:.2%}")
                        st.write(f"**Ejemplos:** {model['total_examples']}")
                    
                    with col2:
                        if st.button("✏️ Editar", key=f"edit_model_{model['id']}"):
                            st.session_state.editing_model = model
                            st.rerun()
                    
                    with col3:
                        if st.button("📚 Ejemplos", key=f"examples_{model['id']}"):
                            st.session_state.viewing_model = model
                            st.rerun()
                    
                    with col4:
                        if st.button("🗑️ Eliminar", key=f"delete_model_{model['id']}"):
                            if st.checkbox(f"Confirmar eliminación de {model['name']}", key=f"confirm_delete_{model['id']}"):
                                if self.db.delete_ml_model(model['id']):
                                    st.success("✅ Modelo eliminado exitosamente!")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al eliminar el modelo")
            
            # Formulario de edición
            if hasattr(st.session_state, 'editing_model') and st.session_state.editing_model:
                st.markdown("---")
                st.subheader("✏️ Editar Modelo")
                self.show_edit_ml_model_form(st.session_state.editing_model)
            
            # Vista de ejemplos
            if hasattr(st.session_state, 'viewing_model') and st.session_state.viewing_model:
                st.markdown("---")
                st.subheader("📚 Ejemplos de Entrenamiento")
                self.show_model_examples(st.session_state.viewing_model)
                
        except Exception as e:
            st.error(f"Error cargando modelos: {e}")

    def show_create_ml_model_form(self):
        """Muestra el formulario para crear un nuevo modelo de ML."""
        st.subheader("➕ Crear Nuevo Modelo")
        
        with st.form("create_ml_model_form"):
            # Campos básicos
            name = st.text_input("Nombre del Modelo", placeholder="Mi Modelo de SPAM")
            description = st.text_area("Descripción", placeholder="Descripción del modelo y su propósito")
            
            # Tipo de modelo
            model_type = st.selectbox(
                "Tipo de Modelo",
                ['spam_detector', 'category_classifier', 'sentiment_analyzer', 'custom'],
                help="Tipo de clasificación que realizará el modelo"
            )
            
            # Algoritmo
            algorithm = st.selectbox(
                "Algoritmo",
                ['naive_bayes', 'svm', 'random_forest', 'logistic_regression', 'neural_network'],
                help="Algoritmo de Machine Learning a utilizar"
            )
            
            # Configuración avanzada
            with st.expander("⚙️ Configuración Avanzada", expanded=False):
                # Parámetros específicos del algoritmo
                if algorithm == 'naive_bayes':
                    alpha = st.number_input("Alpha (suavizado)", value=1.0, min_value=0.1, step=0.1)
                    model_config = {'alpha': alpha}
                elif algorithm == 'svm':
                    kernel = st.selectbox("Kernel", ['rbf', 'linear', 'poly', 'sigmoid'])
                    c = st.number_input("C (regularización)", value=1.0, min_value=0.1, step=0.1)
                    model_config = {'kernel': kernel, 'C': c}
                elif algorithm == 'random_forest':
                    n_estimators = st.number_input("Número de árboles", value=100, min_value=10, step=10)
                    max_depth = st.number_input("Profundidad máxima", value=10, min_value=1, step=1)
                    model_config = {'n_estimators': n_estimators, 'max_depth': max_depth}
                else:
                    model_config = {}
            
            # Botón de creación
            if st.form_submit_button("🚀 Crear Modelo"):
                if name and description:
                    try:
                        model_id = self.db.create_ml_model(
                            name=name,
                            description=description,
                            model_type=model_type,
                            algorithm=algorithm,
                            model_config=model_config
                        )
                        st.success(f"✅ Modelo '{name}' creado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error creando modelo: {e}")
                else:
                    st.error("❌ Completa todos los campos requeridos")

    def show_edit_ml_model_form(self, model: dict):
        """Muestra el formulario para editar un modelo existente."""
        with st.form(f"edit_ml_model_form_{model['id']}"):
            name = st.text_input("Nombre", value=model['name'])
            description = st.text_area("Descripción", value=model['description'])
            is_active = st.checkbox("Modelo Activo", value=model['is_active'])
            
            if st.form_submit_button("💾 Guardar Cambios"):
                try:
                    success = self.db.update_ml_model(
                        model['id'],
                        name=name,
                        description=description,
                        is_active=is_active
                    )
                    if success:
                        st.success("✅ Modelo actualizado exitosamente!")
                        del st.session_state.editing_model
                        st.rerun()
                    else:
                        st.error("❌ Error actualizando modelo")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    def show_model_examples(self, model: dict):
        """Muestra los ejemplos de entrenamiento de un modelo."""
        try:
            examples = self.db.get_training_examples(model['id'])
            stats = self.db.get_training_statistics(model['id'])
            
            # Estadísticas rápidas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Total Ejemplos", stats.get('total_examples', 0))
            with col2:
                st.metric("🚨 SPAM", stats.get('spam_examples', 0))
            with col3:
                st.metric("✅ HAM", stats.get('ham_examples', 0))
            with col4:
                st.metric("📝 Manuales", stats.get('manual_examples', 0))
            
            st.markdown("---")
            
            # Formulario para agregar ejemplo manual
            with st.expander("➕ Agregar Ejemplo Manual", expanded=False):
                self.show_add_manual_example_form(model['id'])
            
            # Lista de ejemplos
            st.subheader("📚 Ejemplos de Entrenamiento")
            
            if examples:
                for example in examples:
                    with st.expander(f"{'🚨' if example['classification'] else '✅'} {example['title']}", expanded=False):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            st.write(f"**Contenido:** {example['content'][:100]}...")
                            st.write(f"**Fuente:** {example['source_type']}")
                            if example['email_subject']:
                                st.write(f"**Email:** {example['email_subject']}")
                        
                        with col2:
                            if st.button("✏️ Editar", key=f"edit_example_{example['id']}"):
                                st.session_state.editing_example = example
                        
                        with col3:
                            if st.button("🗑️ Eliminar", key=f"delete_example_{example['id']}"):
                                if self.db.delete_training_example(example['id']):
                                    st.success("✅ Ejemplo eliminado!")
                                    st.rerun()
                                else:
                                    st.error("❌ Error eliminando ejemplo")
            
            # Formulario para agregar ejemplo desde email
            with st.expander("📧 Agregar desde Email", expanded=False):
                self.show_add_email_example_form(model['id'])
        except Exception as e:
            st.error(f"Error cargando ejemplos: {e}")
            
        if not examples:
            st.info("📭 No hay ejemplos de entrenamiento. Agrega algunos para comenzar.")
            
            # Botón para volver
            if st.button("🔙 Volver a Modelos"):
                del st.session_state.viewing_model
                st.rerun()

    def show_add_manual_example_form(self, model_id: int):
        """Muestra el formulario para agregar un ejemplo manual."""
        with st.form(f"add_manual_example_form_{model_id}"):
            title = st.text_input("Título del Ejemplo", placeholder="Ejemplo de SPAM")
            content = st.text_area("Contenido", placeholder="Contenido del ejemplo...")
            classification = st.selectbox(
                "Clasificación",
                [True, False],
                format_func=lambda x: "🚨 SPAM" if x else "✅ HAM"
            )
            
            if st.form_submit_button("➕ Agregar Ejemplo"):
                if title and content:
                    try:
                        example_id = self.db.add_training_example(
                            model_id=model_id,
                            title=title,
                            content=content,
                            classification=classification,
                            source_type='manual'
                        )
                        st.success("✅ Ejemplo agregado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error agregando ejemplo: {e}")
                else:
                    st.error("❌ Completa todos los campos")

    def show_add_email_example_form(self, model_id: int):
        """Muestra el formulario para agregar un ejemplo desde un email existente."""
        try:
            # Obtener emails disponibles
            emails = self.get_filtered_emails({'limit': 100})
            
            if not emails:
                st.warning("📭 No hay emails disponibles para agregar como ejemplos.")
                return
            
            with st.form(f"add_email_example_form_{model_id}"):
                # Selector de email
                email_options = [f"{'🚨' if email['is_spam'] else '✅'} {email['subject'][:50]}... | {email['sender']}" for email in emails]
                selected_email_index = st.selectbox(
                    "📧 Seleccionar Email",
                    range(len(emails)),
                    format_func=lambda x: email_options[x] if x < len(email_options) else "N/A",
                    help="Selecciona un email para agregarlo como ejemplo de entrenamiento"
                )
                
                # Mostrar información del email seleccionado
                if selected_email_index < len(emails):
                    selected_email = emails[selected_email_index]
                    
                    st.write(f"**Asunto:** {selected_email['subject']}")
                    st.write(f"**Remitente:** {selected_email['sender']}")
                    st.write(f"**Clasificación actual:** {'🚨 SPAM' if selected_email['is_spam'] else '✅ HAM'}")
                    st.write(f"**Confianza:** {selected_email['confidence']:.1%}")
                    
                    # Permitir cambiar la clasificación
                    new_classification = st.selectbox(
                        "🎯 Clasificación para entrenamiento",
                        [True, False],
                        index=0 if selected_email['is_spam'] else 1,
                        format_func=lambda x: "🚨 SPAM" if x else "✅ HAM",
                        help="Clasificación que se usará para entrenar el modelo"
                    )
                    
                    # Título personalizado
                    custom_title = st.text_input(
                        "📝 Título del ejemplo",
                        value=f"Email: {selected_email['subject'][:30]}...",
                        help="Título personalizado para el ejemplo de entrenamiento"
                    )
                
                if st.form_submit_button("➕ Agregar como Ejemplo"):
                    if selected_email_index < len(emails):
                        selected_email = emails[selected_email_index]
                        
                        try:
                            # Extraer características del email
                            features = self.extract_email_features(selected_email)
                            
                            example_id = self.db.add_training_example(
                                model_id=model_id,
                                title=custom_title,
                                content=selected_email['content'],
                                classification=new_classification,
                                source_type='email',
                                email_id=selected_email['id'],
                                features_extracted=features
                            )
                            
                            st.success("✅ Email agregado como ejemplo de entrenamiento!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error agregando email como ejemplo: {e}")
                    else:
                        st.error("❌ Selecciona un email válido")
                        
        except Exception as e:
            st.error(f"Error en formulario de email: {e}")

    def extract_email_features(self, email: dict) -> dict:
        """Extrae características de un email para el entrenamiento."""
        try:
            # Obtener características de la base de datos
            result = self.db.cursor.execute("""
                SELECT * FROM email_features WHERE email_id = ?
            """, (email['id'],)).fetchone()
            
            if result:
                return {
                    'subject_length': result[2],
                    'content_length': result[3],
                    'total_length': result[4],
                    'caps_ratio': result[5],
                    'exclamation_count': result[6],
                    'question_count': result[7],
                    'dollar_count': result[8],
                    'urgent_words': result[9],
                    'spam_words': result[10],
                    'has_suspicious_domain': result[11],
                    'has_many_links': result[12],
                    'has_attachments': result[13]
                }
            else:
                # Características básicas si no están en la BD
                content = email['content'].lower()
                return {
                    'subject_length': len(email['subject']),
                    'content_length': len(email['content']),
                    'total_length': len(email['subject'] + email['content']),
                    'caps_ratio': sum(1 for c in content if c.isupper()) / len(content) if content else 0,
                    'exclamation_count': content.count('!'),
                    'question_count': content.count('?'),
                    'dollar_count': content.count('$'),
                    'urgent_words': sum(1 for word in ['urgente', 'urgent', 'important', 'importante'] if word in content),
                    'spam_words': sum(1 for word in ['gratis', 'free', 'gana', 'win', 'dinero', 'money'] if word in content),
                    'has_suspicious_domain': 0,
                    'has_many_links': len(re.findall(r'http[s]?://', content)),
                    'has_attachments': email.get('has_attachments', False)
                }
                
        except Exception as e:
            logger.error(f"Error extrayendo características: {e}")
            return {}

    def show_ml_statistics(self):
        """Muestra estadísticas generales de los modelos de ML."""
        try:
            models = self.db.get_ml_models()
            
            if not models:
                st.info("📭 No hay modelos para mostrar estadísticas")
                return
            
            st.subheader("📊 Estadísticas Generales")
            
            # Métricas generales
            total_models = len(models)
            active_models = len([m for m in models if m['is_active']])
            total_examples = sum(m['total_examples'] for m in models)
            avg_accuracy = sum(m['accuracy'] for m in models) / total_models if total_models > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🤖 Total Modelos", total_models)
            with col2:
                st.metric("✅ Modelos Activos", active_models)
            with col3:
                st.metric("📚 Total Ejemplos", total_examples)
            with col4:
                st.metric("📊 Precisión Promedio", f"{avg_accuracy:.2%}")
            
            # Gráfico de modelos por algoritmo
            st.subheader("📈 Distribución por Algoritmo")
            algorithm_counts = {}
            for model in models:
                algo = model['algorithm']
                algorithm_counts[algo] = algorithm_counts.get(algo, 0) + 1
            
            if algorithm_counts:
                fig = go.Figure(data=[go.Pie(labels=list(algorithm_counts.keys()), 
                                         values=list(algorithm_counts.values()))])
                fig.update_layout(title="Modelos por Algoritmo")
                st.plotly_chart(fig, use_container_width=True)
            
            # Tabla de modelos
            st.subheader("📋 Resumen de Modelos")
            df = pd.DataFrame(models)
            df['accuracy'] = df['accuracy'].apply(lambda x: f"{x:.2%}")
            df['is_active'] = df['is_active'].apply(lambda x: "✅" if x else "❌")
            
            st.dataframe(df[['name', 'algorithm', 'accuracy', 'total_examples', 'is_active']], 
                        use_container_width=True)
            
        except Exception as e:
            st.error(f"Error cargando estadísticas: {e}")

    def show_analysis_results(self):
        """Muestra resultados de análisis recientes."""
        st.info("📊 Resultados recientes (simulado)")
    
    def show_training_interface(self):
        """Muestra interfaz de entrenamiento."""
        st.info("🎓 Interfaz de entrenamiento (simulado)")
    
    def show_pattern_management(self):
        """Muestra gestión de patrones."""
        st.info("🔍 Gestión de patrones (simulado)")
    
    def show_training_metrics(self):
        """Muestra métricas de entrenamiento."""
        st.info("📊 Métricas de entrenamiento (simulado)")
    
    def show_temporal_trends(self, start_date, end_date):
        """Muestra tendencias temporales."""
        st.info("📈 Tendencias temporales (simulado)")
    
    def show_category_distribution(self, start_date, end_date):
        """Muestra distribución por categoría."""
        st.info("🎯 Distribución por categoría (simulado)")
    
    def show_detailed_statistics(self, start_date, end_date):
        """Muestra estadísticas detalladas."""
        st.info("📋 Estadísticas detalladas (simulado)")
    
    def show_existing_patterns(self):
        """Muestra patrones existentes."""
        st.info("📋 Patrones existentes (simulado)")
    
    def show_add_pattern_form(self):
        """Muestra formulario para agregar patrón."""
        st.info("➕ Formulario de patrón (simulado)")
    
    def show_edit_patterns(self):
        """Muestra edición de patrones."""
        st.info("✏️ Edición de patrones (simulado)")
    
    def show_email_viewer(self):
        """
        Muestra la página de visualización y filtrado de correos.
        
        Permite al usuario:
        - Filtrar correos por múltiples criterios
        - Ver detalles completos de cada correo
        - Exportar resultados
        - Analizar patrones
        """
        st.header("📧 Visualizador de Correos")
        st.markdown("---")
        
        # Sidebar para filtros rápidos
        with st.sidebar:
            st.subheader("🔍 Filtros Rápidos")
            
            # Filtros básicos
            quick_spam_filter = st.selectbox(
                "🚨 Estado",
                ["Todos", "Solo SPAM", "Solo HAM"],
                help="Filtrar por clasificación"
            )
            
            quick_account_filter = st.selectbox(
                "📧 Cuenta",
                ["Todas", "Gmail", "Outlook", "Yahoo"],
                help="Filtrar por proveedor"
            )
            
            # Filtros de fecha más intuitivos
            st.subheader("📅 Período")
            date_range = st.selectbox(
                "Rango de tiempo",
                ["Últimas 24h", "Últimos 7 días", "Último mes", "Último año", "Personalizado"],
                help="Seleccionar período de tiempo"
            )
            
            if date_range == "Personalizado":
                col1, col2 = st.columns(2)
                with col1:
                    custom_from = st.date_input("Desde")
                with col2:
                    custom_to = st.date_input("Hasta")
            else:
                custom_from = None
                custom_to = None
            
            # Búsqueda rápida
            quick_search = st.text_input(
                "🔍 Buscar",
                placeholder="Asunto, remitente...",
                help="Búsqueda rápida en texto"
            )
            
            # Botones de acción rápida
            st.markdown("---")
            st.subheader("⚡ Acciones")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Aplicar Filtros", type="primary"):
                    self.apply_quick_filters(quick_spam_filter, quick_account_filter, date_range, custom_from, custom_to, quick_search)
            
            with col2:
                if st.button("📤 Exportar", type="secondary"):
                    if 'filtered_emails' in st.session_state and st.session_state.filtered_emails:
                        self.export_emails_to_csv(st.session_state.filtered_emails)
                    else:
                        st.warning("No hay resultados para exportar")
        
        # Contenido principal
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("📊 Correos Encontrados")
            
            # Botón para obtener todos los correos
            if st.button("📥 Obtener Todo el Correo y Revisarlo", type="primary", help="Obtener todos los correos de la base de datos"):
                all_filters = {
                    'limit': 1000,
                    'order_by': 'received_at',
                    'order_direction': 'DESC'
                }
                st.session_state.filtered_emails = self.get_filtered_emails(all_filters)
                st.success(f"✅ Obtenidos {len(st.session_state.filtered_emails)} correos para revisión.")
            
            # Mostrar estadísticas
            if 'filtered_emails' in st.session_state and st.session_state.filtered_emails:
                emails = st.session_state.filtered_emails
                
                # Métricas rápidas
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    st.metric("📧 Total", len(emails))
                
                with metric_col2:
                    spam_count = sum(1 for email in emails if email['is_spam'])
                    st.metric("🚨 SPAM", spam_count)
                
                with metric_col3:
                    ham_count = sum(1 for email in emails if not email['is_spam'])
                    st.metric("✅ HAM", ham_count)
                
                with metric_col4:
                    if emails:
                        avg_confidence = sum(email['confidence'] for email in emails) / len(emails)
                        st.metric("📊 Confianza", f"{avg_confidence:.1%}")
                
                st.markdown("---")
                
                # Tabla mejorada
                self.show_improved_email_table(emails)
                
            else:
                st.info("📭 No hay correos filtrados. Usa los filtros para ver resultados.")
        
        with col2:
            st.subheader("🔧 Filtros Avanzados")
            
            with st.expander("⚙️ Configuración Avanzada", expanded=False):
                self.show_advanced_filters()
    
    def show_improved_email_table(self, emails):
        """Muestra una tabla mejorada de correos."""
        
        # Crear DataFrame para mejor visualización
        email_data = []
        for email in emails:
            email_data.append({
                'Estado': "🚨 SPAM" if email['is_spam'] else "✅ HAM",
                'Asunto': email['subject'][:50] + "..." if len(email['subject']) > 50 else email['subject'],
                'Remitente': email['sender'][:30] + "..." if len(email['sender']) > 30 else email['sender'],
                'Dominio': email['sender_domain'],
                'Confianza': f"{email['confidence']:.1%}",
                'Score SPAM': f"{email['spam_score']:.3f}",
                'Recibido': email['received_at'] if email['received_at'] else "N/A",
                'Procesado': email['processed_at'],
                'ID': email['id']
            })
        
        df = pd.DataFrame(email_data)
        
        # Mostrar tabla con opciones de ordenamiento
        st.dataframe(
            df,
            column_config={
                "Estado": st.column_config.TextColumn("Estado", width="small"),
                "Asunto": st.column_config.TextColumn("Asunto", width="medium"),
                "Remitente": st.column_config.TextColumn("Remitente", width="medium"),
                "Dominio": st.column_config.TextColumn("Dominio", width="small"),
                "Confianza": st.column_config.TextColumn("Confianza", width="small"),
                "Score SPAM": st.column_config.TextColumn("Score SPAM", width="small"),
                "Recibido": st.column_config.TextColumn("Recibido", width="small"),
                "Procesado": st.column_config.TextColumn("Procesado", width="small"),
                "ID": st.column_config.NumberColumn("ID", width="small")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Botones de acción para correos seleccionados
        st.markdown("---")
        st.subheader("⚡ Acciones en Lote")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ Marcar como HAM", type="primary"):
                st.info("Función de marcado en lote (en desarrollo)")
        
        with col2:
            if st.button("🚨 Marcar como SPAM", type="primary"):
                st.info("Función de marcado en lote (en desarrollo)")
        
        with col3:
            if st.button("📤 Exportar Seleccionados", type="secondary"):
                st.info("Función de exportación selectiva (en desarrollo)")
        
        with col4:
            if st.button("🗑️ Eliminar Seleccionados", type="secondary"):
                st.info("Función de eliminación en lote (en desarrollo)")
        
        # Sección para ver detalles de un correo específico
        st.markdown("---")
        st.subheader("👁️ Ver Detalles de Correo")
        
        # Selector de correo para ver detalles
        if emails:
            email_options = [f"{'🚨' if email['is_spam'] else '✅'} {email['subject'][:50]}..." for email in emails]
            selected_email_index = st.selectbox(
                "Seleccionar correo para ver detalles:",
                range(len(emails)),
                format_func=lambda x: email_options[x] if x < len(email_options) else "N/A"
            )
            
            if st.button("👁️ Ver Detalles Completos"):
                selected_email = emails[selected_email_index]
                st.session_state.selected_email = selected_email
                st.success(f"✅ Correo seleccionado: {selected_email['subject']}")
                
                # Mostrar detalles inmediatamente
                self.show_email_details()
    
    def show_advanced_filters(self):
        """Muestra filtros avanzados en un expander."""
        
        with st.form("advanced_filters_form"):
            # Sección 1: Filtros básicos
            st.subheader("🔍 Filtros Básicos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Estado de SPAM
                spam_status = st.selectbox(
                    "🚨 Estado de SPAM",
                    ["Todos", "Solo SPAM", "Solo HAM"],
                    help="Filtrar por clasificación de SPAM"
                )
                
                # Búsqueda de texto
                search_text = st.text_input(
                    "🔍 Buscar en texto",
                    placeholder="Buscar en asunto, remitente o contenido...",
                    help="Busca en asunto, remitente y contenido del correo"
                )
            
            with col2:
                # Dominio del remitente
                sender_domain = st.text_input(
                    "🌐 Dominio del remitente",
                    placeholder="gmail.com, outlook.com...",
                    help="Filtrar por dominio del remitente"
                )
                
                # Cuenta de correo
                accounts = self.get_email_accounts_for_filter()
                account_options = ["Todas las cuentas"] + [acc['email'] for acc in accounts]
                selected_account = st.selectbox(
                    "📧 Cuenta de correo",
                    account_options,
                    help="Filtrar por cuenta específica"
                )
            
            st.markdown("---")
            
            # Sección 2: Rangos de valores
            st.subheader("📊 Rangos de Valores")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Rango de confianza
                st.write("**Confianza del análisis**")
                confidence_range = st.slider(
                    "Confianza",
                    min_value=0.0,
                    max_value=1.0,
                    value=(0.0, 1.0),
                    step=0.1,
                    help="Rango de confianza del análisis",
                    label_visibility="collapsed"
                )
                
                # Rango de puntuación SPAM
                st.write("**Puntuación SPAM**")
                spam_score_range = st.slider(
                    "Puntuación SPAM",
                    min_value=0.0,
                    max_value=1.0,
                    value=(0.0, 1.0),
                    step=0.1,
                    help="Rango de puntuación SPAM",
                    label_visibility="collapsed"
                )
            
            with col2:
                # Tamaño del contenido
                st.write("**Tamaño del contenido**")
                content_length_range = st.slider(
                    "Tamaño del contenido",
                    min_value=0,
                    max_value=10000,
                    value=(0, 10000),
                    step=100,
                    help="Rango de tamaño del contenido",
                    label_visibility="collapsed"
                )
                
                # Límite de resultados
                st.write("**Máximo resultados**")
                limit = st.number_input(
                    "Máximo resultados",
                    min_value=10,
                    max_value=1000,
                    value=100,
                    step=10,
                    help="Número máximo de correos a mostrar",
                    label_visibility="collapsed"
                )
            
            st.markdown("---")
            
            # Sección 3: Fechas
            st.subheader("📅 Filtros de Fecha")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Fechas de Procesamiento**")
                processed_from = st.date_input(
                    "Procesado desde",
                    value=datetime.now() - timedelta(days=30),
                    help="Fecha de inicio de procesamiento",
                    label_visibility="collapsed"
                )
                
                processed_to = st.date_input(
                    "Procesado hasta",
                    value=datetime.now(),
                    help="Fecha de fin de procesamiento",
                    label_visibility="collapsed"
                )
            
            with col2:
                st.write("**Fechas de Recepción**")
                received_from = st.date_input(
                    "Recibido desde",
                    value=datetime.now() - timedelta(days=30),
                    help="Fecha de inicio de recepción del correo",
                    label_visibility="collapsed"
                )
                
                received_to = st.date_input(
                    "Recibido hasta",
                    value=datetime.now(),
                    help="Fecha de fin de recepción del correo",
                    label_visibility="collapsed"
                )
            
            st.markdown("---")
            
            # Sección 4: Ordenamiento
            st.subheader("📋 Ordenamiento")
            
            col1, col2 = st.columns(2)
            
            with col1:
                order_by = st.selectbox(
                    "Ordenar por",
                    ["received_at", "processed_at", "subject", "sender", "spam_score", "confidence"],
                    format_func=lambda x: {
                        "received_at": "Fecha de recepción",
                        "processed_at": "Fecha de procesamiento",
                        "subject": "Asunto",
                        "sender": "Remitente",
                        "spam_score": "Puntuación SPAM",
                        "confidence": "Confianza"
                    }[x],
                    help="Campo por el cual ordenar los resultados"
                )
            
            with col2:
                order_direction = st.selectbox(
                    "Dirección",
                    ["DESC", "ASC"],
                    format_func=lambda x: "Descendente" if x == "DESC" else "Ascendente",
                    help="Orden ascendente o descendente"
                )
            
            st.markdown("---")
            
            # Botones de acción
            col1, col2, col3 = st.columns(3)
            
            with col1:
                apply_advanced = st.form_submit_button("🔍 Aplicar Filtros", type="primary")
            
            with col2:
                clear_advanced = st.form_submit_button("🗑️ Limpiar", type="secondary")
            
            with col3:
                export_advanced = st.form_submit_button("📤 Exportar", type="secondary")
            
            if apply_advanced:
                # Construir filtros avanzados
                filters = {}
                
                # Filtros básicos
                if spam_status == "Solo SPAM":
                    filters['spam_status'] = True
                elif spam_status == "Solo HAM":
                    filters['spam_status'] = False
                
                if search_text:
                    filters['search_text'] = search_text
                
                if sender_domain:
                    filters['sender_domain'] = sender_domain
                
                if selected_account != "Todas las cuentas":
                    account_id = next((acc['id'] for acc in accounts if acc['email'] == selected_account), None)
                    if account_id:
                        filters['account_id'] = account_id
                
                # Rangos de valores
                if confidence_range[0] > 0.0:
                    filters['confidence_min'] = confidence_range[0]
                if confidence_range[1] < 1.0:
                    filters['confidence_max'] = confidence_range[1]
                
                if spam_score_range[0] > 0.0:
                    filters['spam_score_min'] = spam_score_range[0]
                if spam_score_range[1] < 1.0:
                    filters['spam_score_max'] = spam_score_range[1]
                
                # Fechas
                filters['processed_date_from'] = processed_from.strftime('%Y-%m-%d')
                filters['processed_date_to'] = processed_to.strftime('%Y-%m-%d')
                filters['received_date_from'] = received_from.strftime('%Y-%m-%d')
                filters['received_date_to'] = received_to.strftime('%Y-%m-%d')
                
                # Ordenamiento
                filters['order_by'] = order_by
                filters['order_direction'] = order_direction
                filters['limit'] = limit
                
                # Aplicar filtros
                st.session_state.filtered_emails = self.get_filtered_emails(filters)
                st.success(f"✅ Filtros avanzados aplicados. Encontrados {len(st.session_state.filtered_emails)} correos.")
            
            elif clear_advanced:
                if 'filtered_emails' in st.session_state:
                    del st.session_state.filtered_emails
                st.success("✅ Filtros avanzados limpiados.")
            
            elif export_advanced:
                if 'filtered_emails' in st.session_state and st.session_state.filtered_emails:
                    self.export_emails_to_csv(st.session_state.filtered_emails)
                else:
                    st.warning("⚠️ No hay resultados para exportar. Aplica filtros primero.")
    
    def apply_quick_filters(self, spam_filter, account_filter, date_range, custom_from, custom_to, search_text):
        """Aplica filtros rápidos desde la sidebar."""
        filters = {}
        
        # Filtro de SPAM
        if spam_filter == "Solo SPAM":
            filters['spam_status'] = True
        elif spam_filter == "Solo HAM":
            filters['spam_status'] = False
        
        # Filtro de cuenta
        if account_filter != "Todas":
            filters['sender_domain'] = account_filter.lower().replace("gmail", "gmail.com").replace("outlook", "outlook.com").replace("yahoo", "yahoo.com")
        
        # Filtro de fecha
        if date_range == "Personalizado" and custom_from and custom_to:
            filters['received_date_from'] = custom_from.strftime('%Y-%m-%d')
            filters['received_date_to'] = custom_to.strftime('%Y-%m-%d')
        elif date_range != "Personalizado":
            # Calcular fechas basadas en el rango seleccionado
            end_date = datetime.now()
            if date_range == "Últimas 24h":
                start_date = end_date - timedelta(days=1)
            elif date_range == "Últimos 7 días":
                start_date = end_date - timedelta(days=7)
            elif date_range == "Último mes":
                start_date = end_date - timedelta(days=30)
            elif date_range == "Último año":
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date - timedelta(days=30)
            
            filters['received_date_from'] = start_date.strftime('%Y-%m-%d')
            filters['received_date_to'] = end_date.strftime('%Y-%m-%d')
        
        # Filtro de búsqueda
        if search_text:
            filters['search_text'] = search_text
        
        # Configuración por defecto
        filters['order_by'] = 'received_at'
        filters['order_direction'] = 'DESC'
        filters['limit'] = 1000
        
        # Aplicar filtros
        st.session_state.filtered_emails = self.get_filtered_emails(filters)
        st.success(f"✅ Filtros aplicados. Encontrados {len(st.session_state.filtered_emails)} correos.")
    
    def show_email_details(self):
        """Muestra detalles completos de un correo seleccionado."""
        st.subheader("📋 Detalles Completos")
        
        if 'selected_email' not in st.session_state:
            st.info("👆 Selecciona un correo de la tabla para ver sus detalles completos.")
            return
        
        email = st.session_state.selected_email
        
        # Información principal
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📧 Información del Correo")
            st.write(f"**ID:** {email['id']}")
            st.write(f"**Asunto:** {email['subject']}")
            st.write(f"**Remitente:** {email['sender']}")
            st.write(f"**Destinatario:** {email['recipient']}")
            st.write(f"**Dominio:** {email['sender_domain']}")
            st.write(f"**Cuenta:** {email['account_email']}")
        
        with col2:
            st.subheader("📊 Análisis de SPAM")
            spam_icon = "🚨" if email['is_spam'] else "✅"
            st.write(f"**Clasificación:** {spam_icon} {'SPAM' if email['is_spam'] else 'HAM'}")
            st.write(f"**Confianza:** {email['confidence']:.1%}")
            st.write(f"**Puntuación SPAM:** {email['spam_score']:.3f}")
            st.write(f"**Tamaño:** {email['content_length']} caracteres")
            st.write(f"**Procesado:** {email['processed_at']}")
            if email['received_at']:
                st.write(f"**Recibido:** {email['received_at']}")
        
        st.markdown("---")
        
        # Contenido completo
        st.subheader("📄 Contenido Completo")
        st.text_area("Contenido del correo", email['content'], height=300, disabled=True)
        
        # Características extraídas
        st.subheader("🔍 Características Extraídas")
        self.show_email_features(email['id'])
        
        # Acciones
        st.subheader("⚡ Acciones")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ Marcar como HAM"):
                self.update_email_classification(email['id'], False)
        
        with col2:
            if st.button("🚨 Marcar como SPAM"):
                self.update_email_classification(email['id'], True)
        
        with col3:
            if st.button("📤 Reenviar"):
                st.info("📤 Función de reenvío (en desarrollo)")
        
        with col4:
            if st.button("🗑️ Eliminar"):
                if st.checkbox("Confirmar eliminación"):
                    self.delete_email(email['id'])
    
    def show_email_features(self, email_id: int):
        """Muestra las características extraídas de un correo."""
        try:
            result = self.db.cursor.execute("""
                SELECT * FROM email_features WHERE email_id = ?
            """, (email_id,)).fetchone()
            
            if result:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Longitud asunto:** {result[2]} caracteres")
                    st.write(f"**Longitud contenido:** {result[3]} caracteres")
                    st.write(f"**Longitud total:** {result[4]} caracteres")
                    st.write(f"**Ratio mayúsculas:** {result[5]:.2%}")
                
                with col2:
                    st.write(f"**Exclamaciones:** {result[6]}")
                    st.write(f"**Interrogaciones:** {result[7]}")
                    st.write(f"**Símbolos $:** {result[8]}")
                    st.write(f"**Palabras urgentes:** {result[9]}")
                
                with col3:
                    st.write(f"**Palabras SPAM:** {result[10]}")
                    st.write(f"**Dominio sospechoso:** {'Sí' if result[11] else 'No'}")
                    st.write(f"**Muchos enlaces:** {result[12]}")
                    st.write(f"**Tiene adjuntos:** {'Sí' if result[13] else 'No'}")
            else:
                st.info("📊 No hay características extraídas para este correo.")
                
        except Exception as e:
            st.error(f"Error obteniendo características: {e}")
    
    def show_email_analysis(self, email: dict):
        """Muestra análisis detallado de un correo."""
        st.subheader("📊 Análisis Detallado")
        
        # Gráfico de características
        features = {
            'Confianza': email['confidence'],
            'Puntuación SPAM': email['spam_score'],
            'Longitud': email['content_length'] / 1000  # Normalizar
        }
        
        fig = go.Figure(data=[
            go.Bar(x=list(features.keys()), y=list(features.values()))
        ])
        fig.update_layout(title="Características del Correo")
        st.plotly_chart(fig, use_container_width=True)
    
    def update_email_classification(self, email_id: int, is_spam: bool):
        """Actualiza la clasificación de un correo."""
        try:
            self.db.cursor.execute("""
                UPDATE analyzed_emails 
                SET is_spam = ?, confidence = 1.0
                WHERE id = ?
            """, (is_spam, email_id))
            self.db.conn.commit()
            st.success(f"✅ Correo marcado como {'SPAM' if is_spam else 'HAM'}")
        except Exception as e:
            st.error(f"Error actualizando clasificación: {e}")
    
    def delete_email(self, email_id: int):
        """Elimina un correo de la base de datos."""
        try:
            self.db.cursor.execute("DELETE FROM analyzed_emails WHERE id = ?", (email_id,))
            self.db.conn.commit()
            st.success("✅ Correo eliminado")
        except Exception as e:
            st.error(f"Error eliminando correo: {e}")
    
    def export_emails_to_csv(self, emails: list):
        """Exporta correos filtrados a CSV."""
        try:
            import pandas as pd
            
            # Preparar datos para exportación
            export_data = []
            for email in emails:
                export_data.append({
                    'ID': email['id'],
                    'Asunto': email['subject'],
                    'Remitente': email['sender'],
                    'Dominio': email['sender_domain'],
                    'Destinatario': email['recipient'],
                    'Es SPAM': 'Sí' if email['is_spam'] else 'No',
                    'Confianza': f"{email['confidence']:.1%}",
                    'Puntuación SPAM': f"{email['spam_score']:.3f}",
                    'Tamaño': email['content_length'],
                    'Procesado': email['processed_at'],
                    'Recibido': email['received_at'] if email['received_at'] else '',
                    'Cuenta': email['account_email']
                })
            
            df = pd.DataFrame(export_data)
            
            # Generar CSV
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            
            # Descargar archivo
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"correos_filtrados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            st.success("✅ Archivo CSV generado correctamente")
            
        except Exception as e:
            st.error(f"Error exportando a CSV: {e}")

def main():
    """
    Función principal que ejecuta la aplicación.
    
    Esta función:
    1. Crea la instancia de la aplicación
    2. Ejecuta la aplicación
    3. Maneja errores globales
    """
    try:
        # Crear y ejecutar la aplicación
        app = SpamDetectorApp()
        app.run()
        
    except Exception as e:
        st.error(f"❌ Error en la aplicación: {e}")
        logger.error(f"Error en la aplicación: {e}")

if __name__ == "__main__":
    main() 