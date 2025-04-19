import serial
import time
import sys
import re
import threading

# Serial port configuration
PORT = '/dev/tty.HC-05' # Update this to your HC-05 serial port
BAUD_RATE = 9600
MAX_RETRY = 5

# Setup serial connection to Arduino via HC-05
def setup_bluetooth():
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {PORT} at {BAUD_RATE} baud")
        time.sleep(2)  # Give the connection time to establish
        return ser
    except serial.SerialException as e:
        print(f"Failed to connect to Bluetooth: {e}")
        return None

# Send text to Arduino
def send_to_arduino(ser, text):
    if ser is None or not ser.is_open:
        print("Serial connection not available")
        return False
    
    try:
        # Clean text and ensure it fits on the OLED
        cleaned_text = re.sub(r'\s+', ' ', text).strip()
        
        # Send the text followed by a newline (our message terminator)
        ser.write((cleaned_text + '\n').encode('utf-8'))
        print(f"Sent to Arduino: {cleaned_text}")
        return True
    except Exception as e:
        print(f"Error sending data: {e}")
        return False

# Monitor console output from mic_to_text.py
def monitor_output():
    ser = setup_bluetooth()
    if not ser:
        print("Failed to establish Bluetooth connection. Exiting.")
        return
    
    print("Bluetooth connection established. Monitoring for translations...")
    print("Waiting for mic_to_text.py output...")
    
    try:
        while True:
            line = input()  # Read line from stdin
            
            # Look for translations in the output
            if line.startswith("Translation:"):
                translation = line[12:].strip()  # Remove the "Translation: " part
                if translation:
                    send_to_arduino(ser, translation)
                    
            # Also capture Sentient's responses
            elif line.startswith("Sentient:"):
                response = line[9:].strip()  # Remove the "Sentient: " part
                if response:
                    send_to_arduino(ser, "AI: " + response)
    
    except KeyboardInterrupt:
        print("Monitoring stopped by user")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Bluetooth connection closed")

if __name__ == "__main__":
    print("Starting Bluetooth bridge for mic_to_text.py")
    monitor_output() 