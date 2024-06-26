from flask import Flask, request, jsonify, render_template
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from sklearn.metrics.pairwise import cosine_similarity
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_pinecone import PineconeVectorStore
import os
import shutil
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate
from pinecone import Pinecone
from pinecone.exceptions import PineconeException
import time
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv
from pinecone import Pinecone, PineconeException

app = Flask(__name__)
load_dotenv()

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Initialize OpenAI and Pinecone
embeddings = OpenAIEmbeddings()
model = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model="gpt-3.5-turbo")
parser = StrOutputParser()

template = """
Answer the question based on the context below. If you can't 
answer the question, reply "I don't know".

Context: {context}

Question: {question}
"""

prompt = ChatPromptTemplate.from_template(template)

# Paths to documents
DATA_PATH1 = "fallout_content/PDFs"
DATA_PATH2 = "fallout_content/Nukapedia"
DATA_PATH3 = "fallout_content/YouTube_oxhorn"
DATA_PATH4 = "fallout_content/YouTube_spanish"


# Load documents from directory
def load_documents(path, extension):
    loader = DirectoryLoader(path, glob=extension)
    return loader.load()


def split_text(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks.")
    return chunks


def generate_data():
    documents = load_documents(DATA_PATH2, "*.txt")
    documents += load_documents(DATA_PATH1, "*.pdf")
    documents += load_documents(DATA_PATH3, "*.txt")
    documents += load_documents(DATA_PATH4, "*.txt")
    chunks = split_text(documents)
    return chunks


chunks = generate_data()

try:
    pinecone = Pinecone(api_key=PINECONE_API_KEY, timeout=60)
    index_name = "fallout2"
    index = PineconeVectorStore.from_documents(
        chunks, embeddings, index_name=index_name
    )
    print(f"Successfully indexed documents in {index_name}")
except PineconeException as e:
    print(f"An error occurred with Pinecone: {e}")
    index = None
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    index = None

chain = (
    {"context": index.as_retriever(), "question": RunnablePassthrough()}
    | prompt
    | model
    | parser
)


@app.route("/")
def home():
    print("Hello")
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    user_question = request.form["question"]
    if user_question.lower() == "exit":
        return jsonify({"response": "Exiting the question loop. Goodbye!"})
    response = chain.invoke(user_question)
    return jsonify({"response": response})


if __name__ == "__main__":
    app.run(debug=True)
