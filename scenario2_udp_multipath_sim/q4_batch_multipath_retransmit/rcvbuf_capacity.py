"""實測 UDP 接收緩衝區實際能堆積多少個最大批次（接收端完全不讀取）。"""
import socket
import sys
import time

DATAGRAM = 65494  # 2,977 筆一批的大小
payload = b"x" * DATAGRAM
sizes = [int(a) for a in sys.argv[1:]] or [2**16, 2**20, 2**24, 2**26, 2**28, 2**30, 2**31 - 1]

for rcvbuf in sizes:
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    rx.bind(("127.0.0.1", 0))
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = rx.getsockname()

    # 送出足以超過緩衝區的數量（上限 40,000 個 ≈ 2.6 GB）
    to_send = min(rcvbuf // DATAGRAM * 2 + 50, 40000)
    t0 = time.time()
    sent = 0
    for _ in range(to_send):
        try:
            tx.sendto(payload, target)
            sent += 1
        except OSError as e:
            print(f"  send error after {sent}: {e}")
            break
    send_time = time.time() - t0

    rx.settimeout(0.5)
    received = 0
    while True:
        try:
            rx.recvfrom(65535)
            received += 1
        except socket.timeout:
            break
    stored = received * DATAGRAM
    print(f"rcvbuf={rcvbuf:>13,}  sent={sent:>6}  queued={received:>6} datagrams "
          f"= {stored/1048576:8.1f} MB ({stored/rcvbuf*100:5.1f}% of setting)  send {send_time:.1f}s", flush=True)
    rx.close()
    tx.close()
