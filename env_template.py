# Observer-Advisor Environment Variables
# Copy to .env and fill in values

# ── Azure OpenAI ──────────────────────────────────────────────
# AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
# AZURE_OPENAI_API_KEY=your-key-here
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_OPENAI_DEPLOYMENT=gpt-4o

# ── ASCM Database (PostgreSQL) ───────────────────────────────
# ASCM_DB_HOST=ulancapppg001.postgres.database.azure.com
# ASCM_DB_NAME=ascm_web
# ASCM_DB_USER=
# ASCM_DB_PASSWORD=
# ASCM_DB_PORT=5432

# ── ATE Database (Oracle) ────────────────────────────────────
# ATE_DB_HOST=uktreddbprd001.uniper.onmicrosoft.com
# ATE_DB_SERVICE=ELATE
# ATE_DB_USER=
# ATE_DB_PASSWORD=
# ATE_DB_PORT=1521

# ── PromptOpt Database (PostgreSQL) ──────────────────────────
# PROMPTOPT_DB_HOST=pgpaas-prompt-prd-001.postgres.database.azure.com
# PROMPTOPT_DB_NAME=ulpoptpg001
# PROMPTOPT_DB_USER=
# PROMPTOPT_DB_PASSWORD=
# PROMPTOPT_DB_PORT=5432

# ── General ─────────────────────────────────────────────────
# OBSERVER_ENV=PROD
# CHECK_INTERVAL=300
# USE_SAMPLE_DB=false



Incident Description:
The ATE application in the PROD environment is experiencing multiple query failures affecting critical trading and exchange synchronization components. The detection rules "ate_query_error" have identified that database tables AUTOTRADE.POWER_TRADE_ERROR, AUTOTRADE.POWER_TRADE, and EXCHSYNC.MESSAGE are inaccessible as of 2026-04-27. This incident is impacting trade error monitoring, trade flow tracking, and exchange message synchronization, potentially disrupting automated energy trading operations. The correlation analysis indicates a high confidence level that these failures are related. Immediate investigation into the ATE database infrastructure is required to restore normal trading functionality.