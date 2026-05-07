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

# DEFAULT PORTS - try
SIP_PORT_CALLER = 6767
SIP_PORT_RECEIVER = 6768
RTP_PORT_CALLER = 6776
RTP_PORT_RECEIVER = 6778
RTCP_PORT_CALLER = 6777
RTCP_PORT_RECEIVER = 6779

# HOLDER
MY_IP = ""

# FOR SIP
Cseq = 1
call_established = False
call_id = str(uuid.uuid4())
myTag = str(uuid.uuid4())
peer_tag = ""
mode = ""
close = False

# FOR RTP
TIMESTAMP = random.getrandbits(32)
HEADER_FORMAT = "!BBHII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
SSRC = random.getrandbits(32)
expected_ssrc = ""
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000

# FOR RTCP
seq = 0
received_seq = -1
expected_seq = 0
packet_loss = 0

# AUDIO FEATURES
sound = None
timeup = False

#TIMEOUT FEATURES
cancelled = False
ringing = False

# SOCKET PART
def createSockets(): # Creates socket for SIP
    global sipSock, rtpSock, rtcpSock, MY_IP

    sipSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtcpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("- - - - - - - - - SOCKET CREATED - - - - - - -")
    if role == "caller":
        sipSock.bind(("0.0.0.0", SIP_PORT_CALLER))
        rtpSock.bind(("0.0.0.0", RTP_PORT_CALLER))
        rtcpSock.bind(("0.0.0.0", RTCP_PORT_CALLER))
        print(f"SIP Socket Created. Listening on port {SIP_PORT_CALLER}")
        print(f"RTP Socket Created. Listening on port {RTP_PORT_CALLER}")
        print(f"RTCP Socket Created. Listening on port {RTCP_PORT_CALLER}")
    elif role == "receiver":
        sipSock.bind(("0.0.0.0", SIP_PORT_RECEIVER))
        rtpSock.bind(("0.0.0.0", RTP_PORT_RECEIVER))
        rtcpSock.bind(("0.0.0.0", RTCP_PORT_RECEIVER))
        print(f"SIP Socket Created. Listening on port {SIP_PORT_RECEIVER}")
        print(f"RTP Socket Created. Listening on port {RTP_PORT_RECEIVER}")
        print(f"RTCP Socket Created. Listening on port {RTCP_PORT_RECEIVER}")
        threading.Thread(target=sipReceive, daemon=True).start()

    MY_IP = socket.gethostbyname(socket.gethostname())

# FOR PRINTING
def printme(message, inputText): # Properly prints server message without removing [server_command]
    sys.stdout.write('\r\033[K')
    sys.stdout.flush()
    print(message)
    sys.stdout.write(inputText)
    sys.stdout.flush()

