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
    "ERC"
]

# ─── Serial Helpers ─────────────────────────────────────────────────────────────
arduino = None

def establish_connection():
    global arduino
    try:
        print(f"[DEBUG] Attempting to connect to Arduino on {ARDUINO_PORT}")
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=0.1)
        time.sleep(2)  # allow Arduino to reset
        arduino.reset_input_buffer()
        print("[DEBUG] Arduino connection established, testing communication...")
        if _send_and_wait("TEST", expect_contains="Ready"):
            print("[DEBUG] Arduino communication test successful")
            return True
        else:
            print("[ERROR] Arduino communication test failed")
            return False
    except Exception as e:
        print(f"[ERROR] Opening {ARDUINO_PORT}: {e}")
        return False

def _send_and_wait(msg, expect_contains=None):
    """Send msg\\n, wait for an ACK or for expect_contains in reply."""
    print(f"[DEBUG] Sending to Arduino: '{msg}'")
    for attempt in range(ACK_RETRIES):
        try:
            arduino.write((msg + "\n").encode())
            print(f"[DEBUG] Written to Arduino (attempt {attempt+1}/{ACK_RETRIES})")
            deadline = time.time() + ACK_TIMEOUT
            while time.time() < deadline:
                line = arduino.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                print(f"[DEBUG] Arduino response: '{line}'")
                if line.startswith("ACK:"):
                    print(f"[DEBUG] Received ACK for '{msg}'")
                    return True
                if expect_contains and expect_contains in line:
                    print(f"[DEBUG] Received expected response containing '{expect_contains}'")
                    # echo back an ACK so callers see success
                    arduino.write(f"ACK:{msg}\n".encode())
                    return True
            print(f"[WARN] No ACK for '{msg}' (attempt {attempt+1}/{ACK_RETRIES})")
        except Exception as e:
            print(f"[ERROR] Arduino communication error: {e}")
    return False

def send_to_arduino(prefix, text=""):
    """Formats and sends prefix+text (e.g. 'T:', 'R:', 'G:')."""
    if not arduino or not arduino.is_open:
        print("[WARN] Cannot send to Arduino - not connected")
        return
    payload = f"{prefix}{text}"[:95]  # clamp length
    print(f"[DEBUG] Preparing Arduino message: {payload}")
    success = _send_and_wait(payload)
    if not success:
        print(f"[WARN] Failed to send message to Arduino: {payload}")

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
    # Send game info to Arduino with G: prefix
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
    
    # Send game info to Arduino with G: prefix
    send_to_arduino("G:", f"RPS YOU:{rps_user_score} CPU:{rps_computer_score}")
    send_to_arduino("G:", "YOUR MOVE?")

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

    # Determine result
    if move == computer_choice:
        round_result = "TIE!"
        result_msg += "It's a tie!"
    elif (move == "rock" and computer_choice == "scissors") or \
         (move == "paper" and computer_choice == "rock") or \
         (move == "scissors" and computer_choice == "paper"):
        rps_user_score += 1
        round_result = "YOU WIN!"
        result_msg += "You win this round!"
    else:
        rps_computer_score += 1
        round_result = "CPU WIN!"
        result_msg += "Computer wins this round!"

    # Show what the user played
    send_to_arduino("G:", f"You played: {move.title()}")
    time.sleep(1)
    # Show what the computer played
    send_to_arduino("G:", f"CPU played: {computer_choice.title()}")
    time.sleep(1)
    # Show the result
    send_to_arduino("G:", round_result)
    time.sleep(1)
    # Show the score
    send_to_arduino("G:", f"You {rps_user_score} : CPU {rps_computer_score}")
    time.sleep(1)

    result_msg += f"\nScore - You: {rps_user_score} | Computer: {rps_computer_score}"
    
    # Check for game end (first to 3 wins)
    if rps_user_score >= 3:
        rps_active = False
        result_msg += "\n🎉 YOU WIN THE GAME! Say 'play rock' to play again."
        send_to_arduino("G:", "GAME OVER")
        send_to_arduino("G:", "YOU WIN!")
    elif rps_computer_score >= 3:
        rps_active = False
        result_msg += "\n💀 COMPUTER WINS THE GAME! Say 'play rock' to play again."
        send_to_arduino("G:", "GAME OVER")
        send_to_arduino("G:", "CPU WIN!")
    else:
        result_msg += "\nSay your next move!"
        # Update display for next round
        send_to_arduino("G:", f"You {rps_user_score} : CPU {rps_computer_score}")
        send_to_arduino("G:", "YOUR MOVE?")
    
    return result_msg

def extract_number(text):
    """Extract a number from the spoken text"""
    print(f"[DEBUG] extract_number called with text: '{text}'")
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
    print(f"[DEBUG] extract_number: text_lower='{text_lower}'")
    for word, digit in number_words.items():
        text_lower = text_lower.replace(word, digit)
    
    # Find any numbers in the text
    numbers = re.findall(r'\d+', text_lower)
    print(f"[DEBUG] extract_number: found numbers={numbers}")
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
    # Send game info to Arduino with G: prefix
    send_to_arduino("G:", "NUMBER GAME | GUESS 1-100 | SAY A NUMBER")

