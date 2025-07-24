import logging
import json
import os
from datetime import datetime

class StructuredLogger:
    def __init__(self, name: str, log_dir: str = 'logs'):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Crear directorio de logs si no existe
        os.makedirs(log_dir, exist_ok=True)
        
        # Evitar duplicar handlers
        if not self.logger.handlers:
            self._setup_handlers(log_dir)
    
    def _setup_handlers(self, log_dir: str):      
        # Formatter para logs estructurados
        json_formatter = logging.Formatter('%(message)s')
        
        # Formatter para consola más legible
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Handler para archivo JSON
        today = datetime.now().strftime('%Y%m%d')
        json_file = os.path.join(log_dir, f'scraper_{today}.jsonl')
        file_handler = logging.FileHandler(json_file, encoding='utf-8')
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(logging.INFO)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        
        # Añadir handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log(self, level: str, message: str, **kwargs):
        # Crear entrada de log estructurada
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.upper(),
            'logger': self.name,
            'message': message,
            **kwargs
        }
        
        # Log estructurado para archivo
        json_message = json.dumps(log_entry, ensure_ascii=False)
        
        # Log legible para consola
        extra_info = []
        for key, value in kwargs.items():
            if isinstance(value, (str, int, float, bool)):
                extra_info.append(f"{key}={value}")
        
        console_message = message
        if extra_info:
            console_message += f" | {' | '.join(extra_info)}"
        
        # Enviar a handlers apropiados
        if level.upper() == 'ERROR':
            # Para errores, usar el mensaje JSON en ambos
            self.logger.error(json_message)
        elif level.upper() == 'WARNING':
            self.logger.warning(console_message)
            # También enviar JSON al archivo
            file_handler = next(
                (h for h in self.logger.handlers 
                 if isinstance(h, logging.FileHandler)), None
            )
            if file_handler:
                file_handler.emit(
                    logging.LogRecord(
                        self.name, logging.WARNING, '', 0, json_message, (), None
                    )
                )
        else:
            self.logger.info(console_message)
            # También enviar JSON al archivo
            file_handler = next(
                (h for h in self.logger.handlers 
                 if isinstance(h, logging.FileHandler)), None
            )
            if file_handler:
                file_handler.emit(
                    logging.LogRecord(
                        self.name, logging.INFO, '', 0, json_message, (), None
                    )
                )
    
    def info(self, message: str, **kwargs):
        self.log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log('ERROR', message, **kwargs)