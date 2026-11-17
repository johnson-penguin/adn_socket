import socket
import sys
import time
import threading
import random
import re

# 用法：python Q4.py [path] [mode] [proportion] [split]
#   path：1 / 2 / 3，mode：1 = single、2 = multi（批次），省略時以 input() 詢問
#   proportion：Path 3 走 Proxy1 的比例（0 ~ 1），預設 0.3
#   split：Path 3 的分流方式，seq = 前段走 Proxy1、後段走 Proxy2（預設）；random = 每次傳送依比例隨機選路
# 選用參數（可放在任意位置）：
#   --packets=N   總封包數（預設 50）
#   --group=N     批次大小（預設 10）
#   --interval=S  每次傳送的間隔秒數（預設 0.1）
#   --rcvbuf=N    Proxy1、Proxy2、Client 的 socket 接收緩衝區大小（bytes，預設使用作業系統預設值）

#Family(IPv4)、Type(UDP) setting
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
proxy1_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
proxy2_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

#IP、Port setting(1)
server_address = ('127.0.0.1', 5405)
proxy1_address = ('127.0.0.1', 5406)
proxy2_address = ('127.0.0.1', 5408)
client_address = ('127.0.0.1', 5407)

#IP、Port setting(2)
proxy1_socket.bind(proxy1_address)
proxy2_socket.bind(proxy2_address)
client_socket.bind(client_address)
server_socket.bind(server_address)

print("Server listening on {}:{}".format(*server_address))
print("Proxy1 listening on {}:{}".format(*proxy1_address))
print("Proxy2 listening on {}:{}".format(*proxy2_address))
print("Client listening on {}:{}".format(*client_address))

num_packet = 50          # 一共有多少筆封包 #100000
packet_group_size = 10   # 設置一批封包組有多少封包 #250
proportion = 0.3         # Path 3 中走 Proxy1 的封包比例
split_mode = "seq"       # seq：封包編號 <= num_packet * proportion 走 Proxy1；random：每次傳送以 proportion 機率走 Proxy1

SEND_INTERVAL = 0.1      # 每次傳送（單筆或一批）的間隔秒數
RECEIVE_TIMEOUT = 2      # Client 超過此秒數沒收到封包即檢查是否還有缺包
MAX_FINAL_RETRIES = 3    # 逾時後連續要求重傳卻沒收到任何新封包的最大輪數
LOSS_RATE = 0.3          # Proxy1 模擬 30% 的封包丟失率
DELAY_RATE = 0.05        # Proxy2 模擬 5% 的延遲傳送
DELAY_SECONDS = 0.5      # Proxy2 每次延遲的秒數
BUFFER_SIZE = 65535      # UDP 單一封包最大 65,507 bytes 資料，緩衝區需足以容納一整批

RETRANSMIT_TAG = "(重傳)"
PACKET_PATTERN = re.compile(r"server (\d+)")

# --- 統計數據（每個計數器只由單一執行緒寫入）---
path1_times = 0              # Server 經由 Proxy1 傳送的次數（單筆或一批算一次）
path2_times = 0              # Server 經由 Proxy2 傳送的次數
server_last_sent_packet = 0  # Server 已送出的最大封包編號
loss_buffer = 0              # Proxy1 丟棄的封包數（以封包計，一批 10 筆即算 10）
loss_messages = 0            # Proxy1 丟棄的 UDP 訊息數（單筆或一批算一次）
delay_buffer = 0             # Proxy2 延遲的封包數
delay_messages = 0           # Proxy2 延遲的 UDP 訊息數
receive_buffer = 0           # Client 第一次傳送就收到的封包數（不含重傳）
retransmit_received = 0      # Client 經由重傳補回的封包數
retransmit_requests = 0      # Client 送出的重傳要求次數
retransmit_requested_packets = 0  # Client 要求重傳的封包總數（含誤判：封包只是晚到）
duplicate_received = 0       # Client 收到已經有的封包數（晚到的原封包或多餘的重傳）
client_received = set()      # Client 已收到的封包編號（去除重複）
max_datagram_bytes = 0       # Server 單次傳送的最大位元組數
send_errors = 0              # Server 傳送失敗的次數（例如超過 UDP 封包大小上限）
send_failed_packets = 0      # 傳送失敗的封包數


