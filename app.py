from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
import json

# Initialize FastAPI app
app = FastAPI()

# CORS Middleware (Optional for testing with frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


# Google Generative AI Configuration
# Replace with your API key
import os
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_schema": content.Schema(
        type=content.Type.OBJECT,
        properties={
            "course_type": content.Schema(
                type=content.Type.STRING,
            ),
        },
    ),
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
    system_instruction=(
        "Classify the given homework into one of the specified courses.\n"
        "Input:\ninput: A string describing the homework (e.g., \"基礎電學直流電壓P23\").\n"
        "course: A list of course names to classify into (e.g., [\"數學\", \"國文\", \"基礎電學\", \"歷史\"]).\n"
        "Output:\nProvide a JSON object indicating the most relevant course for the given homework or \"None\".\n"
        "Input: {\"input\":\"基礎電學直流電壓P23\",\"course\":[\"數學\",\"國文\",\"基礎電學\",\"歷史\"]}  \nOutput: {\"course_type\":\"基礎電學\"}"
    ),
)

def request_llm(data: str, courses: List[str]) -> str:
    """Request to Gemini LLM."""
    chat_session = model.start_chat(history=[])
    request_json = {
        "input": data,
        "course": courses
    }
    response = json.loads(chat_session.send_message(str(request_json)).text)["course_type"]
    return response


# Input Model
class HomeworkRequest(BaseModel):
    line_data: str
    courses: List[str]


# Rate-limited endpoint

@app.post("/get-homework-type", response_class=JSONResponse)
@limiter.limit("1/second")
async def get_homework_type(
    request: Request,
    line_data: str = Form(...),  # Extract 'line_data' from form data
    courses: str = Form(...)     # Extract 'courses' from form data
):
    # Validate input
    if not line_data.strip() or not courses.strip():
        raise HTTPException(status_code=400, detail="Invalid input: line_data or courses cannot be empty.")

    # Process input
    datas = line_data.strip().split("\n")
    course_list = courses.strip().split(",")
    result = []

    for line in datas:
        line_result = request_llm(line, course_list)
        result.append(line_result)

    return {"result": result}


# Custom exception for rate limiting
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