# FOR AUDIO
def playSound(audio, mode, sec=0):
    global sound, close

    if mode == 1:
        winsound.PlaySound(audio, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
    elif mode == 2:
        winsound.PlaySound(audio, winsound.SND_FILENAME)
        close = True
    elif mode == 3:
        winsound.PlaySound(audio, winsound.SND_FILENAME | winsound.SND_ASYNC)
        threading.Thread(target=timer, args=(sec,), daemon=True).start()
        while not timeup and not cancelled:
            pass
        if timeup:
            close = True

def stopSound():
    winsound.PlaySound(None, winsound.SND_PURGE)

# RTCP
def send_rtcp_sr_voip(peer_ip, peer_port):
    global seq, TIMESTAMP, received_seq, packet_loss

    while call_established:
        time.sleep(5)
        try:
            # --- RTCP Header ---
            version = 2
            padding = 0
            rc = 1  # 1 report block
            pt = 200  # SR
            length = 6 + rc * 6  # SR header + report blocks (in 32-bit words minus 1)

            first_byte = (version << 6) | (padding << 5) | rc
            header = struct.pack("!BBH", first_byte, pt, length)

            # --- Sender Info ---
            sender_ssrc = SSRC
            ntp_sec = int(time.time())
            ntp_frac = int((time.time() % 1) * (2**32))
            rtp_timestamp = TIMESTAMP
            packet_count = seq
            octet_count = seq * CHUNK  # assuming CHUNK bytes per RTP packet

            sr_body = struct.pack(
                "!I I I I I I",
                sender_ssrc,
                ntp_sec,
                ntp_frac,
                rtp_timestamp,
                packet_count,
                octet_count
            )

            # --- Report Block (for RTP stream you receive) ---
            # SSRC of the stream you are reporting on (the peer)
            report_ssrc = expected_ssrc

            fraction_lost = 0  # simple version
            cumulative_lost = packet_loss & 0xFFFFFF
            highest_seq = received_seq if received_seq != -1 else 0
            jitter = 0
            lsr = 0
            dlsr = 0

            report_block = struct.pack(
                "!I B 3s I I I I",
                report_ssrc,
                fraction_lost,
                cumulative_lost.to_bytes(3, "big"),
                highest_seq,
                jitter,
                lsr,
                dlsr
            )

            # --- Final RTCP Packet ---
            packet = header + sr_body + report_block

            rtcpSock.sendto(packet, (peer_ip, peer_port))
            printme("- - - - - - - - - - [RTCP SR SENT] - - - - - - - - - -" , "")
            printme(f"[OUTBOUND] PACKET SENT       : {packet_count}", "")
            printme(f"[OUTBOUND] OCTETS COUNT      : {octet_count}", "")
            printme(f"[INBOUND]  PACKET LOSS       : {packet_loss}", "")
            printme(f"[INBOUND]  RECEIVED SEQUENCE : {highest_seq}", "")
            printme("- - - - - - - - - - - - - - - - - - - - - - - - - - - ", f"\n- - Call Menu - - [X] End Call >>> ")

        except Exception as e:
            print(f"[SYSTEM] RTCP SR ERROR: {e}")
            break

def send_rtcp_sr_stream(peer_ip, peer_port):
    global seq, TIMESTAMP

    while call_established:
        time.sleep(5)
        try:
            version = 2
            padding = 0
            rc = 0  # no report blocks
            pt = 200  # SR

            # SR = header (1) + sender info (6) = 7 words → length = 6
            length = 6  

            first_byte = (version << 6) | (padding << 5) | rc
            header = struct.pack("!BBH", first_byte, pt, length)

            sender_ssrc = SSRC

            now = time.time()
            ntp_sec = int(now)
            ntp_frac = int((now - ntp_sec) * (2**32))

            rtp_timestamp = TIMESTAMP

            packet_count = seq
            octet_count = seq * CHUNK  # use actual chunk size

            sr_body = struct.pack(
                "!I I I I I I",
                sender_ssrc,
                ntp_sec,
                ntp_frac,
                rtp_timestamp,
                packet_count,
                octet_count
            )

            packet = header + sr_body

            rtcpSock.sendto(packet, (peer_ip, peer_port))

            printme("- - - - - - - - - - [RTCP SR SENT] - - - - - - - - - -" , "")
            printme(f"[OUTBOUND] PACKET SENT       : {packet_count}", "")
            printme(f"[OUTBOUND] OCTETS COUNT      : {octet_count}", "")
            printme("- - - - - - - - - - - - - - - - - - - - - - - - - - - ", f"\n- - Call Menu - - [X] End Call >>> ")

        except Exception as e:
            print(f"[SYSTEM] RTCP SR ERROR: {e}")
            break

def send_rtcp_rr(peer_ip, peer_port):
    global packet_loss, received_seq, expected_ssrc

    while call_established:
        time.sleep(5)
        try:
            version = 2
            padding = 0
            rc = 1
            pt = 201  # RR

            length = 7  # correct

            first_byte = (version << 6) | (padding << 5) | rc
            header = struct.pack("!BBH", first_byte, pt, length)

            sender_ssrc = SSRC  # YOU

            fraction_lost = 0
            cumulative_lost = packet_loss & 0xFFFFFF
            highest_seq = received_seq if received_seq != -1 else 0
            jitter = 0
            lsr = 0
            dlsr = 0

            report_block = struct.pack(
                "!I B 3s I I I I",
                expected_ssrc,  # <-- peer's SSRC (VERY IMPORTANT)
                fraction_lost,
                cumulative_lost.to_bytes(3, 'big'),
                highest_seq,
                jitter,
                lsr,
                dlsr
            )

            packet = header + struct.pack("!I", sender_ssrc) + report_block

            rtcpSock.sendto(packet, (peer_ip, peer_port))

            printme("- - - - - - - - - - [RTCP RR SENT] - - - - - - - - - -" , "")
            printme(f"[INBOUND]  PACKET LOSS       : {packet_loss}", "")
            printme(f"[INBOUND]  RECEIVED SEQUENCE : {highest_seq}", "")
            printme("- - - - - - - - - - - - - - - - - - - - - - - - - - - ", f"\n- - Call Menu - - [X] End Call >>> ")

        except Exception as e:
            print(f"[SYSTEM] RTCP RR ERROR: {e}")
            break

def receive_rtcp():
    while call_established:
        try:
            data, addr = rtcpSock.recvfrom(1024)
            time.sleep(0.5) # Short Delay for printing to avoid printing collision

            if len(data) < 8:
                continue

            first_byte, pt, length = struct.unpack("!BBH", data[:4])
            rc = first_byte & 0x1F
            sender_info = data[4:28]

            sender_ssrc, ntp_sec, ntp_frac, rtp_timestamp, packet_count, octet_count = struct.unpack(
                "!I I I I I I", sender_info
            )
            
            printme("- - - - - - - - - - [RTCP RECEIVED] - - - - - - - - - -" , "")
            if pt == 200:
                printme(f"Sender Report from {addr[0]}:\n", "")
                printme(f"  Sender SSRC: {sender_ssrc}", "")
                printme(f"  Packets SENT: {packet_count}", "")
                printme(f"  Octets SENT: {octet_count}", "")

            elif pt == 201:
                printme(f"Receiver Report from {addr[0]}:\n", "")
                printme(f"  Sender SSRC: {sender_ssrc}", "")

            if rc > 0:
                if pt == 200:
                    report_block = data[28:52]
                elif pt == 201:
                    report_block = data[8:32]

                report_ssrc, fraction_lost, cumulative_lost_bytes, highest_seq, jitter, lsr, dlsr = struct.unpack(
                    "!I B 3s I I I I", report_block
                )
                cumulative_lost = int.from_bytes(cumulative_lost_bytes, "big")
                printme(f"\n    + + + + + + + R E P O R T + + + + + + +", "")
                printme(f"      Reporting on SSRC: {report_ssrc}", "")
                printme(f"      Packet LOSS: {cumulative_lost}", "")
                printme(f"      Highest Seq Received: {highest_seq}", "")
                printme(f"    + + + + + + + + + + + + + + + + + + + +", "")

            printme("- - - - - - - - - - - - - - - - - - - - - - - - - - - -", f"\n- - Call Menu - - [X] End Call >>> ")

        except Exception as e:
            print(f"[SYSTEM - RTCP ERROR] Receive failed: {e}")
            break

# SENDING AND RECEIVING AUDIO - RTP
def start_audio_stream(peer_ip, peer_rtp_port, peer_rtcp_port):
    audio = pyaudio.PyAudio()

    if mode == "VOIP Call":
        stream_out = audio.open(format=FORMAT, channels=CHANNELS,
                                rate=RATE, input=True,
                                frames_per_buffer=CHUNK)

        stream_in = audio.open(format=FORMAT, channels=CHANNELS,
                            rate=RATE, output=True,
                            frames_per_buffer=CHUNK)

        def send_audio():
            global TIMESTAMP, seq

            while call_established:
                try:
                    version = 2
                    padding = 0
                    extension = 0
                    cc = 0
                    marker = 0
                    payload_type = 0  # PCMU G.711

                    first_byte = (version << 6) | (padding << 5) | (extension << 4) | cc
                    second_byte = (marker << 7) | payload_type

                    header = struct.pack(HEADER_FORMAT, first_byte, second_byte, seq, TIMESTAMP, SSRC)
                    data = stream_out.read(CHUNK, exception_on_overflow=False)
                    rtpSock.sendto(header + data, (peer_ip, peer_rtp_port))

                    seq += 1
                    TIMESTAMP += CHUNK
                except Exception as e:
                    print(f"[SYSTEM] AUDIO SEND ERROR: {e}")
                    break

        def receive_audio():
            global packet_loss, expected_seq, received_seq, expected_ssrc

            while call_established:
                try:
                    data, addr = rtpSock.recvfrom(CHUNK * 2 + HEADER_SIZE)
                    fb, sb, sequence, timestamp, ssrc = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE]) 
                    audio_chunk = data[HEADER_SIZE:]

                    if received_seq == -1:
                        expected_ssrc = ssrc

                    if received_seq != -1:
                        if sequence > received_seq:
                            lost = sequence - received_seq - 1
                            if lost > 0:
                                packet_loss += lost
                                printme(f"[SYSTEM - LOST DETECTION] Packet lost: {lost}, total lost: {packet_loss}", f"\n- - Call Menu - - [X] End Call >>> ")

                        elif sequence <= received_seq:
                            # out-of-order or duplicate - ignore
                            pass

                    received_seq = sequence
                    stream_in.write(audio_chunk)

                except Exception as e:
                    print(f"[SYSTEM] AUDIO RECEIVE ERROR: {e}")
                    break

        threading.Thread(target=send_audio, daemon=True).start()
        threading.Thread(target=receive_audio, daemon=True).start()
        threading.Thread(target=receive_rtcp, daemon=True).start()
        threading.Thread(target=send_rtcp_sr_voip, args=(peer_ip, peer_rtcp_port), daemon=True).start()
    
    elif mode == "Stream Recorded Audio":
        stream_in = None
        if role == "receiver":
            stream_in = audio.open(format=pyaudio.paInt8, channels=1,
                                rate=8000, output=True,
                                frames_per_buffer=4096)

        def send_audio():
            global TIMESTAMP, seq

            wav = wave.open("audios/stream-audio-sample.wav", "rb")
            while call_established:
                data = wav.readframes(4096)
                if not data:
                    sendBye(peer_ip, SIP_PORT_RECEIVER, SIP_PORT_CALLER)

                # Correct signed conversion for paInt8
                data_signed = bytes((b - 128) & 0xFF for b in data)

                version = 2
                padding = 0
                extension = 0
                cc = 0
                marker = 0
                payload_type = 0  # PCMU G.711

                first_byte = (version << 6) | (padding << 5) | (extension << 4) | cc
                second_byte = (marker << 7) | payload_type

                header = struct.pack(HEADER_FORMAT, first_byte, second_byte, seq, TIMESTAMP, SSRC)
                rtpSock.sendto(header + data_signed, (peer_ip, peer_rtp_port))

                seq += 1
                TIMESTAMP += 4096

                time.sleep(4096 / 8000)  # 0.128s real-time pacing

        def receive_audio():
            global packet_loss, expected_seq, received_seq, expected_ssrc

            while call_established:
                try:
                    packet, addr = rtpSock.recvfrom(HEADER_SIZE + 4096)
                    fb, sb, sequence, ts, ssrc = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])
                    audio_chunk = packet[HEADER_SIZE:]

                    if received_seq == -1:
                        expected_ssrc = ssrc

                    if received_seq != -1:
                        if sequence > received_seq:
                            lost = sequence - received_seq - 1
                            if lost > 0:
                                packet_loss += lost
                                printme(f"[SYSTEM - LOST DETECTION] Packet lost: {lost}, total lost: {packet_loss}", f"\n- - Call Menu - - [X] End Call >>> ")

                        elif sequence <= received_seq:
                            # out-of-order or duplicate - ignore
                            pass

                    received_seq = sequence
                    stream_in.write(audio_chunk)
                except Exception as e:
                    print(f"[SYSTEM] AUDIO RECEIVE ERROR: {e}")
                    break

        threading.Thread(target=receive_rtcp, daemon=True).start()
        if role == "caller":
            threading.Thread(target=send_audio, daemon=True).start()
            threading.Thread(target=send_rtcp_sr_stream, args=(peer_ip, RTCP_PORT_RECEIVER), daemon=True).start()
        elif role == "receiver":
            threading.Thread(target=receive_audio, daemon=True).start()
            threading.Thread(target=send_rtcp_rr, args=(peer_ip, RTCP_PORT_CALLER), daemon=True).start()     
            threading.Thread(target=in_call_menu, args=(peer_ip, SIP_PORT_CALLER), daemon=True).start()

