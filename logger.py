import logging
import sys
import traceback
from contextvars import ContextVar

# ContextVar to store task_id dynamically in async contexts/threads
task_id_var: ContextVar[str] = ContextVar("task_id", default="SYSTEM")

class TaskIdFilter(logging.Filter):
    def filter(self, record):
        # Inject the current task_id into the log record.
        # If task_id_var is not set, it defaults to "SYSTEM"
        record.task_id = task_id_var.get()
        return True

def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Formatter requirement: [%(asctime)s] [%(levelname)s] [Task-ID: %(task_id)s] [%(filename)s:%(lineno)d] - %(message)s
    log_format = "[%(asctime)s] [%(levelname)s] [Task-ID: %(task_id)s] [%(filename)s:%(lineno)d] - %(message)s"
    formatter = logging.Formatter(log_format)
    
    # Filter
    task_filter = TaskIdFilter()
    
    # Console Handler (INFO level and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(task_filter)
    logger.addHandler(console_handler)
    
    # File Handler (DEBUG level and above, writes to app.log)
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(task_filter)
    logger.addHandler(file_handler)
    
    return logger

class AppLogger:
    def __init__(self):
        self.logger = get_logger()
        
    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
        
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
        
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
        
    def error(self, msg, *args, **kwargs):
        # Automatically capture traceback and append it to the log message
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            tb_str = traceback.format_exc()
            msg = f"{msg}\nException Stack Trace:\n{tb_str}"
        self.logger.error(msg, *args, **kwargs)

    def set_task_id(self, task_id: str):
        task_id_var.set(task_id)

    def get_task_id(self) -> str:
        return task_id_var.get()

logger = AppLogger()
