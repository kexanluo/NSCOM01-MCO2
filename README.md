# CallMe: Real-Time Audio Streaming over IP (SIP/RTP/RTCP)
A NSCOM01 Machine Project

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
    L. Files and Dependencies  

# A. Overview

  I. Description  
  
    CallMe is a UDP-based real-time communication system that simulates VoIP behavior using SIP, RTP, and RTCP protocols. It supports both live voice calls and recorded audio streaming while handling session control and network feedback.
       
  II. Features  

      a. SIP-based call signaling (INVITE, ACK, BYE, etc.)
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

# L. Files and Dependencies 

  1. callme.py	Main program
  2. audios/ → Sound effects (ringing, busy, etc.)
  # Dependencies:
      pyaudio
      socket
      threading
      winsound
