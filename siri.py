import os
import re
import time
import sys
import serial
import threading
from google.cloud import speech
from dotenv import load_dotenv
import deepl
from openai import OpenAI

# Load environment variables
load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "googleKey.json")
deepl_client = deepl.Translator(os.getenv("DEEPL_API_KEY"))

# Arduino connection setup
arduino_port = None  # Will be set during setup
arduino_connected = False

# Language selection
target_language = input("Enter target language (e.g., 'ES' for Spanish, 'FR' for French): ").strip().upper()
streaming_active = True

def setup_arduino():
    """Connect to Arduino Nano"""
    global arduino_port, arduino_connected
    
    port = "/dev/cu.usbserial-10"
    
    # Try to connect to any available port
    try:
        print(f"Trying to connect to Arduino on {port}...")
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
            
        # Test if it's really an Arduino by sending a test command
        ser.write(b"TEST\n")
        time.sleep(0.5)
        response = ser.readline().decode('utf-8', errors='ignore').strip()
            
        if response == "Arduino Nano Ready" or "Arduino" in response:
            arduino_port = ser
            arduino_connected = True
            print(f"✅ Arduino connected on {port}")
            return True
        else:
            print(f"Device on {port} responded with: {response}")
            ser.close()
    except Exception as e:
        print(f"Failed to connect on {port}: {e}")
    
    print("❌ Could not connect to Arduino. Make sure it's plugged in and the correct sketch is loaded.")
    return False

def send_to_arduino(message):
    """Send a message to the Arduino"""
    global arduino_port, arduino_connected
    
    if not arduino_connected or not arduino_port:
        return False
    
    try:
        # Format message for Arduino (keep it short)
        formatted_message = f"{message[:50]}\n"  # Limit length and add newline
        arduino_port.write(formatted_message.encode())
        return True
    except Exception as e:
        print(f"Arduino communication error: {e}")
        arduino_connected = False
        return False

def arduino_reader_thread():
    """Thread to read responses from Arduino"""
    global arduino_port, arduino_connected
    
    while arduino_connected and streaming_active:
        try:
            if arduino_port.in_waiting:
                response = arduino_port.readline().decode('utf-8', errors='ignore').strip()
                if response:
                    print(f"📟 Arduino: {response}")
        except Exception as e:
            print(f"Error reading from Arduino: {e}")
            arduino_connected = False
            break
        time.sleep(0.1)

def clear_console():
    """Clear the console screen"""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

def translate_text(text, target_language):
    """Use DeepL API to translate text to target language"""
    if not text.strip():
        return ""

    try:
        result = deepl_client.translate_text(text, target_lang=target_language)
        return result.text
    except Exception as e:
        print(f"Translation error: {e}")
        return "(Translation error)"

llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
def ask_openai_question(question):
    """Ask an OpenAI LLM question"""
    if not question or question.isspace():
        return "(Empty question detected)"
        
    try:
        response = llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
            max_tokens=150
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return f"(OpenAI Error: {str(e)})"

def stream_speech_to_text():
    """Stream audio to Google Cloud Speech-to-Text API with Arduino integration"""
    client = speech.SpeechClient()

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US", 
        enable_automatic_punctuation=True,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True 
    )

    def audio_generator():
        import pyaudio

        audio_interface = pyaudio.PyAudio()
        audio_stream = audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
            stream_callback=None
        )

        time.sleep(0.5)
        print("Stream active. Start speaking...")

        while streaming_active:
            data = audio_stream.read(4096, exception_on_overflow=False)
            yield data

        audio_stream.stop_stream()
        audio_stream.close()
        audio_interface.terminate()

    audio_generator_instance = audio_generator()
    requests = (speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator_instance)

    responses = client.streaming_recognize(streaming_config, requests)

    last_transcript = ""
    last_update_time = time.time()
    update_cooldown = 0.3
    openai_question = ""

    try:
        clear_console()
        print(">>> Listening in real-time (Press Ctrl+C to stop)...")
        print("Speak now...")

        for response in responses:
            if not response.results:
                continue

            result = response.results[0]
            transcript = result.alternatives[0].transcript

            current_time = time.time()
            if (transcript != last_transcript and 
                (result.is_final or current_time - last_update_time >= update_cooldown)):

                clear_console()
                print(">>> Listening in real-time (Press Ctrl+C to stop)...")
                print(f"Transcription: {transcript}")
                
                # Send transcript to Arduino
                if result.is_final:
                    send_to_arduino(f"T:{transcript[:50]}")  # Send with 'T:' prefix for transcript
                
                trigger_pattern = r'^\s*hey\s*,?\s*sentient\b'
                if re.search(trigger_pattern, transcript, re.IGNORECASE):
                    if result.is_final:
                        openai_question = re.sub(trigger_pattern, '', transcript, flags=re.IGNORECASE).strip()[2:]
                        
                        if openai_question:
                            openai_response = ask_openai_question(openai_question)
                            print("\n>>> OpenAI LLM Response:")
                            print(f"Question: {openai_question}")
                            print(f"Answer: {openai_response}")
                            
                            # Send OpenAI response to Arduino
                            send_to_arduino(f"A:{openai_response[:50]}")  # Send with 'A:' prefix for AI response
                        else:
                            print("\n>>> Waiting for question after 'Hey Sentient'...")
                else:
                    translated_text = translate_text(transcript, target_language)
                    print(f"Translation: {translated_text}")
                    
                    # Send translation to Arduino if it's a final result
                    if result.is_final:
                        send_to_arduino(f"R:{translated_text[:50]}")  # Send with 'R:' prefix for translated text

                last_transcript = transcript
                last_update_time = current_time

    except KeyboardInterrupt:
        print("\nStream closed by user.")
    except Exception as e:
        print(f"Error in streaming: {e}")
        import traceback
        traceback.print_exc()  
    finally:
        global streaming_active
        streaming_active = False

def main():
    global arduino_connected
    
    print("Google Cloud Speech-to-Text & Translation with Arduino Integration")
    print("-------------------------------------------------------------")
    print(f"Source language: English | Target language: {target_language}")
    
    # Setup Arduino connection
    arduino_connected = setup_arduino()
    
    if arduino_connected:
        # Start Arduino reader thread
        arduino_thread = threading.Thread(target=arduino_reader_thread)
        arduino_thread.daemon = True
        arduino_thread.start()
        
        # Send initial message
        send_to_arduino(f"LANG:{target_language}")
    
    print("Starting in 3 seconds...")
    time.sleep(3)

    try:
        clear_console()
        stream_speech_to_text()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc() 
    finally:
        if arduino_connected and arduino_port:
            send_to_arduino("QUIT")
            arduino_port.close()
        print("Program finished.")

if __name__ == "__main__":
    main()