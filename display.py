import os
import re
import time
import sys
import serial
import random
from google.cloud import speech
from dotenv import load_dotenv
import deepl

# ─── Configuration ─────────────────────────────────────────────────────────────
ARDUINO_PORT = "COM6"#"/dev/cu.usbserial-10"#
ARDUINO_BAUD = 9600
ACK_TIMEOUT = 1.0    # seconds to wait for an ACK
ACK_RETRIES = 3

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "googleKey.json")
deepl_client = deepl.Translator(os.getenv("DEEPL_API_KEY"))

target_language = input("Enter target language (e.g., 'ES' for Spanish, 'FR' for French): ").strip().upper()

streaming_active = True

# Game state management
wordle_active = False
wordle_word = ""
wordle_guessed = []
wordle_strikes = 0
wordle_max_strikes = 6
wordle_display = []

rps_active = False
rps_user_score = 0
rps_computer_score = 0

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

# ─── Serial Helpers ─────────────────────────────────────────────────────────────
arduino = None

def establish_connection():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=0.1)
        time.sleep(2)  # allow Arduino to reset
        arduino.reset_input_buffer()
        return _send_and_wait("TEST", expect_contains="Ready")
    except Exception as e:
        print(f"[ERROR] Opening {ARDUINO_PORT}: {e}")
        return False

def _send_and_wait(msg, expect_contains=None):
    """Send msg\\n, wait for an ACK or for expect_contains in reply."""
    for attempt in range(ACK_RETRIES):
        arduino.write((msg + "\n").encode())
        deadline = time.time() + ACK_TIMEOUT
        while time.time() < deadline:
            line = arduino.readline().decode(errors="ignore").strip()
            if not line:
                continue
            if line.startswith("ACK:"):
                return True
            if expect_contains and expect_contains in line:
                # echo back an ACK so callers see success
                arduino.write(f"ACK:{msg}\n".encode())
                return True
        print(f"[WARN] No ACK for '{msg}' (attempt {attempt+1}/{ACK_RETRIES})")
    return False

def send_to_arduino(prefix, text=""):
    """Formats and sends prefix+text (e.g. 'T:', 'R:', 'G:')."""
    if not arduino or not arduino.is_open:
        return
    payload = f"{prefix}{text}"[:95]  # clamp length
    _send_and_wait(payload)

# ─── Utility Functions ─────────────────────────────────────────────────────────
def clear_console():
    os.system('cls' if sys.platform == 'win32' else 'clear')

def translate_text(text):
    if not text.strip():
        return ""
    try:
        return deepl_client.translate_text(text, target_lang=target_language).text
    except Exception as e:
        print(f"[ERROR] Translation: {e}")
        return "(Translation error)"

# ─── Game Functions ─────────────────────────────────────────────────────────────
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
    
    # Send game info to Arduino
    send_to_arduino("G:", f"WORDLE: {' '.join(wordle_display)}")

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
            result = f"🎉 CONGRATULATIONS! You guessed it: {wordle_word}"
            send_to_arduino("G:", f"WON: {wordle_word}")
            return result
        else:
            result = f"Good guess! {' '.join(wordle_display)}"
            send_to_arduino("G:", f"WORDLE: {' '.join(wordle_display)}")
            return result
    else:
        wordle_strikes += 1
        if wordle_strikes >= wordle_max_strikes:
            wordle_active = False
            result = f"💀 Game Over! The word was: {wordle_word}"
            send_to_arduino("G:", f"LOST: {wordle_word}")
            return result
        else:
            result = f"Strike {wordle_strikes}/{wordle_max_strikes}! Letter '{letter}' not found. {' '.join(wordle_display)}"
            send_to_arduino("G:", f"STRIKE {wordle_strikes}: {' '.join(wordle_display)}")
            return result

