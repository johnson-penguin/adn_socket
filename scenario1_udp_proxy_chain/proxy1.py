import socket
import multiprocessing

def proxy1_function():
    proxy1_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    proxy1_address = ('127.0.0.1', 8888)
    proxy1_socket.bind(proxy1_address)
    
    proxy2_address = ('127.0.0.1', 8889)

    while True:
        data, client_address = proxy1_socket.recvfrom(1024)
        print("Received from UDP Client: {}".format(data.decode('utf-8')))
        proxy1_socket.sendto(data, proxy2_address)

if __name__ == '__main__':
    print("proxy1 connect")
    proxy1_function()
