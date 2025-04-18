import os
import re
import time
import sys
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
    if re.search(r'\s*slay\s*,?\s*sentient\b', user_input, re.IGNORECASE):
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
            model="gpt-4",
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
    global conversation_active

    try:
        clear_console()
        print(">>> Listening in real-time (Press Ctrl+C to stop)...")
        print("Speak now...")
        if conversation_active:
            print(">>> In conversation with Sentient (say 'bye, sentient' to end)")
        else:
            print(">>> Say 'hey, sentient' to start a conversation")

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
                    print(">>> In conversation with Sentient (say 'bye, sentient' to end)")
                else:
                    print(">>> Say 'hey, sentient' to start a conversation")
                print(f"Transcription: {transcript}")

                # Always translate everything
                translated_text = translate_text(transcript, target_language)
                print(f"Translation: {translated_text}")

                # Handle conversation if needed
                if result.is_final:
                    if not conversation_active:
                        # Check for conversation start
                        if re.search(r'\s*hey\s*,?\s*sentient\b.?\s*', transcript, re.IGNORECASE):
                            conversation_active = True
                            print("\n>>> Starting conversation with Sentient...")
                            response = handle_conversation("Hello!")
                            print(f"Sentient: {response}")
                            # Translate Sentient's response too
                            translated_response = translate_text(response, target_language)
                            print(f"Translation: {translated_response}")
                    else:
                        # Continue conversation
                        response = handle_conversation(transcript)
                        print(f"Sentient: {response}")
                        # Translate Sentient's response too
                        translated_response = translate_text(response, target_language)
                        print(f"Translation: {translated_response}")
                        
                        # Check if conversation just ended
                        if not conversation_active:
                            print("\n>>> Conversation ended. Say 'Hey Sentient' to start a new conversation.")

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