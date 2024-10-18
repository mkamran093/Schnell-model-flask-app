import io
import os
import sys
import base64
import logging
import replicate
from PIL import Image
from openai import OpenAI
from termcolor import colored
from dotenv import load_dotenv
from httplib2 import Credentials
from pydantic import BaseModel, Field
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from flask import Flask, render_template, request, send_file, jsonify

# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Load environment variables
load_dotenv()

# Initialize sheets client
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1JTZt9e3hOH7QNe4dOxAs1RXetUOJ-ir6L9ucdGCflLQ'
SHEET_NAME = 'Sheet1'

# Initialize OpenAI API client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        prompt = request.form['prompt']
        is_logo = isLogo(prompt)
        if is_logo:
            # generate a prompt for this info
            new_prompt = create_prompt(prompt)
            try:
                output = replicate.run(
                    "black-forest-labs/flux-schnell",
                    input={"prompt": new_prompt},
                )
                base64_string = str(output[0])
                return jsonify({"success": True, "image": base64_string})
            except Exception as e:
                print(f"Error generating image: {e}")
                return jsonify({"success": False, "error": "Failed to generate the logo. Please try again."})
        else:
            error_message = "The provided information does not appear to be related to logo design. Please provide details specific to logo creation."
            return jsonify({"success": False, "error": error_message})
    return render_template('index.html')

@app.route('/submit_download', methods=['POST'])
def submit_download():
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    
    # Print the name and email to the terminal
    print(colored(f"Download requested by: {name} ({phone} - {email})", "green"))
    store_in_sheets(name, phone, email)
    return jsonify({"message": "Download information received"})

def store_in_sheets(name, phone, email):
    service = get_google_sheets_service()
    try:
        values = [name, phone, email]
        body = {'values': [values]}
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"Sheet1!A:D",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body).execute()
        updated_cells = result.get('updates', {}).get('updatedCells', 0)
        logger.info(f"Updated {updated_cells} cells in Google Sheets")
    except HttpError as e:
        logger.error(f"HttpError occurred while updating Google Sheets: {e}")
    except Exception as e:
        logger.error(f"An error occurred while updating Google Sheets: {e}")
    

def get_google_sheets_service(force_new_token=False):
    creds = None
    if os.path.exists('token.json') and not force_new_token:
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            logger.error(f"Error reading token.json: {str(e)}")
            os.remove('token.json')
            logger.info("Removed invalid token.json file")

    if not creds or not creds.valid or force_new_token:
        if creds and creds.expired and creds.refresh_token and not force_new_token:
            try:
                creds.refresh(Request())
                logger.info("Successfully refreshed the token")
            except Exception as e:
                logger.error(f"Error refreshing credentials: {str(e)}")
                creds = None

        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                logger.info("Generated new token through authorization flow")
            except Exception as e:
                logger.error(f"Error in authorization flow: {str(e)}")
                raise

        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            logger.info("Saved new token.json file")

    try:
        service = build('sheets', 'v4', credentials=creds)
        logger.info("Successfully created Google Sheets service")
        return service
    except HttpError as error:
        logger.error(f"An error occurred while building the service: {error}")
        if "invalid_grant" in str(error) or "invalid_scope" in str(error):
            logger.info("Token seems to be invalid. Attempting to generate a new one.")
            return get_google_sheets_service(force_new_token=True)
        raise

class isLogoRequest(BaseModel):
    isLogo: bool = Field(description="Check if the given details refer to a logo design or not. return a boolean value.")

class createPromptRequest(BaseModel):
    prompt: str = Field(description="Generate a specific prompt for a text-to-image model to create a logo design based on the provided information.")

def create_prompt(prompt):
    print(colored("Creating a prompt for the given details...", color="blue"))
    system_prompt = "You will receive a set of information related to a business or design request. Your task is to create a detailed and specific prompt for a text-to-image model to generate a logo design. Ensure that the prompt focuses solely on generating logo designs relevant to the provided information."

    user_prompt = (
        f"Here are the details: {prompt}."
        " Please generate a specific prompt for a text-to-image model to create a logo design based on this information."
    )

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=createPromptRequest,        
        )
        result = response.choices[0].message.parsed
        
        return result.prompt
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "None"

def isLogo(prompt):
    print(colored("Checking if the given details refer to a logo design or not...", color="blue"))
    system_prompt = "You will receive a set of information related to a business or design request. Your task is to analyze the provided information and determine if it pertains to logo design. Return a boolean value: 'True' if the information is relevant to logo design and 'False' if it is not."

    user_prompt = (
        f"Here are the details of my business request: {prompt}."
        "Please analyze this information and let me know if it pertains to logo design by responding with 'True' or 'False'."
    )

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=isLogoRequest,        
        )
        result = response.choices[0].message.parsed
        
        return result.isLogo
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return False

if __name__ == '__main__':
    app.run(debug=True)