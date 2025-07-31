# E-Commerce Chatbot  
### GenAI RAG Project using LLaMA 3.3 & GROQ API

This project is a proof-of-concept (PoC) for an intelligent, retrieval-augmented chatbot tailored for e-commerce platforms. It provides context-aware, real-time responses by identifying user intent and integrating with a live product database. Powered by LLaMA 3.3 via GROQ.

---

## Folder Structure

| Folder         | Description                                                   |
|----------------|---------------------------------------------------------------|
| `app/`         | Main chatbot logic, Streamlit UI, and intent-handling modules |
| `web-scraping/`| Scripts for scraping product data from e-commerce websites    |

---

## Supported Intents

The chatbot supports the following intent types:

- **FAQ**  
  Answers questions related to platform policies or general info.  
  Example: `Is online payment available?`

- **SQL Query**  
  Extracts and filters product data from the database.  
  Example: `Show me all Nike shoes below Rs. 3000.`

- **Small Talk**  
  Handles casual user messages.  
  Example: `How are you?`

---

## Screenshots

**Product Query Result**  
![Product Screenshot](app/resources/product-ss.png)

**Architecture Diagram**  
![Architecture Diagram](app/resources/architecture-diagram.png)

---

## Setup & Execution

### 1. Install Dependencies

```bash
pip install -r app/requirements.txt
