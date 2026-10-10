"""
Arbitraje P2P y Umbrales Dinámicos (Fase 3)
core/dynamic_threshold.py

Objetivo:
- Alertas inteligentes que se adaptan a la volatilidad del mercado.
- Lee las últimas operaciones de Planilla_Arbitraje_Alan.xlsx con Pandas.
- Calcula el spread promedio reciente y la volatilidad.
- Ajusta dinámicamente el "Umbral mínimo de ganancia" antes de disparar webhooks de Discord o Telegram.
- Silencia alertas cuando el mercado está "chato" y las activa ante picos de volatilidad.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np

DEFAULT_EXCEL_PATH = ROOT_DIR / "Planilla_Arbitraje_Alan.xlsx"


class ArbitrageDataStore:
    """Responsable exclusivamente de la lectura y creación de la plantilla de arbitraje."""

    @classmethod
    def ensure_excel_exists(cls, filepath: Path = DEFAULT_EXCEL_PATH) -> Path:
        """Si la planilla no existe, genera una estructura inicial con operaciones de muestra."""
        if not filepath.exists():
            print(f"ℹ️ Creando planilla de arbitraje inicial en: {filepath.name}")
            fechas = [datetime.now() - timedelta(minutes=15 * i) for i in range(30)][::-1]
            # Simulación de operaciones con diferentes spreads (chatos y con picos)
            base_spreads = [1.1, 1.2, 1.05, 1.15, 0.95, 1.0, 1.1, 1.25, 2.4, 3.1, 1.8, 1.2, 1.0, 0.9, 0.85]
            spreads = (base_spreads * 2)[:30]

            data = {
                "Fecha": [f.strftime("%Y-%m-%d %H:%M") for f in fechas],
                "Tipo_Operacion": ["P2P_COMPRA_VENTA"] * 30,
                "Cripto": ["USDT"] * 30,
                "Moneda_Fiat": ["ARS"] * 30,
                "Precio_Compra": [1280.0 + (i * 0.5) for i in range(30)],
                "Precio_Venta": [1280.0 * (1 + s / 100.0) for s in spreads],
                "Comision_Pct": [0.15] * 30,
                "Spread_Pct": spreads,
                "Volumen_USDT": [1500 + (i * 50) for i in range(30)],
                "Estado": ["COMPLETADA"] * 30
            }
            df = pd.DataFrame(data)
            df.to_excel(filepath, index=False)
        return filepath

    @classmethod
    def load_recent_operations(cls, filepath: Path = DEFAULT_EXCEL_PATH, last_n: int = 25) -> pd.DataFrame:
        """Lee las últimas operaciones de la planilla."""
        cls.ensure_excel_exists(filepath)
        try:
            df = pd.read_excel(filepath)
            if df.empty:
                return pd.DataFrame()
            return df.tail(last_n)
        except Exception as e:
            print(f"Error al leer planilla de arbitraje {filepath}: {e}")
            return pd.DataFrame()


class SpreadMetricsCalculator:
    """Responsable del cálculo estadístico sobre los spreads recientes."""

    @staticmethod
    def calculate_metrics(df: pd.DataFrame) -> Dict[str, float]:
        if df.empty or "Spread_Pct" not in df.columns:
            return {
                "spread_promedio": 1.2,
                "volatilidad": 0.2,
                "spread_minimo": 1.0,
                "spread_maximo": 1.5,
                "mercado_chato": True
            }

        spreads = df["Spread_Pct"].dropna().astype(float)
        promedio = float(spreads.mean())
        volatilidad = float(spreads.std() if len(spreads) > 1 else 0.1)
        minimo = float(spreads.min())
        maximo = float(spreads.max())

        # Un mercado se considera "chato" si la volatilidad reciente es muy reducida
        # o el spread promedio cae por debajo del 1.1%
        mercado_chato = bool(volatilidad < 0.25 or promedio < 1.05)

        return {
            "spread_promedio": round(promedio, 3),
            "volatilidad": round(volatilidad, 3),
            "spread_minimo": round(minimo, 3),
            "spread_maximo": round(maximo, 3),
            "mercado_chato": mercado_chato
        }


class DynamicThresholdManager:
    """
    Gestor de umbrales dinámicos.
    Adapta el umbral mínimo de ganancia en función de la volatilidad y estado del mercado.
    """

    def __init__(self, base_profit_threshold: float = 1.3, excel_path: Path = DEFAULT_EXCEL_PATH):
        self.base_profit_threshold = base_profit_threshold
        self.excel_path = excel_path

    def compute_dynamic_threshold(self) -> Dict[str, Any]:
        """
        Calcula el umbral dinámico actual y evalúa el régimen de mercado.
        """
        df = ArbitrageDataStore.load_recent_operations(self.excel_path)
        metrics = SpreadMetricsCalculator.calculate_metrics(df)

        spread_prom = metrics["spread_promedio"]
        vol = metrics["volatilidad"]
        es_chato = metrics["mercado_chato"]

        if es_chato:
            # Mercado chato: Elevamos el umbral para evitar alertas falsas/ruido
            umbral_dinamico = max(self.base_profit_threshold, spread_prom + 1.5 * vol)
            estado_alertas = "SILENCIADAS_MERCADO_CHATO"
        else:
            # Mercado con volatilidad: El umbral acompaña los picos
            umbral_dinamico = max(self.base_profit_threshold, spread_prom + 0.8 * vol)
            estado_alertas = "ACTIVAS_VOLATILIDAD"

        return {
            "umbral_dinamico_pct": round(float(umbral_dinamico), 3),
            "spread_promedio_pct": spread_prom,
            "volatilidad_pct": vol,
            "mercado_chato": es_chato,
            "estado_alertas": estado_alertas,
            "operaciones_analizadas": len(df)
        }

    def should_dispatch_alert(self, spread_detectado: float) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Decide si se debe disparar la alerta a webhooks (Discord / Telegram).
        
        Reglas:
        - Si el mercado está chato y el spread no supera un pico extraordinario -> Silenciar.
        - Si el spread detectado supera el umbral dinámico -> Disparar alerta.
        """
        info = self.compute_dynamic_threshold()
        umbral = info["umbral_dinamico_pct"]
        es_chato = info["mercado_chato"]

        if spread_detectado < umbral:
            razon = (
                f"Alerta silenciada: Spread actual ({spread_detectado:.2f}%) "
                f"inferior al umbral dinámico ({umbral:.2f}%)."
            )
            return False, razon, info

        if es_chato and spread_detectado < (umbral * 1.2):
            razon = (
                f"Alerta silenciada: Mercado chato (volatilidad baja). "
                f"Spread ({spread_detectado:.2f}%) no califica como pico relevante."
            )
            return False, razon, info

        razon = (
            f"🔥 ¡PICO DE VOLATILIDAD DETECTADO! Spread ({spread_detectado:.2f}%) "
            f"superó el umbral dinámico ({umbral:.2f}%)."
        )
        return True, razon, info


