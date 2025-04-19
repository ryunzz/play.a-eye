import os
import re
import time
import sys
import serial
from google.cloud import speech
from dotenv import load_dotenv
import deepl
from openai import OpenAI

# ─── Configuration ─────────────────────────────────────────────────────────────
ARDUINO_PORT = "/dev/cu.usbserial-10"
ARDUINO_BAUD = 9600
ACK_TIMEOUT = 1.0    # seconds to wait for an ACK
ACK_RETRIES = 3

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), "googleKey.json")
deepl_client = deepl.Translator(os.getenv("DEEPL_API_KEY"))
llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

target_language = input("Enter target language (e.g., 'ES' for Spanish, 'FR' for French): ").strip().upper()

streaming_active = True
conversation_active = False
conversation_history = []

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
    """Formats and sends prefix+text (e.g. 'T:', 'R:', 'A:', 'CONV:START')."""
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

def handle_conversation(user_input):
    global conversation_active, conversation_history
    if not user_input.strip():
        return "(Empty input detected)"
    if re.search(r'\s*bye\s*,?\s*sentient\b', user_input, re.IGNORECASE):
        conversation_active = False
        conversation_history.clear()
        send_to_arduino("CONV:END")     # notify Arduino we’ve ended
        return "Goodbye! It was nice talking to you."
    conversation_history.append({"role": "user", "content": user_input})
    msgs = [{"role": "system", "content": "You are a helpful and friendly AI named Sentient."}] + conversation_history
    try:
        resp = llm.chat.completions.create(
            model="gpt-4o-mini", messages=msgs, temperature=0.7, max_tokens=150
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] OpenAI: {e}")
        answer = "(OpenAI Error)"
    conversation_history.append({"role": "assistant", "content": answer})
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
    return answer

# ─── Streaming Speech → Text → Arduino ────────────────────────────────────────
def stream_speech_to_text():
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
    global conversation_active

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
            print(f"Transcription: {txt!r}  (final={res.is_final})")

            # if not in LLM‑mode, send transcript+translation
            if not conversation_active:
                send_to_arduino("T:", txt)
                tr = translate_text(txt)
                print(f"Translation: {tr}")
                send_to_arduino("R:", tr)

            # on final, detect wake‑word or handle convo
            if res.is_final:
                clean = re.sub(r'[^\w\s]', '', txt).lower()

                # ── Wake‑word: enter LLM‑mode ───────────────────────
                if not conversation_active and "hey sentient" in clean:
                    conversation_active = True
                    print("🔍 Detected wake‑word! Starting conversation.")
                    # **CLEAR** all previous lines on the OLED:
                    send_to_arduino("T:", "")
                    send_to_arduino("R:", "")
                    send_to_arduino("CONV:START")
                    ans = handle_conversation("Hello!")
                    print(f"Sentient: {ans}")
                    send_to_arduino("A:", ans)

                # ── In LLM‑mode: only send AI replies ───────────────
                elif conversation_active:
                    ans = handle_conversation(txt)
                    print(f"Sentient: {ans}")
                    send_to_arduino("A:", ans)

            last = txt
            last_time = now

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Speech→Text→Translation→Arduino")
    if not establish_connection():
        print("[WARN] Arduino not responding; continuing without display.")
    else:
        print("[OK] Arduino ready.")
        send_to_arduino("LANG:", target_language)
    print("Starting in 3 seconds…")
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
