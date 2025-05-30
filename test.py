import os
import re
import time
import sys
import random
from google.cloud import speech
from dotenv import load_dotenv
import deepl
from openai import OpenAI

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "googleKey.json")
deepl_client = deepl.Translator(os.getenv("DEEPL_API_KEY"))

#language we want to translate to
target_language = input("Enter target language (e.g., 'ES' for Spanish, 'FR' for French): ").strip().upper()
streaming_active = True

# Conversation state management
conversation_active = False
conversation_history = []

# Wordle game state management
wordle_active = False
wordle_word = ""
wordle_guessed = []
wordle_strikes = 0
wordle_max_strikes = 6
wordle_display = []

# Rock Paper Scissors game state management
rps_active = False
rps_user_score = 0
rps_computer_score = 0

# Number guessing game state management
number_game_active = False
target_number = None
num_guesses = 0

campus_places = [
    "GEISEL LIBRARY",
    "WONG AVERY LIBRARY", 
    "REVELLE COLLEGE",
    "MUIR COLLEGE",
    "WARREN COLLEGE",
    "MARSHALL COLLEGE",
    "EIGHTH COLLEGE",
    "SEVENTH COLLEGE",
    "SIXTH COLLEGE",
    "ERC",
    "PRICE CENTER",
    "PEPPER CANYON",
    "RIMAC",
    "SUN GOD LAWN",
    "SCRIPPS INSTITUTION",
    "BIRCH AQUARIUM",
]


def clear_console():
    """Clear the console screen"""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

#use DeepL API to translate text to target language
def translate_text(text, target_language):
    if not text.strip():
        return ""

    try:
        result = deepl_client.translate_text(text, target_lang=target_language)
        return result.text
    except Exception as e:
        print(f"Translation error: {e}")
        return "(Translation error)"

#handle conversation with OpenAI LLM
def handle_conversation(user_input):
    global conversation_active, conversation_history
    
    if not user_input or user_input.isspace():
        return "(Empty input detected)"
    
    # Check for conversation end
    if re.search(r'\s*(bye\s*,?\s*sentient|stop)\b', user_input, re.IGNORECASE):
        conversation_active = False
        conversation_history = []
        return "Goodbye! It was nice talking to you."
        
    try:
        # Add user's message to conversation history
        conversation_history.append({"role": "user", "content": user_input})
        
        # Prepare messages with conversation history
        messages = [
            {"role": "system", "content": "You are a helpful and friendly AI assistant named Sentient. Engage in natural conversation while being helpful and concise."}
        ] + conversation_history
        
        response = llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        answer = response.choices[0].message.content.strip()
        
        # Add assistant's response to conversation history
        conversation_history.append({"role": "assistant", "content": answer})
        
        # Keep conversation history manageable (last 10 exchanges)
        if len(conversation_history) > 20:
            conversation_history = conversation_history[-20:]
            
        return answer
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return f"(OpenAI Error: {str(e)})"

#ask an OpenAI LLM question if transcript starts with "Hey Sentient"
llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
def ask_openai_question(question):
    
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

