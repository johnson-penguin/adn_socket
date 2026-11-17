import socket
import time
import threading
import random

#Family(IPv4)、Type(UDP) steeing
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

num_transmissions = 1000
receive_buffer = 0
loss_buffer = 0
delay_buffer = 0


print("Choose path:")
print("Q1. Path 1 - proxy1 (from server to client)")
print("Q2. Path 2 - proxy2 (from server to client)")
print("3. Path 3 - directly (from client to server)")


def server_send_data():
    for i in range(1, num_transmissions + 1):
        message = f"Hi, I am server {i}\n"
        if choice == "1":
            server_socket.sendto(message.encode('utf-8'), proxy1_address)
        elif choice == "2":
            server_socket.sendto(message.encode('utf-8'), proxy2_address)
        print(f"Server send message: {message}")
        time.sleep(0.1)
        

def server_receive_data():
    while True:
        data, _ = server_socket.recvfrom(1024)
        print("Server received messages: {}".format(data.decode('utf-8')))

def proxy1_receive_and_send():
    global loss_buffer
    while True:
        data, _ = proxy1_socket.recvfrom(1024)
        if random.random() < 0.2:  # 模擬 20% 的封包丟失率
            print("Simulated packet loss")
            loss_buffer = loss_buffer + 1
        else:
            proxy1_socket.sendto(data, client_address)
            print("Proxy1 received messages: {}".format(data.decode('utf-8')))

def proxy2_receive_and_send():
    global delay_buffer
    while True:
        data, _ = proxy2_socket.recvfrom(1024)
        if random.random() < 0.5:  # 模擬 50% 的延遲傳送
            print("Simulated packet delay send")
            time.sleep(0.5)
            delay_buffer = delay_buffer + 1
            proxy2_socket.sendto(data, client_address)
            print("Proxy2 received messages: {}".format(data.decode('utf-8')))

        else:
            proxy2_socket.sendto(data, client_address)
            print("Proxy2 received messages: {}".format(data.decode('utf-8')))
        

def client_send_data():
    for i in range(1, num_transmissions + 1):
        message = f"Hi, I am client {i}\n"
        if choice == "3":
            client_socket.sendto(message.encode('utf-8'), server_address)
        print(f"Client send message: {message}")
        time.sleep(0.1)
        

# def client_receive_data():
#     client_socket.settimeout(5)  # 設置超時為10秒
#     while True:
#         try:
#             data, _ = client_socket.recvfrom(1024)
#             if not data:
#                 print("No data received. Exiting...")
#                 break
#             print("Client received message: {}".format(data.decode('utf-8')))
#         except socket.timeout:
#             print("No data received within the timeout. Exiting...")              
#             break
#         except Exception as e:
#             print("An error occurred:", str(e))
#             break
#     client_socket.close()

# 使用 threading.Event 來控制線程的停止
stop_threads = threading.Event()

def client_receive_data():
    client_socket.settimeout(5)  # 設置超時為5秒
    global receive_buffer
    while not stop_threads:
        try:
            data, _ = client_socket.recvfrom(1024)
            if not data:
                print("No data received. Exiting...")
            print("Client received message: {}".format(data.decode('utf-8')))
            receive_buffer += 1
        except socket.timeout:
            print("No data received within the timeout. Exiting...")
            break
        except Exception as e:
            print("An error occurred:", str(e))
            break
    client_socket.close()







   

choice = input("Input your path (1/2/3): ")
start = time.time()


stop_threads = False
server_thread = threading.Thread(target=server_receive_data if choice == "3" else server_send_data)
proxy1_thread = threading.Thread(target=proxy1_receive_and_send)
proxy2_thread = threading.Thread(target=proxy2_receive_and_send)
   #client_send_thread = threading.Thread(target=client_send_data)
client_receive_thread = threading.Thread(target=client_receive_data)


server_thread.start()
proxy1_thread.start()
proxy2_thread.start()
#client_send_thread.start()
client_receive_thread.start()


# 主程序等待所有線程結束
client_receive_thread.join()
end = time.time()
print(format(end - start))
print("Done \n")
print("封包損失:",loss_buffer)
print("封包接收:",receive_buffer)
print("封包損失率:",(loss_buffer/(receive_buffer + loss_buffer)))
print("//////////////////////////////////////////////////////////////")
print("封包延遲接收:",delay_buffer)
print("封包接收:",receive_buffer)
print("封包延遲率:",(delay_buffer/(receive_buffer)))
