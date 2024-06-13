# Mini-RAG Chatbot with Climate QA

This project showcases a Retrieval-Augmented Generation (RAG) chatbot designed with Climate QA as the base. The chatbot leverages advanced NLP models and libraries to provide accurate and efficient responses. 

## Table of Contents
- [Project Overview](#project-overview)
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Project Overview
The Mini-RAG chatbot is built to handle queries related to climate and environmental issues. It integrates various cutting-edge technologies to enhance its performance and user experience.

## Features
- Utilizes the llama3-8b-8192 model with Groq for powerful language understanding.
- Provides a user-friendly front end using Gradio.
- Implements FAISS for efficient similarity search and clustering of dense vectors.
- Incorporates Google Text-to-Speech for converting text responses to speech.
- Uses OpenAI Whisper base model for converting speech inputs to text.

## Technologies Used
- **[Groq](https://groq.com/)**: For deploying the llama3-8b-8192 model.
- **[Gradio](https://gradio.app/)**: For setting up the front end of the application.
- **[FAISS](https://github.com/facebookresearch/faiss)**: For similarity search and clustering of dense vectors.
- **[Google Text-to-Speech](https://cloud.google.com/text-to-speech)**: For converting text responses to speech.
- **[OpenAI Whisper](https://github.com/openai/whisper)**: For speech-to-text conversion.

## Installation
To install and run the project locally, follow these steps:

1. **Clone the repository**:
   ```sh
   git clone https://github.com/yourusername/mini-rag-chatbot.git
   cd mini-rag-chatbot

2. **Setup environment variables**:
     Create a .env file in the root directory of the project and add the necessary environment variables for Groq API Key and other configurations.

## Usage
To use the chatbot, open the provided Gradio interface in your browser. You can interact with the chatbot by typing or speaking your queries related to climate and environmental issues. The chatbot will respond with accurate information, utilizing the integrated technologies for text and speech processing.

## Contribution

## License