class ArbitrageWebhookDispatcher:
    """Responsable del envío desacoplado de alertas a Discord y Telegram."""

    @staticmethod
    def send_alert(
        spread_detectado: float,
        cripto: str = "USDT",
        fiat: str = "ARS",
        threshold_manager: Optional[DynamicThresholdManager] = None
    ) -> Dict[str, Any]:
        mgr = threshold_manager or DynamicThresholdManager()
        debe_disparar, razon, info = mgr.should_dispatch_alert(spread_detectado)

        resultado = {
            "disparado": debe_disparar,
            "razon": razon,
            "metricas": info,
            "canales": []
        }

        if not debe_disparar:
            print(f"🔇 [UmbralDinámico] {razon}")
            return resultado

        # Construir payload de alerta para webhooks
        mensaje = (
            f"🚀 **ALERTA DE ARBITRAJE P2P**\n"
            f"• Par: **{cripto}/{fiat}**\n"
            f"• Spread Actual: **{spread_detectado:.2f}%**\n"
            f"• Umbral Dinámico: **{info['umbral_dinamico_pct']:.2f}%** (Promedio: {info['spread_promedio_pct']:.2f}%)\n"
            f"• Régimen: **{info['estado_alertas']}**\n"
            f"• Hora: {datetime.now().strftime('%H:%M:%S')}"
        )

        # 1. Integración Discord
        discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
        if discord_webhook:
            try:
                import httpx
                httpx.post(discord_webhook, json={"content": mensaje}, timeout=5.0)
                resultado["canales"].append("Discord")
            except Exception as e:
                print(f"Error enviando webhook a Discord: {e}")

        # 2. Integración Telegram
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if telegram_token and telegram_chat_id:
            try:
                import httpx
                url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                httpx.post(url, json={"chat_id": telegram_chat_id, "text": mensaje, "parse_mode": "Markdown"}, timeout=5.0)
                resultado["canales"].append("Telegram")
            except Exception as e:
                print(f"Error enviando alerta a Telegram: {e}")

        print(f"📢 [UmbralDinámico] {razon} Canales notificados: {resultado['canales'] or 'Modo Simulación (Sin webhooks configurados)'}")
        return resultado


if __name__ == "__main__":
    manager = DynamicThresholdManager()
    status = manager.compute_dynamic_threshold()
    print("Estado del Umbral Dinámico:", json.dumps(status, indent=2, ensure_ascii=False))

    # Prueba con spread chato (debe silenciarse)
    print("\n--- Test 1: Spread chato (0.95%) ---")
    ArbitrageWebhookDispatcher.send_alert(0.95, threshold_manager=manager)

    # Prueba con pico de volatilidad (debe activarse)
    print("\n--- Test 2: Pico de volatilidad (2.85%) ---")
    ArbitrageWebhookDispatcher.send_alert(2.85, threshold_manager=manager)
