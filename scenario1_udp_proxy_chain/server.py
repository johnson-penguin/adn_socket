import socket

# Define the server address and port
server_address = ('127.0.0.1', 12345)

# Create a socket object for the UDP server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the server address
server_socket.bind(server_address)

print("Server is listening on {}:{}".format(*server_address))

received_count = 0
while True:
    try:
        data, client_address = server_socket.recvfrom(1024)
    except ConnectionResetError:
        # Windows 上若前一次 sendto 的目的地已關閉，會在下一次 recvfrom 收到 ICMP 錯誤，忽略即可
        continue
    received_count += 1
    print("Received #{}: {}".format(received_count, data.decode('utf-8')))
    # 回傳給發送方（即 Proxy2），由 Proxy2 沿原路轉回 Client
    server_socket.sendto(data, client_address)
