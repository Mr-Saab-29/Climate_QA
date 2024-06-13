# -*- coding: utf-8 -*-
"""Mini_RAG_QA.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Ih_diqTDv6B1BV6DpoqTtoe1OHL6PexW
"""

#Mounting the google drive
from google.colab import drive
drive.mount('/content/drive')

"""# Install libraries"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install langchain gtts langchain-community  gradio sentence-transformers tiktoken langchain-groq faiss-gpu -q

"""# Import libraries"""

import shutil
import pickle
import tempfile
from operator import itemgetter
import time
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import gradio as gr

from gtts import gTTS
from IPython.display import Audio

import os
import yaml
from tqdm import tqdm
from langchain.prompts.prompt import PromptTemplate
from typing import Tuple, List
from langchain.schema.runnable import RunnableMap
from langchain.schema import format_document
from datetime import datetime
from operator import itemgetter
from langchain.memory import ConversationBufferMemory

from langchain.document_loaders import DataFrameLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.vectorstores import FAISS
from langchain.schema import Document, HumanMessage, BaseMessage
from langchain.schema.chat_history import BaseChatMessageHistory
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.base import AsyncCallbackHandler, BaseCallbackManager
from langchain.globals import set_llm_cache

from langchain_groq import ChatGroq

from transformers import pipeline

"""# Define some functions"""

#Function to combine documents
def _combine_documents(
    docs, document_prompt, document_separator="\n\n"
):
    doc_strings = [
        f"Document {i}: \n'''\n{format_document(doc, document_prompt)}\n'''"
        for i, doc in enumerate(docs, 1)
    ]
    return document_separator.join(doc_strings)

#Funcition to format the chat history
def _format_chat_history(chat_history: List[Tuple]) -> str:
    turn = 1
    buffer = []
    for dialogue in chat_history:
        buffer.append(("Human: " if turn else "Assistant: ") + dialogue.content)
        turn ^= 1
    return "\n".join(buffer) + "\n"


#Pairing function
def make_pairs(lst):
    """from a list of even lenght, make tupple pairs"""
    return [(lst[i], lst[i + 1]) for i in range(0, len(lst), 2)]


#Generate html source
def make_html_source(i, doc):
    return f"""
<div class="card">
  <div class="card-content">
      <h3>Doc {i}</h2>
      <p>{BeautifulSoup(doc.page_content, 'html.parser')}</p>
  </div>
  <div class="card-footer">
    <span>page: {doc.metadata['page_number']}</span>
  </div>
</div>
"""

#Text to speech using Google text to speech API
def create_audio(text):
  tts = gTTS(text=text, lang='en')
  # Save the generated audio to a temporary file
  with tempfile.NamedTemporaryFile(delete=False) as f:
      tts.save(f.name)
      audio_path = f.name
  return audio_path

#Speech to Text using Open AI whishper model
def transcribe(audio):
    sr, y = audio
    y = y.astype(np.float32)
    y /= np.max(np.abs(y))

    return transcriber({"sampling_rate": sr, "raw": y})["text"]

#chat definition
async def chat(
    query: str,
    input_audio,
    history: list = [],
):
    if (input_audio):
      query = transcribe(input_audio)
    """taking a query and a message history, use a pipeline (reformulation, retriever, answering) to yield a tuple of:
    (messages in gradio format, messages in langchain format, source documents)"""
    source_string = ""
    gradio_format = make_pairs([a.content for a in history]) + [(query, "")]
    audio_path = "./test" # will try to play this path in every step so can't leave it blank, should find another solution

    # reset memory
    memory.clear()
    for message in history:
        memory.chat_memory.add_message(message)

    inputs = {"question": query}
    result = final_chain.astream_log({"question": query})

    reformulated_question_path_id = "/logs/ChatGroq/streamed_output_str/-"
    retriever_path_id = "/logs/Retriever/final_output"
    final_answer_path_id = "/logs/ChatGroq:2/streamed_output_str/-"

    async for op in result:
        op = op.ops[0]
        if op["path"] == reformulated_question_path_id:  # reforulated question
            new_token = op["value"]  # str

        elif op["path"] == retriever_path_id:  # documents
            sources = op["value"]["documents"]  # List[Document]
            source_string = "\n\n".join(
                [make_html_source(i, doc) for i, doc in enumerate(sources, 1)]
            )

        elif op["path"] == final_answer_path_id:  # final answer
            new_token = op["value"]  # str
            answer_yet = gradio_format[-1][1]
            gradio_format[-1] = (query, answer_yet + new_token)

        yield "", gradio_format, history, source_string, audio_path

    memory.save_context(inputs, {"answer": gradio_format[-1][1]})
    audio_path = create_audio(answer_yet + new_token)
    yield "", gradio_format, memory.load_memory_variables({})["history"], source_string, audio_path

"""# Define global params"""

demo_name = "ClimateQA"

# Put your token from https://console.groq.com/keys
os.environ["GROQ_API_KEY"] = ""

"""# Treat data

## Load and prepare parsed data
"""

documents = []
path_data = "/content/drive/MyDrive/Data" # Adapt accordingly

