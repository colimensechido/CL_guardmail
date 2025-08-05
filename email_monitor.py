"""
CL_guardmail - Módulo de Monitoreo de Correos
Archivo: email_monitor.py

DESCRIPCIÓN:
Módulo para conectar con servidores IMAP, descargar correos
y almacenar información detallada en la base de datos.

FUNCIONALIDADES:
- Conexión IMAP segura
- Descarga de correos no leídos
- Análisis y clasificación
- Almacenamiento detallado
- Reportes de revisión

AUTOR: Tu nombre
FECHA: 2025
"""

import imaplib
import email
import ssl
import logging
from datetime import datetime, timedelta
from email.header import decode_header
import re
from typing import Dict, List, Tuple, Optional
import time

# Importar nuestros módulos
from database import create_database
from config import get_config

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailMonitor:
    """
    Clase para monitorear y procesar correos electrónicos.
    
    Esta clase maneja:
    - Conexión IMAP con diferentes proveedores
    - Descarga de correos no leídos
    - Análisis y clasificación de SPAM
    - Almacenamiento en base de datos
    - Generación de reportes detallados
    """
    
    def __init__(self):
        """Inicializa el monitor de correos."""
        self.config = get_config()
        self.db = create_database()
        self.connection = None
        
    def connect_to_server(self, account_id: int) -> bool:
        """
        Conecta al servidor IMAP de una cuenta específica.
        
        Args:
            account_id (int): ID de la cuenta en la base de datos
            
        Returns:
            bool: True si la conexión es exitosa, False en caso contrario
        """
        try:
            # Obtener información de la cuenta
            account = self.db.cursor.execute(
                "SELECT * FROM email_accounts WHERE id = ?", (account_id,)
            ).fetchone()
            
            if not account:
                logger.error(f"Cuenta {account_id} no encontrada")
                return False
            
            # Configurar conexión SSL
            context = ssl.create_default_context()
            
            # Conectar al servidor IMAP
            self.connection = imaplib.IMAP4_SSL(
                account['server'], 
                account['port'], 
                ssl_context=context
            )
            
            # Autenticar
            self.connection.login(account['email'], account['password'])
            
            logger.info(f"Conexión exitosa a {account['email']}")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a la cuenta {account_id}: {e}")
            return False
    
    def disconnect(self):
        """Cierra la conexión IMAP."""
        if self.connection:
            try:
                # Verificar el estado de la conexión antes de cerrar
                if hasattr(self.connection, '_state') and self.connection._state != 'LOGOUT':
                    try:
                        self.connection.logout()
                    except Exception as e:
                        logger.warning(f"Error en logout (puede ser normal): {e}")
                
                # Cerrar la conexión de socket
                try:
                    self.connection.close()
                except Exception as e:
                    logger.warning(f"Error cerrando socket (puede ser normal): {e}")
                
                logger.info("Conexión IMAP cerrada")
            except Exception as e:
                logger.error(f"Error cerrando conexión: {e}")
            finally:
                self.connection = None
    
    def get_all_emails(self, max_emails: int = 1000) -> List[Dict]:
        """
        Obtiene TODOS los correos del servidor (no solo no leídos).
        Obtiene los últimos N correos basado en UID (más recientes).
        
        Args:
            max_emails (int): Número máximo de correos a procesar
            
        Returns:
            List[Dict]: Lista de correos con información detallada
        """
        try:
            # Seleccionar bandeja de entrada
            self.connection.select('INBOX')
            
            # Buscar TODOS los correos (no solo UNSEEN)
            status, messages = self.connection.search(None, 'ALL')
            
            if status != 'OK':
                logger.error("Error buscando todos los correos")
                return []
            
            # Obtener IDs de correos
            email_ids = messages[0].split()
            
            # Verificar que tenemos correos
            if not email_ids:
                logger.info("No hay correos en la bandeja de entrada")
                return []
            
            # Mostrar información de diagnóstico
            total_emails = len(email_ids)
            logger.info(f"Total de correos encontrados: {total_emails}")
            
            # Limitar número de correos - tomar los últimos N (más recientes)
            if len(email_ids) > max_emails:
                email_ids = email_ids[-max_emails:]  # Últimos N correos por UID
                logger.info(f"Limitando a los últimos {max_emails} correos (UIDs más altos = más recientes)")
                logger.info(f"UIDs de correos a procesar: {email_ids[-5:]} (últimos 5)")
            else:
                logger.info(f"Procesando todos los {len(email_ids)} correos disponibles")
            
            emails = []
            
            for i, email_id in enumerate(email_ids):
                try:
                    # Obtener correo completo
                    status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK':
                        logger.warning(f"Error obteniendo correo {email_id}: {status}")
                        continue
                    
                    # Parsear correo
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Extraer información del correo
                    email_info = self._extract_email_info(email_message, email_id.decode())
                    
                    # Log del primer correo para diagnóstico
                    if i == 0:
                        logger.info(f"Primer correo procesado - Asunto: {email_info['subject'][:50]}... | De: {email_info['sender']}")
                    
                    emails.append(email_info)
                    
                except Exception as e:
                    logger.error(f"Error procesando correo {email_id}: {e}")
                    continue
            
            logger.info(f"Procesados {len(emails)} correos exitosamente de {len(email_ids)} intentados")
            return emails
            
        except Exception as e:
            logger.error(f"Error obteniendo todos los correos: {e}")
            return []

    def get_recent_emails(self, days_back: int = 7, max_emails: int = 1000) -> List[Dict]:
        """
        Obtiene correos recientes basado en fecha (últimos N días).
        Útil para encontrar correos muy recientes que pueden no estar en los últimos UIDs.
        
        Args:
            days_back (int): Número de días hacia atrás para buscar
            max_emails (int): Número máximo de correos a procesar
            
        Returns:
            List[Dict]: Lista de correos con información detallada
        """
        try:
            # Seleccionar bandeja de entrada
            self.connection.select('INBOX')
            
            # Calcular fecha de búsqueda
            from datetime import datetime, timedelta
            search_date = datetime.now() - timedelta(days=days_back)
            date_str = search_date.strftime("%d-%b-%Y")
            
            # Buscar correos desde la fecha especificada
            status, messages = self.connection.search(None, f'SINCE {date_str}')
            
            if status != 'OK':
                logger.error(f"Error buscando correos desde {date_str}")
                return []
            
            # Obtener IDs de correos
            email_ids = messages[0].split()
            
            if not email_ids:
                logger.info(f"No hay correos desde {date_str}")
                return []
            
            logger.info(f"Encontrados {len(email_ids)} correos desde {date_str}")
            
            # Limitar número de correos
            if len(email_ids) > max_emails:
                email_ids = email_ids[-max_emails:]  # Últimos N correos
                logger.info(f"Limitando a los últimos {max_emails} correos")
            
            emails = []
            
            for i, email_id in enumerate(email_ids):
                try:
                    # Obtener correo completo
                    status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK':
                        continue
                    
                    # Parsear correo
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Extraer información del correo
                    email_info = self._extract_email_info(email_message, email_id.decode())
                    
                    # Log del primer correo para diagnóstico
                    if i == 0:
                        logger.info(f"Primer correo reciente - Asunto: {email_info['subject'][:50]}... | De: {email_info['sender']}")
                    
                    emails.append(email_info)
                    
                except Exception as e:
                    logger.error(f"Error procesando correo {email_id}: {e}")
                    continue
            
            logger.info(f"Procesados {len(emails)} correos recientes")
            return emails
            
        except Exception as e:
            logger.error(f"Error obteniendo correos recientes: {e}")
            return []

    def get_unread_emails(self, max_emails: int = 50) -> List[Dict]:
        """
        Obtiene correos no leídos del servidor.
        
        Args:
            max_emails (int): Número máximo de correos a procesar
            
        Returns:
            List[Dict]: Lista de correos con información detallada
        """
        try:
            # Seleccionar bandeja de entrada
            self.connection.select('INBOX')
            
            # Buscar correos no leídos
            status, messages = self.connection.search(None, 'UNSEEN')
            
            if status != 'OK':
                logger.error("Error buscando correos no leídos")
                return []
            
            # Obtener IDs de correos
            email_ids = messages[0].split()
            
            # Limitar número de correos
            if len(email_ids) > max_emails:
                email_ids = email_ids[-max_emails:]  # Últimos N correos
            
            emails = []
            
            for email_id in email_ids:
                try:
                    # Obtener correo completo
                    status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK':
                        continue
                    
                    # Parsear correo
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Extraer información del correo
                    email_info = self._extract_email_info(email_message, email_id.decode())
                    emails.append(email_info)
                    
                except Exception as e:
                    logger.error(f"Error procesando correo {email_id}: {e}")
                    continue
            
            logger.info(f"Procesados {len(emails)} correos no leídos")
            return emails
            
        except Exception as e:
            logger.error(f"Error obteniendo correos no leídos: {e}")
            return []
    
    def get_recent_unread_emails(self, days_back: int = 7, max_emails: int = 50) -> List[Dict]:
        """
        Obtiene correos no leídos de los últimos N días Y correos leídos de los últimos 2 días.
        
        Args:
            days_back (int): Número de días hacia atrás para buscar correos no leídos
            max_emails (int): Número máximo de correos a procesar
            
        Returns:
            List[Dict]: Lista de correos con información detallada
        """
        try:
            # Seleccionar bandeja de entrada
            self.connection.select('INBOX')
            
            # Calcular fechas límite
            from datetime import datetime, timedelta
            unread_limit_date = datetime.now() - timedelta(days=days_back)
            read_limit_date = datetime.now() - timedelta(days=2)  # Solo últimos 2 días para leídos
            
            unread_date_str = unread_limit_date.strftime('%d-%b-%Y')
            read_date_str = read_limit_date.strftime('%d-%b-%Y')
            
            emails = []
            
            # 1. Buscar correos no leídos de los últimos 7 días
            logger.info(f"Buscando correos no leídos desde {unread_date_str}")
            status, messages = self.connection.search(None, f'UNSEEN SINCE {unread_date_str}')
            
            if status == 'OK' and messages[0]:
                unread_email_ids = messages[0].split()
                logger.info(f"Encontrados {len(unread_email_ids)} correos no leídos recientes")
                
                # Procesar correos no leídos
                for email_id in unread_email_ids:
                    try:
                        # Obtener correo completo
                        status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                        
                        if status != 'OK':
                            continue
                        
                        # Parsear correo
                        email_body = msg_data[0][1]
                        email_message = email.message_from_bytes(email_body)
                        
                        # Extraer información del correo
                        email_info = self._extract_email_info(email_message, email_id.decode())
                        emails.append(email_info)
                        
                    except Exception as e:
                        logger.error(f"Error procesando correo no leído {email_id}: {e}")
                        continue
            else:
                logger.info("No hay correos no leídos recientes")
            
            # 2. Buscar correos leídos de los últimos 2 días (por si alguien los leyó antes)
            logger.info(f"Buscando correos leídos desde {read_date_str}")
            status, messages = self.connection.search(None, f'SEEN SINCE {read_date_str}')
            
            if status == 'OK' and messages[0]:
                read_email_ids = messages[0].split()
                logger.info(f"Encontrados {len(read_email_ids)} correos leídos recientes")
                
                # Procesar correos leídos (solo los más recientes)
                read_emails_count = 0
                max_read_emails = max_emails // 2  # Máximo la mitad para correos leídos
                
                for email_id in read_email_ids[-max_read_emails:]:  # Solo los más recientes
                    try:
                        # Obtener correo completo
                        status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                        
                        if status != 'OK':
                            continue
                        
                        # Parsear correo
                        email_body = msg_data[0][1]
                        email_message = email.message_from_bytes(email_body)
                        
                        # Extraer información del correo
                        email_info = self._extract_email_info(email_message, email_id.decode())
                        emails.append(email_info)
                        read_emails_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error procesando correo leído {email_id}: {e}")
                        continue
                
                logger.info(f"Procesados {read_emails_count} correos leídos recientes")
            else:
                logger.info("No hay correos leídos recientes")
            
            # Limitar número total de correos si es necesario
            if len(emails) > max_emails:
                emails = emails[-max_emails:]  # Mantener los más recientes
                logger.info(f"Limitando a los últimos {max_emails} correos totales")
            
            logger.info(f"Total procesados: {len(emails)} correos (no leídos + leídos recientes)")
            return emails
            
        except Exception as e:
            logger.error(f"Error obteniendo correos recientes: {e}")
            return []
    
    def _extract_email_info(self, email_message, email_id: str) -> Dict:
        """
        Extrae información detallada de un correo.
        
        Args:
            email_message: Objeto de correo parseado
            email_id (str): ID del correo en el servidor
            
        Returns:
            Dict: Información detallada del correo
        """
        # Extraer headers básicos
        subject = self._decode_header(email_message.get('Subject', ''))
        sender = self._decode_header(email_message.get('From', ''))
        to = self._decode_header(email_message.get('To', ''))
        date = email_message.get('Date', '')
        
        # Extraer contenido
        content = self._extract_content(email_message)
        
        # Extraer características para análisis de SPAM
        features = self._extract_spam_features(subject, sender, content, email_message)
        
        return {
            'email_id': email_id,
            'subject': subject,
            'sender': sender,
            'to': to,
            'date': date,
            'content': content,
            'features': features,
            'size': len(content),
            'has_attachments': self._has_attachments(email_message)
        }
    
    def _decode_header(self, header: str) -> str:
        """Decodifica headers de correo."""
        try:
            decoded_parts = decode_header(header)
            decoded_string = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
                else:
                    decoded_string += str(part)
            return decoded_string
        except Exception:
            return str(header)
    
    def _extract_content(self, email_message) -> str:
        """Extrae el contenido del correo."""
        content = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except Exception:
                        continue
        else:
            try:
                content = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except Exception:
                content = str(email_message.get_payload())
        
        return content
    
    def _extract_spam_features(self, subject: str, sender: str, content: str, email_message=None) -> Dict:
        """
        Extrae características para análisis de SPAM.
        
        Args:
            subject (str): Asunto del correo
            sender (str): Remitente
            content (str): Contenido del correo
            email_message: Objeto de correo (opcional)
            
        Returns:
            Dict: Características extraídas
        """
        # Combinar todo el texto para análisis
        full_text = f"{subject} {content}".lower()
        
        features = {
            'subject_length': len(subject),
            'content_length': len(content),
            'total_length': len(full_text),
            'caps_ratio': sum(1 for c in full_text if c.isupper()) / len(full_text) if full_text else 0,
            'exclamation_count': full_text.count('!'),
            'question_count': full_text.count('?'),
            'dollar_count': full_text.count('$'),
            'urgent_words': sum(1 for word in ['urgente', 'urgent', 'important', 'importante', 'actúa', 'actua'] if word in full_text),
            'spam_words': sum(1 for word in ['gratis', 'free', 'gana', 'win', 'dinero', 'money', 'oferta', 'offer'] if word in full_text),
            'has_suspicious_domain': self._check_suspicious_domain(sender),
            'has_many_links': len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)),
            'has_attachments': self._has_attachments(email_message) if email_message else False
        }
        
        return features
    
    def _check_suspicious_domain(self, sender: str) -> bool:
        """Verifica si el dominio del remitente es sospechoso."""
        suspicious_domains = [
            'spam.com', 'malware.com', 'virus.com', 'fake.com',
            'suspicious.com', 'scam.com', 'phishing.com'
        ]
        
        sender_lower = sender.lower()
        return any(domain in sender_lower for domain in suspicious_domains)
    
    def _has_attachments(self, email_message) -> bool:
        """Verifica si el correo tiene archivos adjuntos."""
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    return True
            return False
        except Exception:
            return False
    
    def analyze_email_spam(self, email_info: Dict) -> Dict:
        """
        Analiza un correo para determinar si es SPAM.
        
        Args:
            email_info (Dict): Información del correo
            
        Returns:
            Dict: Resultado del análisis con puntuación y clasificación
        """
        features = email_info['features']
        
        # Calcular puntuación de SPAM basada en características
        spam_score = 0.0
        
        # Factores de peso para diferentes características
        weights = {
            'caps_ratio': 0.2,
            'exclamation_count': 0.15,
            'urgent_words': 0.25,
            'spam_words': 0.2,
            'has_suspicious_domain': 0.3,
            'has_many_links': 0.1
        }
        
        # Normalizar características
        if features['caps_ratio'] > 0.3:
            spam_score += weights['caps_ratio']
        
        if features['exclamation_count'] > 3:
            spam_score += weights['exclamation_count']
        
        if features['urgent_words'] > 0:
            spam_score += weights['urgent_words']
        
        if features['spam_words'] > 2:
            spam_score += weights['spam_words']
        
        if features['has_suspicious_domain']:
            spam_score += weights['has_suspicious_domain']
        
        if features['has_many_links'] > 5:
            spam_score += weights['has_many_links']
        
        # Clasificar como SPAM si la puntuación es alta
        is_spam = spam_score > 0.6
        confidence = min(spam_score * 1.5, 1.0)  # Normalizar confianza
        
        return {
            'is_spam': is_spam,
            'spam_score': spam_score,
            'confidence': confidence,
            'features_used': features
        }
    
    def store_email_in_database(self, account_id: int, email_info: Dict, analysis_result: Dict) -> bool:
        """
        Almacena un correo y su análisis en la base de datos.
        
        Args:
            account_id (int): ID de la cuenta
            email_info (Dict): Información del correo
            analysis_result (Dict): Resultado del análisis
            
        Returns:
            bool: True si se almacenó correctamente, False si ya existe
        """
        try:
            # Verificar si el correo ya existe en la base de datos por email_id
            self.db.cursor.execute("""
                SELECT id FROM analyzed_emails 
                WHERE account_id = ? AND email_id = ?
            """, (account_id, email_info['email_id']))
            
            existing_email = self.db.cursor.fetchone()
            
            if existing_email:
                logger.info(f"Correo ya existe en BD (email_id: {email_info['email_id']}) - Saltando duplicado")
                return False  # Ya existe, no insertar
            
            # Extraer dominio del remitente
            sender_domain = ""
            if email_info['sender']:
                try:
                    sender_domain = email_info['sender'].split('@')[-1].split('>')[0]
                except:
                    sender_domain = ""
            
            # Insertar correo analizado con TODAS las columnas requeridas
            self.db.cursor.execute("""
                INSERT INTO analyzed_emails (
                    account_id, email_id, subject, sender, sender_domain, 
                    recipient, content, content_length, email_size, 
                    has_attachments, attachment_count, is_spam, 
                    confidence, spam_score, processed_at, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_id,
                email_info['email_id'],
                email_info['subject'],
                email_info['sender'],
                sender_domain,
                email_info['to'],
                email_info['content'],
                len(email_info['content']),
                email_info['size'],
                email_info['has_attachments'],
                0,  # attachment_count por defecto
                analysis_result['is_spam'],
                analysis_result['confidence'],
                analysis_result['spam_score'],
                datetime.now(),
                email_info.get('date', datetime.now())
            ))
            
            # Obtener ID del correo insertado
            email_db_id = self.db.cursor.lastrowid
            
            # Almacenar características extraídas
            features = analysis_result['features_used']
            self.db.cursor.execute("""
                INSERT INTO email_features (
                    email_id, subject_length, content_length, total_length,
                    caps_ratio, exclamation_count, question_count, dollar_count,
                    urgent_words, spam_words, has_suspicious_domain,
                    has_many_links, has_attachments, extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email_db_id,
                features['subject_length'],
                features['content_length'],
                features['total_length'],
                features['caps_ratio'],
                features['exclamation_count'],
                features['question_count'],
                features['dollar_count'],
                features['urgent_words'],
                features['spam_words'],
                features['has_suspicious_domain'],
                features['has_many_links'],
                features['has_attachments'],
                datetime.now()
            ))
            
            self.db.conn.commit()
            logger.info(f"Correo almacenado exitosamente (email_id: {email_info['email_id']})")
            return True
            
        except Exception as e:
            logger.error(f"Error almacenando correo en base de datos: {e}")
            return False
    
    def process_account_emails(self, account_id: int, max_emails: int = 50, get_all: bool = False, get_recent: bool = False) -> Dict:
        """
        Procesa correos de una cuenta.
        
        Args:
            account_id (int): ID de la cuenta a procesar
            max_emails (int): Número máximo de correos a procesar
            get_all (bool): Si True, obtiene todos los correos (no solo no leídos)
            get_recent (bool): Si True, obtiene correos recientes (últimos 7 días)
            
        Returns:
            Dict: Reporte detallado del procesamiento
        """
        start_time = time.time()
        
        try:
            # Conectar al servidor
            if not self.connect_to_server(account_id):
                return {
                    'success': False,
                    'error': 'No se pudo conectar al servidor',
                    'account_id': account_id,
                    'emails_processed': 0,
                    'spam_detected': 0,
                    'ham_detected': 0,
                    'processing_time': 0
                }
            
            # Obtener correos según el tipo de búsqueda
            if get_recent:
                emails = self.get_recent_emails(days_back=7, max_emails=max_emails)
                logger.info("Buscando correos recientes (últimos 7 días)")
            elif get_all:
                emails = self.get_all_emails(max_emails)
                logger.info("Buscando todos los correos")
            else:
                # CAMBIO: Por defecto obtener correos no leídos (7 días) + leídos recientes (2 días)
                # para asegurar que no se pierda ningún correo reciente
                emails = self.get_recent_unread_emails(days_back=7, max_emails=max_emails)
                logger.info("Buscando correos no leídos (7 días) + leídos recientes (2 días)")
            
            if not emails:
                return {
                    'success': True,
                    'account_id': account_id,
                    'emails_processed': 0,
                    'spam_detected': 0,
                    'ham_detected': 0,
                    'processing_time': time.time() - start_time,
                    'message': 'No hay correos nuevos para procesar'
                }
            
            # Procesar cada correo
            processed_emails = []
            spam_count = 0
            ham_count = 0
            
            for email_info in emails:
                try:
                    # Analizar correo
                    analysis_result = self.analyze_email_spam(email_info)
                    
                    # Almacenar en base de datos
                    if self.store_email_in_database(account_id, email_info, analysis_result):
                        # Contar resultados
                        if analysis_result['is_spam']:
                            spam_count += 1
                        else:
                            ham_count += 1
                        
                        # Agregar a lista de procesados
                        processed_emails.append({
                            'subject': email_info['subject'],
                            'sender': email_info['sender'],
                            'is_spam': analysis_result['is_spam'],
                            'confidence': analysis_result['confidence'],
                            'spam_score': analysis_result['spam_score']
                        })
                        
                except Exception as e:
                    logger.error(f"Error procesando correo: {e}")
                    continue
            
            # Actualizar estadísticas de la cuenta
            self._update_account_statistics(account_id, len(processed_emails), spam_count)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'account_id': account_id,
                'emails_processed': len(processed_emails),
                'spam_detected': spam_count,
                'ham_detected': ham_count,
                'processing_time': processing_time,
                'emails_detail': processed_emails
            }
            
        except Exception as e:
            logger.error(f"Error procesando cuenta {account_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'account_id': account_id,
                'emails_processed': 0,
                'spam_detected': 0,
                'ham_detected': 0,
                'processing_time': time.time() - start_time
            }
        finally:
            # Siempre cerrar la conexión al final
            self.disconnect()
    
    def _update_account_statistics(self, account_id: int, emails_processed: int, spam_detected: int):
        """Actualiza las estadísticas de la cuenta en la base de datos."""
        try:
            self.db.cursor.execute("""
                UPDATE email_accounts 
                SET last_check_at = CURRENT_TIMESTAMP,
                    total_emails_checked = total_emails_checked + ?,
                    total_spam_detected = total_spam_detected + ?
                WHERE id = ?
            """, (emails_processed, spam_detected, account_id))
            
            self.db.conn.commit()
            
        except Exception as e:
            logger.error(f"Error actualizando estadísticas de cuenta: {e}")

    def diagnose_email_processing(self, account_id: int) -> Dict:
        """
        Método de diagnóstico para verificar el funcionamiento del sistema automático.
        
        Args:
            account_id (int): ID de la cuenta a diagnosticar
            
        Returns:
            Dict: Información detallada del diagnóstico
        """
        try:
            # Conectar al servidor
            if not self.connect_to_server(account_id):
                return {
                    'success': False,
                    'error': 'No se pudo conectar al servidor'
                }
            
            # Obtener información de la cuenta
            account = self.db.cursor.execute(
                "SELECT * FROM email_accounts WHERE id = ?", (account_id,)
            ).fetchone()
            
            diagnosis = {
                'success': True,
                'account_email': account['email'],
                'last_check': account['last_check_at'],
                'total_processed': account['total_emails_checked'],
                'total_spam': account['total_spam_detected'],
                'unread_emails': 0,
                'recent_read_emails': 0,
                'total_recent_emails': 0
            }
            
            # Seleccionar bandeja de entrada
            self.connection.select('INBOX')
            
            # Diagnosticar correos no leídos de los últimos 7 días
            from datetime import datetime, timedelta
            unread_limit_date = datetime.now() - timedelta(days=7)
            unread_date_str = unread_limit_date.strftime('%d-%b-%Y')
            
            status, messages = self.connection.search(None, f'UNSEEN SINCE {unread_date_str}')
            if status == 'OK' and messages[0]:
                unread_ids = messages[0].split()
                diagnosis['unread_emails'] = len(unread_ids)
            
            # Diagnosticar correos leídos de los últimos 2 días
            read_limit_date = datetime.now() - timedelta(days=2)
            read_date_str = read_limit_date.strftime('%d-%b-%Y')
            
            status, messages = self.connection.search(None, f'SEEN SINCE {read_date_str}')
            if status == 'OK' and messages[0]:
                read_ids = messages[0].split()
                diagnosis['recent_read_emails'] = len(read_ids)
            
            diagnosis['total_recent_emails'] = diagnosis['unread_emails'] + diagnosis['recent_read_emails']
            
            # Verificar configuración de la cuenta
            diagnosis['check_interval'] = account['check_interval']
            diagnosis['max_emails_per_check'] = account['max_emails_per_check']
            diagnosis['is_active'] = account['is_active']
            
            return diagnosis
            
        except Exception as e:
            logger.error(f"Error en diagnóstico: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.disconnect()

# Función de conveniencia para uso desde app.py
def process_account_emails(account_id: int, max_emails: int = 50, get_all: bool = False, get_recent: bool = False) -> Dict:
    """
    Función de conveniencia para procesar correos de una cuenta.
    
    Args:
        account_id (int): ID de la cuenta
        max_emails (int): Número máximo de correos a procesar
        get_all (bool): Si True, obtiene todos los correos (no solo no leídos)
        get_recent (bool): Si True, obtiene correos recientes (últimos 7 días)
        
    Returns:
        Dict: Reporte detallado del procesamiento
    """
    monitor = EmailMonitor()
    return monitor.process_account_emails(account_id, max_emails, get_all, get_recent)

def diagnose_account_emails(account_id: int) -> Dict:
    """
    Función de conveniencia para diagnosticar el procesamiento de correos de una cuenta.
    
    Args:
        account_id (int): ID de la cuenta a diagnosticar
        
    Returns:
        Dict: Información detallada del diagnóstico
    """
    monitor = EmailMonitor()
    return monitor.diagnose_email_processing(account_id) 