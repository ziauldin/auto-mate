import os
import logging
import traceback
import pandas as pd
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Product

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/diagnose_llm.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Read DATABASE_URL from your .env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:admin@localhost:5432/auto_chatbot_db"
)

# Create a sync engine & session for pandas loading
sync_engine = create_engine(DATABASE_URL.replace("+asyncpg", ""), echo=False)
SyncSession = sessionmaker(bind=sync_engine)

# Module-level cache
_data_cache = {
    "df": None,
    "vectorizer": None,
    "matrix": None
}

def _load_and_index_from_db():
    global _data_cache

    try:
        logger.info("Loading products from database")
        with SyncSession() as db:
            products = db.query(
                Product.id,
                Product.title,
                Product.details,
                Product.manufacturer,
                Product.price,
                Product.url
            ).all()

        df = pd.DataFrame(products, columns=[
            "id", "title", "details", "manufacturer", "price", "url"
        ])

        df["title"] = df["title"].str.replace(r'[^\w\s]', '', regex=True)
        df["details"] = df["details"].str.replace(r'[^\w\s]', '', regex=True)
        df["manufacturer"] = df["manufacturer"].str.replace(r'[^\w\s]', '', regex=True)

        df["price"] = pd.to_numeric(
            df["price"].str.replace(r'PKR\s*', '', regex=True).str.replace(',', '', regex=True),
            errors='coerce'
        ).astype(float)

        df["combined_text"] = (
            df["title"].fillna("") + " " +
            df["details"].fillna("") + " " +
            df["manufacturer"].fillna("")
        ).str.lower()

        vect = TfidfVectorizer(
            min_df=1,
            max_df=0.95,
            stop_words="english",
            ngram_range=(1, 3),
            max_features=10000,
            analyzer='word'
        )
        mat = vect.fit_transform(df["combined_text"])

        _data_cache["df"] = df
        _data_cache["vectorizer"] = vect
        _data_cache["matrix"] = mat

        logger.info(f"Indexed {mat.shape[0]} products, {mat.shape[1]} features.")

    except Exception:
        logger.error("Error loading/indexing products:\n" + traceback.format_exc())
        _data_cache = {"df": pd.DataFrame(), "vectorizer": None, "matrix": None}

def _extract_keywords(text):
    if not isinstance(text, str):
        logger.warning(f"_extract_keywords received non-string input: {type(text)}")
        return ""

    front_light_terms = [
        'front light', 'headlight', 'head lamp', 'light bulb', 'lighting issue',
        'dim light', 'flickering light', 'burnt-out bulb', 'halogen', 'LED',
        'light socket', 'bulb holder', 'light assembly', 'headlight assembly',
        'light switch', 'light cover', 'light trim', 'light bracket', 'light housing'
    ]

    additional_terms = [
        'check engine light', 'oil change', 'tire rotation', 'alignment', 'air filter',
        'brake pads', 'brake rotors', 'coolant', 'oil leak', 'battery terminal',
        'spark plugs', 'fuel filter', 'airbag', 'steering wheel', 'seatbelt',
        'wipers', 'windshield washer', 'battery charger', 'alternator belt',
        'oil pressure', 'temperature gauge', 'fuel gauge', 'tire pressure',
        'brake fluid', 'coolant level', 'air conditioning', 'heating system',
        'engine oil', 'engine coolant', 'engine air filter', 'engine spark plugs',
        'engine timing belt', 'engine water pump', 'engine oil pump', 'engine alternator',
        'engine starter', 'engine clutch', 'engine differential', 'engine catalytic converter',
        'engine oxygen sensor', 'engine mass airflow', 'engine throttle body', 'engine ignition coil',
        'engine fuel injector', 'engine turbocharger', 'engine supercharger', 'engine shock absorber',
        'engine strut', 'engine control arm', 'engine ball joint', 'engine tie rod', 'engine wheel bearing',
        'engine cv joint', 'engine serpentine belt', 'engine power steering', 'engine ac compressor',
        'engine heater core', 'engine thermostat', 'engine head gasket', 'engine piston',
        'engine crankshaft', 'engine camshaft', 'engine valve', 'engine cylinder head'
    ]

    text_lower = text.lower()
    keywords = [term for term in front_light_terms + additional_terms if term in text_lower]

    codes = re.findall(r'\b[pP]\d{4}\b', text)
    keywords.extend(codes)

    return " ".join(keywords)

def recommend_products(query: str, top_k: int = 5) -> list[dict]:
    if not isinstance(query, str):
        logger.error(f"[FATAL] recommend_products received non-string input: {type(query)} — {query}")
        return []

    logger.info(f"Recommending products for query: {query[:50]}")
    
    if _data_cache["df"] is None:
        _load_and_index_from_db()

    df = _data_cache["df"]
    vect = _data_cache["vectorizer"]
    mat = _data_cache["matrix"]

    if df.empty or vect is None or mat is None:
        logger.warning("Recommendation engine not ready or no data.")
        return []

    try:
        processed_query = _extract_keywords(query) + " " + query.lower()
        qv = vect.transform([processed_query])

        sims = cosine_similarity(qv, mat).flatten()
        top_idxs = sims.argsort()[:-top_k - 1:-1]

        recs = []
        for idx in top_idxs:
            row = df.iloc[idx]
            recs.append({
                "id": int(row["id"]),
                "title": row["title"],
                "manufacturer": row["manufacturer"],
                "price": float(row["price"]) if pd.notna(row["price"]) else None,
                "url": row["url"]
            })

        logger.info(f"Returning {len(recs)} recommendations.")
        return recs

    except Exception:
        logger.error("Error during recommendation:\n" + traceback.format_exc())
        return []
