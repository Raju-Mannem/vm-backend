import ssl
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "bill_processor",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # Auto discover tasks in the worker folder
    include=["app.worker.tasks"] 
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Prevent tasks from hanging indefinitely
    task_time_limit=300,        # Hard kill after 5 minutes
    task_soft_time_limit=240,   # Raise exception after 4 minutes
    broker_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE
    },
)