for file in tqdm(os.listdir(path_data)):
  df = pd.read_parquet(os.path.join(path_data, file))
  df = df[df["sub_type"] == "Text"]
  df = df[["content", "file_name", "page_number"]]
  loader = DataFrameLoader(df, page_content_column="content")
  text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=256, chunk_overlap=50, length_function=lambda x: len(x.split())
  )

  docs = loader.load_and_split(text_splitter)
  documents.extend(docs)

"""## Get embeddings, vectorstore and retriever"""

model_name = "BAAI/bge-small-en"
encode_kwargs = {'normalize_embeddings': True} # set True to compute cosine similarity
print("Loading embeddings model: ", model_name)
embeddings = HuggingFaceBgeEmbeddings(
    model_name=model_name,
    encode_kwargs=encode_kwargs,
    query_instruction="Represent this sentence for searching relevant passages: "
)

# Around 3mins with GPU enabled
vectorstore = FAISS.from_documents(
    documents, embedding=embeddings,
)

retriever = vectorstore.as_retriever()

retriever.invoke("What is climate change ?")

"""## Get LLM from Groq"""

chat_model = ChatGroq(temperature=0, model_name="llama3-8b-8192") # llama3-70b-8192 / mixtral-8x7b-32768

"""## Create a prompt"""

reformulation_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question, in its original language.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""

CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(reformulation_template)

answering_template = """
  You are ClimateQ&A, an AI Assistant created by Ekimetrics. You are given a question and extracted passages of the IPCC and/or IPBES reports. Provide a clear and structured answer based on the passages provided, the context and the guidelines.

  Guidelines:
  - If the passages have useful facts or numbers, use them in your answer.
  - When you use information from a passage, mention where it came from by using [Doc i] at the end of the sentence. i stands for the number of the document.
  - Do not use the sentence 'Doc i says ...' to say where information came from.
  - If the same thing is said in more than one document, you can mention all of them like this: [Doc i, Doc j, Doc k]
  - Do not just summarize each passage one by one. Group your summaries to highlight the key parts in the explanation.
  - If it makes sense, use bullet points and lists to make your answers easier to understand.
  - You do not need to use every passage. Only use the ones that help answer the question.
  - If the documents do not have the information needed to answer the question, just say you do not have enough information.
  - Consider by default that the question is about the past century unless it is specified otherwise.
  - If the passage is the caption of a picture, you can still use it as part of your answer as any other document.

  -----------------------
  Passages:
  {context}

  -----------------------
  Question: {question}
  Answer with the passages citations:
  """

ANSWER_PROMPT = ChatPromptTemplate.from_template(answering_template)

DEFAULT_DOCUMENT_PROMPT = PromptTemplate.from_template(template="{page_content}.\page: {page_number}")

"""## Chain some functions"""

memory = ConversationBufferMemory(
    return_messages=True, output_key="answer", input_key="question"
)

# First we add a step to load memory
# This adds a "memory" key to the input object
loaded_memory = RunnablePassthrough.assign(
    chat_history=RunnableLambda(memory.load_memory_variables) | itemgetter("history"),
)

# Now we calculate the standalone question
standalone_question = {
    "standalone_question": {
        "question": lambda x: x["question"],
        "chat_history": lambda x: _format_chat_history(x["chat_history"]),
    }
    | CONDENSE_QUESTION_PROMPT
    | chat_model
    | StrOutputParser(),
}

# Now we retrieve the documents
retrieved_documents = {
    "docs": itemgetter("standalone_question") | retriever,
    "question": lambda x: x["standalone_question"],
}

# Now we construct the inputs for the final prompt
final_inputs = {
    "context": lambda x: _combine_documents(x["docs"], DEFAULT_DOCUMENT_PROMPT),
    "question": itemgetter("question")
}

# And finally, we do the part that returns the answers
answer = {
    "answer": final_inputs | ANSWER_PROMPT | chat_model,
    "docs": itemgetter("docs"),
}

# And now we put it all together!
final_chain = loaded_memory | standalone_question | retrieved_documents | answer

#pipeline defintion to use the whisper base model
transcriber = pipeline("automatic-speech-recognition", model="openai/whisper-base.en")

"""# Setup your Gradio

## Get CSS styling
"""

with open("/content/style copy_green.txt", "r") as f:# maybe path need to be adapted
    css = f.read()

"""## Create your app"""

with gr.Blocks(title=f"{demo_name}", css=css) as demo:
    gr.Markdown(f"<h1><center>{demo_name}</center></h1>")

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                elem_id="chatbot", label=f"{demo_name} chatbot", show_label=False
            )
            state = gr.State([])

            with gr.Row(elem_id="audio-container"):
              ask = gr.Textbox(
                  show_label=False,
                  placeholder="Input your question then press enter",
              )
            with gr.Row(elem_id="audio-container"):
              input_audio = gr.Audio(sources=["microphone"])

        with gr.Column(scale=1, variant="panel"):
            gr.Markdown("### Sources")
            sources_textbox = gr.Markdown(show_label=False)


        with gr.Row(elem_id="audio-container"):
          audio = gr.Audio(
            type='filepath',
            autoplay=False,
            visible=True,
        )



        ask.submit(
            fn=chat,
            inputs=[
                ask,
                input_audio,
                state,
            ],
            outputs=[ask, chatbot, state, sources_textbox, audio],
        )


demo.launch(
    share=True,
    # auth=("", ""),
    debug=True
)
