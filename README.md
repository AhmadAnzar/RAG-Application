# EasyLM RAG App

EasyLM is a document question answering app built as a simple NotebookLM style RAG system.

A user can upload a file, the app processes the content, stores it in a vector database, and then answers questions using the most relevant retrieved chunks.

## What the app does

The app supports these flows:

- Upload a PDF file
- Upload a CSV file
- Paste plain text into the app
- Chunk the content
- Create embeddings for the content
- Store the embeddings in Qdrant
- Retrieve the most relevant chunks for a question
- Generate an answer from the retrieved context
- Show source citations under assistant answers

## Project structure

- backend: FastAPI server that handles upload, indexing, and question answering
- frontend: React and Vite user interface

## Requirements

You need these before running the app:

- Python 3.10 or later
- Node.js 18 or later
- A Qdrant account or Qdrant instance
- A GitHub token for the OpenAI compatible model access used by the backend

## Backend setup

Go to the backend folder and install the Python dependencies used by the project.

Set these environment variables before starting the backend:

- GITHUB_TOKEN
- QDRANT_URL
- QDRANT_API_KEY
- QDRANT_COLLECTION, if you want a custom collection name

Then start the backend server from the backend folder.

The backend runs on port 8000 by default.

## Frontend setup

Go to the frontend folder and install the Node dependencies.

Then start the frontend development server from the frontend folder.

The frontend runs on port 5173 by default.

## How to use the app

1. Open the frontend in your browser.
2. Upload a file or paste text.
3. Wait for the content to be processed and indexed.
4. Ask a question about the uploaded content.
5. Read the answer and check the source citations.

## Supported input

The app currently supports:

- PDF files
- CSV files
- Plain text pasted into the app

## Notes

- The app uses Qdrant for vector storage and retrieval.
- The backend uses retrieved chunks when generating answers.
- The app is designed to answer from the uploaded content, not from general model memory alone.
- If a required environment variable is missing, the backend may not be able to complete uploads or query requests.

## Assignment fit

This project matches the main goals of the assignment:

- A user can upload a document
- The system chunks, embeds, stores, retrieves, and answers questions
- Answers are grounded in retrieved document content
- The app works with new files it has not seen before

