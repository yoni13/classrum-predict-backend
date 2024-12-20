from flask import Flask, request, abort, jsonify
from flask_limiter import Limiter
import json
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
import os
from pydantic import BaseModel, ValidationError

app = Flask(__name__)

def get_remote_address():
    '''
    Get real user ip instead of localhost since we are using traefik
    '''
    if request.headers.get('cf-connecting-ip'):
        return request.headers.get('cf-connecting-ip')
    else:
        return request.remote_addr
    
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Create the model
generation_config = {
  "temperature": 0.2, # to control the randomness of the output
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
  "response_schema": content.Schema(
    type = content.Type.OBJECT,
    properties = {
      "course_type": content.Schema(
        type = content.Type.STRING,
      ),
    },
  ),
  "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
  model_name="gemini-2.0-flash-exp",
  generation_config=generation_config,
  system_instruction="Classify the given homework into one of the specified courses.\nInput:\ninput: A string describing the homework (e.g., \"基礎電學直流電壓P23\").\ncourse: A list of course names to classify into (e.g., [\"數學\", \"國文\", \"基礎電學\", \"歷史\"]).\nOutput:\nProvide a JSON object indicating the most relevant course for the given homework or \"None\".\nInput: {\"input\":\"基礎電學直流電壓P23\",\"course\":[\"數學\",\"國文\",\"基礎電學\",\"歷史\"]}  \nOutput: {\"course_type\":\"基礎電學\"}",
)

def request_llm(data, courses):
  chat_session = model.start_chat(history=[],)
  request_json = {
      "input": data,
      "course": courses
  }

  response = json.loads(chat_session.send_message(str(request_json)).text).get("course_type","None")
  if response not in courses:
    response = "None"
  return response

class HomeworkRequest(BaseModel):
    line_data: str
    courses: list[str]

@app.route("/get-homework-type", methods=["POST"])
@limiter.limit("1 per second")
def get_homework_type():
  try:
    input_data = HomeworkRequest(line_data=request.json["line_data"], courses=request.json["courses"])
    datas = input_data.line_data.split("\n")
    courses = input_data.courses
  except ValidationError as e:
    return abort(400)

  for i in range(len(datas)):
    data = datas[i].strip()

    if data == "" or len(data) > 100:
      datas[i] = "None"
      continue

    datas[i] = request_llm(data, courses)
  return jsonify({"result": datas})
    


if __name__ == "__main__":
    app.run()