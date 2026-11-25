# Sentinel-X
### AI-Powered Cybersecurity Alert Prioritization and Analysis

Sentinel-X is a network intrusion detection and security-analysis prototype. It analyses uploaded network-flow records, predicts benign or malicious traffic and attack types, calculates a risk score, ranks records for investigation, generates explanations, and provides a retrieval-augmented chatbot for questions about the analysed dataset.

> **Implementation note:** The source implementation in this repository is a Google Colab notebook. The Gradio interface is created and launched from the notebook; this repository does not contain a separate `app.py` service.

---

## Key capabilities

- **Multiclass intrusion detection:** LightGBM classifier trained on CIC-IDS2017 network-flow features.
- **Risk assessment:** Estimates malicious probability and probability-weighted expected attack severity.
- **Threat prioritization:** Assigns risk categories and ranks flows by risk score.
- **Explainability:** Produces traffic-indicator explanations and feature contributions for up to 300 high-risk records.
- **Hybrid RAG retrieval:** Combines BM25 keyword retrieval and FAISS vector retrieval using Reciprocal Rank Fusion (RRF).
- **AI security assistant:** Uses a Groq-hosted language model to rewrite queries and answer from retrieved evidence.
- **Gradio dashboard:** Provides upload and analysis, charts, a filterable risk-ranking table, chatbot and CSV export.

The system is an analyst-assistance and prioritization tool. It does **not** automatically block IP addresses, terminate network connections, or remediate devices.

---

## Architecture and workflow

### Phase 1 — Dataset preparation and model training

1. Download the Kaggle dataset `chethuhn/network-intrusion-dataset` using Kaggle API credentials.
2. Clean labels and column names; convert features to numeric values.
3. Replace infinite values, remove missing rows and duplicates, and cast features to `float32`.
4. Encode the attack labels and create a stratified 70% training, 10% validation and 20% test split.
5. Cap the training sample at 30,000 records per class and calculate class weights.
6. Train a multiclass LightGBM model with early stopping.
7. Optionally train five fold models and compare their performance with the single model.
8. Tune the malicious-probability threshold on validation data.
9. Compare candidates on a sampled held-out test set and select the deployed model.
10. Save the model bundle and a demo flow file under `sentinelx_artifacts/`.

**Validation detail:** In the notebook's optional five-fold procedure, each fold model is evaluated on the same validation sample. This is not conventional out-of-fold validation.

### Phase 2 — Network traffic analysis and risk prioritization

1. Upload a CSV or Parquet network-flow file through Gradio, or use the generated demo file.
2. Align the uploaded columns with the model's expected feature columns.
3. Convert features to numeric values and replace invalid or missing values with zero.
4. Run batch predictions using the saved LightGBM model.
5. Calculate malicious probability:

   `P(malicious) = 1 - P(BENIGN)`

6. Predict the most likely attack class for flows classified as malicious.
7. Calculate probability-weighted expected severity and risk score:

   `Risk = 100 × P(malicious) × (0.35 + 0.65 × expected_severity)`

   The severity values are normalized to the 0–1 range for this calculation.

8. Assign categories:
   - Critical: score >= 85
   - High: score >= 65
   - Medium: score >= 40
   - Low: score >= 15
   - Informational: score < 15
9. Rank records by risk score.
10. Generate traffic indicators and feature-contribution explanations for up to 300 highest-risk records.
11. Generate dataset summaries, charts and a downloadable risk table.

### Phase 3 — RAG knowledge-base creation

The notebook creates documents from the analysis output, including:

- Dataset overview and risk statistics.
- Per-attack-type summaries, indicators and suggested actions.
- Risk-category summaries.
- Destination-port summaries.
- Selected individual network-flow records.

It then creates:
- MiniLM embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
- A BM25 keyword index.
- A FAISS vector index using normalized embeddings.

### Phase 4 — Chatbot question answering

1. The user asks a question in the Gradio chatbot.
2. The question is rewritten into a retrieval-friendly query using the Groq LLM, with a rule-based fallback.
3. BM25 and FAISS retrieve documents in parallel.
4. Reciprocal Rank Fusion combines the rankings (`k = 60`).
5. The dataset overview and up to eight retrieved documents are included as evidence.
6. The LLM generates an answer grounded in the retrieved context.
7. The chatbot displays source IDs and the rewritten search query.

**LLM configured in the uploaded notebook:** `openai/gpt-oss-120b` through Groq. This README reflects the uploaded code, rather than an earlier proposed model name.

### Phase 5 — Gradio application output

The interface contains:

- **Upload & Analyze:** Upload CSV/Parquet files, run analysis, view summary charts and top-risk records, and download the CSV.
- **Risk Ranking Table:** Filter by risk category, predicted type, minimum risk score and destination port; choose sorting and row count.
- **Chatbot:** Ask natural-language questions about the analysed dataset.
- **About & Metrics:** View model information, test metrics and limitations.

---

## Repository structure

```text
Sentinel-X/
├── README.md
├── SentinelX.ipynb
├── requirements.txt
├── .gitignore
└── .env.example
```

The notebook generates its runtime artifacts in `sentinelx_artifacts/`, including:

- `sentinelx_model.joblib`
- `demo_flows.csv`
- `demo_flows.parquet`
- `sentinelx_risk_table.csv`

These generated files are excluded from Git by default. They are created when the notebook is executed.

---

## Setup and execution

### Recommended environment: Google Colab

The notebook uses Google Colab paths and Colab's file/secret interfaces. Google Colab is the intended execution environment for the uploaded notebook.

1. Open [Google Colab](https://colab.research.google.com/).
2. Upload `SentinelX.ipynb` from this repository.
3. In Colab, open **Secrets** and add:
   - Name: `GROQ_API_KEY`
   - Value: your Groq API key
   - Enable notebook access to the secret.
4. Obtain a Kaggle API token:
   - Sign in to [Kaggle](https://www.kaggle.com/).
   - Open your account settings and create/download an API token (`kaggle.json`).
   - When prompted by the notebook, upload `kaggle.json`.
   - Do not commit this token to GitHub.
5. Run the notebook cells from top to bottom.
6. The notebook downloads the configured Kaggle dataset, preprocesses it, trains/evaluates the model, saves the model bundle and demo data, builds the RAG index, and launches the Gradio interface.
7. Use the generated Gradio link to open the interface. Keep the Colab runtime running while using it.

The notebook also contains installation commands for some packages. If running in a fresh Colab runtime, install the repository dependencies first:

```bash
!pip install -r requirements.txt
```

### Groq API key

The notebook first checks Colab Secrets for `GROQ_API_KEY`, then checks the environment variable of the same name. If no key is configured, the non-LLM analysis can still run, but query rewriting and generated chatbot answers will use the notebook's fallback behaviour.

Never paste an API key into notebook source code or commit it to GitHub.

---

## Requirements

The main Python dependencies are listed in [`requirements.txt`](requirements.txt). The notebook uses:

- Python scientific stack: NumPy, pandas, Matplotlib
- Machine learning: LightGBM, scikit-learn, Joblib
- RAG: sentence-transformers, FAISS CPU, rank-bm25
- LLM access: Groq Python SDK
- Interface: Gradio
- Data support: PyArrow and Kaggle API

A GPU is not required by the notebook, although embedding and model operations may run faster with suitable hardware.

---

## Dataset

The notebook downloads the dataset configured in its source:

- Kaggle dataset: [`chethuhn/network-intrusion-dataset`](https://www.kaggle.com/datasets/chethuhn/network-intrusion-dataset)
- Dataset family: CIC-IDS2017 network traffic.

You must comply with the dataset provider's terms and any applicable research/data-use conditions. The dataset is not included in this repository.

---

## Important implementation details

- The classifier is a **LightGBM multiclass model**; the chatbot LLM is a separate component.
- Risk scores are model-derived estimates, not proof that a real attack occurred.
- The chatbot retrieves from generated summaries and selected records; it does not search every original flow directly.
- The notebook samples up to 300,000 held-out test flows for candidate comparison.
- The notebook includes a Friday/day-held-out diagnostic to illustrate performance when traffic differs from the random training split.
- The model was trained on 2017 lab traffic. Performance on modern or unseen network environments may differ.
- Rare attack classes have limited examples, and unseen attacks may be detected less reliably.
- The chatbot's knowledge base contains summaries and selected records. Use the risk-ranking table or exported CSV for exact record-level inspection.
- The Gradio app uses in-memory, single-session state in the notebook. It is a project prototype, not a hardened multi-user production deployment.

---

## Security and GitHub hygiene

Before pushing the project:

- Never upload `kaggle.json`.
- Never upload Groq API keys, `.env` files or credentials.
- Do not commit downloaded datasets or generated model artifacts unless you have checked their size, redistribution rights and repository needs.
- Review notebook outputs before publishing; clear outputs if they contain credentials, private data, or large generated content.

---

## Project purpose

Sentinel-X brings together network intrusion detection, risk assessment, threat prioritization, explainability and retrieval-augmented security assistance in one notebook-driven prototype. It is designed to help a security analyst understand which network flows appear most suspicious, why they were flagged, and what actions may be worth investigating.

**Disclaimer:** Sentinel-X is a research/academic prototype. It should not be used as the sole basis for production security decisions or automatic incident response.