#attach microphone input to the Google Cloud Speech-to-Text API
def stream_speech_to_text():
    global wordle_active, conversation_active, rps_active, number_game_active
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
    current_input = ""

    try:
        clear_console()
        print(">>> Listening in real-time (Press Ctrl+C to stop)...")
        print("Speak now...")
        if conversation_active:
            print(">>> In conversation with Sentient (say 'bye, sentient' or 'stop' to end)")
        elif wordle_active:
            print(">>> Playing Wordle! Say letters to guess (say 'stop' to quit)")
            print(get_wordle_status())
        elif rps_active:
            print(">>> Playing Rock Paper Scissors! Say 'rock', 'paper', or 'scissors' (say 'stop' to quit)")
            print(get_rps_status())
        elif number_game_active:
            print(">>> Playing Number Guessing Game! Say a number between 1-100 (say 'stop' to quit)")
            print(get_number_game_status())
        else:
            print(">>> Say 'hey, sentient' to chat, 'play word' for Wordle, 'play rock' for RPS, or 'play number' for Number Game")

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
                if conversation_active:
                    print(">>> In conversation with Sentient (say 'bye, sentient' or 'stop' to end)")
                elif wordle_active:
                    print(">>> Playing Wordle! Say letters to guess (say 'stop' to quit)")
                    print(get_wordle_status())
                elif rps_active:
                    print(">>> Playing Rock Paper Scissors! Say 'rock', 'paper', or 'scissors' (say 'stop' to quit)")
                    print(get_rps_status())
                elif number_game_active:
                    print(">>> Playing Number Guessing Game! Say a number between 1-100 (say 'stop' to quit)")
                    print(get_number_game_status())
                else:
                    print(">>> Say 'hey, sentient' to chat, 'play word' for Wordle, 'play rock' for RPS, or 'play number' for Number Game")
                print(f"Transcription: {transcript}")

                # Only translate and show translation if not in game or conversation
                if not conversation_active and not wordle_active and not rps_active and not number_game_active:
                    translated_text = translate_text(transcript, target_language)
                    print(f"Translation: {translated_text}")

                # Handle different modes when transcript is final OR looks complete (ends with punctuation)
                transcript_looks_complete = transcript.strip().endswith(('.', '!', '?'))
                if result.is_final or transcript_looks_complete:
                    if wordle_active:
                        # Handle Wordle game
                        # Clean transcript for better matching
                        cleaned_transcript = re.sub(r'[^\w\s]', '', transcript).strip()
                        
                        # Check if user wants to quit wordle
                        if re.search(r'\s*(quit\s*game|stop)\b', cleaned_transcript, re.IGNORECASE):
                            wordle_active = False
                            print("\n>>> Wordle game ended. Say 'play word' to start a new game.")
                        else:
                            # Extract single letter from transcript
                            # Remove punctuation and extra spaces, then look for single letters
                            letters = re.findall(r'\b[A-Za-z]\b', cleaned_transcript)
                            
                            # Special handling for common speech recognition issues
                            if not letters:
                                # Handle cases like "I," -> "I"
                                if cleaned_transcript.upper() in ['I', 'A', 'O', 'U', 'E']:
                                    letters = [cleaned_transcript.upper()]
                                # Handle common speech recognition substitutions
                                elif cleaned_transcript.lower() in ['oh', 'owe']:
                                    letters = ['O']
                                elif cleaned_transcript.lower() in ['ay', 'eh']:
                                    letters = ['A']
                                elif cleaned_transcript.lower() in ['bee']:
                                    letters = ['B']
                                elif cleaned_transcript.lower() in ['see', 'sea']:
                                    letters = ['C']
                                elif cleaned_transcript.lower() in ['dee']:
                                    letters = ['D']
                                elif cleaned_transcript.lower() in ['gee']:
                                    letters = ['G']
                                elif cleaned_transcript.lower() in ['jay']:
                                    letters = ['J']
                                elif cleaned_transcript.lower() in ['kay']:
                                    letters = ['K']
                                elif cleaned_transcript.lower() in ['pee']:
                                    letters = ['P']
                                elif cleaned_transcript.lower() in ['cue', 'queue', 'que']:
                                    letters = ['Q']
                                elif cleaned_transcript.lower() in ['are']:
                                    letters = ['R']
                                elif cleaned_transcript.lower() in ['tea', 'tee']:
                                    letters = ['T']
                                elif cleaned_transcript.lower() in ['you', 'yu']:
                                    letters = ['U']
                                elif cleaned_transcript.lower() in ['vee']:
                                    letters = ['V']
                                elif cleaned_transcript.lower() in ['why']:
                                    letters = ['Y']
                                elif cleaned_transcript.lower() in ['zee']:
                                    letters = ['Z']
                                # Handle single letters with trailing punctuation in original transcript
                                elif len(transcript.strip()) <= 3:
                                    letter_match = re.search(r'([A-Za-z])', transcript)
                                    if letter_match:
                                        letters = [letter_match.group(1)]
                            
                            if letters:
                                print(f">>> Extracted letter: '{letters[0]}'")
                                guess_result = handle_wordle_guess(letters[0])
                                print(f">>> {guess_result}")
                                if not wordle_active:
                                    print("\n>>> Game ended. Say 'play word' to start a new game.")
                            else:
                                print(">>> Please say a single letter to guess!")
                                
                    elif rps_active:
                        # Handle Rock Paper Scissors game
                        # Clean transcript for better matching
                        cleaned_transcript = re.sub(r'[^\w\s]', '', transcript).strip()
                        
                        # Check if user wants to quit RPS
                        if re.search(r'\s*stop\b', cleaned_transcript, re.IGNORECASE):
                            rps_active = False
                            print("\n>>> Rock Paper Scissors game ended. Say 'play rock' to start a new game.")
                        else:
                            # Check for RPS moves
                            if re.search(r'\brock\b', cleaned_transcript, re.IGNORECASE):
                                move_result = handle_rps_move("rock")
                                print(f">>> {move_result}")
                            elif re.search(r'\bpaper\b', cleaned_transcript, re.IGNORECASE):
                                move_result = handle_rps_move("paper")
                                print(f">>> {move_result}")
                            elif re.search(r'\bscissors\b', cleaned_transcript, re.IGNORECASE):
                                move_result = handle_rps_move("scissors")
                                print(f">>> {move_result}")
                            else:
                                print(">>> Please say 'rock', 'paper', or 'scissors'!")
                                
                    elif number_game_active:
                        # Handle Number Guessing game
                        # Clean transcript for better matching
                        cleaned_transcript = re.sub(r'[^\w\s]', '', transcript).strip()
                        
                        # Check if user wants to quit number game
                        if re.search(r'\s*stop\b', cleaned_transcript, re.IGNORECASE):
                            number_game_active = False
                            print("\n>>> Number guessing game ended. Say 'play number' to start a new game.")
                        else:
                            # Process the guess
                            guess_result = handle_number_guess(transcript)
                            print(f">>> {guess_result}")
                                
                    elif not conversation_active:
                        # Clean transcript for better matching
                        cleaned_transcript = re.sub(r'[^\w\s]', '', transcript).strip()
                        
                        # Check for wordle start
                        if re.search(r'\bplay\s+word\b', cleaned_transcript, re.IGNORECASE):
                            start_wordle_game()
                            
                        # Check for RPS start
                        elif re.search(r'\bplay\s+rock\b', cleaned_transcript, re.IGNORECASE):
                            start_rps_game()
                            
                        # Check for Number Game start
                        elif re.search(r'\bplay\s+number\b', cleaned_transcript, re.IGNORECASE):
                            start_number_game()
                            
                        # Check for conversation start
                        elif re.search(r'\s*hey\s*,?\s*sentient\b.?\s*', cleaned_transcript, re.IGNORECASE):
                            conversation_active = True
                            print("\n>>> Starting conversation with Sentient...")
                            response = handle_conversation("Hello!")
                            print(f"Sentient: {response}")
                    else:
                        # Continue conversation
                        response = handle_conversation(transcript)
                        print(f"Sentient: {response}")
                      
                        # Check if conversation just ended
                        if not conversation_active:
                            print("\n>>> Conversation ended. Say 'Hey Sentient' to chat, 'play word' for Wordle, 'play rock' for RPS, or 'play number' for Number Game.")

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

