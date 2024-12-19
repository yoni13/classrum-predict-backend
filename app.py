from flask import Flask, request, abort
# flask limiter
from flask_limiter import Limiter
import json

app = Flask(__name__)
limiter = Limiter(app)


import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
import os


genai.configure(api_key=os.environ["GEMINI_API_KEY"])
#genai.configure(api_key="Roatated")

# Create the model
generation_config = {
  "temperature": 1,
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
    response = json.loads(chat_session.send_message(str(request_json)).text)["course_type"]
    print(response)

    return response

@app.route("/get-homework-type", methods=["POST"])
@limiter.limit("1 per second")
def get_homework_type():
    if not request.form['line_data'] or not request.form['courses'] or request.form['line_data'].strip() == "" or request.form['courses'].strip() == "":
        return abort(400)
    
    datas = str(request.form['line_data'])
    courses = str(request.form['courses'])

    # get llm per line
    datas = datas.split("\n")
    for i in range(len(datas)):
        datas[i] = request_llm(datas[i], courses.split(","))
    return {"result": datas}
    


if __name__ == "__main__":
    app.run()