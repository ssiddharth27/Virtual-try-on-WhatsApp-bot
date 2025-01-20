from flask import Flask, request, jsonify
from twilio.rest import Client
import requests
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

app = Flask(__name__)

# Twilio configuration
account_sid = '###############################'  # Replace with your own access code
auth_token = '##################################' # Replace with your own auth token
twilio_whatsapp_number = 'whatsapp:##########'  # Replace with your own whatsapp number
client = Client(account_sid, auth_token)

# FastAPI server URL
TRY_ON_SERVER_URL = "http://localhost:8000/try-on"

# Authenticate Google Drive
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# User session storage
user_sessions = {}  # A dictionary to track users and their current session state


def download_image(url):
    """Downloads an image from a URL with Twilio authentication."""
    response = requests.get(url, auth=(account_sid, auth_token))
    response.raise_for_status()
    return response.content


def upload_to_google_drive(local_file_path, file_name):
    """Uploads a file to Google Drive and generates a public URL."""
    file_drive = drive.CreateFile({'title': file_name})
    file_drive.SetContentFile(local_file_path)
    file_drive.Upload()

    # Make the file publicly accessible
    file_drive.InsertPermission({
        'type': 'anyone',
        'value': 'anyone',
        'role': 'reader'
    })

    # Return the public URL to the uploaded file
    return f"https://drive.google.com/uc?export=download&id={file_drive['id']}"


#     )
def send_whatsapp_message(to, message, media_url=None):
    """Helper function to send a WhatsApp message."""
    print(f"Sending message to {to} with media URL: {media_url}")  # Debug log
    if media_url:
        # Send only the URL in the message body, no media attachment
        message += f"\n\nHere is your virtual try-on result: {media_url}"
        
    client.messages.create(
        body=message,
        from_=twilio_whatsapp_number,
        to=to
    )


def process_virtual_try_on(user_image_url, dress_image_url):
    """Downloads images, sends them to the FastAPI server, and uploads the result to Google Drive."""
    user_image = download_image(user_image_url)
    dress_image = download_image(dress_image_url)

    files = {
        "user_image": ('user.jpg', user_image, 'image/jpeg'),
        "dress_image": ('dress.jpg', dress_image, 'image/jpeg')
    }
    
    try:
        response = requests.post(TRY_ON_SERVER_URL, files=files)
        response_data = response.json()
        result_file_path = response_data.get("try_on_image_url")

        if result_file_path:
            # Here, we directly use the Google Drive URL instead of uploading to Google Drive
            result_url = f"https://drive.google.com/uc?export=download&id={result_file_path.split('=')[-1]}"
            return result_url
        return None
    except Exception as e:
        print(f"Error processing try-on: {e}")
        return None
    

@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    user_msg = request.form.get("Body").strip().lower()
    from_number = request.form.get("From")

    # Initialize a session for the user if it does not already exist
    if from_number not in user_sessions:
        user_sessions[from_number] = {"step": 0, "images": []}

    session = user_sessions[from_number]

    # Step 1: Initiate try-on process
    if "try-on" in user_msg and session["step"] == 0:
        session["step"] = 1
        send_whatsapp_message(from_number, "Please send a clear photo of yourself.")
    
    # Step 2: Receive and store user photo
    elif session["step"] == 1 and "MediaUrl0" in request.form:
        user_image_url = request.form["MediaUrl0"]
        session["images"].append(user_image_url)
        session["step"] = 2
        send_whatsapp_message(from_number, "Great! Now, please send the image of the dress you want to try on.")
    
    # Step 3: Receive and process dress photo
    elif session["step"] == 2 and "MediaUrl0" in request.form:
        dress_image_url = request.form["MediaUrl0"]
        session["images"].append(dress_image_url)

        # Process images through the FastAPI try-on API
        result_image_url = process_virtual_try_on(session["images"][0], session["images"][1])

        if result_image_url:
            send_whatsapp_message(from_number, "", media_url=result_image_url)
        else:
            send_whatsapp_message(from_number, "Sorry, there was an issue with processing. Please try again later.")

        # Reset session
        user_sessions[from_number] = {"step": 0, "images": []}
    else:
        send_whatsapp_message(from_number, "To use the virtual try-on feature, reply with 'try-on'.")

    return jsonify({"status": "success"})


if __name__ == "__main__":
    app.run(port=5000)