def safe_percent(numerator, denominator):
    """避免收到 0 筆封包時發生 ZeroDivisionError"""
    return numerator / denominator * 100 if denominator else 0.0


def parse_packet_numbers(text):
    """從單筆或批次訊息中取出所有封包編號"""
    return [int(n) for n in PACKET_PATTERN.findall(text)]


def to_ranges(numbers):
    """將排序後的編號整理成連續區間，例如 [1,2,3,7,8] -> [(1,3),(7,8)]"""
    ranges = []
    for n in numbers:
        if ranges and n == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], n)
        else:
            ranges.append((n, n))
    return ranges


def choose_proxy(first_packet):
    """依路徑選擇決定要送往哪個 Proxy，並記錄各路徑使用次數"""
    global path1_times, path2_times
    if choice == "3" and split_mode == "random":
        use_proxy1 = random.random() < proportion
    else:
        use_proxy1 = choice == "3" and first_packet <= num_packet * proportion
    if choice == "1" or use_proxy1:
        path1_times += 1
        return proxy1_address
    path2_times += 1
    return proxy2_address


def server_send(payload, target, first, last):
    """送出一則訊息；超過 UDP 大小上限等錯誤時記錄下來，該段封包由 Client 之後要求重傳"""
    global max_datagram_bytes, send_errors, send_failed_packets
    max_datagram_bytes = max(max_datagram_bytes, len(payload))
    try:
        server_socket.sendto(payload, target)
    except OSError as e:
        send_errors += 1
        send_failed_packets += last - first + 1
        print(f"Server send failed for packets {first} ~ {last} ({len(payload)} bytes): {e}")


def server_send_single_data():
    global server_last_sent_packet
    for i in range(1, num_packet + 1):
        message = f"Hi, I am server {i}\n"
        target = choose_proxy(i)
        server_send(message.encode('utf-8'), target, i, i)
        server_last_sent_packet = i
        print(f"Server send message via {'Proxy1' if target == proxy1_address else 'Proxy2'}: {message}")
        time.sleep(SEND_INTERVAL)


def server_send_multi_data():
    global server_last_sent_packet
    for i in range(1, num_packet + 1, packet_group_size):
        last = min(i + packet_group_size - 1, num_packet)
        messages = "".join(f"Hi, I am server {n}\n" for n in range(i, last + 1))
        target = choose_proxy(i)
        server_send(messages.encode('utf-8'), target, i, last)
        server_last_sent_packet = last
        print(f"\nServer send packets {i} ~ {last} via {'Proxy1' if target == proxy1_address else 'Proxy2'}\n")
        time.sleep(SEND_INTERVAL)


def server_receive_data():
    # 處理 Client 的重傳要求：REQUEST_RETRANSMISSION <起始編號> <結束編號>
    while True:
        try:
            data, addr = server_socket.recvfrom(BUFFER_SIZE)
        except (ConnectionResetError, OSError):
            continue
        received_data = data.decode('utf-8')
        if not received_data.startswith("REQUEST_RETRANSMISSION"):
            print("Server received messages: {}".format(received_data))
            continue

        try:
            _, first, last = received_data.split()
            first, last = int(first), int(last)
        except ValueError:
            print("Invalid retransmission request:", received_data)
            continue

        last = min(last, server_last_sent_packet)  # 只重傳已經送出過的封包
        print(f"收到重傳要求: {first} ~ {last}")
        # 重傳直接送回 Client，不經過會掉包的 Proxy
        for packet_num in range(first, last + 1):
            message = f"Hi, I am server {packet_num} {RETRANSMIT_TAG}\n"
            server_socket.sendto(message.encode('utf-8'), addr)
        print(f"Server retransmitted packets {first} ~ {last}")


