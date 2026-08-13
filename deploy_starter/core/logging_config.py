import logging
import os
import socket
from logging.handlers import RotatingFileHandler

from core.config import config


# Initialize application logger
# - APP_LOG_DIR: env override; default `/home/admin/app_logs`
# - LOG_LEVEL: env or config.yml; default INFO
# - File: `app.log` with rotation (50MB x 5); also outputs to stdout
LOG_DIR = os.getenv("APP_LOG_DIR", "/home/admin/app_logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_level = (os.getenv("LOG_LEVEL") or config.get("LOG_LEVEL", "INFO")).upper()

logger = logging.getLogger("agent_app")
logger.setLevel(_log_level)

if not logger.handlers:
    _formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    log_name = os.getenv("LOG_FILE_NAME") or config.get("LOG_FILE_NAME", "app.log")
    _file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_name),
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    _file_handler.setFormatter(_formatter)
    logger.addHandler(_file_handler)

    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(_formatter)
    logger.addHandler(_stream_handler)


def get_local_ip() -> str:
    """获取当前节点的 IP 地址"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


LOCAL_IP = get_local_ip()


def success_response(data=None, message="success"):
    """标准 HTTP 响应格式"""
    return {"code": 200, "message": message, "data": data, "host": LOCAL_IP}


def error_response(message="error", code=500, data=None):
    """标准错误响应格式"""
    return {"code": code, "message": message, "data": data, "host": LOCAL_IP}
