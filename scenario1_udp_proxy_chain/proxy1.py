import socket

PROXY1_ADDRESS = ('127.0.0.1', 8888)
PROXY2_ADDRESS = ('127.0.0.1', 8889)


def proxy1_function():
    proxy1_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    proxy1_socket.bind(PROXY1_ADDRESS)

    client_address = None  # 記錄最後一個發送請求的 Client，用來回傳 Server 的回應

    while True:
        try:
            data, source_address = proxy1_socket.recvfrom(1024)
        except ConnectionResetError:
            # Windows 上若前一次 sendto 的目的地已關閉，會在下一次 recvfrom 收到 ICMP 錯誤，忽略即可
            continue

        if source_address == PROXY2_ADDRESS:
            # 回程：Server -> Proxy2 -> Proxy1 -> Client
            if client_address is None:
                continue
            print("Received from UDP Proxy2: {}".format(data.decode('utf-8')))
            proxy1_socket.sendto(data, client_address)
        else:
            # 去程：Client -> Proxy1 -> Proxy2
            client_address = source_address
            print("Received from UDP Client: {}".format(data.decode('utf-8')))
            proxy1_socket.sendto(data, PROXY2_ADDRESS)


if __name__ == '__main__':
    print("proxy1 connect")
    proxy1_function()
