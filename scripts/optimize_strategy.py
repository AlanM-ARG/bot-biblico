"""
Machine Learning para Trading (Fase 2)
scripts/optimize_strategy.py

Objetivo:
- Auto-ajustar algoritmos sin tocar el código manualmente.
- Conecta la librería Optuna a un motor de backtesting técnico (RSI, MACD, Medias Móviles).
- Ejecuta 100 pruebas (trials) maximizando el retorno neto (ROI).
- Envuelve la función objetivo con mlflow.start_run() para telemetría y trazabilidad.
- Guarda el mejor resultado en la tabla system_settings de biblico.db.
"""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from database.connection import get_connection, DB_PATH

# Importaciones condicionales para Optuna y MLflow con graceful fallback
try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False

try:
    import mlflow
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False


class BacktestEngine:
    """Motor modular de backtesting para estrategias técnicas (RSI, MACD, MA)."""

    def __init__(self, price_series: Optional[pd.Series] = None):
        if price_series is None:
            # Generar serie sintética realista (Random walk con drift y estacionalidad)
            np.random.seed(42)
            steps = 500
            returns = np.random.normal(0.0005, 0.015, steps)
            prices = 100.0 * np.exp(np.cumsum(returns))
            self.prices = pd.Series(prices, name="close")
        else:
            self.prices = price_series

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss.replace(0, 1e-9))
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line

    def run_strategy(
        self,
        rsi_period: int,
        rsi_oversold: float,
        rsi_overbought: float,
        macd_fast: int,
        macd_slow: int,
        macd_signal: int,
        ma_fast: int,
        ma_slow: int
    ) -> Dict[str, float]:
        df = pd.DataFrame({"close": self.prices})
        df["rsi"] = self.calculate_rsi(df["close"], period=rsi_period)
        df["macd"], df["macd_signal"] = self.calculate_macd(df["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal)
        df["ma_fast"] = df["close"].rolling(window=ma_fast).mean()
        df["ma_slow"] = df["close"].rolling(window=ma_slow).mean()

        # Generar señales combinadas
        # Compra: RSI en sobreventa + MACD cruza hacia arriba + tendencia alcista (MA fast > slow)
        buy_condition = (
            (df["rsi"] < rsi_oversold) |
            ((df["macd"] > df["macd_signal"]) & (df["ma_fast"] > df["ma_slow"]))
        )
        # Venta: RSI en sobrecompra o MACD cruza hacia abajo
        sell_condition = (
            (df["rsi"] > rsi_overbought) |
            (df["macd"] < df["macd_signal"])
        )

        df["position"] = 0
        df.loc[buy_condition, "position"] = 1
        df.loc[sell_condition, "position"] = 0
        df["position"] = df["position"].ffill().fillna(0)

        # Retornos diarios de la estrategia
        df["market_return"] = df["close"].pct_change().fillna(0)
        df["strategy_return"] = df["position"].shift(1).fillna(0) * df["market_return"]

        # Retorno acumulado / ROI neto (%)
        cumulative_return = (1 + df["strategy_return"]).prod() - 1
        net_roi = float(cumulative_return * 100.0)

        # Métricas complementarias
        win_trades = (df["strategy_return"] > 0).sum()
        total_trades = (df["position"].diff() != 0).sum()
        win_rate = float(win_trades / max(total_trades, 1) * 100.0)

        return {
            "roi": net_roi,
            "win_rate": win_rate,
            "total_trades": float(total_trades)
        }


def save_best_settings_to_db(best_params: Dict[str, Any], best_roi: float):
    """Guarda la mejor combinación encontrada en la tabla system_settings."""
    conn = get_connection()
    cursor = conn.cursor()

    payload = {
        "strategy": "RSI_MACD_MA_Optimizer",
        "best_roi_pct": round(best_roi, 4),
        "parameters": best_params,
        "optimized_at": datetime.now().isoformat(),
        "trials_evaluated": 100
    }

    cursor.execute("""
        INSERT INTO system_settings (key, value, updated_at)
        VALUES ('trading_strategy_best_params', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET 
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
    """, (json.dumps(payload, indent=2),))

    conn.commit()
    conn.close()
    print(f"💾 Parámetros óptimos guardados exitosamente en system_settings (ROI: {best_roi:.2f}%).")


def run_optimization(n_trials: int = 100):
    """Ejecuta la optimización bayesiana con Optuna y registro en MLflow."""
    print(f"🚀 Iniciando optimización de estrategia ({n_trials} trials)...")
    engine = BacktestEngine()

    if HAS_MLFLOW:
        mlflow.set_experiment("Trading_Strategy_Optimization")

    if not HAS_OPTUNA:
        print("⚠️ Optuna no está instalado. Ejecutando búsqueda simulada (Fallback)...")
        best_roi = -float("inf")
        best_params = {}
        for trial_num in range(1, n_trials + 1):
            params = {
                "rsi_period": int(np.random.randint(7, 30)),
                "rsi_oversold": float(np.random.randint(20, 40)),
                "rsi_overbought": float(np.random.randint(60, 80)),
                "macd_fast": int(np.random.randint(8, 16)),
                "macd_slow": int(np.random.randint(20, 32)),
                "macd_signal": int(np.random.randint(5, 12)),
                "ma_fast": int(np.random.randint(5, 25)),
                "ma_slow": int(np.random.randint(30, 100))
            }
            res = engine.run_strategy(**params)
            roi = res["roi"]
            if roi > best_roi:
                best_roi = roi
                best_params = params

        save_best_settings_to_db(best_params, best_roi)
        return best_params, best_roi

    # Función objetivo Optuna + MLflow
    def objective(trial: optuna.Trial) -> float:
        rsi_period = trial.suggest_int("rsi_period", 7, 28)
        rsi_oversold = trial.suggest_float("rsi_oversold", 20.0, 40.0)
        rsi_overbought = trial.suggest_float("rsi_overbought", 60.0, 80.0)
        macd_fast = trial.suggest_int("macd_fast", 8, 16)
        macd_slow = trial.suggest_int("macd_slow", 20, 34)
        macd_signal = trial.suggest_int("macd_signal", 5, 12)
        ma_fast = trial.suggest_int("ma_fast", 5, 25)
        ma_slow = trial.suggest_int("ma_slow", 30, 90)

        params = {
            "rsi_period": rsi_period,
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought,
            "macd_fast": macd_fast,
            "macd_slow": macd_slow,
            "macd_signal": macd_signal,
            "ma_fast": ma_fast,
            "ma_slow": ma_slow
        }

        # Ejecución del backtest
        result = engine.run_strategy(**params)
        roi = result["roi"]

        # Trazabilidad con MLflow
        if HAS_MLFLOW:
            try:
                with mlflow.start_run(nested=True):
                    mlflow.log_params(params)
                    mlflow.log_metric("roi", roi)
                    mlflow.log_metric("win_rate", result["win_rate"])
                    mlflow.log_metric("total_trades", result["total_trades"])
            except Exception as e:
                pass

        return roi

    # Crear y ejecutar el estudio de Optuna
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    print("\n✅ Optimización completada!")
    print(f"Mejor ROI obtenido: {study.best_value:.2f}%")
    print(f"Mejores Hiperparámetros: {study.best_params}")

    save_best_settings_to_db(study.best_params, study.best_value)
    return study.best_params, study.best_value


if __name__ == "__main__":
    from database.connection import init_db
    init_db()
    run_optimization(n_trials=100)
