# algo_3

## Setup

```powershell
# 1. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the env template and fill in your keys
copy .env.example .env

# 4. Run
python -m src.main
```

## Layout

- `src/` — application code
- `requirements.txt` — Python dependencies
- `.env` — secrets (git-ignored; copy from `.env.example`)
- `venv/` — virtual environment (git-ignored)