# CALL MENU
def in_call_menu(peer_ip, peer_port):
    global call_established, close, Cseq, cancelled, ringing

    while True:
        userCommand = input("- - Call Menu - - [X] End Call >>> ")
        if userCommand.lower() == "x":
                if call_established == True:
                    call_established = False
                    if role == "caller":
                        sendBye(peer_ip, SIP_PORT_RECEIVER, SIP_PORT_CALLER)
                    else:
                        sendBye(peer_ip, SIP_PORT_CALLER, SIP_PORT_RECEIVER)
                    break
                elif ringing:
                    cancelled = True
                    printme("[SYSTEM] Cancelling call...", "")
                    Cseq += 1
                    branch = str(uuid.uuid4())
                    headers = [
                        f"CANCEL sip:client@{peer_ip}:{SIP_PORT_RECEIVER} SIP/2.0",
                        f"Via: SIP/2.0/UDP {MY_IP}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
                        f"From: <sip:client@{MY_IP}>;tag={myTag}",
                        f"To: <sip:client@{peer_ip}>; tag={peer_tag}",
                        f"Call-ID: {call_id}",
                        f"CSeq: {Cseq} CANCEL",
                        "Content-Length: 0"
                    ]

                    message = "\r\n".join(headers) + "\r\n\r\n"
                    sipSock.sendto(message.encode(), (peer_ip, SIP_PORT_RECEIVER))
                    stopSound()
                    playSound("audios/end-call-sound.wav", 2)
                    break
                elif not ringing:
                    printme("[SYSTEM] Terminating call ...", "")
                    cancelled = True
                    stopSound()
                    playSound("audios/end-call-sound.wav", 2)
                    close = True
                    break
        else:
            print("Invalid input!")

