# Stock Market Application & AI News Auto-Categorization System

An enterprise-grade stock market data crawling and analysis platform for the Nepal Stock Exchange (NEPSE), built with Django REST Framework, PostgreSQL, Celery + Redis, Scrapy, and React + Vite.

---

## 🚀 Key Features

* **Multi-Source Scrapy Crawlers**: Automated extraction of company financials, stock prices, floorsheet transactions, and market news from leading financial portals (Sharesansar, Merolagani, Bizmandu, Arthakhabar, FiscalNepal, NepseAlpha).
* **AI/ML News Auto-Categorization**: Hybrid architecture combining sentence embeddings (`SentenceTransformers`), cosine similarity, deterministic entity/alias matching, and independent multi-label confidence scoring.
* **Celery Background Processing**: Heavy ML inference and crawling run asynchronously without blocking synchronous REST API calls or Scrapy spider parsing loops.
* **Analyst Manual Review & Audit Trail**: Full capability for market analysts to correct, add, or update company tags, preserving manual precedence and persisting an unalterable audit log.
* **Strict Role-Based Access Control (RBAC)**: Enforced server-side permissions for `ADMIN`, `ANALYST`, and `VIEWER` roles.
* **Modern React Dashboard**: Real-time ticker feeds, interactive charts, news review queues, confidence gauges, and categorization correction controls.

---

## 🧠 Automatic News Categorization Architecture

### 1. Why Semantic Categorization?
Financial news articles often discuss companies using descriptive phrases, partial names, or indirect contextual references (e.g., "The leading commercial bank in Durbar Marg posted 35% profit surge"). A purely keyword-based system misses synonym variations and contextual nuances. Semantic embeddings capture the dense semantic meaning of both the news article and company profiles.

### 2. Why Multi-Label Classification?
A single financial news article frequently concerns multiple companies simultaneously. For example:
> *"Nabil Bank and NIC Asia report higher quarterly earnings following joint ATM integration."*

Single-label classification (`max(scores)`) would arbitrarily discard one company. Our system evaluates **every company in the watchlist independently**, allowing an article to receive tags for all companies exceeding the confidence threshold.

### 3. Why Embeddings Were Chosen
We utilize `SentenceTransformers` (`all-MiniLM-L6-v2`), a lightweight (384-dimensional dense vectors, ~80MB) open-source transformer model. It produces rich contextual representations of articles and company profiles quickly on standard CPU infrastructure without costly external API dependencies.

### 4. Why Keyword / Entity Matching is Also Used
Embeddings can sometimes generate false positives for companies in the same sector (e.g., confusing one commercial bank with another). Deterministic entity matching evaluates exact ticker symbols (`NABIL`), canonical names (`Nabil Bank Limited`), and configured aliases (`Nabil Bank`, `Nabil`) using regex word boundaries (`(?<!\w)term(?!\w)`). This provides a hard deterministic signal.

### 5. Why a Hybrid Approach Was Selected
The hybrid approach balances strengths and eliminates weaknesses:
* **Lexical matching** provides high precision and explainability when names/symbols are present.
* **Semantic embeddings** capture context, sector semantics, and thematic relevance.
* **Combined heuristic score**:
$$\text{Confidence Score} = w_{\text{embedding}} \times \text{CosineSimilarity} + w_{\text{lexical}} \times \text{LexicalScore}$$
* Default weights: `EMBEDDING_WEIGHT = 0.60`, `KEYWORD_WEIGHT = 0.40` (configurable in Django settings).

### 6. Cosine Similarity Comparison
Cosine similarity measures the angular similarity between the normalized article embedding $\vec{u}$ and company profile embedding $\vec{v}$:
$$\text{CosineSimilarity}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$$
Clipped to $[0.0, 1.0]$.

### 7. Confidence Score Interpretation
> **Important Note on Confidence**: The confidence score is a normalized heuristic classification score derived from lexical and semantic evidence. It is used for ranking and thresholding, not as a statistically calibrated probability.

### 8. Configurable Threshold
The multi-label threshold is configurable:
* `CATEGORIZATION_THRESHOLD = 0.65` (default)
* Evaluated per company:
  * $\text{NABIL} = 0.95 \ge 0.65 \implies \text{TAGGED}$
  * $\text{NICA} = 0.91 \ge 0.65 \implies \text{TAGGED}$
  * $\text{NLIC} = 0.28 < 0.65 \implies \text{EXCLUDED}$
* If no company meets the threshold, the article remains untagged (`needs_review=True`).

### 9. Why FAISS / Vector Database Was NOT Used
The project tracks a focused watchlist of 5–10 companies. Performing exact cosine similarity against 5–10 cached NumPy vectors takes **< 0.1 milliseconds** in Python. Introducing FAISS, Pinecone, or Milvus would add unnecessary infrastructure complexity without measurable benefit.

### 10. Manual Correction & Precedence
Market Analysts and Admins can override, add, or remove tags through the REST API (`POST /api/news/:id/recategorize/`) or the frontend interface.
* **Manual Precedence Rule**: Manual corrections (`is_manual=True`) have 100% precedence and are **NEVER overwritten or removed** by subsequent automatic background categorization tasks.

### 11. Correction Audit Trail
Every manual action creates an unalterable record in `CategorizationCorrection`:
* `article_id`
* `company_id`
* `action` (`add`, `remove`, `update`)
* `previous_confidence` / `new_confidence`
* `previous_method` / `new_method`
* `reason` (mandatory explanation from the analyst)
* `corrected_by` (authenticated user)
* `corrected_at` (timestamp)

---

## ⚖️ Trade-offs & Limitations

| Approach | Advantages | Limitations |
| :--- | :--- | :--- |
| **Keyword Matching** | Fast, deterministic, explainable, exact. | Misses synonyms, insensitive to context, alias dependent. |
| **Embeddings** | Understands semantics, handles rephrasings, robust to variations. | Can generate sector false positives, requires threshold tuning. |
| **Hybrid System** | Best balance of precision and recall, explainable confidence breakdown. | Heuristic weights require tuning for specific domains. |

---

## 🛠️ Technology Stack

* **Backend**: Django 5.1, Django REST Framework, SimpleJWT
* **Database**: PostgreSQL
* **Task Queue**: Celery 5.4 + Redis
* **Scraping**: Scrapy 2.12 + Twisted
* **AI/ML**: `sentence-transformers`, `torch`, `scikit-learn`, `numpy`
* **Frontend**: React 18, Vite, TypeScript, TailwindCSS, Lucide Icons

---

## 🧪 Running Automated Tests

Run the full categorization test suite:
```powershell
Backend\venv\Scripts\python.exe Backend\manage.py test apps.news
```

Run Django system check:
```powershell
Backend\venv\Scripts\python.exe Backend\manage.py check
```

---

## 📦 API Endpoints

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/news/` | List news with company, sentiment, search, and needs_review filters | All |
| `GET` | `/api/news/:id/` | Retrieve article details and multi-label tags | All |
| `POST` | `/api/news/:id/recategorize/` | Manually add/update/remove company tags with audit reason | Analyst, Admin |
| `POST` | `/api/news/:id/trigger-categorize/` | Trigger asynchronous Celery categorization for an article | Analyst, Admin |
| `GET` | `/api/news/corrections/` | Audit log of categorization corrections | All |
| `GET` | `/api/news/stats/` | News categorization distribution metrics | All |