def start_wordle_game():
    """Start a new Wordle game with a random campus place"""
    global wordle_active, wordle_word, wordle_guessed, wordle_strikes, wordle_display
    
    wordle_active = True
    wordle_word = random.choice(campus_places).upper()
    wordle_guessed = []
    wordle_strikes = 0
    wordle_display = ['_' if c.isalpha() else c for c in wordle_word]
    
    print(f"\n>>> WORDLE GAME STARTED! <<<")
    print(f"Guess the campus location: {' '.join(wordle_display)}")
    print(f"Strikes: {wordle_strikes}/{wordle_max_strikes}")
    print("Say letters to guess!")

def handle_wordle_guess(letter):
    """Handle a letter guess in Wordle game"""
    global wordle_active, wordle_strikes, wordle_display
    
    if not letter or len(letter) != 1 or not letter.isalpha():
        return "Please say a single letter!"
    
    letter = letter.upper()
    
    if letter in wordle_guessed:
        return f"You already guessed '{letter}'. Try another letter!"
    
    wordle_guessed.append(letter)
    
    if letter in wordle_word:
        # Update display with correct letter
        for i, c in enumerate(wordle_word):
            if c == letter:
                wordle_display[i] = letter
        
        # Check if word is complete
        if '_' not in wordle_display:
            wordle_active = False
            return f"🎉 CONGRATULATIONS! You guessed it: {wordle_word}"
        else:
            return f"Good guess! {' '.join(wordle_display)}"
    else:
        wordle_strikes += 1
        if wordle_strikes >= wordle_max_strikes:
            wordle_active = False
            return f"💀 Game Over! The word was: {wordle_word}"
        else:
            return f"Strike {wordle_strikes}/{wordle_max_strikes}! Letter '{letter}' not found. {' '.join(wordle_display)}"

def get_wordle_status():
    """Get current Wordle game status"""
    if not wordle_active:
        return ""
    return f"Word: {' '.join(wordle_display)} | Strikes: {wordle_strikes}/{wordle_max_strikes} | Guessed: {', '.join(wordle_guessed)}"

