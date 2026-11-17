import socket
import multiprocessing

PROXY1_ADDRESS = ('127.0.0.1', 8888)
PROXY2_ADDRESS = ('127.0.0.1', 8889)
SERVER_ADDRESS = ('127.0.0.1', 12345)


def proxy2_function():
    proxy2_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    proxy2_socket.bind(PROXY2_ADDRESS)

    while True:
        try:
            data, source_address = proxy2_socket.recvfrom(1024)
        except ConnectionResetError:
            # Windows 上若前一次 sendto 的目的地已關閉，會在下一次 recvfrom 收到 ICMP 錯誤，忽略即可
            continue

        if source_address == SERVER_ADDRESS:
            # 回程：Server 的回應直接轉回 Proxy1，不再送回 Server（避免無限迴圈）
            proxy2_socket.sendto(data, PROXY1_ADDRESS)
        elif source_address == PROXY1_ADDRESS:
            # 去程：轉成大寫後送往 Server
            modified_data = data.decode('utf-8').upper().encode('utf-8')
            proxy2_socket.sendto(modified_data, SERVER_ADDRESS)
        # 其他來源的封包一律丟棄


if __name__ == '__main__':
    print("proxy2 connect")
    p = multiprocessing.Process(target=proxy2_function)
    p.start()
    p.join()
