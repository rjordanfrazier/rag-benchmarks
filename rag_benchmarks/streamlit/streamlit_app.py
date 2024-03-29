import os
import streamlit as st
from dotenv import load_dotenv

from langchain.schema import Document

from rag_benchmarks.ingestion.load import load_dataset
from rag_benchmarks.ingestion.chunking import token_text_split
from rag_benchmarks.ingestion.embeddings import open_ai_embeddings
from rag_benchmarks.ingestion.storage.astradb import initialize_astra_db
from rag_benchmarks.retrieval.chains import as_retriever, basic_chat_with_memory
from rag_benchmarks.generation.models import chat_open_ai

@st.cache_data
def load_env_vars():
    load_dotenv()

def initialize_streamlit_app():
    title = "Chat with philosophy AI AriBotle: powered by RAGStacks"
    st.set_page_config(
        page_title=title,
        layout="centered",
        initial_sidebar_state="auto",
        menu_items=None,
    )

    load_env_vars()

    st.title(title)
    # st.info(
    #     "TODO:",
    # )

    if "messages" not in st.session_state.keys():
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Ask me a question about philosophy!",
            }
        ]

    if "chat_engine" not in st.session_state.keys():
        vstore = load_data()

        retriever = as_retriever(vstore)
        model = chat_open_ai()

        prompt = """
        You are a philosopher that draws inspiration from great thinkers of the past
        to craft well-thought answers to user questions. Use the provided context as the basis
        for your answers and do not make up new reasoning paths - just mix-and-match what you are given.
        Your answers must be concise and to the point, and refrain from answering about other topics than philosophy.
        """

        print(f"Initializing model with prompt:\n{prompt}")
        chain = basic_chat_with_memory(retriever, model, prompt)
        st.session_state.chat_engine = chain

    if question := st.chat_input("Your question: "):
        st.session_state.messages.append({"role": "user", "content": question})

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if st.session_state.messages[-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            with st.spinner("Pondering..."):
                response = st.session_state.chat_engine.invoke(question)
                st.write(response["answer"])
                message = {"role": "assistant", "content": response["answer"]}
                st.session_state.messages.append(message)


@st.cache_resource(show_spinner=False)
def load_data():
    with st.spinner(text="Loading and indexing"):
        # Ingestion
        dataset = load_dataset("datastax/philosopher-quotes", split="train")
        documents = []
        for entry in dataset:
            metadata = {"author": entry["author"]}
            doc = Document(page_content=entry["quote"], metadata=metadata)
            documents.append(doc)

        # Chunking
        split_documents = token_text_split(documents, chunk_size=1028, chunk_overlap=64)

        # Storage / Embedding
        # collection = input("Collection: ")
        collection = "test"
        embedding = open_ai_embeddings()
        token = os.environ["ASTRA_DB_APPLICATION_TOKEN"]
        api_endpoint = os.environ["ASTRA_DB_API_ENDPOINT"]

        vstore = initialize_astra_db(collection, embedding, token, api_endpoint)
        print(f"Adding {len(split_documents)} documents to AstraDB...")
        vstore.add_documents(split_documents)
        return vstore


initialize_streamlit_app()
