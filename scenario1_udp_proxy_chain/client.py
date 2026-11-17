import socket
import time
# Create a socket object for the UDP client
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
num_transmissions = 100

# Send data to UDP Proxy1
for i in range(1, num_transmissions + 1):
    message = f"UDP Server sends Packet {i} to UDP Client as the {i}-th transmission."
    proxy1_address = ('127.0.0.1', 8888)  # Address of UDP Proxy1
    client_socket.sendto(message.encode('utf-8'), proxy1_address)
    
    if i < num_transmissions:
        time.sleep(0.1)  # Wait for 100 ms before the next transmission

data, _ = client_socket.recvfrom(1024)
print("Received from UDP Proxy1: {}".format(data.decode('utf-8')))