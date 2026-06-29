import sys
from loguru import logger
from google.cloud import logging as gcp_logging


def setup_logging():
    logger.remove()

    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    try:
        gcp_client = gcp_logging.Client()

        class GCPSink:
            def write(self, message):
                record = message.record
                level = record["level"].name
                log_entry = {
                    "message": record["message"],
                    "level": level,
                    "module": record["name"],
                    "line": record["line"],
                    "extra": record["extra"],
                }
                gcp_client.logger("termiqueue-backend").log_struct(
                    log_entry,
                    severity=level,
                )

            def flush(self):
                pass

        logger.add(GCPSink(), level="INFO")
        logger.info("GCP Cloud Logging initialized")

    except Exception as e:
        logger.warning(f"GCP Cloud Logging not available: {e}")


setup_logging()
