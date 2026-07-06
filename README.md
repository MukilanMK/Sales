# Supply Chain Multi-Agent System

This project is an advanced, automated Supply Chain Management system powered by multiple AI agents. It intelligently manages inventory, sources suppliers, negotiates terms, and finalizes purchase orders with minimal human intervention.

The system features both a **Command-Line Interface (CLI)** and a **modern, glassmorphism-styled Web User Interface** built with Streamlit.

## Features

The system operates across three distinct stages, each managed by a specialized AI agent:

### 1. Inventory Management (Agent 1)
- Connects to a MongoDB database to read current inventory and historical sales data.
- Analyzes the data using a LangGraph workflow to predict and identify products that require replenishment.
- Outputs a detailed list of products to restock.

### 2. Supplier Sourcing (Agent 2)
- **Segmentation:** Groups the required replenishments into logical categories.
- **Outbound RFQs:** Automatically drafts and sends Request for Quotation (RFQ) emails to relevant suppliers for each category.
- **Inbound Quotes:** Monitors inbound replies, parses supplier quotes, and processes the proposed pricing.
- **Ranking:** Ranks the received quotes based on price and other factors to present the best options.

### 3. Compliance & Fulfillment (Agent 3)
- **Policy Evaluation:** Evaluates the top-ranked supplier's terms against your configured target policies (e.g., maximum advance payment, minimum return window, acceptable liability parties).
- **Automated Negotiation:** If a policy mismatch is detected, the agent can draft and send a counter-offer to the supplier, negotiating better terms.
- **Deal Finalization:** Once terms are accepted, the agent dispatches a formal Purchase Order (PO) to the supplier and sends rejection notices to the others.

## Project Structure

- `app.py`: The Streamlit web application featuring a rich, interactive UI for managing the agent workflows.
- `main.py`: The CLI script to run the multi-agent pipeline from the terminal.
- `agents/`: Contains the logic for the different AI agents.
  - `inventory_management/`: Agent 1 logic (LangGraph workflow).
  - `supplier_sourcing/`: Agent 2 logic.
  - `compliance_fulfillment/`: Agent 3 logic.
- `shared/`: Shared utilities and database connections (`shared/database.py`).
- `services/`: Helper services (e.g., email utilities).

## Requirements

The project relies on several key libraries:
- `streamlit` (for the web UI)
- `langgraph` & `langchain-core` (for agent workflows)
- `langchain-groq` & `groq` (for LLM integrations)
- `openai`
- `pymongo` (for database access)
- `pydantic`
- `python-dotenv`
- `fastapi` & `uvicorn`

## Setup and Installation

1. **Clone the repository.**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install streamlit  # Ensure streamlit is installed if not in requirements.txt
   ```
3. **Environment Variables:**
   Create a `.env` file in the root directory and add necessary API keys (e.g., OpenAI, Groq, MongoDB connection string, email credentials).

## Usage

### Web Interface (Streamlit)
To run the interactive web application with the beautiful UI:
```bash
streamlit run app.py
```
This will open a browser window where you can configure your sender details, set target policies, and step through the entire supply chain process visually.

### Command Line Interface
To run the pipeline directly from the terminal:
```bash
python main.py
```
You will be prompted to enter your details and target compliance policies, and you can guide the agents through the terminal menu.
