from fastapi import FastAPI, UploadFile, File
from gradio_client import Client, file
import uvicorn
import tempfile
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# Initialize FastAPI app
app = FastAPI()

# Initialize Gradio Client
client = Client("Nymbo/Virtual-Try-On")  

# Authenticate Google Drive
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)


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
    return f"https://drive.google.com/uc?id={file_drive['id']}"


@app.post("/try-on")
async def try_on(user_image: UploadFile = File(...), dress_image: UploadFile = File(...)):
    # Save uploaded files temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_user_file, \
        tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_dress_file:
        temp_user_file.write(await user_image.read())
        temp_dress_file.write(await dress_image.read())
        temp_user_file_path = temp_user_file.name
        temp_dress_file_path = temp_dress_file.name

    # Call the Gradio API
    result = client.predict(
        dict={
            "background": file(temp_user_file_path),
            "layers": [],
            "composite": None
        },
        garm_img=file(temp_dress_file_path),
        garment_des="Virtual try-on",
        is_checked=True,
        is_checked_crop=False,
        denoise_steps=30,
        seed=42,
        api_name="/tryon"
    )

    # file path for the try-on result (first element of the tuple)
    result_file_path = result[0]

    # Upload the result to Google Drive
    try:
        result_url = upload_to_google_drive(result_file_path, "tryon_result.jpg")
        return {"try_on_image_url": result_url}
    except Exception as e:
        return {"error": f"Failed to upload to Google Drive: {e}"}


# Run FastAPI server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
