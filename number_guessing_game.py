import os
import re
import sys
import time
import random
import pyaudio
from google.cloud import speech
from dotenv import load_dotenv

# Load environment variables and set up Google Cloud credentials
load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "googleKey.json")

# Game state variables
game_active = False
target_number = None
num_guesses = 0

def clear_console():
    """Clear the console screen"""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

def extract_number(text):
    """Extract a number from the spoken text"""
    # Look for number words or digits
    number_words = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50',
        'sixty': '60', 'seventy': '70', 'eighty': '80', 'ninety': '90'
    }
    
    # Convert word numbers to digits
    for word, digit in number_words.items():
        text = text.replace(word, digit)
    
    # Find any numbers in the text
    numbers = re.findall(r'\d+', text)
    return int(numbers[0]) if numbers else None

def process_guess(guess):
    """Process the player's guess and provide feedback"""
    global num_guesses
    
    if not guess:
        return "I didn't catch that number. Please try again."
    
    num_guesses += 1
    
    if guess < target_number:
        return f"{guess} is too low! Try a higher number."
    elif guess > target_number:
        return f"{guess} is too high! Try a lower number."
    else:
        return f"Congratulations! You found the number {target_number} in {num_guesses} guesses! Say 'Play Number' to start a new game."

def stream_speech_to_text():
    """Stream speech input and process it for the game"""
    global game_active, target_number, num_guesses
    
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )
    
    # Create an audio generator function
    def audio_generator():
        audio_interface = pyaudio.PyAudio()
        audio_stream = audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
            stream_callback=None
        )
        
        time.sleep(0.5)  # Give the microphone a moment to initialize
        
        print("Listening... Say 'Play Number' to start!")
        
        try:
            while True:
                data = audio_stream.read(4096, exception_on_overflow=False)
                yield data
        except KeyboardInterrupt:
            pass
        finally:
            audio_stream.stop_stream()
            audio_stream.close()
            audio_interface.terminate()
    
    # Create audio generator instance and requests
    audio_generator_instance = audio_generator()
    requests = (speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator_instance)
    
    # Start streaming recognition
    responses = client.streaming_recognize(streaming_config, requests)

    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.is_final:
            continue

        transcript = result.alternatives[0].transcript.lower()
        
        # Check for game start command
        if "play number" in transcript and not game_active:
            game_active = True
            target_number = random.randint(1, 100)
            num_guesses = 0
            print("\nGame started! I'm thinking of a number between 1 and 100.")
            print("Try to guess it!")
            continue
        
        # Process guesses when game is active
        if game_active:
            guess = extract_number(transcript)
            feedback = process_guess(guess)
            print(f"\n{feedback}")
            
            # Reset game if won
            if guess == target_number:
                game_active = False

def main():
    clear_console()
    print("Welcome to the Voice Number Guessing Game!")
    print("Say 'Play Number' to start a new game.")
    print("Then guess numbers between 1 and 100.")
    print("I'll tell you if your guess is too high or too low.")
    print("\nListening...")
    
    try:
        stream_speech_to_text()
    except KeyboardInterrupt:
        print("\nGame ended. Thanks for playing!")

if __name__ == "__main__":
    main()
