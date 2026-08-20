import threading
import os
from apscheduler.schedulers.background import BackgroundScheduler
from services.openbible_service import OpenBibleService
from services.etl_processor import forzar_reprocesamiento_total

class SchedulerService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SchedulerService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.scheduler = BackgroundScheduler()
        self.openbible_service = OpenBibleService()
        self._setup_jobs()
        self._initialized = True

    def _setup_jobs(self):
        # Si detectamos que estamos en producción (Hugging Face Spaces), desactivamos el ETL
        # para que la app inicie de forma ligera y no intente procesar datos sin las carpetas locales.
        if os.environ.get("TURSO_DATABASE_URL"):
            print("🚀 Modo Producción detectado. Cron Jobs de ETL desactivados para optimizar el arranque.")
            return

        # Programar los trabajos de OpenBible para que corran una vez por semana (ej. Domingo a las 3 AM)
        self.scheduler.add_job(
            self.openbible_service.sync_topics,
            'cron',
            day_of_week='sun',
            hour=3,
            minute=0,
            id='sync_topics',
            replace_existing=True
        )
        self.scheduler.add_job(
            self.openbible_service.sync_cross_references,
            'cron',
            day_of_week='sun',
            hour=3,
            minute=30,
            id='sync_cross_references',
            replace_existing=True
        )
        self.scheduler.add_job(
            self.openbible_service.sync_geocoding,
            'cron',
            day_of_week='sun',
            hour=4,
            minute=0,
            id='sync_geocoding',
            replace_existing=True
        )
        self.scheduler.add_job(
            forzar_reprocesamiento_total,
            'cron',
            day_of_week='sun',
            hour=5,
            minute=0,
            id='etl_hard_reset',
            replace_existing=True
        )
        
        # Job para Discord Webhooks varias veces al día
        try:
            from cron_reminders import trigger_discord_reminder
            self.scheduler.add_job(
                trigger_discord_reminder,
                'cron',
                hour='9,14,19', # 9:00 AM, 2:00 PM, 7:00 PM
                minute=0,
                id='discord_daily_reminder',
                replace_existing=True
            )
        except ImportError as e:
            print(f"[SchedulerService] Error al importar trigger_discord_reminder: {e}. Tarea omitida.")

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            print("Background Scheduler iniciado. Cron jobs programados.")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Background Scheduler detenido.")
