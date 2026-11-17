import socket
import time
import threading
import random
import re

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

num_packet = 50 # 一共有多少筆封包 #100000
packet_group_size = 10  # 設置一批封包組有多少封包 #250
transmission_times = num_packet / packet_group_size # 傳送次數 = 總封包數量 / 一組多少封包


path1_times = 0
path2_times = 0

proportion = 0.3 # path1 rate
server_last_sent_packet = 0
client_last_sent_packet = 0

client_chack_arrary = []

receive_buffer = 0
loss_buffer = 0
delay_buffer = 0


print("Choose path:")
print("Q1. Path 1 - proxy1 (from server to client)")
print("Q2. Path 2 - proxy2 (from server to client)")
print("Q3. Path 3 - proxy1 +proxy2")



def server_send_single_data():
    global transmission_times
    for i in range(1, num_packet + 1):
        message = f"Hi, I am server {i}\n"
        if choice == "1":
            server_socket.sendto(message.encode('utf-8'), proxy1_address)
        elif choice == "2":
            server_socket.sendto(message.encode('utf-8'), proxy2_address)
        
    
        print(f"Server send message:{message}")
        time.sleep(0.1)
        

def server_send_multi_data():
    global packet_group_size, path1_times, path2_times, proportion, server_last_sent_packet
    
    for i in range(1, num_packet + 1, packet_group_size):
        batch = [f"Hi, I am server {i + j}\n" for j in range(packet_group_size)]
        messages = "".join(batch)
        if choice == "1":
            server_socket.sendto(messages.encode('utf-8'), proxy1_address)
        elif choice == "2":
            server_socket.sendto(messages.encode('utf-8'), proxy2_address)
        elif choice == "3":
            if i < num_packet * proportion:
                print("\nSend by Proxy1\n")
                server_socket.sendto(messages.encode('utf-8'), proxy1_address)
                path1_times = path1_times + 1
            else:  
                print("\nSend by Proxy2\n")    
                server_socket.sendto(messages.encode('utf-8'), proxy2_address)
                path2_times = path2_times + 1




        ##
        server_last_sent_packet += packet_group_size
        ##
        print(f"Server send messages:\n{messages}")
        time.sleep(0.1)




def server_receive_data():
    while True:
        data, addr = server_socket.recvfrom(8192)
        received_data = data.decode('utf-8')
        print("已經接收")
        if received_data.startswith("REQUEST_RETRANSMISSION"):
            # 解析请求中的数据包编号
            print("收到重傳要求")
            requested_packet_number = int(received_data.split()[-1])
            print("重傳要求編號:",received_data,"~~~~~~~~~~~~~~~~")
            # TODO: 根据请求的数据包编号找到并重新发送对应的数据包
            if requested_packet_number <= server_last_sent_packet:
                # 重發從requested_packet_number開始的封包
                for packet_num in range(requested_packet_number, server_last_sent_packet + 1):
                    message = f"Hi, I am server {packet_num} (重傳)\n"
                    server_socket.sendto(message.encode('utf-8'), addr)
                    print(f"Server retransmitted message: {message}")
        else:
            # 处理普通的数据包
            print("Server received messages: {}".format(received_data))



#def server_receive_data():
#    while True:
#        data, _ = server_socket.recvfrom(8192)
#        print("Server received messages: {}".format(data.decode('utf-8')))

def proxy1_receive_and_send():
    global loss_buffer
    while True:
        data, _ = proxy1_socket.recvfrom(8192)
        if random.random() < 0.3:  # 模擬 10% 的封包丟失率
            print("Simulated packet loss")
            loss_buffer = loss_buffer + 1
        else:
            proxy1_socket.sendto(data, client_address)
            print("Proxy1 received messages:\n{}".format(data.decode('utf-8')))

def proxy2_receive_and_send():
    global delay_buffer
    while True:
        data, _ = proxy2_socket.recvfrom(8192)
        if random.random() < 0.05:  # 模擬 5% 的延遲傳送
            print("Simulated packet delay send")
            time.sleep(0.5)
            delay_buffer = delay_buffer + 1
            proxy2_socket.sendto(data, client_address)
            print("Proxy2 received messages:\n{}".format(data.decode('utf-8')))
        else:
            proxy2_socket.sendto(data, client_address)
            print("Proxy2 received messages:\n{}".format(data.decode('utf-8')))
        

