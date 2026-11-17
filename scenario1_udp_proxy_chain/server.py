import socket

# Define the server address and port
server_address = ('127.0.0.1', 12345)

# Create a socket object for the UDP server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the server address
server_socket.bind(server_address)

print("Server is listening on {}:{}".format(*server_address))

while True:
    data, client_address = server_socket.recvfrom(1024)
    print("Received: {}".format(data.decode('utf-8')))
    server_socket.sendto(data, client_address)