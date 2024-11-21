from flask import Flask, request, render_template, send_file, redirect, url_for
import subprocess
import os
from gtts import gTTS
import speech_recognition as sr
from deep_translator import GoogleTranslator
import traceback
import concurrent.futures

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('web.html')

@app.route('/dub_video', methods=['POST'])
def dub_video():
    video_file = request.files['video']
    target_language = request.form['language']

    # List of valid languages
    valid_languages = ["hi", "ta", "te", "bn", "gu", "mr", "kn", "ml", "pa", "or", "ur", "ne", "bh", "sd", "ks", "ma"]
    if target_language not in valid_languages:
        return "Invalid target language selected."

    # Save the uploaded video
    video_path = 'uploaded_video.mp4'
    video_file.save(video_path)

    try:
        output_video = extract_audio_and_translate(video_path, target_language)

        # Move dubbed video to the static folder, handle the file already existing
        static_video_path = os.path.join('static', os.path.basename(output_video))
        
        if os.path.exists(static_video_path):
            os.remove(static_video_path)
        
        os.rename(output_video, static_video_path)
        
        # Redirect to the result page with the video path
        return redirect(url_for('result', video_path=os.path.basename(static_video_path)))
    except Exception as e:
        return str(e)

@app.route('/result')
def result():
    video_filename = request.args.get('video_path')
    return render_template('result.html', output_video=video_filename)

@app.route('/download_video')
def download_video():
    video_filename = request.args.get('video_path')
    video_path = os.path.join('static', video_filename)
    return send_file(video_path, as_attachment=True)

def extract_audio_and_translate(video_path, target_language):
    audio_path = 'extracted_audio.wav'
    subprocess.run(['ffmpeg', '-y', '-i', video_path, '-ar', '16000', '-ac', '1', '-q:a', '0', '-map', 'a', audio_path], check=True)

    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)
    
    try:
        # Transcribe audio to text
        original_text = recognizer.recognize_google(audio)

        # Use concurrent processing for translation and TTS generation
        with concurrent.futures.ThreadPoolExecutor() as executor:
            translation_future = executor.submit(GoogleTranslator(source='en', target=target_language).translate, original_text)
            translation_result = translation_future.result()

            new_audio_path = 'dubbed_audio.mp3'
            audio_future = executor.submit(generate_audio, translation_result, target_language, new_audio_path)
            audio_future.result()

        # Merge the original video with the dubbed audio
        output_video_path = 'dubbed_video.mp4'
        subprocess.run([
            'ffmpeg', '-y', '-i', video_path, '-i', new_audio_path,
            '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', '-c:a', 'aac', output_video_path
        ], check=True)

        return os.path.abspath(output_video_path)
    
    except sr.UnknownValueError:
        raise Exception("Speech Recognition could not understand the audio.")
    except sr.RequestError as e:
        raise Exception(f"Error with Speech Recognition service: {str(e)}")
    except Exception as e:
        print("Error details:", traceback.format_exc())
        raise Exception(f"An unexpected error occurred: {str(e)}")

def generate_audio(text, lang, output_path):
    tts = gTTS(text.strip(), lang=lang)
    tts.save(output_path)

if __name__ == "__main__":
    app.run(debug=True)