import io
import os
import base64
import replicate
from PIL import Image
from openai import OpenAI
from termcolor import colored
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from flask import Flask, render_template, request, send_file, jsonify

load_dotenv()

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