def incoming_call_menu(msg, addr, branch):
    global mode, close
    
    while True:
        callAccept = input("- - Incoming-Call -- [1] Accept Call [2] Reject Call >>> ")
        if userIn_role in ("1", "2"):
            break
        print("Invalid input. Please enter 1 or 2.")
    stopSound()

    if callAccept == "1":
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
        print("\n[SYSTEM] Sent 200 OK with SDP to caller")
    elif callAccept == "2":
        headers = [
            f"SIP/2.0 603 Decline",
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
        print("\n[SYSTEM] Sent 603 Decline to caller")
        close = True

# CALL CONTROL
def ringingTimeout(peer_ip):
    global Cseq

    counter = 0

    while not call_established and not cancelled:
        time.sleep(1)
        counter += 1

        if counter == 12:
            print(f"\n\n[SYSTEM] Another client did not answer your call ...")
            Cseq += 1
            branch = str(uuid.uuid4())
            headers = [
                f"CANCEL sip:client@{peer_ip}:{SIP_PORT_RECEIVER} SIP/2.0",
                f"Via: SIP/2.0/UDP {MY_IP}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
                f"From: <sip:client@{MY_IP}>;tag={myTag}",
                f"To: <sip:client@{peer_ip}>;tag={peer_tag}",
                f"Call-ID: {call_id}",
                f"CSeq: {Cseq} CANCEL",
                "Content-Length: 0"
            ]

            message = "\r\n".join(headers) + "\r\n\r\n"
            sipSock.sendto(message.encode(), (peer_ip, SIP_PORT_RECEIVER))
            print(f"[SYSTEM] CANCEL sent to {peer_ip} ...")
            stopSound()
            playSound("audios/end-call-sound.wav", 2)

def timer(sec):
    global timeup

    counter = 0
    timeup = False

    while not counter == sec and not cancelled:
        time.sleep(1)
        counter += 1

        if counter == sec:
            timeup = True
            break

# SIP
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
    printme(f"\n[SYSTEM] BYE sent to {peer_ip}", "")
    call_established = False

def sipReceive():
    global mode, call_id, call_established, peer_tag, Cseq, close, ringing

    while True:
        try:
            data, addr = sipSock.recvfrom(1024)
        except (socket.timeout, ConnectionResetError):
            printme(f"\n[SYSTEM] Call can't be reach. Please try again later ...", f"\n- - Call Menu - - [X] End Call >>> ")
            playSound("audios/cant-reach-audio.wav", 3, 14)
            break

        msg = data.decode(errors="ignore")

        if msg.startswith("INVITE"):
            if not call_established and not ringing:
                ringing = True
                print(f"\n[SYSTEM] INVITE received from {addr[0]}\n")
                playSound("audios/incoming-call-sound.wav", 1)

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
                threading.Thread(target=incoming_call_menu, args=(msg, addr, branch), daemon=True).start()
            else:
                for line in msg.split("\r\n"):
                    if line.startswith("Via:"):
                        br = line.split("branch=z9hG4bK")[1].split(";")[0]
                    
                    if line.startswith("From:"):
                        ptag = line.split("tag=")[1].split(";")[0]

                    if line.startswith("Call-ID:"):
                        cid = line.split("Call-ID:")[1].strip()

                headers = [
                    f"SIP/2.0 486 Busy Here",
                    f"Via: SIP/2.0/UDP {addr[0]}:{SIP_PORT_CALLER};branch=z9hG4bK{br}",
                    f"From: <sip:client@{addr[0]}>;tag={ptag}",
                    f"To: <sip:client@{MY_IP}>;tag={myTag}",
                    f"Call-ID: {cid}",
                    f"CSeq: 1 INVITE",
                    "Content-Length: 0"
                ]

            response = "\r\n".join(headers) + "\r\n\r\n"
            sipSock.sendto(response.encode(), addr)


        elif msg.startswith("SIP/2.0 180 Ringing"):
            sipSock.settimeout(None)
            ringing = True
            playSound("audios/dialing-sound.wav", 1)
            threading.Thread(target=ringingTimeout, args=(receiverIP,), daemon=True).start()

        elif msg.startswith("SIP/2.0 603 Decline"):
            printme(f"\n[SYSTEM] Your call is declined ...", f"")
            cancelled = True
            playSound("audios/end-call-sound.wav", 2)

        elif msg.startswith("SIP/2.0 486 Busy Here"):
            sipSock.settimeout(None)
            printme(f"\n[SYSTEM] Client is in another call ...", f"\n- - Call Menu - - [X] End Call >>> ")
            playSound("audios/client-busy-sound.wav", 3, 6)
        
        elif msg.startswith("SIP/2.0 200 OK"):
            for line in msg.split("\r\n"):
                if line.startswith("CSeq:"):
                    req = line.split()[2]
                    break

            if req == "INVITE":
                stopSound()
                printme(f"[SYSTEM] 200 OK for INVITE received from {addr[0]}", "")

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
                printme("[SYSTEM] VOIP Call Started" , f"\n- - Call Menu - - [X] End Call >>> ")
                start_audio_stream(addr[0], RTP_PORT_RECEIVER, RTCP_PORT_RECEIVER)
            
            elif req == "BYE":
                print(f"[SYSTEM] 200 OK for BYE received from {addr[0]}")
                call_established = False
                print("[SYSTEM] Call terminated gracefully")
                if mode == "VOIP Call":
                    playSound("audios/end-call-sound.wav", 2)
                close = True

            elif req == "CANCEL":
                print(f"[SYSTEM] 200 OK for CANCEL received from {addr[0]}")
                call_established = False
                print("[SYSTEM] Call terminated gracefully")

        elif msg.startswith("CANCEL"):
            print(f"\n\n[SYSTEM] Cancel request received from {addr[0]}")
            stopSound()
            for line in msg.split("\r\n"):
                if line.startswith("Via:"):
                    branch = line.split("branch=z9hG4bK")[1].split(";")[0]
            Cseq += 1
            headers = [
                f"SIP/2.0 200 OK",
                f"Via: SIP/2.0/UDP {addr[0]}:{SIP_PORT_CALLER};branch=z9hG4bK{branch}",
                f"From: <sip:client@{addr[0]}>;tag={peer_tag}",
                f"To: <sip:client@{MY_IP}>;tag={myTag}",
                f"Call-ID: {call_id}",
                f"CSeq: {Cseq} CANCEL",
                f"Contact: <sip:client@{MY_IP}:{SIP_PORT_RECEIVER}>",
                "Content-Length: 0"
            ]
            response = "\r\n".join(headers) + "\r\n\r\n"
            sipSock.sendto(response.encode(), addr)
            print(f"[SYSTEM] 200 OK for CANCEL sent to {addr[0]}")
            close = True

        elif msg.startswith("ACK"):
            print(f"[SYSTEM] ACK received from {addr[0]}")
            print("[SYSTEM] Call established on both sides")

            call_established = True
            Cseq += 1

            print(f"[SYSTEM] VOIP Call Started\n")
            threading.Thread(target=in_call_menu, args=(addr[0], SIP_PORT_CALLER), daemon=True).start()
            start_audio_stream(addr[0], RTP_PORT_CALLER, RTCP_PORT_CALLER)

        elif msg.startswith("BYE"):
            printme(f"[SYSTEM] BYE received from {addr[0]}", "")
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
                f"Contact: <sip:client@{MY_IP}:{SIP_PORT_RECEIVER}>",
                "Content-Length: 0"
            ]
            response = "\r\n".join(headers) + "\r\n\r\n"
            sipSock.sendto(response.encode(), addr)
            print(f"[SYSTEM] 200 OK for BYE sent to {addr[0]}")
            print("[SYSTEM] Call terminated gracefully")
            if mode == "VOIP Call":
                playSound("audios/end-call-sound.wav", 2)
            close = True