def proxy1_receive_and_send():
    global loss_buffer, loss_messages
    while True:
        data, _ = proxy1_socket.recvfrom(BUFFER_SIZE)
        if random.random() < LOSS_RATE:
            lost = parse_packet_numbers(data.decode('utf-8'))
            print(f"Simulated packet loss: {lost[0]} ~ {lost[-1]}")
            loss_buffer += len(lost)
            loss_messages += 1
        else:
            proxy1_socket.sendto(data, client_address)


def proxy2_receive_and_send():
    global delay_buffer, delay_messages
    while True:
        data, _ = proxy2_socket.recvfrom(BUFFER_SIZE)
        if random.random() < DELAY_RATE:
            delayed = parse_packet_numbers(data.decode('utf-8'))
            print(f"Simulated packet delay send: {delayed[0]} ~ {delayed[-1]}")
            time.sleep(DELAY_SECONDS)
            delay_buffer += len(delayed)
            delay_messages += 1
        proxy2_socket.sendto(data, client_address)


def request_retransmission(missing):
    global retransmit_requests, retransmit_requested_packets
    for first, last in to_ranges(missing):
        retransmit_requested_packets += last - first + 1
        request_message = f"REQUEST_RETRANSMISSION {first} {last}"
        print(f"\nPacket {first} ~ {last} missing, requesting retransmission...\n")
        client_socket.sendto(request_message.encode('utf-8'), server_address)
        retransmit_requests += 1


def client_receive_data():
    global receive_buffer, retransmit_received, duplicate_received
    client_socket.settimeout(RECEIVE_TIMEOUT)
    expected_packet = 1   # 下一個預期收到的封包編號
    final_retries = 0

    while True:
        try:
            data, _ = client_socket.recvfrom(BUFFER_SIZE)
        except socket.timeout:
            # 傳送已結束：若仍有缺包（例如最後一批被丟棄），要求重傳後繼續等待
            missing = sorted(set(range(1, num_packet + 1)) - client_received)
            if missing and final_retries < MAX_FINAL_RETRIES:
                final_retries += 1
                request_retransmission(missing)
                continue
            print("No data received within the timeout. Exiting...")
            break
        except ConnectionResetError:
            continue

        received_data = data.decode('utf-8')
        numbers = parse_packet_numbers(received_data)
        if not numbers:
            continue
        new_numbers = [n for n in numbers if n not in client_received]
        duplicate_received += len(numbers) - len(new_numbers)
        client_received.update(new_numbers)
        if new_numbers:
            final_retries = 0  # 仍有進展，重新計算尾端重傳次數

        if RETRANSMIT_TAG in received_data:
            retransmit_received += len(new_numbers)
            print(f"Client received retransmitted packets: {numbers[0]} ~ {numbers[-1]}")
            continue

        receive_buffer += len(new_numbers)
        print(f"Client received packets: {numbers[0]} ~ {numbers[-1]}")

        # 收到的編號跳過了預期編號 -> 中間的封包遺失，要求重傳
        if numbers[0] > expected_packet:
            gap = [n for n in range(expected_packet, numbers[0]) if n not in client_received]
            if gap:
                request_retransmission(gap)
        expected_packet = max(expected_packet, numbers[-1] + 1)


print("Choose path:")
print("1. Path 1 - proxy1 (from server to client)")
print("2. Path 2 - proxy2 (from server to client)")
print("3. Path 3 - proxy1 + proxy2")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
options = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
try:
    num_packet = int(options.get("packets", num_packet))
    packet_group_size = int(options.get("group", packet_group_size))
    SEND_INTERVAL = float(options.get("interval", SEND_INTERVAL))
except ValueError:
    print("Invalid --packets / --group / --interval value.")
    sys.exit(1)
if num_packet < 1 or packet_group_size < 1 or SEND_INTERVAL < 0:
    print("--packets and --group must be >= 1, --interval must be >= 0.")
    sys.exit(1)

