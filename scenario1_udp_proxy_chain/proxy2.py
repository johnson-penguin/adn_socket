import socket
import multiprocessing

def proxy2_function():
    proxy2_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    proxy2_address = ('127.0.0.1', 8889)
    proxy2_socket.bind(proxy2_address)
    server_address = ('127.0.0.1', 12345)
    
    while True:
        proxy1_data, proxy1_address = proxy2_socket.recvfrom(1024)
        modified_data = proxy1_data.decode('utf-8').upper().encode('utf-8')
        proxy2_socket.sendto(modified_data,  server_address)

if __name__ == '__main__':
    print("proxy2 connect")
    p = multiprocessing.Process(target=proxy2_function)
    p.start()
    p.join()
