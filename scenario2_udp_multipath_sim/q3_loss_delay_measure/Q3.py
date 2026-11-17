import socket
import sys
import time
import threading
import random

# 用法：python Q3.py [path] [num_transmissions]
#   path：1 / 2 / 3，省略時以 input() 詢問
#   num_transmissions：傳送封包數，省略時為 1000

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

num_transmissions = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
SEND_INTERVAL = 0.1     # 每筆封包的傳送間隔（秒）
RECEIVE_TIMEOUT = 5     # 接收端超過此秒數沒收到封包即結束
LOSS_RATE = 0.2         # Proxy1 模擬 20% 的封包遺失率
DELAY_RATE = 0.5        # Proxy2 模擬 50% 的延遲傳送
DELAY_SECONDS = 0.5     # Proxy2 每次延遲的秒數

sent_buffer = 0         # 實際送出的封包數
receive_buffer = 0      # 接收端收到的封包數（Path 1/2 為 Client，Path 3 為 Server）
loss_buffer = 0
delay_buffer = 0


def safe_ratio(numerator, denominator):
    """避免收到 0 筆封包時發生 ZeroDivisionError"""
    return numerator / denominator if denominator else 0.0


def server_send_data():
    global sent_buffer
    for i in range(1, num_transmissions + 1):
        message = f"Hi, I am server {i}\n"
        if choice == "1":
            server_socket.sendto(message.encode('utf-8'), proxy1_address)
        elif choice == "2":
            server_socket.sendto(message.encode('utf-8'), proxy2_address)
        sent_buffer += 1
        print(f"Server send message: {message}")
        time.sleep(SEND_INTERVAL)


def server_receive_data():
    # Path 3：Server 為接收端，與 client_receive_data 相同採用逾時結束
    global receive_buffer
    server_socket.settimeout(RECEIVE_TIMEOUT)
    while True:
        try:
            data, _ = server_socket.recvfrom(1024)
        except socket.timeout:
            print("No data received within the timeout. Exiting...")
            break
        print("Server received messages: {}".format(data.decode('utf-8')))
        receive_buffer += 1


def proxy1_receive_and_send():
    global loss_buffer
    while True:
        data, _ = proxy1_socket.recvfrom(1024)
        if random.random() < LOSS_RATE:
            print("Simulated packet loss")
            loss_buffer = loss_buffer + 1
        else:
            proxy1_socket.sendto(data, client_address)
            print("Proxy1 received messages: {}".format(data.decode('utf-8')))


def proxy2_receive_and_send():
    global delay_buffer
    while True:
        data, _ = proxy2_socket.recvfrom(1024)
        if random.random() < DELAY_RATE:
            print("Simulated packet delay send")
            time.sleep(DELAY_SECONDS)
            delay_buffer = delay_buffer + 1
        proxy2_socket.sendto(data, client_address)
        print("Proxy2 received messages: {}".format(data.decode('utf-8')))


def client_send_data():
    # Path 3：Client 直接傳送給 Server
    global sent_buffer
    for i in range(1, num_transmissions + 1):
        message = f"Hi, I am client {i}\n"
        client_socket.sendto(message.encode('utf-8'), server_address)
        sent_buffer += 1
        print(f"Client send message: {message}")
        time.sleep(SEND_INTERVAL)


def client_receive_data():
    global receive_buffer
    client_socket.settimeout(RECEIVE_TIMEOUT)
    while True:
        try:
            data, _ = client_socket.recvfrom(1024)
        except socket.timeout:
            print("No data received within the timeout. Exiting...")
            break
        print("Client received message: {}".format(data.decode('utf-8')))
        receive_buffer += 1


print("Choose path:")
print("1. Path 1 - proxy1 (from server to client)")
print("2. Path 2 - proxy2 (from server to client)")
print("3. Path 3 - directly (from client to server)")

choice = sys.argv[1] if len(sys.argv) > 1 else input("Input your path (1/2/3): ").strip()
if choice not in ("1", "2", "3"):
    print("Invalid path choice. Please choose 1, 2 or 3.")
    sys.exit(1)

start = time.time()

# Proxy 為無窮迴圈，設為 daemon，主程式印完結果後即可結束
proxy1_thread = threading.Thread(target=proxy1_receive_and_send, daemon=True)
proxy2_thread = threading.Thread(target=proxy2_receive_and_send, daemon=True)

if choice == "3":
    sender_thread = threading.Thread(target=client_send_data, daemon=True)
    receiver_thread = threading.Thread(target=server_receive_data)
else:
    sender_thread = threading.Thread(target=server_send_data, daemon=True)
    receiver_thread = threading.Thread(target=client_receive_data)

proxy1_thread.start()
proxy2_thread.start()
receiver_thread.start()
sender_thread.start()

# 主程序等待傳送完成，以及接收端逾時結束
sender_thread.join()
receiver_thread.join()
end = time.time()

print(format(end - start))
print("Done \n")
print("封包送出:", sent_buffer)
print("封包損失:", loss_buffer)
print("封包接收:", receive_buffer)
print("封包損失率:", safe_ratio(loss_buffer, receive_buffer + loss_buffer))
print("//////////////////////////////////////////////////////////////")
print("封包延遲接收:", delay_buffer)
print("封包接收:", receive_buffer)
print("封包延遲率:", safe_ratio(delay_buffer, receive_buffer))
