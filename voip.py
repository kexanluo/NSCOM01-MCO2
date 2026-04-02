import os
import sys
import wave
import uuid
import time
import struct
import socket
import random
import pyaudio
import winsound
import threading

# DEFAULT PORTS
SIP_PORT_CALLER = 6767
SIP_PORT_RECEIVER = 6768
RTP_PORT_CALLER = 6777
RTP_PORT_RECEIVER = 6778

# HOLDER
MY_IP = ""

# FOR SIP
Cseq = 1
call_established = False
call_id = str(uuid.uuid4())
myTag = str(uuid.uuid4())
peerTag = ""
mode = ""
close = False

# FOR RTP
TIMESTAMP = random.getrandbits(32)
HEADER_FORMAT = "!HII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
SSRC = random.getrandbits(32)
expected_ssrc = ""
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000

# FOR RTCP
seq = 0
received_seq = 0
packetLoss = 0

# AUDIO FEATURES
sound = None

def createSockets(): # Creates socket for SIP
    global sipSock, rtpSock, MY_IP

    sipSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if role == "caller":
        sipSock.bind(("0.0.0.0", SIP_PORT_CALLER))
        rtpSock.bind(("0.0.0.0", RTP_PORT_CALLER))
        print(f"SIP Socket Created. Listening on port {SIP_PORT_CALLER}\n")
        print(f"RTP Socket Created. Listening on port {RTP_PORT_CALLER}")
    elif role == "receiver":
        sipSock.bind(("0.0.0.0", SIP_PORT_RECEIVER))
        rtpSock.bind(("0.0.0.0", RTP_PORT_RECEIVER))
        print(f"SIP Socket Created. Listening on port {SIP_PORT_RECEIVER}")
        print(f"RTP Socket Created. Listening on port {RTP_PORT_RECEIVER}")

    MY_IP = socket.gethostbyname(socket.gethostname())
    threading.Thread(target=sipReceive, daemon=True).start()

def playSound(audio):
    global sound
    winsound.PlaySound(audio, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)

def stopSound():
    winsound.PlaySound(None, winsound.SND_PURGE)

def start_audio_stream(peer_ip, peer_port):
    audio = pyaudio.PyAudio()

    if mode == "VOIP Call":
        stream_out = audio.open(format=FORMAT, channels=CHANNELS,
                                rate=RATE, input=True,
                                frames_per_buffer=CHUNK)

        stream_in = audio.open(format=FORMAT, channels=CHANNELS,
                            rate=RATE, output=True,
                            frames_per_buffer=CHUNK)

        def send_audio():
            while call_established:
                try:
                    header = struct.pack(HEADER_FORMAT, seq + 1, TIMESTAMP, SSRC)
                    data = stream_out.read(CHUNK, exception_on_overflow=False)
                    rtpSock.sendto(header + data, (peer_ip, peer_port))
                except Exception as e:
                    print(f"[SYSTEM] AUDIO SEND ERROR: {e}")
                    break

        def receive_audio():
            while call_established:
                try:
                    data, addr = rtpSock.recvfrom(2058)
                    sequence, timestamp, ssrc = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE]) 
                    audio = data[HEADER_SIZE:]
                    stream_in.write(audio)
                except Exception as e:
                    print(f"[SYSTEM] AUDIO RECEIVE ERROR: {e}")
                    break

        threading.Thread(target=send_audio, daemon=True).start()
        threading.Thread(target=receive_audio, daemon=True).start()
    
    elif mode == "Stream Recorded Audio":
        stream_in = None
        if role == "receiver":
            stream_in = audio.open(format=pyaudio.paInt8, channels=1,
                                rate=8000, output=True,
                                frames_per_buffer=4096)

        def send_audio():
            global seq, TIMESTAMP

            wav = wave.open("audios/stream-audio-sample.wav", "rb")
            while call_established:
                data = wav.readframes(4096)
                if not data:
                    sendBye(peer_ip, SIP_PORT_RECEIVER, SIP_PORT_CALLER)

                # Correct signed conversion for paInt8
                data_signed = bytes((b - 128) & 0xFF for b in data)
                header = struct.pack(HEADER_FORMAT, seq, TIMESTAMP, SSRC)
                rtpSock.sendto(header + data_signed, (peer_ip, peer_port))

                seq = (seq + 1) & 0xFFFF
                TIMESTAMP = (TIMESTAMP + 1024) & 0xFFFFFFFF

                time.sleep(4096 / 8000)  # 0.128s real-time pacing

        def receive_audio():
            while call_established:
                try:
                    packet, addr = rtpSock.recvfrom(HEADER_SIZE + 4096)
                    sequence, ts, ssrc = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])
                    audio_chunk = packet[HEADER_SIZE:]
                    stream_in.write(audio_chunk)
                except Exception as e:
                    print(f"[SYSTEM] AUDIO RECEIVE ERROR: {e}")
                    break

        if role == "caller":
            threading.Thread(target=send_audio, daemon=True).start()
        elif role == "receiver":
            threading.Thread(target=receive_audio, daemon=True).start()
            
    threading.Thread(target=in_call_menu, args=(peer_ip, peer_port), daemon=True).start()

