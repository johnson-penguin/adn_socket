import socket
import time

PROXY1_ADDRESS = ('127.0.0.1', 8888)  # Address of UDP Proxy1
NUM_TRANSMISSIONS = 100
RECEIVE_TIMEOUT = 2.0  # 秒；超過這段時間沒收到回應就結束

# Create a socket object for the UDP client
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Send data to UDP Proxy1
for i in range(1, NUM_TRANSMISSIONS + 1):
    message = f"UDP Server sends Packet {i} to UDP Client as the {i}-th transmission."
    client_socket.sendto(message.encode('utf-8'), PROXY1_ADDRESS)

    if i < NUM_TRANSMISSIONS:
        time.sleep(0.1)  # Wait for 100 ms before the next transmission

# 接收回應：回應在發送期間已排入 socket 緩衝區，這裡依序讀出，逾時即結束
client_socket.settimeout(RECEIVE_TIMEOUT)
received = 0
while received < NUM_TRANSMISSIONS:
    try:
        data, _ = client_socket.recvfrom(1024)
    except socket.timeout:
        break
    except ConnectionResetError:
        # Windows：Proxy1 未啟動時會收到 ICMP Port Unreachable
        print("Proxy1 is unreachable.")
        break
    received += 1
    print("Received from UDP Proxy1: {}".format(data.decode('utf-8')))

client_socket.close()
print("Sent {} packets, received {} responses ({} lost).".format(
    NUM_TRANSMISSIONS, received, NUM_TRANSMISSIONS - received))
