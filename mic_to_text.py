# import os
# import tempfile
# import sounddevice as sd
# import scipy.io.wavfile as wav
# from openai import OpenAI
# from dotenv import load_dotenv

# load_dotenv()

# # Initialize the OpenAI client with your API key
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# def record_audio(duration=5, samplerate=16000):
#     print(f"Recording for {duration} seconds...")
#     recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
#     sd.wait()
    
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
#         wav.write(f.name, samplerate, recording)
#         return f.name

# def transcribe_audio(file_path):
#     print("Transcribing with Whisper API...")
#     with open(file_path, "rb") as audio_file:
#         response = client.audio.transcriptions.create(
#             model="whisper-1",
#             file=audio_file
#         )
#     return response.text

# def translate_text(text, target_lang="chinese"):
#     print(f"Translating to {target_lang}...")
#     response = client.chat.completions.create(
#         model="gpt-4",  # or "gpt-3.5-turbo"
#         messages=[
#             {"role": "system", "content": f"You are a translator. Translate the user's text to {target_lang}."},
#             {"role": "user", "content": text}
#         ]
#     )
#     return response.choices[0].message.content.strip()

# if __name__ == "__main__":
#     audio_file = record_audio(duration=5)
#     original_text = transcribe_audio(audio_file)
#     print("Original:", original_text)
    
#     translated_text = translate_text(original_text, target_lang="chinese")
#     print("Translated:", translated_text)
    
#     os.remove(audio_file)

import os
import queue
import threading
import time
import numpy as np
import sounddevice as sd
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize the OpenAI client with your API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Audio parameters
SAMPLE_RATE = 16000  # Hz
CHUNK_DURATION = 3  # seconds
SILENCE_THRESHOLD = 500  # Adjust based on your microphone and environment
SILENCE_DURATION = 1.0  # seconds of silence to consider a pause

# Queue for audio chunks
audio_queue = queue.Queue()
# Flag to control recording state
recording = True

def is_silent(audio_data, threshold):
    """Check if audio chunk is silent based on amplitude threshold"""
    return np.max(np.abs(audio_data)) < threshold

def audio_callback(indata, frames, time, status):
    """Callback for sounddevice stream to collect audio chunks"""
    if status:
        print(f"Error in audio stream: {status}")
    # Convert to int16 for consistent format
    audio_chunk = indata.copy()
    audio_queue.put(audio_chunk)

def process_audio():
    """Process audio chunks from the queue, transcribe and translate"""
    global recording
    
    accumulated_audio = np.array([], dtype=np.float32).reshape(0, 1)
    silence_counter = 0
    
    while recording:
        try:
            # Get audio chunk from queue
            audio_chunk = audio_queue.get(timeout=1)
            
            # Check for silence
            if is_silent(audio_chunk, SILENCE_THRESHOLD):
                silence_counter += len(audio_chunk) / SAMPLE_RATE
                # If enough silence and we have accumulated audio, process it
                if silence_counter >= SILENCE_DURATION and len(accumulated_audio) > 0:
                    # Process accumulated audio
                    process_chunk(accumulated_audio)
                    # Reset accumulated audio
                    accumulated_audio = np.array([], dtype=np.float32).reshape(0, 1)
                    silence_counter = 0
            else:
                # Reset silence counter if sound detected
                silence_counter = 0
            
            # Accumulate audio
            accumulated_audio = np.vstack((accumulated_audio, audio_chunk))
            
            # If accumulated audio exceeds chunk duration, process it
            if len(accumulated_audio) / SAMPLE_RATE >= CHUNK_DURATION:
                process_chunk(accumulated_audio)
                accumulated_audio = np.array([], dtype=np.float32).reshape(0, 1)
                
        except queue.Empty:
            pass  # No audio to process
        except Exception as e:
            print(f"Error processing audio: {e}")

def process_chunk(audio_data):
    """Transcribe and translate an audio chunk"""
    try:
        # Create a temporary file for the audio data
        import tempfile
        import soundfile as sf
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            filename = temp_file.name
            
        # Save audio as WAV file
        sf.write(filename, audio_data, SAMPLE_RATE)
        
        # Transcribe the audio
        transcription = transcribe_audio(filename)
        if transcription.strip():
            print(f"Original: {transcription}")
            
            # Translate the transcription
            translation = translate_text(transcription)
            print(f"Translated: {translation}")
            print("-" * 50)
        
        # Clean up the temporary file
        os.remove(filename)
        
    except Exception as e:
        print(f"Error in processing chunk: {e}")

def transcribe_audio(file_path):
    """Transcribe audio file using OpenAI Whisper API"""
    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return response.text

def translate_text(text, target_lang="French"):
    """Translate text using OpenAI API"""
    if not text.strip():
        return ""
        
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Faster than GPT-4 for real-time usage
        messages=[
            {"role": "system", "content": f"You are a translator. Translate the user's text to {target_lang}. Be concise."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

def main():
    global recording
    
    try:
        # Start processing thread
        process_thread = threading.Thread(target=process_audio)
        process_thread.daemon = True
        process_thread.start()
        
        # Start audio stream
        with sd.InputStream(callback=audio_callback, channels=1, samplerate=SAMPLE_RATE):
            print("Real-time translation started. Speak now...")
            print("Press Ctrl+C to stop")
            
            # Keep main thread alive
            while True:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\nStopping translation...")
        recording = False
        process_thread.join(timeout=2)
        print("Translation stopped.")
    except Exception as e:
        print(f"Error: {e}")
        recording = False

if __name__ == "__main__":
    main()