def start_rps_game():
    """Start a new Rock Paper Scissors game"""
    global rps_active, rps_user_score, rps_computer_score
    
    rps_active = True
    rps_user_score = 0
    rps_computer_score = 0
    
    print(f"\n>>> ROCK PAPER SCISSORS STARTED! <<<")
    print(f"Score - You: {rps_user_score} | Computer: {rps_computer_score}")
    print("Say 'rock', 'paper', or 'scissors' to play!")
    
    # Send game info to Arduino
    send_to_arduino("G:", f"RPS: {rps_user_score}-{rps_computer_score}")

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
        send_to_arduino("G:", f"TIE: {move} vs {computer_choice}")
    elif (move == "rock" and computer_choice == "scissors") or \
         (move == "paper" and computer_choice == "rock") or \
         (move == "scissors" and computer_choice == "paper"):
        rps_user_score += 1
        result_msg += "You win this round!"
        send_to_arduino("G:", f"WIN: {rps_user_score}-{rps_computer_score}")
    else:
        rps_computer_score += 1
        result_msg += "Computer wins this round!"
        send_to_arduino("G:", f"LOSE: {rps_user_score}-{rps_computer_score}")
    
    result_msg += f"\nScore - You: {rps_user_score} | Computer: {rps_computer_score}"
    
    # Check for game end (first to 3 wins)
    if rps_user_score >= 3:
        rps_active = False
        result_msg += "\n🎉 YOU WIN THE GAME! Say 'play rock' to play again."
        send_to_arduino("G:", "GAME WON!")
    elif rps_computer_score >= 3:
        rps_active = False
        result_msg += "\n💀 COMPUTER WINS THE GAME! Say 'play rock' to play again."
        send_to_arduino("G:", "GAME LOST!")
    else:
        result_msg += "\nSay your next move!"
    
    return result_msg

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
    
    # Send game info to Arduino
    send_to_arduino("G:", "NUMBER: 1-100")

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
        result = f"{guess} is too low! Try a higher number. (Guess #{num_guesses})"
        send_to_arduino("G:", f"LOW: {guess} (#{num_guesses})")
        return result
    elif guess > target_number:
        result = f"{guess} is too high! Try a lower number. (Guess #{num_guesses})"
        send_to_arduino("G:", f"HIGH: {guess} (#{num_guesses})")
        return result
    else:
        number_game_active = False
        result = f"🎉 Congratulations! You found the number {target_number} in {num_guesses} guesses! Say 'play number' to start a new game."
        send_to_arduino("G:", f"CORRECT: {target_number} in {num_guesses}")
        return result

