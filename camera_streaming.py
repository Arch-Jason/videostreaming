import cv2
import socket
import struct
import zlib

UDP_IP = "192.168.0.118"
UDP_PORT = 5600
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

CHUNK_SIZE = 32767

HEADER_INDICATOR = -114514

cap = cv2.VideoCapture(0)

def send_frame_udp(jpg_bytes: bytes, udp_ip=UDP_IP, udp_port=UDP_PORT, sock_inst=sock):
    data = jpg_bytes
    frame_len = len(data)
    num_chunks = (frame_len + CHUNK_SIZE - 1) // CHUNK_SIZE
    checksum = zlib.crc32(data)

    # header
    header = struct.pack(">iii", HEADER_INDICATOR, frame_len, checksum // 100)
    sock_inst.sendto(header, (udp_ip, udp_port))
    
    for i in range(num_chunks):
        chunk = data[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
        sock_inst.sendto(chunk, (udp_ip, udp_port))

while True:
    _, frame = cap.read()
    success, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
    if not success:
        exit()

    data = jpg.tobytes()

    send_frame_udp(jpg.tobytes())