def handle_number_guess(guess_text):
    """Process the player's guess and provide feedback"""
    global num_guesses, number_game_active
    
    # If guess_text is already an integer, use it directly
    if isinstance(guess_text, int):
        guess = guess_text
    else:
        guess = extract_number(guess_text)
    
    print(f"[DEBUG] handle_number_guess: guess={guess}")
    
    if not guess:
        return "I didn't catch a number. Please say a number between 1 and 100."
    
    if guess < 1 or guess > 100:
        return "Please guess a number between 1 and 100."
    
    num_guesses += 1
    
    if guess < target_number:
        result = f"{guess} is too low! Try a higher number. (Guess #{num_guesses})"
        send_to_arduino("G:", f"GUESS {num_guesses}: {guess} TOO LOW! TRY HIGHER")
        return result
    elif guess > target_number:
        result = f"{guess} is too high! Try a lower number. (Guess #{num_guesses})"
        send_to_arduino("G:", f"GUESS {num_guesses}: {guess} TOO HIGH! TRY LOWER")
        return result
    else:
        number_game_active = False
        result = f"🎉 Congratulations! You found the number {target_number} in {num_guesses} guesses! Say 'play number' to start a new game."
        send_to_arduino("G:", f"CORRECT! {target_number} IN {num_guesses} GUESSES!")
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

        print(f"[DEBUG] Transcript: '{txt}' | final={res.is_final}")  # Debug print

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

            # Process the transcript
            clean = re.sub(r'[^-\x7f\w\s]', '', txt).lower().strip()
            print(f"[DEBUG] Processing transcript: '{clean}' (final={res.is_final})")

            # Check for stop/quit command first
            if re.search(r'\b(stop|quit|exit)\b', clean, re.IGNORECASE):
                print(f"[DEBUG] Detected stop/quit command.")
                if wordle_active:
                    wordle_active = False
                    send_to_arduino("G:", "WORDLE ENDED")
                    print("\n>>> Wordle game ended. Say 'play word' to start a new game.")
                elif rps_active:
                    rps_active = False
                    send_to_arduino("G:", "RPS ENDED")
                    print("\n>>> Rock Paper Scissors game ended. Say 'play rock' to start a new game.")
                elif number_game_active:
                    number_game_active = False
                    send_to_arduino("G:", "NUMBER ENDED")
                    print("\n>>> Number game ended. Say 'play number' to start a new game.")
                return

            # Process game moves
            if wordle_active:
                print("[DEBUG] Processing Wordle game")
                # Special handling for common speech recognition issues
                if clean in ['oh', 'owe']:
                    letters = ['O']
                elif len(clean) == 1 and clean.isalpha():
                    letters = [clean]
                else:
                    # Extract single letter from transcript
                    letters = re.findall(r'\b[A-Za-z]\b', clean)
                    if not letters and len(clean) <= 3:
                        letter_match = re.search(r'([A-Za-z])', clean)
                        if letter_match:
                            letters = [letter_match.group(1)]
                print(f"[DEBUG] After extraction: clean='{clean}', letters={letters}")
                if letters:
                    print(f">>> Extracted letter: '{letters[0]}'")
                    guess_result = handle_wordle_guess(letters[0].upper())
                    print(f">>> {guess_result}")
                    if not wordle_active:
                        print("\n>>> Game ended. Say 'play word' to start a new game.")
                    return
                else:
                    print(">>> Please say a single letter to guess!")
                    return
            elif rps_active:
                print("[DEBUG] Processing RPS game")
                # Improved: pick the first move mentioned in the transcript
                original_lower = txt.lower().strip()
                move_found = False
                move_order = []
                for move in ["rock", "paper", "scissors", "scissor"]:
                    idx = original_lower.find(move)
                    if idx != -1:
                        move_order.append((idx, move))
                if move_order:
                    move_order.sort()
                    chosen_move = move_order[0][1]
                    if chosen_move == "scissor":
                        chosen_move = "scissors"
                    print(f"[DEBUG] Recognized RPS move: {chosen_move}")
                    move_result = handle_rps_move(chosen_move)
                    print(f">>> {move_result}")
                    move_found = True
                if not move_found:
                    print(f">>> Didn't recognize move in: '{txt}'. Please say 'rock', 'paper', or 'scissors'!")
                    send_to_arduino("G:", f"SAY: ROCK PAPER SCISSORS | YOU:{rps_user_score} CPU:{rps_computer_score}")
                return
            elif number_game_active:
                print("[DEBUG] Processing Number game")
                # Try to get a number from the input
                guess = None
                
                # First try direct digit
                if clean.isdigit():
                    guess = int(clean)
                    print(f"[DEBUG] Found direct digit: {guess}")
                # Then try to extract from text
                else:
                    # Look for numbers in the text
                    numbers = re.findall(r'\d+', clean)
                    if numbers:
                        guess = int(numbers[0])
                        print(f"[DEBUG] Found number in text: {guess}")
                
                if guess is not None and 1 <= guess <= 100:
                    print(f"[DEBUG] Processing valid guess: {guess}")
                    guess_result = handle_number_guess(guess)
                    print(f">>> {guess_result}")
                else:
                    print(">>> Please say a number between 1 and 100!")

            # Check for game start commands
            elif not (wordle_active or rps_active or number_game_active):
                print("[DEBUG] Checking for game start commands")
                if re.search(r'\b(play|start)\s*(?:the\s*)?(?:word|wordle)\b', clean, re.IGNORECASE):
                    wordle_active = True
                    rps_active = False
                    number_game_active = False
                    print("[DEBUG] Starting Wordle game.")
                    start_wordle_game()
                elif re.search(r'\b(play|start)\s*(?:the\s*)?(?:rock|rps)\b', clean, re.IGNORECASE):
                    wordle_active = False
                    rps_active = True
                    number_game_active = False
                    print("[DEBUG] Starting RPS game.")
                    start_rps_game()
                elif re.search(r'\b(play|start)\s*(?:the\s*)?(?:number|numbers?)\b', clean, re.IGNORECASE):
                    wordle_active = False
                    rps_active = False
                    number_game_active = True
                    print("[DEBUG] Starting Number game.")
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
        while True:
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