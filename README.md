# CallMe: Real-Time Audio Streaming over IP (SIP/RTP/RTCP)
A NSCOM01 Machine Project  
Ke, Xan Luo and Mojica, Maurienne Marie

This project is a console-based peer-to-peer VoIP and audio streaming application built in Python.
 It implements core concepts of SIP (Session Initiation Protocol) for signaling, RTP (Real-time Transport Protocol) for media transmission, and RTCP (Real-time Transport Control Protocol) for feedback.

---

# Table of Contents

    A. Overview  
    B. Requirements  
    C. Roles  
    D. Communication Model  
    E. SIP Message Types  
    F. Call Flow  
    G. RTP Implementation  
    H. RTCP Feedback System  
    I. Audio Handling  
    J. Running the Program  
    K. Error Handling & Edge Cases  
    L. Test Cases and Sample Outputs  
    M. Files and Dependencies  
    N. Limitations

# A. Overview

  I. Description  
  
    CallMe is a UDP-based real-time communication system that simulates VoIP behavior using SIP, RTP, and RTCP protocols. It supports both live voice calls and recorded audio streaming while handling session control and network feedback.
       
  II. Features  

      a. SIP-based call signaling (INVITE, RINGING, BUSY HERE, DECLINE, CANCEL, OK, ACK, BYE)
      b. Real-time voice communication using RTP
      c. Recorded audio streaming over RTP
      d. RTCP feedback for packet statistics and monitoring
      e. Packet loss detection using sequence numbers
      f. Multi-threaded communication handling
      g. Console-based interactive call control

# B. Requirements

  - **Python**: 3.8+ (recommended)
  - **Dependencies** (install via `pip`):

    ```bash
    pip install pyaudio
    ```

# C. Roles

  I. Caller

    a. Initiates the call using SIP INVITE  
    b. Sends RTP audio stream  
    c. Sends RTCP Sender Reports  
    d. Can cancel or terminate calls  

  II. Receiver

    a. Waits for incoming calls  
    b. Responds with Ringing / Accept / Decline  
    c. Receives RTP audio stream  
    d. Sends RTCP Receiver Reports  

# D. Communication Model

  Three UDP channels are used:

    a. SIP Signaling → Ports 6767 / 6768
    b. RTP Media Stream → Ports 6776 / 6778
    c. RTCP Feedback → Ports 6777 / 6779

 The system uses sequence numbers and timestamps to ensure proper packet handling and synchronization.

# E. SIP Message Types
  Message Type  | Direction           | Description                              |
|---------------|---------------------|------------------------------------------|
| INVITE        | Caller -> Receiver  | Initiates Call                           |
| 180 Ringing	  |  Receiver -> Caller	| Indicates Incoming Call                  |
| 200 OK	      | Both	              | Confirms successful request (INVITE/BYE) |
| ACK           | Caller -> Receiver	| Finalizes Call Setup                     |
| BYE           | ANY -> ANY	        | Terminates Call                          |
| CANCEL	      | Caller -> Receiver	| Cancels call before answer               |
| 603 Decline	  | Receiver -> Caller	| Rejects Call                             |
| 486 Busy Here | Receiver -> Caller	| Indicates user is busy                   |

# F. Call Flow

  I. Call Establishment

    a. Caller sends INVITE
    b. Receiver responds 180 Ringing
    c. Receiver sends 200 OK
    d. Caller sends ACK
    e. Call Established

  II. Call Termination

    a. One side sends BYE
    b. Receiver replies 200 OK
    c. Call Ends

  III. Call Handling Cases

    a. Declined → 603 Decline
    b. Busy → 486 Busy Here
    c. Cancelled → CANCEL + 200 OK

# G. RTP Implementation
RTP is used for real-time audio transmission.
  
  # Features

    a. Custom RTP packet construction  
    b. Sequence number tracking  
    c. Timestamp-based synchronization  
    d. SSRC identification  
    e. Audio chunk transmission    

  # RTP Header Structure

    a. Version  
    b. Payload Type  
    c. Sequence Number  
    d. Timestamp  
    e. SSRC  

  # Payload
    Raw audio data (PCM format via PyAudio)

# H. RTCP Feedback System 
RTCP is used for feedbacking only.

  # Features
    a. Sender Reports (SR)
    b. Receiver Reports (RR)
    c. Packet loss monitoring
    d. Sequence tracking  

  # Feedback Includes
    a. Total packets sent
    b. Total bytes transmitted
    c. Packet loss count
    d. Highest sequence received
  
# I. Audio Handling 
    a. Uses PyAudio for live audio capture and playback

    b. Supports two modes:
      - VoIP Call (microphone input)
      - Stream Recorded Audio (WAV file)

    c. Uses winsound for system sounds:
      - Incoming call ringtone
      - Dial tone
      - Busy tone
      - End call sound  