def in_call_menu(peer_ip, peer_port):
    global call_established, close

    while call_established:
        userCommand = input("- - In-call Menu -- [X] End Call ")
        if userCommand.lower() == "x":
            print("[SYSTEM] Ending call...")
            call_established = False
            close = True
            if role == "caller":
                sendBye(peer_ip, SIP_PORT_RECEIVER, SIP_PORT_CALLER)
            else:
                sendBye(peer_ip, SIP_PORT_CALLER, SIP_PORT_RECEIVER)
            break
        else:
            print("Invalid input!")

def sendBye(peer_ip, peer_port, my_port):
    branch = str(uuid.uuid4())
    headers = [
        f"BYE sip:client@{peer_ip}:{peer_port} SIP/2.0",
        f"Via: SIP/2.0/UDP {MY_IP}:{my_port};branch=z9hG4bK{branch}",
        "Max-Forwards: 70",
        f"From: <sip:client@{MY_IP}>;tag={myTag}",
        f"To: <sip:client@{peer_ip}>;tag={peer_tag}",
        f"Call-ID: {call_id}",
        f"CSeq: {Cseq} BYE",
        f"Contact: <sip:client@{MY_IP}:{my_port}>",
        "Content-Length: 0"
    ]

    message = "\r\n".join(headers) + "\r\n\r\n"
    sipSock.sendto(message.encode(), ((peer_ip, peer_port)))
    print(f"[SYSTEM] BYE sent to {peer_ip}")

def callerFunction(receiverIP):
    createSockets()

    branch = str(uuid.uuid4())
    headers = [
        f"INVITE sip:client@{receiverIP}:{SIP_PORT_RECEIVER} SIP/2.0",
        f"Via: SIP/2.0/UDP {MY_IP}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
        f"From: <sip:client@{MY_IP}>;tag={myTag}",
        f"To: <sip:client@{receiverIP}>",
        f"Call-ID: {call_id}",
        f"CSeq: {Cseq} INVITE",
        f"Contact: <sip:client@{MY_IP}:{SIP_PORT_CALLER}>",
        "Max-Forwards: 70"
    ]
    body = ""
    sdp = [
        "v=0",
        f"o=- {Cseq} {Cseq} IN IP4 {MY_IP}",
        f"s={mode}",
        f"c=IN IP4 {MY_IP}",
        "t=0 0",
        f"m=audio {RTP_PORT_CALLER} RTP/AVP 0",
        "a=rtpmap:0 PCMU/8000"
    ]
    body = "\r\n".join(sdp)
    headers.append("Content-Type: application/sdp")
    headers.append(f"Content-Length: {len(body)}")
    message = "\r\n".join(headers) + "\r\n\r\n" + body
    sipSock.sendto(message.encode(), (receiverIP, SIP_PORT_RECEIVER))
    print(f"[SYSTEM] INVITE sent to {receiverIP}")

