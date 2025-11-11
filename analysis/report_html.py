"""Generate weekly performance report."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from .live_metrics import LiveMetricsStore


class WeeklyReport:
    def __init__(self, metrics: LiveMetricsStore) -> None:
        self.metrics = metrics

    def render(self, output_path: Path, lookback_days: int = 7) -> Path:
        df = self.metrics.fetch_recent()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df[df["timestamp"] >= pd.Timestamp.utcnow() - pd.Timedelta(days=lookback_days)]
        if df.empty:
            raise ValueError("no metrics to render")
        stats = self._summary(df)
        html = self._html_template(stats, df)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def _summary(self, df: pd.DataFrame) -> Dict[str, float]:
        return {
            "avg_equity": float(df["equity"].mean()),
            "max_drawdown": float(df["drawdown_pct"].max()),
            "avg_profit_factor": float(df["profit_factor"].mean()),
            "avg_win_rate": float(df["win_rate"].mean()),
        }

    def _html_template(self, stats: Dict[str, float], df: pd.DataFrame) -> str:
        rows = "".join(
            f"<tr><td>{row.timestamp}</td><td>{row.equity:.2f}</td><td>{row.drawdown_pct:.2f}%</td>"
            f"<td>{row.profit_factor:.2f}</td><td>{row.win_rate:.2%}</td></tr>"
            for row in df.itertuples(index=False)
        )
        return f"""
        <html>
            <head>
                <style>
                    body {{ background-color: #0f172a; color: #e2e8f0; font-family: sans-serif; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ border: 1px solid #1e293b; padding: 8px; text-align: left; }}
                    th {{ background-color: #1e293b; }}
                </style>
            </head>
            <body>
                <h1>SnipeTrade Weekly Report</h1>
                <p>Average Equity: {stats['avg_equity']:.2f}</p>
                <p>Max Drawdown: {stats['max_drawdown']:.2f}%</p>
                <p>Average Profit Factor: {stats['avg_profit_factor']:.2f}</p>
                <p>Average Win Rate: {stats['avg_win_rate']:.2%}</p>
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Equity</th>
                            <th>Drawdown %</th>
                            <th>Profit Factor</th>
                            <th>Win Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </body>
        </html>
        """
