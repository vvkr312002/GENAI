# YouTube Video QA Extension

This project uses your YouTube transcript QA idea as the backend logic.

## What it does
- Opens on a YouTube video
- Builds a transcript-based FAISS index
- Answers questions from that video's transcript
- Includes a quick summary button that just asks: "Can you summarize the video?"

## Backend setup
1. Create a virtual environment
2. Install dependencies:
   pip install -r requirements.txt

3. Create a `.env` file from `.env.example`
4. Add your OpenAI API key
5. Start the backend:
   uvicorn app:app --reload --port 8000

## Load extension
1. Open Chrome or Brave
2. Go to chrome://extensions or brave://extensions
3. Enable Developer Mode
4. Click Load unpacked
5. Select this folder

## Notes
- The extension calls the backend at http://localhost:8000
- It answers from transcript context, not from general web knowledge