# 接收緩衝區：批次大或 Proxy2 延遲時，封包會在這裡排隊，超過容量就會被作業系統丟棄
if "rcvbuf" in options:
    try:
        rcvbuf = int(options["rcvbuf"])
    except ValueError:
        rcvbuf = 0
    if rcvbuf < 1:
        print("--rcvbuf must be a positive integer (bytes).")
        sys.exit(1)
    for s in (proxy1_socket, proxy2_socket, client_socket):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
receive_buffer_bytes = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

choice = args[0] if len(args) > 0 else input("Input your path (1/2/3): ").strip()
if choice not in ("1", "2", "3"):
    print("Invalid path choice. Please choose 1, 2 or 3.")
    sys.exit(1)

transmissions_choice = args[1] if len(args) > 1 else input("single (1) or multi (2): ").strip()
if transmissions_choice == "1":
    server_send_thread = threading.Thread(target=server_send_single_data, daemon=True)
elif transmissions_choice == "2":
    server_send_thread = threading.Thread(target=server_send_multi_data, daemon=True)
else:
    print("Invalid transmission choice. Please choose 1 (single) or 2 (multi).")
    sys.exit(1)

if len(args) > 2:
    try:
        proportion = float(args[2])
    except ValueError:
        proportion = -1
    if not 0 <= proportion <= 1:
        print("Invalid proportion. Please use a number between 0 and 1.")
        sys.exit(1)
if len(args) > 3:
    split_mode = args[3]
    if split_mode not in ("seq", "random"):
        print("Invalid split mode. Please choose seq or random.")
        sys.exit(1)
if choice == "3":
    print(f"Path 3 split: {split_mode}, proportion via Proxy1 = {proportion}")

# Proxy 與 Server 接收端為無窮迴圈，設為 daemon，主程式印完結果後即可結束
server_receive_thread = threading.Thread(target=server_receive_data, daemon=True)
proxy1_thread = threading.Thread(target=proxy1_receive_and_send, daemon=True)
proxy2_thread = threading.Thread(target=proxy2_receive_and_send, daemon=True)
client_receive_thread = threading.Thread(target=client_receive_data)

start = time.time()
server_receive_thread.start()
proxy1_thread.start()
proxy2_thread.start()
client_receive_thread.start()
server_send_thread.start()

# 主程序等待傳送完成，以及 Client 逾時結束
server_send_thread.join()
client_receive_thread.join()
end = time.time()

missing_final = sorted(set(range(1, num_packet + 1)) - client_received)

print(format(end - start))
print("Done \n")
print("封包總數:", num_packet)
print("封包遺失:", loss_buffer, f"（{loss_messages} 次傳送被丟棄）")
print("封包延遲接收:", delay_buffer, f"（{delay_messages} 次傳送被延遲）")
print("封包接收（首次傳送）:", receive_buffer)
print("掉包率:", safe_percent(loss_buffer, num_packet))
print("封包延遲率:", safe_percent(delay_buffer, receive_buffer))
print("//////////////////////////////////////////////////////////////")
print("重傳要求次數:", retransmit_requests)
print("要求重傳封包:", retransmit_requested_packets)
print("重傳補回封包:", retransmit_received)
print("重複收到封包:", duplicate_received)
print("最終收到封包:", len(client_received), "/", num_packet)
if missing_final:
    preview = missing_final[:20]
    print("最終缺少封包:", len(missing_final), "筆", preview, "..." if len(missing_final) > 20 else "")
else:
    print("最終缺少封包: 無")
print("//////////////////////////////////////////////////////////////")
print("批次大小:", packet_group_size if transmissions_choice == "2" else 1, "，傳送間隔:", SEND_INTERVAL)
print("單次傳送最大位元組:", max_datagram_bytes)
print("接收緩衝區大小:", receive_buffer_bytes)
print("傳送失敗次數:", send_errors)
print("傳送失敗封包:", send_failed_packets)
print("//////////////////////////////////////////////////////////////")
print("路徑1被選擇次數: ", path1_times)
print("路徑2被選擇次數: ", path2_times)