def sipReceive():
    global mode, call_id, call_established, peer_tag, Cseq, close

    while True:
        data, addr = sipSock.recvfrom(1024)
        msg = data.decode(errors="ignore")

        if msg.startswith("INVITE"):
            print(f"\n[SYSTEM] INVITE received from {addr[0]}")
            playSound("audios/incoming-call-sound.wav")

            for line in msg.split("\r\n"):
                if line.startswith("Via:"):
                    branch = line.split("branch=z9hG4bK")[1].split(";")[0]
                
                if line.startswith("From:"):
                    peer_tag = line.split("tag=")[1].split(";")[0]

                if line.startswith("Call-ID:"):
                    call_id = line.split("Call-ID:")[1].strip()

            headers = [
                f"SIP/2.0 180 Ringing",
                f"Via: SIP/2.0/UDP {addr[0]}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
                f"From: <sip:client@{addr[0]}>;tag={peer_tag}",
                f"To: <sip:client@{MY_IP}>;tag={myTag}",
                f"Call-ID: {call_id}",
                f"CSeq: {Cseq} INVITE",
                f"Contact: <sip:client@{MY_IP}:{SIP_PORT_RECEIVER}>",
                "Content-Length: 0"
            ]
            response = "\r\n".join(headers) + "\r\n\r\n"
            sipSock.sendto(response.encode(), addr)

            input("wait")
            stopSound()

            if "\r\n\r\n" in msg:
                    sdp_part = msg.split("\r\n\r\n")[1]
                    for line in sdp_part.split("\r\n"):
                        if line.startswith("s="):
                            mode = line.split("=", 1)[1]
                            break
            headers = [
                f"SIP/2.0 200 OK",
                f"Via: SIP/2.0/UDP {addr[0]}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
                f"From: <sip:client@{addr[0]}>;tag={peer_tag}",
                f"To: <sip:client@{MY_IP}>;tag={myTag}",
                f"Call-ID: {call_id}",
                f"CSeq: {Cseq} INVITE",
                f"Contact: <sip:client@{MY_IP}:{SIP_PORT_RECEIVER}>"
            ]
            body = ""
            sdp_answer = [
                "v=0",
                f"o=- {Cseq} {Cseq} IN IP4 {MY_IP}",
                f"s={mode}",
                f"c=IN IP4 {MY_IP}",
                "t=0 0",
                f"m=audio {RTP_PORT_RECEIVER} RTP/AVP 0",
                "a=rtpmap:0 PCMU/8000"
            ]
            body = "\r\n".join(sdp_answer)
            headers.append("Content-Type: application/sdp")
            headers.append(f"Content-Length: {len(body)}")
            response = "\r\n".join(headers) + "\r\n\r\n" + body
            sipSock.sendto(response.encode(), addr)
            print("\n[SYSTEM] Sent 200 OK with SDP")

        elif msg.startswith("SIP/2.0 180 Ringing"):
            playSound("audio/dialing-sound.wav")
        
        elif msg.startswith("SIP/2.0 200 OK"):
            for line in msg.split("\r\n"):
                if line.startswith("CSeq:"):
                    req = line.split()[2]
                    break

            if req == "INVITE":
                stopSound()
                print(f"\n[SYSTEM] 200 OK for INVITE received from {addr[0]}")

                for line in msg.split("\r\n"):
                    if line.startswith("To:"):
                        peer_tag = line.split("tag=")[1].split(";")[0]

                    if line.startswith("Via:"):
                        branch = line.split("branch=z9hG4bK")[1].split(";")[0]

                headers = [
                    f"ACK sip:client@{receiverIP}:{SIP_PORT_RECEIVER} SIP/2.0",
                    f"Via: SIP/2.0/UDP {MY_IP}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
                    f"From: <sip:client@{MY_IP}>;tag={myTag}",
                    f"To: <sip:client@{MY_IP}>;tag={peer_tag}",
                    f"Call-ID: {call_id}",
                    f"CSeq: {Cseq} INVITE",
                    f"Contact: <sip:client@{MY_IP}:{SIP_PORT_CALLER}>",
                    "Content-Length: 0"
                ]
                response = "\r\n".join(headers) + "\r\n\r\n"
                sipSock.sendto(response.encode(), addr)

                call_established = True
                Cseq += 1

                print(f"[SYSTEM] ACK sent to {addr[0]}")
                print("[SYSTEM]] Call established successfully")
                print("[SYSTEM] VOIP Call Started")
                start_audio_stream(addr[0], RTP_PORT_RECEIVER)
            
            elif req == "BYE":
                print(f"\n[SYSTEM] 200 OK for BYE received from {addr[0]}")
                call_established = False
                print("[SYSTEM] Call terminated gracefully")
                close = True

        elif msg.startswith("ACK"):
            print(f"[SYSTEM] ACK received from {addr[0]}")
            print("[SYSTEM] Call established on both sides")

            call_established = True
            Cseq += 1

            print("[SYSTEM] VOIP Call Started")
            start_audio_stream(addr[0], RTP_PORT_CALLER)

        elif msg.startswith("BYE"):
            print(f"[SYSTEM] BYE received from {addr[0]}")
            call_established = False


            for line in msg.split("\r\n"):
                if line.startswith("Via:"):
                    branch = line.split("branch=z9hG4bK")[1].split(";")[0]

            headers = [
                f"SIP/2.0 200 OK",
                f"Via: SIP/2.0/UDP {addr[0]}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
                f"From: <sip:client@{addr[0]}>;tag={peer_tag}",
                f"To: <sip:client@{MY_IP}>;tag={myTag}",
                f"Call-ID: {call_id}",
                f"CSeq: {Cseq} BYE",
                f"Contact: <sip:client@{MY_IP}:{SIP_PORT_RECEIVER}>"
            ]
            response = "\r\n".join(headers) + "\r\n\r\n"
            sipSock.sendto(response.encode(), addr)
            print(f"\n[SYSTEM] 200 OK for BYE sent to {addr[0]}")
            print("[SYSTEM] Call terminated gracefully")
            close = True