# ROLE-BASED CONTROL
def callerFunction(receiverIP):
    createSockets()

    print(f"\n\n- - - - - - - CALL - - - - - - -")
    print(f"[SYSTEM] Dialing <{receiverIP}> ...")

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

    try:
        sipSock.sendto(message.encode(), (receiverIP, SIP_PORT_RECEIVER))
        print(f"[SYSTEM] INVITE sent to {receiverIP}\n")
        sipSock.settimeout(0.5) # Timeout if no ring reply
        threading.Thread(target=in_call_menu, args=(receiverIP, SIP_PORT_RECEIVER), daemon=True).start()
        threading.Thread(target=sipReceive, daemon=True).start()
    except Exception as e:
        print(f"\n[SYSTEM] Call can't be completed as dialed. Please check the IP Address ...\n")
        threading.Thread(target=in_call_menu, args=(receiverIP, SIP_PORT_RECEIVER), daemon=True).start()
        playSound("audios/incorrect-number-audio.wav", 3, 12)

def receiverFunction():
    createSockets()
    print(f"\n\n- - - - - - - CALL - - - - - - -")
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
    userIn_role = input("Select role >>> ")
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
        userIn_mode = input("Select mode >>> ")
        if userIn_mode in ("1", "2"):
            if userIn_mode == "1":
                mode = "VOIP Call"
            else:
                mode = "Stream Recorded Audio"

            break
        print("Invalid input. Please enter 1 or 2.")
    os.system('cls')

    print(f"- - Configuration - -\n")
    receiverIP = input("Enter the IP address you're calling >>> ")
    os.system('cls')
    callerFunction(receiverIP)
elif userIn_role == "2":
    os.system('cls')
    role = "receiver"
    receiverFunction()

while True:
    if close == True:
        print(f"\n[SYSTEM] Thank you for using Call Me. Bye <3")
        sys.exit()