def start_rps_game():
    """Start a new Rock Paper Scissors game"""
    global rps_active, rps_user_score, rps_computer_score
    
    rps_active = True
    rps_user_score = 0
    rps_computer_score = 0
    
    print(f"\n>>> ROCK PAPER SCISSORS STARTED! <<<")
    print(f"Score - You: {rps_user_score} | Computer: {rps_computer_score}")
    print("Say 'rock', 'paper', or 'scissors' to play!")

def handle_rps_move(move):
    """Handle a rock paper scissors move"""
    global rps_active, rps_user_score, rps_computer_score
    
    if not move:
        return "Please say 'rock', 'paper', or 'scissors'!"
    
    move = move.lower().strip()
    options = ["rock", "paper", "scissors"]
    
    if move not in options:
        return "Invalid choice. Please say 'rock', 'paper', or 'scissors'."
    
    computer_choice = random.choice(options)
    result_msg = f"You chose: {move} | Computer chose: {computer_choice}\n"
    
    if move == computer_choice:
        result_msg += "It's a tie!"
    elif (move == "rock" and computer_choice == "scissors") or \
         (move == "paper" and computer_choice == "rock") or \
         (move == "scissors" and computer_choice == "paper"):
        rps_user_score += 1
        result_msg += "You win this round!"
    else:
        rps_computer_score += 1
        result_msg += "Computer wins this round!"
    
    result_msg += f"\nScore - You: {rps_user_score} | Computer: {rps_computer_score}"
    
    # Check for game end (first to 3 wins)
    if rps_user_score >= 3:
        rps_active = False
        result_msg += "\n🎉 YOU WIN THE GAME! Say 'play rock' to play again."
    elif rps_computer_score >= 3:
        rps_active = False
        result_msg += "\n💀 COMPUTER WINS THE GAME! Say 'play rock' to play again."
    else:
        result_msg += "\nSay your next move!"
    
    return result_msg

def get_rps_status():
    """Get current RPS game status"""
    if not rps_active:
        return ""
    return f"RPS Score - You: {rps_user_score} | Computer: {rps_computer_score}"

def extract_number(text):
    """Extract a number from the spoken text"""
    # Look for number words or digits
    number_words = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14', 'fifteen': '15',
        'sixteen': '16', 'seventeen': '17', 'eighteen': '18', 'nineteen': '19',
        'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50',
        'sixty': '60', 'seventy': '70', 'eighty': '80', 'ninety': '90'
    }
    
    # Convert word numbers to digits
    text_lower = text.lower()
    for word, digit in number_words.items():
        text_lower = text_lower.replace(word, digit)
    
    # Find any numbers in the text
    numbers = re.findall(r'\d+', text_lower)
    if numbers:
        return int(numbers[0])
    return None

def start_number_game():
    """Start a new number guessing game"""
    global number_game_active, target_number, num_guesses
    
    number_game_active = True
    target_number = random.randint(1, 100)
    num_guesses = 0
    
    print(f"\n>>> NUMBER GUESSING GAME STARTED! <<<")
    print(f"I'm thinking of a number between 1 and 100.")
    print("Say a number to make your guess!")

def handle_number_guess(guess_text):
    """Process the player's guess and provide feedback"""
    global num_guesses, number_game_active
    
    guess = extract_number(guess_text)
    
    if not guess:
        return "I didn't catch a number. Please say a number between 1 and 100."
    
    if guess < 1 or guess > 100:
        return "Please guess a number between 1 and 100."
    
    num_guesses += 1
    
    if guess < target_number:
        return f"{guess} is too low! Try a higher number. (Guess #{num_guesses})"
    elif guess > target_number:
        return f"{guess} is too high! Try a lower number. (Guess #{num_guesses})"
    else:
        number_game_active = False
        return f"🎉 Congratulations! You found the number {target_number} in {num_guesses} guesses! Say 'play number' to start a new game."

def get_number_game_status():
    """Get current number game status"""
    if not number_game_active:
        return ""
    return f"Number Game - Guesses: {num_guesses} | Range: 1-100"

def main():
    print("Google Cloud Speech-to-Text & Translation - Real-time Translator")
    print("-------------------------------------------------------------")
    print(f"Source language: English | Target language: {target_language}")
    print("Make sure your Google Cloud credentials are properly set up.")
    print("Starting in 3 seconds...")
    time.sleep(3)

    try:
        clear_console()
        stream_speech_to_text()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        print(f"Error details: {str(e)}")
        import traceback
        traceback.print_exc() 
    finally:
        print("Program finished.")

if __name__ == "__main__":
    main()