# J. Running the Program 

  # Prerequisites
  ```bash
    pip install pyaudio
  ```

  # Caller
  ```bash
    python callme.py
  ```
    Role: Caller
    Mode: VoIP / Stream
    Enter Receiver IP

  # Receiver
  ```bash
    python callme.py
  ```
    Role: Receiver
 
# K. Error Handling & Edge Cases
    1. Invalid IP address → Call fails
    2. No response → Automatic CANCEL
    3. Busy receiver → 486 Busy Here
    4. Call declined → 603 Decline
    5. Packet loss → Detected via RTP sequence gaps
    6. Audio overflow → handled via PyAudio exception control

# L. Test Cases and Sample Outputs

  # Test Case 1 : Successful VoIP Call

          Caller Side:
            [SYSTEM] INVITE sent to 192.168.1.5
            [SYSTEM] 200 OK for INVITE received from 192.168.1.5
            [SYSTEM] ACK sent to 192.168.1.5
            [SYSTEM] Call established successfully
            [SYSTEM] VOIP Call Started
            - - Call Menu - - [X] End Call >>>

          Receiver Side:
            [SYSTEM] INVITE received from 192.168.1.4
            - - Incoming-Call -- [1] Accept Call [2] Reject Call >>> 1
            [SYSTEM] Sent 200 OK with SDP to caller
            [SYSTEM] Call established on both sides
            [SYSTEM] VOIP Call Started

  # Test Case 2: Call Declined (603 Decline)
  Setup: Caller dials Receiver, Receiver choosed to reject.

          Caller Side:
            [SYSTEM] INVITE sent to 192.168.1.5
            [SYSTEM] Your call is declined ...
              
          Receiver Side:
            [SYSTEM] INVITE received from 192.168.1.4
            - - Incoming-Call -- [1] Accept Call [2] Reject Call >>> 2
            [SYSTEM] Sent 603 Decline to caller

  # Test Case 3: Busy Receiver (486 Busy Here)
  Setup: Receiver is already in an active call, A second caller dials in.

          Second Caller Side:
            [SYSTEM] INVITE sent to 192.168.1.5
            [SYSTEM] Client is in another call ...
              
          Receiver Side:
            [SYSTEM] INVITE received from 192.168.1.6
            SIP/2.0 486 Busy Here -> send automatically

  # Test Case 4: No Answer/Timeout 
  Setup: Caller dials Receiver, Receiver does not answer within 12 seconds.

          Caller Side:
            [SYSTEM] Another client did not answer your call ...
            [SYSTEM] CANCEL sent to 192.168.1.5
            [SYSTEM] 200 OK for CANCEL received from 192.168.1.5
            [SYSTEM] Call terminated gracefully
            [SYSTEM] Thank you for using Call Me. Bye <3
              
          Receiver Side:
            - - Incoming-Call -- [1] Accept Call [2] Reject Call >>> 
            [SYSTEM] Cancel request received from 192.168.1.4
            [SYSTEM] 200 OK for CANCEL sent to 192.168.1.4
            [SYSTEM] Thank you for using Call Me. Bye <3

  # Test Case 5: Caller Cancels Mid-Ring
  Setup: Caller dials Receiver.Before Receiver answers, Caller types X to cancel 

          Caller Side:
            - - Call Menu - - [X] End Call >>> x
            [SYSTEM] Cancelling call ...
            [SYSTEM] 200 OK for CANCEL received from 192.168.1.5
            [SYSTEM] Call terminated gracefully
            [SYSTEM] Thank you for using Call Me. Bye <3
              
          Receiver Side:
            - - Incoming-Call -- [1] Accept Call [2] Reject Call >>> 
            [SYSTEM] Cancel request received from 192.168.1.4
            [SYSTEM] 200 OK for CANCEL sent to 192.168.1.4
            [SYSTEM] Thank you for using Call Me. Bye <3
              
  # Test Case 6: BYE/ Call Termination
  Setup: Both sides are in an active VoIP call. Caller ends the call by typing X

          Caller Side:
            [SYSTEM] VOIP Call Started
            - - Call Menu - - [X] End Call >>> x
            [SYSTEM] BYE sent to 192.168.1.5
            [SYSTEM] 200 OK for BYE received from 192.168.1.5
            [SYSTEM] Call terminated gracefully
            [SYSTEM] Thank you for using Call Me. Bye <3
              
          Receiver Side:
            [SYSTEM] VOIP Call Started
            - - Call Menu - - [X] End Call >>> 
            [SYSTEM] BYE received from 192.168.1.4
            [SYSTEM] 200 OK for BYE sent to 192.168.1.4
            [SYSTEM] Call terminated gracefully
            [SYSTEM] Thank you for using Call Me. Bye <3

  # Test Case 7: RTCP SR/RR Output
  Setup: Both sides are in an active VoIP call. RTCP reports are sent every 5 seconds

          Caller Side (Sender Report):
             ---------- [RTCP SR SENT] ----------
             [OUTBOUND] PACKET SENT      : 142
             [OUTBOUND] OCTETS COUNT     : 145408
             [INBOUND] PACKET LOSS       : 0
             [INBOUND] RECEIVED SEQUENCE : 139

             ---------- [RTCP RECEIVED] ----------
             Receiver Report from 192.168.1.5:
              Sender SSRC: 2847362910

                ++++++++++++ REPORT ++++++++++++
                  Reporting on SSRC: 2847362910
                  Packet LOSS: 0
                  Highest Seq Received : 141
                ++++++++++++++++++++++++++++++++
            ---------------------------------------
      
          Receiver Side:
              ---------- [RTCP RR SENT] ----------
              [INBOUND] PACKET LOSS       : 0
              [INBOUND] RECEIVED SEQUENCE : 141

             ---------- [RTCP RECEIVED] ----------
             Sender Report from 192.168.1.4:
              Sender SSRC: 2847362910
              Packets SENT: 142
              Octets SENT: 145408

                ++++++++++++ REPORT ++++++++++++
                  Reporting on SSRC: 3921047284
                  Packet LOSS: 0
                  Highest Seq Received : 139
                ++++++++++++++++++++++++++++++++
            ---------------------------------------

  # Test Case 8: Packet Loss Detection
  Setup: Both sides are in a VoIP call under a simulated lossy network condition. A gap in RTP sequence numbers is detected.

          Receiver Side:
            [SYSTEM - LOST DETECTION] Packet lost: 2, total lost: 2
            - - Call Menu - - [X] End Call >>> 
            [SYSTEM - LOST DETECTION] Packet lost: 1, total lost: 3
            - - Call Menu - - [X] End Call >>> 

          RTCP Report reflecting loss:
            ---------- [RTCP RR SENT] ----------
              [INBOUND] PACKET LOSS      : 3
              [INBOUND] RECEIVED SEQUENCE: 201
            ------------------------------------

  # Test Case 9: Stream Recorded Audio Mode
  Setup: Caller selects mode 2 (Stream Recored Audio). Receiver listens passively

        Caller Side: 
          - - Configuration - -
            [1] VoIP
            [2] Stream Recorded Audio
            Select mode >>> 2
            Enter the IP address you're calling >>> 192.168.1.5
            [SYSTEM] INVITE sent to 192.168.1.5
            [SYSTEM] 200 OK for INVITE received from 192.168.1.5
            [SYSTEM] ACK sent to 192.168.1.5
            [SYSTEM] VOIP Call Started
            - - - - - - - - - - [RTCP SR SENT] - - - - - - - - - -
            [OUTBOUND] PACKET SENT       : 78
            [OUTBOUND] OCTETS COUNT      : 319488
            - - - - - - - - - - - - - - - - - - - - - - - - - - -
            [SYSTEM] BYE sent to 192.168.1.5        ← auto-sent when WAV file ends
            [SYSTEM] Call terminated gracefully
            [SYSTEM] Thank you for using Call Me. Bye <3

          Receiver Side: 
            [SYSTEM] INVITE received from 192.168.1.4
            - - Incoming-Call -- [1] Accept Call [2] Reject Call >>> 1
            [SYSTEM] Sent 200 OK with SDP to caller
            [SYSTEM] ACK received from 192.168.1.4
            [SYSTEM] VOIP Call Started
            - - Call Menu - - [X] End Call >>>
            - - - - - - - - - - [RTCP RR SENT] - - - - - - - - - -
            [INBOUND]  PACKET LOSS       : 0
            [INBOUND]  RECEIVED SEQUENCE : 77
            - - - - - - - - - - - - - - - - - - - - - - - - - - -
            [SYSTEM] BYE received from 192.168.1.4
            [SYSTEM] 200 OK for BYE sent to 192.168.1.4
            [SYSTEM] Call terminated gracefully
            [SYSTEM] Thank you for using Call Me. Bye <3

# M. Files and Dependencies 

  1. callme.py	Main program
  2. audios/ → Sound effects (ringing, busy, etc.)
  # Dependencies:
      pyaudio
      socket
      threading
      winsound

# N. Limitations
    1. Single Active Call per Device — Each device can only handle one active caller and one active receiver at a time. If a second caller attempts to dial an already-busy receiver, the receiver automatically responds with 486 Busy Here and rejects the new call without interrupting the ongoing session.

    2. Windows Only — The program uses winsound for system sounds (ringtone, dial tone, busy tone, end call), which is a Windows-exclusive library. The program will not run on macOS or Linux without replacing the audio playback logic.

    3. Same Network Required — Both devices must be on the same local network. The program uses local IP addresses and fixed ports, so cross-network calls without port forwarding or VPN are not supported.

    4. Fixed Ports — All SIP, RTP, and RTCP ports are hardcoded. Running multiple instances of the program on the same machine will cause port binding conflicts.

    5. WAV File Dependency — Stream Recorded Audio mode requires a specific WAV file (audios/stream-audio-sample.wav) to be present. If the file is missing, the stream will fail.

    6. No Encryption — All audio and signaling data is transmitted in plaintext over UDP with no encryption or authentication.

