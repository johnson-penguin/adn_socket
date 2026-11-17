"""十萬筆封包的批次大小測試：比較不同批次大小、路徑下的耗時與重傳情況。

用法：python run_batch_sweep.py [--repeats=3] [--rcvbuf=1048576] [--packets=100000] [--out=檔名]
  --rcvbuf=0 表示使用作業系統預設接收緩衝區

輸出：results/<out>.csv（每次執行的原始數據）、results/<out>.md（平均值彙整）
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

options = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
REPEATS = int(options.get("repeats", 3))
RCVBUF = int(options.get("rcvbuf", 1048576))
PACKETS = int(options.get("packets", 100000))
OUT = options.get("out", "batch_size_sweep_100k_rcvbuf1m")

SEND_INTERVAL = 0.1
RECEIVE_TIMEOUT = 2
PATHS = ("2", "1")
GROUPS = (250, 500, 1000, 2000, 2500, 2800, 2977, 2978, 3000)
OVER_LIMIT_REPEATS = 1  # 超過 UDP 上限的批次只跑 1 次（已知會傳送失敗，且耗時較長）

FIELDS = {
    "elapsed_s": r"^(\d+\.\d+)\s*$",
    "proxy1_lost": r"^封包遺失: (\d+)",
    "delay_messages": r"^封包延遲接收: \d+ （(\d+) 次",
    "retx_requests": r"^重傳要求次數: (\d+)",
    "retx_requested_packets": r"^要求重傳封包: (\d+)",
    "retx_recovered": r"^重傳補回封包: (\d+)",
    "final_received": r"^最終收到封包: (\d+)",
    "max_bytes": r"^單次傳送最大位元組: (\d+)",
    "send_errors": r"^傳送失敗次數: (\d+)",
    "send_failed_packets": r"^傳送失敗封包: (\d+)",
    "rcvbuf": r"^接收緩衝區大小: (\d+)",
}


def run_once(path, group):
    args = [sys.executable, Q4_PATH, path, "2", f"--packets={PACKETS}", f"--group={group}"]
    if RCVBUF > 0:
        args.append(f"--rcvbuf={RCVBUF}")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=600)
    row = {"exit_code": proc.returncode,
           "traceback": int("Traceback" in proc.stdout + proc.stderr)}
    for key, pattern in FIELDS.items():
        match = re.search(pattern, proc.stdout, re.MULTILINE)
        row[key] = float(match.group(1)) if match else None
    # 重傳補回的封包中，扣除 Proxy1 丟棄與 Server 傳送失敗後，剩下的即為作業系統在接收端丟棄
    if row["retx_recovered"] is not None and row["proxy1_lost"] is not None:
        row["os_dropped"] = row["retx_recovered"] - row["proxy1_lost"] - (row["send_failed_packets"] or 0)
    else:
        row["os_dropped"] = None
    return row


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else float("nan")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    plan = [(p, g, r) for p in PATHS for g in GROUPS
            for r in range(1, (OVER_LIMIT_REPEATS if g > 2977 else REPEATS) + 1)]
    print(f"共 {len(plan)} 次執行（rcvbuf={RCVBUF or '預設'}，封包數={PACKETS}）", flush=True)

    rows = []
    started = time.time()
    for i, (path, group, run) in enumerate(plan, 1):
        row = run_once(path, group)
        sends = -(-PACKETS // group)
        row.update(path=path, group=group, run=run, sends=sends,
                   theoretical_s=round(sends * SEND_INTERVAL + RECEIVE_TIMEOUT, 2))
        rows.append(row)
        print(f"[{i}/{len(plan)}] Path {path} group {group} #{run}: exit={row['exit_code']} "
              f"elapsed={row['elapsed_s']:.2f}s final={row['final_received']:.0f} "
              f"retx_req={row['retx_requests']:.0f} os_dropped={row['os_dropped']:.0f}", flush=True)

    write_outputs(rows, f"{datetime.now():%Y-%m-%d %H:%M}", time.time() - started)


def write_outputs(rows, run_time, total_seconds):
    columns = ["path", "group", "run", "sends", "theoretical_s", "exit_code", "traceback",
               "os_dropped"] + list(FIELDS)
    with open(os.path.join(RESULTS_DIR, OUT + ".csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        f"# 十萬筆封包批次大小測試（rcvbuf = {RCVBUF or '作業系統預設'}）",
        "",
        f"- 執行時間：{run_time}，總耗時 {total_seconds:.0f} 秒",
        f"- 封包數 {PACKETS}、傳送間隔 {SEND_INTERVAL}s、接收逾時 {RECEIVE_TIMEOUT}s；"
        f"每種組合重複 {REPEATS} 次（超過 2,977 筆只跑 {OVER_LIMIT_REPEATS} 次），下表為平均值",
        "- 理論最短 = 傳送次數 × 0.1s + 2s 接收逾時；作業系統掉包 = 重傳補回 − Proxy1 實際丟棄 − 傳送失敗封包",
        "",
        "| 路徑 | 每批筆數 | 傳送次數 | 理論最短 s | 平均耗時 s | 最短 / 最長 s | Proxy1 丟棄 | 傳送失敗封包 | 作業系統掉包 | 重傳要求次數 | 最終收到 (最少) | 異常 |",
        "| :---: | :---: | :---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: | :---: | :---: |",
    ]
    for path in PATHS:
        for group in GROUPS:
            rs = [r for r in rows if r["path"] == path and r["group"] == group]
            el = [r["elapsed_s"] for r in rs if r["elapsed_s"] is not None]
            failures = sum(1 for r in rs if r["exit_code"] != 0 or r["traceback"])
            lines.append(
                f"| {path} | {group} | {rs[0]['sends']} | {rs[0]['theoretical_s']:.1f} "
                f"| {mean(el):.2f} | {min(el):.1f} / {max(el):.1f} "
                f"| {mean([r['proxy1_lost'] for r in rs]):.0f} "
                f"| {mean([r['send_failed_packets'] for r in rs]):.0f} "
                f"| {mean([r['os_dropped'] for r in rs]):.0f} "
                f"| {mean([r['retx_requests'] for r in rs]):.0f} "
                f"| {mean([r['final_received'] for r in rs]):.0f} ({min(r['final_received'] or 0 for r in rs):.0f}) "
                f"| {failures} |")
    with open(os.path.join(RESULTS_DIR, OUT + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
