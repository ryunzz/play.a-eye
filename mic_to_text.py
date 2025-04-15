import speech_recognition as sr
import time
from dotenv import load_dotenv
import deepl
import os

load_dotenv()

API_KEY = os.getenv("DEEPL_API_KEY")
deepl_client = deepl.DeepLClient(API_KEY)

def recognition_callback(recognizer, audio):
    print(">>> Audio detected! Recognizing...")
    try:
        #recognize speech using Google Speech Recognition
        text = recognizer.recognize_google(audio)
        result = deepl_client.translate_text(text, target_lang="ES")
        print(f"Transcription: {text}")
        print(f"Translation: {result}")
    except sr.UnknownValueError:
        #API recognized speech, but couldn't match it to text
        print("Google Speech Recognition could not understand audio")
    except sr.RequestError as e:
        #API unreachable or unresponsive
        print(f"Could not request results from Google Speech Recognition service; {e}")
    except Exception as e:
        #any other unexpected error
        print(f"Unexpected error during recognition: {e}")
    finally:
        #ready for input in background thread
        print(">>> Listening in background...") 

r = sr.Recognizer()
m = sr.Microphone() #create mic instance outside the main loop/try block
stop_listening = None #this stops the program from listening

try:
    # we open the mic at the start
    print("Calibrating for ambient noise (1s)... Please wait.")
    with m as source:
        r.adjust_for_ambient_noise(source, duration=1)
    print("Calibration complete.")


    #start listening to audio from the microphone
    print("\n>>> Listening in background (Press Ctrl+C to stop)...")
    stop_listening = r.listen_in_background(m, recognition_callback, phrase_time_limit=10)

    #keep thread running if still listening
    while True:
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nCtrl+C detected. Stopping background listener...")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if stop_listening:
        print("Shutting down listener thread...")
        stop_listening(wait_for_stop=False)
        print("Listener thread stopped.")
    print("Program finished.")