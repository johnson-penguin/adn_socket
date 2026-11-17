

i = 2
message = f"Hi, I am server {i}\n"

received_data = "Hi, I am server 991 Hi, I am server 992 Hi, I am server 993\n"
packet_number = int(received_data.split()[-1])
print(packet_number)