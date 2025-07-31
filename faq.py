import os
from pathlib import Path
from chromadb.utils import embedding_functions
from groq import Groq
import pandas as pd
from dotenv import load_dotenv
import chromadb

chromadb.api.client.SharedSystemClient.clear_system_cache()

load_dotenv()

faqs_path = Path(__file__).parent / "resources/faq_data.csv"


chroma_client = chromadb.PersistentClient(path='./chroma')

collection_name_faq = "faq"
groq_client = Groq(api_key="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")

ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def ingest_faq_data(path):
    if collection_name_faq not in [collection_name for collection_name in chroma_client.list_collections()]:
        print("Ingesting FAQ data into Chromadb...")
        collection = chroma_client.get_or_create_collection(
            name=collection_name_faq,
            embedding_function=ef
        )

        chromadb.api.client.SharedSystemClient.clear_system_cache()

        df = pd.read_csv(path)
        docs = df['question'].to_list()
        metadata = [{"answer": ans} for ans in df["answer"].to_list()]
        ids = [f"id_{i}" for i in range(len(docs))]

        collection.add(
            documents=docs,
            metadatas=metadata,
            ids=ids
        )
        print(f"FAQ data successfully ingested into Chroma collections: {collection_name_faq}")

    else:
        print(f"Collection {collection_name_faq} already exists")


def get_relevant_qa(query):
    collection = chroma_client.get_collection(
        name=collection_name_faq,
        embedding_function=ef
    )

    chromadb.api.client.SharedSystemClient.clear_system_cache()

    result = collection.query(
        query_texts=[query],
        n_results=2
    )

    return result


def generate_answer(query, context):
    prompt = f'''Given the question and context below, generate the answer based on the context only.
    If you don't find the answer inside the context then say "I don't know".
    Do not make things up.

    'QUESTION: {query}

    CONTEXT: {context}
    '''

    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        model=os.environ['GROQ_MODEL']
    )

    return chat_completion.choices[0].message.content


def faq_chain(query):
    result = get_relevant_qa(query)
    context = ''.join([r.get('answer') for r in result['metadatas'][0]])
    answer = generate_answer(query, context)

    return answer


if __name__ == "__main__":
    ingest_faq_data(faqs_path)
    query = "Do you take cash as payment option?"
    # result = get_relevant_qa(query)
    answer = faq_chain(query)
    print(answer)
