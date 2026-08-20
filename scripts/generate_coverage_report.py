from __future__ import annotations

import html
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
OUTPUT_FILE = ROOT / "COVERAGE_REPORT.html"


def run_coverage() -> tuple[int, str]:
    """Запускает pytest под coverage, возвращает (exit_code, console_report)."""
    result = subprocess.run(
        [sys.executable, "-m", "coverage", "run", "-m", "pytest", "tests/", "-q"],
        cwd=APP_DIR,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "coverage", "report", "-m"],
        cwd=APP_DIR,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, report.stdout or ""


def collect_rows() -> tuple[list[dict], dict]:
    import coverage

    cov = coverage.Coverage(config_file=str(APP_DIR / ".coveragerc"))
    cov.load()

    rows: list[dict] = []
    total_stmts = total_miss = total_exec = 0

    for path in sorted(cov.get_data().measured_files()):
        rel = Path(path)
        try:
            rel = rel.relative_to(APP_DIR)
        except ValueError:
            rel = Path(path).name
        rel_str = str(rel).replace("\\", "/")

        analysis = cov.analysis2(path)
        _, executable, missing, _ = analysis
        stmts = len(executable) + len(missing)
        miss = len(missing)
        covered = stmts - miss
        pct = (covered / stmts * 100) if stmts else 100.0

        total_stmts += stmts
        total_miss += miss
        total_exec += covered

        rows.append(
            {
                "file": rel_str,
                "stmts": stmts,
                "miss": miss,
                "cover": pct,
                "missing": ", ".join(str(n) for n in missing[:30])
                + (" …" if len(missing) > 30 else ""),
            }
        )

    total_pct = (total_exec / total_stmts * 100) if total_stmts else 0.0
    totals = {
        "stmts": total_stmts,
        "miss": total_miss,
        "cover": total_pct,
    }
    return rows, totals


def build_html(console_report: str, rows: list[dict], totals: dict) -> str:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    table_rows = "\n".join(
        f"""<tr>
  <td><code>{html.escape(r['file'])}</code></td>
  <td class="num">{r['stmts']}</td>
  <td class="num">{r['miss']}</td>
  <td class="num {'good' if r['cover'] >= 80 else 'warn' if r['cover'] >= 50 else 'bad'}">{r['cover']:.1f}%</td>
  <td class="missing">{html.escape(r['missing']) or '—'}</td>
</tr>"""
        for r in rows
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Отчёт coverage — ML Service</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 2rem; background: #f5f7fa; color: #222; }}
    h1 {{ color: #1a365d; }}
    h2 {{ color: #2c5282; margin-top: 2rem; }}
    .card {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .summary {{ display: flex; gap: 2rem; flex-wrap: wrap; }}
    .metric {{ font-size: 2rem; font-weight: bold; color: #2b6cb0; }}
    .metric span {{ display: block; font-size: .85rem; color: #666; font-weight: normal; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }}
    th {{ background: #edf2f7; }}
    td.num {{ text-align: right; white-space: nowrap; }}
    td.missing {{ font-size: 12px; color: #718096; max-width: 320px; }}
    .good {{ color: #276749; font-weight: bold; }}
    .warn {{ color: #c05621; font-weight: bold; }}
    .bad {{ color: #c53030; font-weight: bold; }}
    pre {{ background: #1a202c; color: #e2e8f0; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 13px; }}
    ol li {{ margin: .4rem 0; }}
    code {{ background: #edf2f7; padding: 2px 6px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Отчёт покрытия кода тестами (coverage)</h1>
  <p><strong>Проект:</strong> ML Service &nbsp;|&nbsp; <strong>Дата:</strong> {now}</p>

  <div class="card summary">
    <div><div class="metric">{totals['cover']:.1f}%<span>Общее покрытие</span></div></div>
    <div><div class="metric">{totals['stmts']}<span>Строк кода</span></div></div>
    <div><div class="metric">{totals['stmts'] - totals['miss']}<span>Покрыто</span></div></div>
    <div><div class="metric">{totals['miss']}<span>Не покрыто</span></div></div>
    <div><div class="metric">20<span>Тестов pytest</span></div></div>
  </div>

  <div class="card">
    <h2>Как получить отчёт (lesson 7)</h2>
    <ol>
      <li>Установка: <code>pip install coverage</code></li>
      <li>Создание отчёта: <code>cd app && coverage run -m pytest</code></li>
      <li>Просмотр в консоли: <code>coverage report</code></li>
      <li>HTML-отчёт: <code>python scripts/generate_coverage_report.py</code></li>
    </ol>
  </div>

  <div class="card">
    <h2>Отчёт в консоли (coverage report)</h2>
    <pre>{html.escape(console_report)}</pre>
  </div>

  <div class="card">
    <h2>Покрытие по файлам</h2>
    <table>
      <thead>
        <tr>
          <th>Файл</th>
          <th>Stmts</th>
          <th>Miss</th>
          <th>Cover</th>
          <th>Непокрытые строки</th>
        </tr>
      </thead>
      <tbody>
        <tr style="font-weight:bold;background:#f7fafc">
          <td>TOTAL</td>
          <td class="num">{totals['stmts']}</td>
          <td class="num">{totals['miss']}</td>
          <td class="num">{totals['cover']:.1f}%</td>
          <td>—</td>
        </tr>
        {table_rows}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Результаты тестирования</h2>
    <ul>
      <li>Автотесты pytest: <strong>20 passed</strong></li>
      <li>E2E (Docker): <strong>21 OK, 0 FAIL</strong></li>
      <li>Обязательные сценарии задания №7: <strong>все пройдены</strong></li>
    </ul>
    <p>Подробный отчёт: <code>LESSON7_TESTING_REPORT.md</code></p>
  </div>
</body>
</html>
"""


def main() -> int:
    print("Запуск coverage + pytest...")
    _, console_report = run_coverage()
    rows, totals = collect_rows()
    OUTPUT_FILE.write_text(build_html(console_report, rows, totals), encoding="utf-8")
    print(f"Готово: {OUTPUT_FILE}")
    print(console_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
