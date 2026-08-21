from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

DATABASE_PATH = DATA_DIR / "stocks.db"


TEST_MODE = True

TEST_STOCKS = [
    {
        "stock_id": "2330",
        "stock_name": "台積電",
        "market": "TWSE",
    },
    {
        "stock_id": "2317",
        "stock_name": "鴻海",
        "market": "TWSE",
    },
    {
        "stock_id": "2454",
        "stock_name": "聯發科",
        "market": "TWSE",
    },
    {
        "stock_id": "6488",
        "stock_name": "環球晶",
        "market": "TPEx",
    },
    {
        "stock_id": "6770",
        "stock_name": "力積電",
        "market": "TWSE",
    },
]