# ─── Streaming Speech → Text → Arduino ────────────────────────────────────────
def stream_speech_to_text():
    global wordle_active, rps_active, number_game_active
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_automatic_punctuation=True
    )
    stream_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

    def audio_gen():
        import pyaudio
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        time.sleep(0.5)
        while streaming_active:
            yield stream.read(4096, exception_on_overflow=False)
        stream.stop_stream(); stream.close(); pa.terminate()

    requests = (speech.StreamingRecognizeRequest(audio_content=chunk)
                for chunk in audio_gen())
    responses = client.streaming_recognize(stream_config, requests)

    last = ""
    last_time = time.time()
    cooldown = 0.3

    print(">>> Listening (Ctrl‑C to stop)")
    for resp in responses:
        if not resp.results:
            continue
        res = resp.results[0]
        txt = res.alternatives[0].transcript
        now = time.time()

        # throttle updates
        if txt != last and (res.is_final or now - last_time > cooldown):
            clear_console()
            
            # Show current game status
            if wordle_active:
                print(">>> Playing Wordle! Say letters to guess (say 'stop' to quit)")
                print(f"Word: {' '.join(wordle_display)} | Strikes: {wordle_strikes}/{wordle_max_strikes} | Guessed: {', '.join(wordle_guessed)}")
            elif rps_active:
                print(">>> Playing Rock Paper Scissors! Say 'rock', 'paper', or 'scissors' (say 'stop' to quit)")
                print(f"Score - You: {rps_user_score} | Computer: {rps_computer_score}")
            elif number_game_active:
                print(">>> Playing Number Guessing Game! Say a number between 1-100 (say 'stop' to quit)")
                print(f"Guesses: {num_guesses} | Range: 1-100")
            else:
                print(">>> Say 'play word' for Wordle, 'play rock' for RPS, or 'play number' for Number Game")
            
            print(f"Transcription: {txt!r}  (final={res.is_final})")

            # if not in game mode, send transcript+translation
            if not wordle_active and not rps_active and not number_game_active:
                send_to_arduino("T:", txt)
                tr = translate_text(txt)
                print(f"Translation: {tr}")
                send_to_arduino("R:", tr)

            # on final, handle games or detect game start
            if res.is_final:
                clean = re.sub(r'[^\w\s]', '', txt).lower()

                if wordle_active:
                    # Handle Wordle game
                    if re.search(r'\s*(quit\s*game|stop)\b', clean, re.IGNORECASE):
                        wordle_active = False
                        send_to_arduino("G:", "WORDLE ENDED")
                        print("\n>>> Wordle game ended. Say 'play word' to start a new game.")
                    else:
                        # Extract single letter from transcript
                        letters = re.findall(r'\b[A-Za-z]\b', clean)
                        
                        # Special handling for common speech recognition issues
                        if not letters:
                            if clean in ['i', 'a', 'o', 'u', 'e']:
                                letters = [clean.upper()]
                            elif clean in ['oh', 'owe']:
                                letters = ['O']
                            elif clean in ['ay', 'eh']:
                                letters = ['A']
                            elif clean in ['bee']:
                                letters = ['B']
                            elif clean in ['see', 'sea']:
                                letters = ['C']
                            elif clean in ['dee']:
                                letters = ['D']
                            elif clean in ['gee']:
                                letters = ['G']
                            elif clean in ['jay']:
                                letters = ['J']
                            elif clean in ['kay']:
                                letters = ['K']
                            elif clean in ['pee']:
                                letters = ['P']
                            elif clean in ['cue', 'queue', 'que']:
                                letters = ['Q']
                            elif clean in ['are']:
                                letters = ['R']
                            elif clean in ['tea', 'tee']:
                                letters = ['T']
                            elif clean in ['you', 'yu']:
                                letters = ['U']
                            elif clean in ['vee']:
                                letters = ['V']
                            elif clean in ['why']:
                                letters = ['Y']
                            elif clean in ['zee']:
                                letters = ['Z']
                            elif len(txt.strip()) <= 3:
                                letter_match = re.search(r'([A-Za-z])', txt)
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
                    if re.search(r'\s*stop\b', clean, re.IGNORECASE):
                        rps_active = False
                        send_to_arduino("G:", "RPS ENDED")
                        print("\n>>> Rock Paper Scissors game ended. Say 'play rock' to start a new game.")
                    else:
                        # Check for RPS moves
                        if re.search(r'\brock\b', clean, re.IGNORECASE):
                            move_result = handle_rps_move("rock")
                            print(f">>> {move_result}")
                        elif re.search(r'\bpaper\b', clean, re.IGNORECASE):
                            move_result = handle_rps_move("paper")
                            print(f">>> {move_result}")
                        elif re.search(r'\bscissors\b', clean, re.IGNORECASE):
                            move_result = handle_rps_move("scissors")
                            print(f">>> {move_result}")
                        else:
                            print(">>> Please say 'rock', 'paper', or 'scissors'!")

                elif number_game_active:
                    # Handle Number Guessing game
                    if re.search(r'\s*stop\b', clean, re.IGNORECASE):
                        number_game_active = False
                        send_to_arduino("G:", "NUMBER ENDED")
                        print("\n>>> Number guessing game ended. Say 'play number' to start a new game.")
                    else:
                        # Process the guess
                        guess_result = handle_number_guess(txt)
                        print(f">>> {guess_result}")

                else:
                    # Check for game starts
                    if re.search(r'\bplay\s+word\b', clean, re.IGNORECASE):
                        start_wordle_game()
                    elif re.search(r'\bplay\s+rock\b', clean, re.IGNORECASE):
                        start_rps_game()
                    elif re.search(r'\bplay\s+number\b', clean, re.IGNORECASE):
                        start_number_game()

            last = txt
            last_time = now

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Speech→Text→Translation→Arduino + Games")
    if not establish_connection():
        print("[WARN] Arduino not responding; continuing without display.")
    else:
        print("[OK] Arduino ready.")
        send_to_arduino("LANG:", target_language)
    print("Starting in 3 seconds…")
    time.sleep(3)

    try:
        stream_speech_to_text()
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        global streaming_active
        streaming_active = False
        if arduino and arduino.is_open:
            send_to_arduino("QUIT")
            arduino.close()
        print("Done.")

if __name__ == "__main__":
    main()