def client_send_data():
    for i in range(1, num_packet + 1):
        message = f"Hi, I am client {i}"
        if choice == "99":
            client_socket.sendto(message.encode('utf-8'), server_address)
        print(f"Client send message:\n{message}")
        time.sleep(0.1)
        

# 使用 threading.Event 來控制線程的停止
stop_threads = threading.Event()

def client_receive_data():
    client_socket.settimeout(2)  # 設置超時為2秒
    global receive_buffer, client_last_sent_packet, client_chack_arrary
    waiting_for_retransmission = False  # 设置等待重传标志
    while not stop_threads:
        try:
            data, _ = client_socket.recvfrom(8192)
            if not data:
                print("No data received. Exiting...")
            ##
            received_data = data.decode('utf-8')
            received_data = received_data.strip()
            packet_number = int(received_data.split()[-1])  # 从数据中提取数据包编号
            
            client_last_sent_packet += 10
            print("server已經傳送 packet_number:",packet_number)
            print("client當前已收到 client_last_sent_packet:",client_last_sent_packet)
            client_chack_arrary.append(packet_number)
            print("測試用:",client_chack_arrary)


            if packet_number != client_last_sent_packet :
                if not waiting_for_retransmission:

                    print(f"\nPacket {client_last_sent_packet - 9} ~ {client_last_sent_packet} missing, requesting retransmission...\n")
                    # 发送请求重新发送特定数据包的消息
                    print(f"REQUEST_RETRANSMISSION  {client_last_sent_packet -9 } ~ {client_last_sent_packet }")

                    request_message = f"REQUEST_RETRANSMISSION {client_last_sent_packet // 10}"
                    ##
                    waiting_for_retransmission = True  # 设置等待重传标志
                    ##
                    print("需要重傳:",request_message)
                    client_socket.sendto(request_message.encode('utf-8'), server_address)
                else:
                    print(f"Waiting for retransmission of packet {client_last_sent_packet - 9} ~ {client_last_sent_packet}")

            else:
                client_last_sent_packet = packet_number
                print("Client received message:\n", received_data)
                waiting_for_retransmission = False
            #print("Client received message:\n{}".format(data.decode('utf-8')))
            receive_buffer += 1
        except socket.timeout:
            print("No data received within the timeout. Exiting...")
            break
        except Exception as e:
            print("An error occurred:", str(e))
            break
    client_socket.close()


   

choice = input("Input your path (1/2/3): ")
transmissions_choice = input("single (1) or multi (2): ")
stop_threads = False

if transmissions_choice == "1":
    server_thread = threading.Thread(target = server_send_single_data)
elif transmissions_choice == "2":
    server_thread = threading.Thread(target = server_send_multi_data)
else:
    print("Invalid transmission choice. Please choose 'single' or 'batch'.")






proxy1_thread = threading.Thread(target=proxy1_receive_and_send)
proxy2_thread = threading.Thread(target=proxy2_receive_and_send)
#client_send_thread = threading.Thread(target=client_send_data)
client_receive_thread = threading.Thread(target=client_receive_data)
#server_receive_thread = threading.Thread(target=server_receive_data)


start = time.time()
server_thread.start()
#server_receive_thread.start()
proxy1_thread.start()
proxy2_thread.start()
#client_send_thread.start()
client_receive_thread.start()

# 主程序等待所有線程結束
client_receive_thread.join()
end = time.time()
print(format(end - start))
print("Done \n")
print("封包遺失:",loss_buffer)
print("封包延遲接收:",delay_buffer,"\n")
print("封包接收:",receive_buffer,"\n")
print("掉包率:",(loss_buffer/(receive_buffer + loss_buffer)*100))
print("封包延遲率:",(delay_buffer/(receive_buffer)*100))
print(client_chack_arrary)

print("//////////////////////////////////////////////////////////////")
print("路徑1被選擇次數: ",path1_times)
print("路徑2被選擇次數: ",path2_times)