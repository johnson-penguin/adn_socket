"""批次執行 Q4.py 的多種情境，記錄每次結果並彙整平均值。

用法：python run_experiments.py [每個情境重複次數，預設 5]

輸出：
  results/raw_results.csv  每一次執行的原始數據
  results/summary.md       各情境的平均值彙整
"""
import csv
import os
import re
import subprocess
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
Q4_PATH = os.path.join(HERE, "Q4.py")
RESULTS_DIR = os.path.join(HERE, "results")
REPEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
RUN_TIMEOUT = 180  # 單次執行的逾時秒數

MODE_NAMES = {"1": "單筆", "2": "批次"}

# (群組, 路徑, 模式, 比例, 分流方式)
SCENARIOS = []
for mode in ("1", "2"):
    SCENARIOS.append(("A 單一路徑", "1", mode, None, None))
    SCENARIOS.append(("A 單一路徑", "2", mode, None, None))
for mode in ("1", "2"):
    for p in (0.0, 0.3, 0.5, 0.7, 1.0):
        SCENARIOS.append(("B 前後段分流 (seq)", "3", mode, p, "seq"))
for mode in ("1", "2"):
    for p in (0.3, 0.5, 0.7):
        SCENARIOS.append(("C 隨機分流 (random)", "3", mode, p, "random"))

# Q4.py 輸出的欄位 -> 正規表示式
FIELDS = {
    "elapsed_s": r"^(\d+\.\d+)\s*$",
    "loss_packets": r"^封包遺失: (\d+)",
    "loss_messages": r"^封包遺失: \d+ （(\d+) 次",
    "delay_packets": r"^封包延遲接收: (\d+)",
    "delay_messages": r"^封包延遲接收: \d+ （(\d+) 次",
    "first_received": r"^封包接收（首次傳送）: (\d+)",
    "loss_rate_pct": r"^掉包率: ([\d.]+)",
    "delay_rate_pct": r"^封包延遲率: ([\d.]+)",
    "retx_requests": r"^重傳要求次數: (\d+)",
    "retx_requested_packets": r"^要求重傳封包: (\d+)",
    "retx_recovered": r"^重傳補回封包: (\d+)",
    "duplicates": r"^重複收到封包: (\d+)",
    "final_received": r"^最終收到封包: (\d+)",
    "path1_times": r"^路徑1被選擇次數:\s+(\d+)",
    "path2_times": r"^路徑2被選擇次數:\s+(\d+)",
}


def scenario_label(path, mode, proportion, split):
    if path != "3":
        return f"Path {path} / {MODE_NAMES[mode]}"
    return f"Path 3 {split} {proportion:.1f} / {MODE_NAMES[mode]}"


def run_once(path, mode, proportion, split):
    args = [sys.executable, Q4_PATH, path, mode]
    if proportion is not None:
        args += [str(proportion), split]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=RUN_TIMEOUT)
    row = {"exit_code": proc.returncode,
           "traceback": int("Traceback" in proc.stdout + proc.stderr)}
    for key, pattern in FIELDS.items():
        match = re.search(pattern, proc.stdout, re.MULTILINE)
        row[key] = float(match.group(1)) if match else None
    return row


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else float("nan")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    total = len(SCENARIOS) * REPEATS
    print(f"共 {len(SCENARIOS)} 個情境 × {REPEATS} 次 = {total} 次執行")

    rows = []
    started = time.time()
    count = 0
    for group, path, mode, proportion, split in SCENARIOS:
        label = scenario_label(path, mode, proportion, split)
        for run in range(1, REPEATS + 1):
            count += 1
            row = run_once(path, mode, proportion, split)
            row.update(group=group, scenario=label, path=path, mode=MODE_NAMES[mode],
                       proportion="" if proportion is None else proportion,
                       split=split or "", run=run)
            rows.append(row)
            print(f"[{count}/{total}] {label} #{run}: exit={row['exit_code']} "
                  f"final={row['final_received']} loss={row['loss_rate_pct']}% "
                  f"elapsed={row['elapsed_s']}s", flush=True)

    columns = ["group", "scenario", "path", "mode", "proportion", "split", "run",
               "exit_code", "traceback"] + list(FIELDS)
    with open(os.path.join(RESULTS_DIR, "raw_results.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Q4 多情境實驗結果",
        "",
        f"- 執行時間：{datetime.now():%Y-%m-%d %H:%M}，總耗時 {time.time() - started:.0f} 秒",
        f"- 每個情境重複 **{REPEATS}** 次，下表為平均值；每次的原始數據見 `raw_results.csv`",
        "- 固定參數：50 筆封包、批次 10 筆、Proxy1 掉包 30%、Proxy2 延遲 5%（0.5s）、接收逾時 2s",
        "",
        "| 群組 | 情境 | 掉包率 % | 延遲率 % | 重傳要求次數 | 要求重傳封包 | 重傳補回 | 重複收到 | 最終收到 (最少) | Path1 / Path2 次數 | 耗時 s | 異常次數 |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: | :---: | ---: | :---: |",
    ]
    for group, path, mode, proportion, split in SCENARIOS:
        label = scenario_label(path, mode, proportion, split)
        rs = [r for r in rows if r["scenario"] == label]
        failures = sum(1 for r in rs if r["exit_code"] != 0 or r["traceback"])
        min_final = min((r["final_received"] or 0) for r in rs)
        lines.append(
            f"| {group} | {label} "
            f"| {mean([r['loss_rate_pct'] for r in rs]):.1f} "
            f"| {mean([r['delay_rate_pct'] for r in rs]):.1f} "
            f"| {mean([r['retx_requests'] for r in rs]):.1f} "
            f"| {mean([r['retx_requested_packets'] for r in rs]):.1f} "
            f"| {mean([r['retx_recovered'] for r in rs]):.1f} "
            f"| {mean([r['duplicates'] for r in rs]):.1f} "
            f"| {mean([r['final_received'] for r in rs]):.1f} ({min_final:.0f}) "
            f"| {mean([r['path1_times'] for r in rs]):.1f} / {mean([r['path2_times'] for r in rs]):.1f} "
            f"| {mean([r['elapsed_s'] for r in rs]):.2f} "
            f"| {failures} |")
    with open(os.path.join(RESULTS_DIR, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
