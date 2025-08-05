import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpamDatabase:
    """
    Clase principal para manejar la base de datos SQLite del sistema de SPAM.
    
    Esta clase encapsula todas las operaciones de base de datos:
    - Creación de tablas
    - Operaciones CRUD
    - Consultas complejas
    - Gestión de transacciones
    """
    
    def __init__(self, db_path: str = "spam_detector.db"):
        """
        Inicializa la conexión a la base de datos.
        
        Args:
            db_path (str): Ruta al archivo de base de datos SQLite
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
        self.initialize_catalogs()
    
    def connect(self):
        """Establece conexión con la base de datos SQLite."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Habilitar foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Configurar para que retorne diccionarios
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            logger.info(f"✅ Conexión exitosa a {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Error conectando a la base de datos: {e}")
            raise
    
    def create_tables(self):
        """
        Crea todas las tablas necesarias para el sistema de SPAM.
        
        TABLAS CREADAS:
        1. email_accounts - Cuentas de correo configuradas
        2. analyzed_emails - Correos analizados
        3. spam_categories - Tipos de SPAM (catálogo)
        4. email_spam_categories - Relación correo-categoría
        5. spam_features - Características para detección
        6. email_features - Características extraídas de cada correo
        7. suspicious_domains - Dominios sospechosos
        8. spam_statistics - Estadísticas diarias
        9. model_configurations - Configuraciones de modelos
        10. training_examples - Ejemplos para entrenamiento
        11. spam_patterns - Patrones de detección
        12. category_keywords - Palabras clave por categoría
        13. user_feedback - Feedback del usuario
        """
        
        # Crear todas las tablas
        self._create_all_tables()
        
        # Ejecutar migraciones si es necesario
        self._run_migrations()
    
    def _create_all_tables(self):
        """Crea todas las tablas de la base de datos."""
        
        # 1. TABLA: Cuentas de correo configuradas
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,                    -- Dirección de correo
                password TEXT NOT NULL,                        -- Contraseña (encriptada)
                server TEXT NOT NULL,                          -- gmail.com, outlook.com, etc.
                port INTEGER NOT NULL,                         -- 993 para IMAP SSL
                protocol TEXT DEFAULT 'IMAP',                  -- IMAP, POP3
                is_active BOOLEAN DEFAULT 1,                   -- Cuenta activa/inactiva
                check_interval INTEGER DEFAULT 15,              -- Minutos entre revisiones
                max_emails_per_check INTEGER DEFAULT 50,       -- Máximo correos por revisión
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación
                last_check_at TIMESTAMP,                       -- Última revisión
                total_emails_checked INTEGER DEFAULT 0,        -- Total correos revisados
                total_spam_detected INTEGER DEFAULT 0          -- Total SPAM detectado
            )
        """)
        
        # 2. TABLA: Correos analizados
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyzed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,                            -- ID de la cuenta de correo
                email_id TEXT,                                 -- ID único del correo en el servidor
                subject TEXT,                                  -- Asunto del correo
                sender TEXT,                                   -- Remitente
                sender_domain TEXT,                            -- Dominio del remitente
                recipient TEXT,                                -- Destinatario
                content TEXT,                                  -- Contenido del correo
                content_length INTEGER,                        -- Longitud del contenido
                email_size INTEGER,                            -- Tamaño del correo en bytes
                has_attachments BOOLEAN DEFAULT 0,             -- Tiene adjuntos
                attachment_count INTEGER DEFAULT 0,             -- Número de adjuntos
                is_spam BOOLEAN,                              -- Es SPAM (1) o HAM (0)
                confidence FLOAT,                              -- Confianza del modelo (0.0-1.0)
                spam_score FLOAT,                             -- Puntuación de SPAM
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de procesamiento
                received_at TIMESTAMP,                         -- Fecha de recepción
                FOREIGN KEY (account_id) REFERENCES email_accounts(id)
            )
        """)
        
        # 3. TABLA: Catálogo de tipos de SPAM
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS spam_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,                     -- Nombre de la categoría
                description TEXT,                              -- Descripción detallada
                risk_level INTEGER,                            -- Nivel de riesgo (1-5)
                is_active BOOLEAN DEFAULT 1                    -- Categoría activa/inactiva
            )
        """)
        
        # 4. TABLA: Relación correo-categoría de SPAM
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_spam_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER,                              -- ID del correo analizado
                category_id INTEGER,                           -- ID de la categoría de SPAM
                confidence FLOAT,                              -- Confianza en esta categoría
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de detección
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(id),
                FOREIGN KEY (category_id) REFERENCES spam_categories(id)
            )
        """)
        
        # 5. TABLA: Características para detección de SPAM
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS spam_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,                     -- Nombre de la característica
                description TEXT,                              -- Descripción
                weight FLOAT DEFAULT 1.0,                      -- Peso en el modelo
                is_active BOOLEAN DEFAULT 1                    -- Característica activa/inactiva
            )
        """)
        
        # 6. TABLA: Características extraídas de cada correo
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER,                              -- ID del correo
                subject_length INTEGER,                        -- Longitud del asunto
                content_length INTEGER,                        -- Longitud del contenido
                total_length INTEGER,                          -- Longitud total del texto
                caps_ratio FLOAT,                             -- Ratio de mayúsculas
                exclamation_count INTEGER,                     -- Número de exclamaciones
                question_count INTEGER,                        -- Número de interrogaciones
                dollar_count INTEGER,                          -- Número de símbolos $
                urgent_words INTEGER,                          -- Palabras urgentes
                spam_words INTEGER,                            -- Palabras de SPAM
                has_suspicious_domain BOOLEAN,                 -- Dominio sospechoso
                has_many_links INTEGER,                        -- Número de enlaces
                has_attachments BOOLEAN,                       -- Tiene adjuntos
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de extracción
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(id)
            )
        """)
        
        # 7. TABLA: Dominios sospechosos
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS suspicious_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,                   -- Dominio sospechoso
                risk_level INTEGER,                            -- Nivel de riesgo (1-5)
                category_id INTEGER,                           -- Categoría de SPAM asociada
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Primera vez visto
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Última vez visto
                report_count INTEGER DEFAULT 1,                -- Número de reportes
                is_active BOOLEAN DEFAULT 1,                   -- Dominio activo/inactivo
                FOREIGN KEY (category_id) REFERENCES spam_categories(id)
            )
        """)
        
        # 8. TABLA: Estadísticas diarias
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS spam_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,                            -- ID de la cuenta
                date DATE,                                     -- Fecha de las estadísticas
                total_emails INTEGER DEFAULT 0,                -- Total de correos
                spam_count INTEGER DEFAULT 0,                  -- Correos SPAM
                ham_count INTEGER DEFAULT 0,                   -- Correos HAM
                avg_confidence FLOAT,                          -- Confianza promedio
                most_common_category_id INTEGER,               -- Categoría más común
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación
                FOREIGN KEY (account_id) REFERENCES email_accounts(id),
                FOREIGN KEY (most_common_category_id) REFERENCES spam_categories(id)
            )
        """)
        
        # 9. TABLA: Configuraciones de modelos
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,                     -- Nombre del modelo
                algorithm TEXT NOT NULL,                       -- Algoritmo usado
                parameters TEXT,                               -- Parámetros en JSON
                accuracy FLOAT,                                -- Precisión del modelo
                precision FLOAT,                               -- Precisión
                recall FLOAT,                                  -- Recall
                f1_score FLOAT,                               -- F1-Score
                is_active BOOLEAN DEFAULT 0,                   -- Modelo activo/inactivo
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación
                trained_at TIMESTAMP                           -- Fecha de entrenamiento
            )
        """)
        

        
        # 11. TABLA: Patrones de SPAM
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS spam_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,                         -- Patrón o expresión regular
                category_id INTEGER,                           -- Categoría asociada
                weight FLOAT DEFAULT 1.0,                      -- Peso del patrón
                is_regex BOOLEAN DEFAULT 0,                    -- Es expresión regular?
                examples TEXT,                                 -- Ejemplos de uso
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación
                FOREIGN KEY (category_id) REFERENCES spam_categories(id)
            )
        """)
        
        # 12. TABLA: Palabras clave por categoría
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,                           -- Categoría de SPAM
                keyword TEXT NOT NULL,                         -- Palabra clave
                weight FLOAT DEFAULT 1.0,                      -- Peso de la palabra
                is_positive BOOLEAN DEFAULT 1,                 -- 1=indica SPAM, 0=indica HAM
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación
                FOREIGN KEY (category_id) REFERENCES spam_categories(id)
            )
        """)
        
        # 13. TABLA: Feedback del usuario
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER,                              -- ID del correo analizado
                user_classification BOOLEAN,                   -- Clasificación del usuario (SPAM/HAM)
                feedback_notes TEXT,                           -- Notas del usuario
                feedback_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(id) ON DELETE CASCADE
            )
        """)
        
        # 14. TABLA: Modelos de Machine Learning
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,                     -- Nombre del modelo
                description TEXT,                              -- Descripción del modelo
                model_type TEXT NOT NULL,                      -- Tipo: 'spam_detector', 'category_classifier', etc.
                algorithm TEXT NOT NULL,                       -- Algoritmo: 'naive_bayes', 'svm', 'random_forest', etc.
                is_active BOOLEAN DEFAULT 1,                   -- Modelo activo/inactivo
                accuracy REAL DEFAULT 0.0,                     -- Precisión del modelo (0-1)
                total_examples INTEGER DEFAULT 0,              -- Total de ejemplos de entrenamiento
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación
                last_trained_at TIMESTAMP,                     -- Última vez que se entrenó
                model_config TEXT,                             -- Configuración del modelo (JSON)
                model_file_path TEXT                           -- Ruta al archivo del modelo entrenado
            )
        """)
        
        # 15. TABLA: Ejemplos de entrenamiento
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,                     -- ID del modelo
                title TEXT NOT NULL,                           -- Título del ejemplo
                content TEXT NOT NULL,                         -- Contenido del ejemplo
                classification BOOLEAN NOT NULL,               -- Clasificación: 1=SPAM, 0=HAM
                source_type TEXT NOT NULL,                     -- 'manual' o 'email'
                email_id INTEGER,                              -- ID del correo (si viene de email)
                features_extracted TEXT,                       -- Características extraídas (JSON)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación
                created_by TEXT DEFAULT 'system',              -- Quién creó el ejemplo
                is_validated BOOLEAN DEFAULT 0,                -- Si ha sido validado
                FOREIGN KEY (model_id) REFERENCES ml_models(id) ON DELETE CASCADE,
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(id) ON DELETE SET NULL
            )
        """)
        
        # 16. TABLA: Configuraciones de características
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,                     -- ID del modelo
                feature_name TEXT NOT NULL,                    -- Nombre de la característica
                feature_type TEXT NOT NULL,                    -- Tipo: 'text', 'numeric', 'boolean'
                is_enabled BOOLEAN DEFAULT 1,                  -- Si está habilitada
                weight REAL DEFAULT 1.0,                       -- Peso de la característica
                extraction_method TEXT,                        -- Método de extracción
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES ml_models(id) ON DELETE CASCADE
            )
        """)
        
        # 17. TABLA: Evaluaciones de modelos
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,                     -- ID del modelo
                evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accuracy REAL,                                 -- Precisión
                precision REAL,                                -- Precisión para SPAM
                recall REAL,                                   -- Recall para SPAM
                f1_score REAL,                                 -- F1-Score
                confusion_matrix TEXT,                         -- Matriz de confusión (JSON)
                test_examples_count INTEGER,                   -- Número de ejemplos de prueba
                evaluation_notes TEXT,                         -- Notas de la evaluación
                FOREIGN KEY (model_id) REFERENCES ml_models(id) ON DELETE CASCADE
            )
        """)
        
        # 18. TABLA: Historial de entrenamiento
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,                     -- ID del modelo
                training_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                training_examples_count INTEGER,               -- Número de ejemplos usados
                training_accuracy REAL,                        -- Precisión durante entrenamiento
                training_loss REAL,                            -- Pérdida durante entrenamiento
                training_duration REAL,                        -- Duración del entrenamiento (segundos)
                training_parameters TEXT,                      -- Parámetros de entrenamiento (JSON)
                FOREIGN KEY (model_id) REFERENCES ml_models(id) ON DELETE CASCADE
            )
        """)
        
        # Confirmar cambios
        self.conn.commit()
        logger.info("✅ Tablas de Machine Learning creadas exitosamente")
    
    def _run_migrations(self):
        """Ejecuta migraciones necesarias para actualizar la base de datos."""
        try:
            # Migración 1: Agregar columna model_id a training_examples si no existe
            self._migrate_training_examples_table()
            
            logger.info("✅ Migraciones ejecutadas exitosamente")
        except Exception as e:
            logger.error(f"❌ Error ejecutando migraciones: {e}")
    
    def _migrate_training_examples_table(self):
        """Migra la tabla training_examples para agregar las columnas necesarias."""
        try:
            # Verificar columnas existentes
            self.cursor.execute("PRAGMA table_info(training_examples)")
            columns = [column[1] for column in self.cursor.fetchall()]
            
            # Lista de columnas que necesitamos agregar
            columns_to_add = []
            
            if 'model_id' not in columns:
                columns_to_add.append(('model_id', 'INTEGER DEFAULT 1'))
            
            if 'title' not in columns:
                columns_to_add.append(('title', 'TEXT'))
            
            if 'content' not in columns:
                columns_to_add.append(('content', 'TEXT'))
            
            if 'classification' not in columns:
                columns_to_add.append(('classification', 'BOOLEAN'))
            
            if 'source_type' not in columns:
                columns_to_add.append(('source_type', 'TEXT DEFAULT "manual"'))
            
            if 'email_id' not in columns:
                columns_to_add.append(('email_id', 'INTEGER'))
            
            if 'created_by' not in columns:
                columns_to_add.append(('created_by', 'TEXT DEFAULT "system"'))
            
            if 'is_validated' not in columns:
                columns_to_add.append(('is_validated', 'BOOLEAN DEFAULT 0'))
            
            # Agregar columnas faltantes
            for column_name, column_def in columns_to_add:
                logger.info(f"🔄 Agregando columna {column_name} a training_examples...")
                self.cursor.execute(f"""
                    ALTER TABLE training_examples 
                    ADD COLUMN {column_name} {column_def}
                """)
            
            # Migrar datos existentes si es necesario
            if columns_to_add and 'email_content' in columns:
                logger.info("🔄 Migrando datos existentes...")
                
                # Actualizar contenido y título basado en datos existentes
                self.cursor.execute("""
                    UPDATE training_examples 
                    SET content = COALESCE(email_content, ''),
                        title = COALESCE(subject, 'Sin título'),
                        classification = COALESCE(is_spam, 0),
                        source_type = 'legacy'
                    WHERE content IS NULL OR title IS NULL OR classification IS NULL
                """)
            
            # Crear índices si no existen
            if 'model_id' in [col[0] for col in columns_to_add]:
                self.cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_training_examples_model_id 
                    ON training_examples(model_id)
                """)
            
            self.conn.commit()
            
            if columns_to_add:
                logger.info(f"✅ Migración completada. Columnas agregadas: {[col[0] for col in columns_to_add]}")
            else:
                logger.info("✅ Tabla training_examples ya está actualizada")
                
        except Exception as e:
            logger.error(f"❌ Error migrando tabla training_examples: {e}")
            raise
    
    def initialize_catalogs(self):
        """
        Inicializa los catálogos con datos por defecto.
        
        CATÁLOGOS INICIALIZADOS:
        1. spam_categories - Tipos de SPAM
        2. spam_features - Características de detección
        3. spam_patterns - Patrones comunes
        4. category_keywords - Palabras clave
        """
        
        # 1. CATÁLOGO: Tipos de SPAM
        categories = [
            (1, 'Phishing', 'Suplantación de identidad para robar datos', 5),
            (2, 'Scam', 'Estafa o fraude general', 4),
            (3, 'Malware', 'Software malicioso', 5),
            (4, 'Spam Comercial', 'Publicidad no deseada', 2),
            (5, 'Sextorsion', 'Extorsión sexual', 5),
            (6, 'Lottery Scam', 'Estafa de lotería', 4),
            (7, 'Nigerian Prince', 'Estafa del príncipe nigeriano', 4),
            (8, 'Tech Support', 'Soporte técnico falso', 4),
            (9, 'Romance Scam', 'Estafa romántica', 4),
            (10, 'Investment Scam', 'Estafa de inversión', 4)
        ]
        
        for cat_id, name, desc, risk in categories:
            self.cursor.execute("""
                INSERT OR IGNORE INTO spam_categories (id, name, description, risk_level)
                VALUES (?, ?, ?, ?)
            """, (cat_id, name, desc, risk))
        
        # 2. CATÁLOGO: Características de detección
        features = [
            (1, 'URGENT_WORDS', 'Palabras urgentes (URGENTE, INMEDIATO)', 1.5),
            (2, 'MONEY_WORDS', 'Palabras relacionadas con dinero', 1.3),
            (3, 'FREE_WORDS', 'Palabras gratuitas (GRATIS, FREE)', 1.2),
            (4, 'CAPS_RATIO', 'Proporción de mayúsculas', 1.4),
            (5, 'EXCLAMATION_COUNT', 'Número de exclamaciones', 1.3),
            (6, 'LINK_COUNT', 'Número de enlaces', 1.2),
            (7, 'SUSPICIOUS_DOMAIN', 'Dominio sospechoso', 2.0),
            (8, 'ATTACHMENT_TYPE', 'Tipo de archivo adjunto', 1.8),
            (9, 'SENDER_REPUTATION', 'Reputación del remitente', 1.6),
            (10, 'CONTENT_LENGTH', 'Longitud del contenido', 1.1)
        ]
        
        for feat_id, name, desc, weight in features:
            self.cursor.execute("""
                INSERT OR IGNORE INTO spam_features (id, name, description, weight)
                VALUES (?, ?, ?, ?)
            """, (feat_id, name, desc, weight))
        
        # 3. CATÁLOGO: Patrones comunes de SPAM
        patterns = [
            ('URGENTE|INMEDIATO|CRÍTICO', 1, 1.5, 0, 'URGENTE: Su cuenta ha sido suspendida'),
            ('GRATIS|FREE|SIN COSTO', 4, 1.2, 0, 'Gana dinero GRATIS'),
            ('\\$\\d+', 2, 1.3, 1, 'Gana $1000 al día'),
            ('príncipe nigeriano', 7, 2.0, 0, 'Soy un príncipe nigeriano'),
            ('viagra|cialis', 4, 1.8, 0, 'Compre viagra barato'),
            ('\\b[A-Z]{3,}\\b', 1, 1.4, 1, 'URGENTE ACTUAR AHORA')
        ]
        
        for pattern, cat_id, weight, is_regex, examples in patterns:
            self.cursor.execute("""
                INSERT OR IGNORE INTO spam_patterns (pattern, category_id, weight, is_regex, examples)
                VALUES (?, ?, ?, ?, ?)
            """, (pattern, cat_id, weight, is_regex, examples))
        
        # 4. CATÁLOGO: Palabras clave por categoría
        keywords = [
            # Phishing
            (1, 'banco', 1.3), (1, 'cuenta', 1.4), (1, 'suspender', 1.8),
            (1, 'verificar', 1.5), (1, 'seguridad', 1.2),
            # Scam
            (2, 'dinero', 1.3), (2, 'ganar', 1.4), (2, 'millones', 1.6),
            (2, 'herencia', 1.7), (2, 'inversión', 1.5),
            # Malware
            (3, 'descargar', 1.2), (3, 'actualizar', 1.3), (3, 'virus', 1.8),
            (3, 'seguridad', 1.4), (3, 'escaneo', 1.5)
        ]
        
        for cat_id, keyword, weight in keywords:
            self.cursor.execute("""
                INSERT OR IGNORE INTO category_keywords (category_id, keyword, weight)
                VALUES (?, ?, ?)
            """, (cat_id, keyword, weight))
        
        self.conn.commit()
        logger.info("✅ Catálogos inicializados exitosamente")
    
    # ===== MÉTODOS CRUD PARA MODELOS DE MACHINE LEARNING =====
    
    def create_ml_model(self, name: str, description: str, model_type: str, algorithm: str, model_config: dict = None) -> int:
        """
        Crea un nuevo modelo de Machine Learning.
        
        Args:
            name (str): Nombre del modelo
            description (str): Descripción del modelo
            model_type (str): Tipo de modelo ('spam_detector', 'category_classifier', etc.)
            algorithm (str): Algoritmo a usar ('naive_bayes', 'svm', 'random_forest', etc.)
            model_config (dict): Configuración del modelo
            
        Returns:
            int: ID del modelo creado
        """
        try:
            config_json = json.dumps(model_config) if model_config else None
            
            self.cursor.execute("""
                INSERT INTO ml_models (name, description, model_type, algorithm, model_config)
                VALUES (?, ?, ?, ?, ?)
            """, (name, description, model_type, algorithm, config_json))
            
            model_id = self.cursor.lastrowid
            self.conn.commit()
            
            logger.info(f"✅ Modelo '{name}' creado exitosamente (ID: {model_id})")
            return model_id
            
        except Exception as e:
            logger.error(f"❌ Error creando modelo: {e}")
            raise
    
    def get_ml_models(self, active_only: bool = False) -> List[Dict]:
        """
        Obtiene todos los modelos de Machine Learning.
        
        Args:
            active_only (bool): Si True, solo retorna modelos activos
            
        Returns:
            List[Dict]: Lista de modelos
        """
        try:
            query = "SELECT * FROM ml_models"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"
            
            self.cursor.execute(query)
            models = [dict(row) for row in self.cursor.fetchall()]
            
            return models
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo modelos: {e}")
            return []
    
    def get_ml_model(self, model_id: int) -> Optional[Dict]:
        """
        Obtiene un modelo específico por ID.
        
        Args:
            model_id (int): ID del modelo
            
        Returns:
            Optional[Dict]: Modelo o None si no existe
        """
        try:
            self.cursor.execute("SELECT * FROM ml_models WHERE id = ?", (model_id,))
            row = self.cursor.fetchone()
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo modelo {model_id}: {e}")
            return None
    
    def update_ml_model(self, model_id: int, **kwargs) -> bool:
        """
        Actualiza un modelo de Machine Learning.
        
        Args:
            model_id (int): ID del modelo
            **kwargs: Campos a actualizar
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        try:
            # Construir query dinámicamente
            fields = []
            values = []
            
            for field, value in kwargs.items():
                if field in ['name', 'description', 'model_type', 'algorithm', 'is_active', 'accuracy', 'total_examples', 'model_config', 'model_file_path']:
                    fields.append(f"{field} = ?")
                    values.append(value)
            
            if not fields:
                return False
            
            values.append(model_id)
            query = f"UPDATE ml_models SET {', '.join(fields)} WHERE id = ?"
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            logger.info(f"✅ Modelo {model_id} actualizado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error actualizando modelo {model_id}: {e}")
            return False
    
    def delete_ml_model(self, model_id: int) -> bool:
        """
        Elimina un modelo de Machine Learning.
        
        Args:
            model_id (int): ID del modelo
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            self.cursor.execute("DELETE FROM ml_models WHERE id = ?", (model_id,))
            self.conn.commit()
            
            logger.info(f"✅ Modelo {model_id} eliminado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error eliminando modelo {model_id}: {e}")
            return False
    
    # ===== MÉTODOS CRUD PARA EJEMPLOS DE ENTRENAMIENTO =====
    
    def add_training_example(self, model_id: int, title: str, content: str, classification: bool, 
                           source_type: str = 'manual', email_id: int = None, features_extracted: dict = None) -> int:
        """
        Agrega un ejemplo de entrenamiento a un modelo.
        
        Args:
            model_id (int): ID del modelo
            title (str): Título del ejemplo
            content (str): Contenido del ejemplo
            classification (bool): Clasificación (True=SPAM, False=HAM)
            source_type (str): 'manual' o 'email'
            email_id (int): ID del correo (si viene de email)
            features_extracted (dict): Características extraídas
            
        Returns:
            int: ID del ejemplo creado
        """
        try:
            features_json = json.dumps(features_extracted) if features_extracted else None
            
            self.cursor.execute("""
                INSERT INTO training_examples (model_id, title, content, classification, source_type, email_id, features_extracted)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (model_id, title, content, classification, source_type, email_id, features_json))
            
            example_id = self.cursor.lastrowid
            
            # Actualizar contador de ejemplos del modelo
            self.cursor.execute("""
                UPDATE ml_models 
                SET total_examples = total_examples + 1 
                WHERE id = ?
            """, (model_id,))
            
            self.conn.commit()
            
            logger.info(f"✅ Ejemplo de entrenamiento agregado (ID: {example_id})")
            return example_id
            
        except Exception as e:
            logger.error(f"❌ Error agregando ejemplo de entrenamiento: {e}")
            raise
    
    def get_training_examples(self, model_id: int, limit: int = 100) -> List[Dict]:
        """
        Obtiene ejemplos de entrenamiento de un modelo.
        
        Args:
            model_id (int): ID del modelo
            limit (int): Límite de ejemplos a retornar
            
        Returns:
            List[Dict]: Lista de ejemplos
        """
        try:
            self.cursor.execute("""
                SELECT te.*, ae.subject as email_subject, ae.sender as email_sender
                FROM training_examples te
                LEFT JOIN analyzed_emails ae ON te.email_id = ae.id
                WHERE te.model_id = ?
                ORDER BY te.created_at DESC
                LIMIT ?
            """, (model_id, limit))
            
            examples = [dict(row) for row in self.cursor.fetchall()]
            return examples
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo ejemplos de entrenamiento: {e}")
            return []
    
    def update_training_example(self, example_id: int, **kwargs) -> bool:
        """
        Actualiza un ejemplo de entrenamiento.
        
        Args:
            example_id (int): ID del ejemplo
            **kwargs: Campos a actualizar
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        try:
            fields = []
            values = []
            
            for field, value in kwargs.items():
                if field in ['title', 'content', 'classification', 'is_validated']:
                    fields.append(f"{field} = ?")
                    values.append(value)
            
            if not fields:
                return False
            
            values.append(example_id)
            query = f"UPDATE training_examples SET {', '.join(fields)} WHERE id = ?"
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            logger.info(f"✅ Ejemplo {example_id} actualizado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error actualizando ejemplo {example_id}: {e}")
            return False
    
    def delete_training_example(self, example_id: int) -> bool:
        """
        Elimina un ejemplo de entrenamiento.
        
        Args:
            example_id (int): ID del ejemplo
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            # Obtener model_id antes de eliminar
            self.cursor.execute("SELECT model_id FROM training_examples WHERE id = ?", (example_id,))
            row = self.cursor.fetchone()
            
            if row:
                model_id = row['model_id']
                
                # Eliminar ejemplo
                self.cursor.execute("DELETE FROM training_examples WHERE id = ?", (example_id,))
                
                # Actualizar contador del modelo
                self.cursor.execute("""
                    UPDATE ml_models 
                    SET total_examples = total_examples - 1 
                    WHERE id = ?
                """, (model_id,))
                
                self.conn.commit()
                
                logger.info(f"✅ Ejemplo {example_id} eliminado exitosamente")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error eliminando ejemplo {example_id}: {e}")
            return False
    
    def get_training_statistics(self, model_id: int) -> Dict:
        """
        Obtiene estadísticas de entrenamiento de un modelo.
        
        Args:
            model_id (int): ID del modelo
            
        Returns:
            Dict: Estadísticas del modelo
        """
        try:
            # Estadísticas generales
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total_examples,
                    SUM(CASE WHEN classification = 1 THEN 1 ELSE 0 END) as spam_examples,
                    SUM(CASE WHEN classification = 0 THEN 1 ELSE 0 END) as ham_examples,
                    SUM(CASE WHEN source_type = 'manual' THEN 1 ELSE 0 END) as manual_examples,
                    SUM(CASE WHEN source_type = 'email' THEN 1 ELSE 0 END) as email_examples,
                    SUM(CASE WHEN is_validated = 1 THEN 1 ELSE 0 END) as validated_examples
                FROM training_examples 
                WHERE model_id = ?
            """, (model_id,))
            
            stats = dict(self.cursor.fetchone())
            
            # Últimos ejemplos agregados
            self.cursor.execute("""
                SELECT created_at, title, classification, source_type
                FROM training_examples 
                WHERE model_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            """, (model_id,))
            
            recent_examples = [dict(row) for row in self.cursor.fetchall()]
            stats['recent_examples'] = recent_examples
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas de entrenamiento: {e}")
            return {}
    
    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()
            logger.info("✅ Conexión a base de datos cerrada")

# Función de conveniencia para crear instancia
def create_database(db_path: str = "spam_detector.db") -> SpamDatabase:
    """
    Función helper para crear una instancia de la base de datos.
    
    Args:
        db_path (str): Ruta al archivo de base de datos
        
    Returns:
        SpamDatabase: Instancia de la base de datos
    """
    return SpamDatabase(db_path)

if __name__ == "__main__":
    # Test de la base de datos
    db = create_database()
    print("✅ Base de datos creada exitosamente")
    db.close() 