def receiverFunction():
    createSockets()
    print("[SYSTEM] Waiting for caller ...")


# Main Program
os.system('cls')
print(f"NSCOM01 Real-Time Audio Streaming over IP")
print("     VoIP or Stream Recorded Audio")
print(f"\nCreated by: Ke, Xan Luo and Mojica, Maurienne Marie\n\n")
input("PRESS [ENTER] TO START CONFIGURATION")
os.system('cls')

print(f"- - Configuration - -\n")
print(f"[1] Caller")
print(f"[2] Receiver\n")

while True:
    userIn_role = input("Select role: ")
    if userIn_role in ("1", "2"):
        break
    print("Invalid input. Please enter 1 or 2.")

if userIn_role == "1":
    os.system('cls')
    role = "caller"
    print(f"- - Configuration - -\n")
    print(f"[1] VoIP")
    print(f"[2] Stream Recorded Audio\n")

    while True:
        userIn_mode = input("Select mode: ")
        if userIn_mode in ("1", "2"):
            if userIn_mode == "1":
                mode = "VOIP Call"
            else:
                mode = "Stream Recorded Audio"

            break
        print("Invalid input. Please enter 1 or 2.")
    os.system('cls')

    print(f"- - Configuration - -\n")
    receiverIP = input("Enter the IP address you're calling: ")
    callerFunction(receiverIP)
elif userIn_role == "2":
    os.system('cls')
    role = "receiver"
    receiverFunction()

while True:
    if close == True:
        sys.exit()