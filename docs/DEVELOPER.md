# Developer Notes — iMat Warehouse

## Layout

| Path | Role |
|------|------|
| `main.py` | Entry point, splash, login, main window |
| `db/` | SQLAlchemy engine, models, sessions |
| `logic/` | Business rules (stock, documents, reports) |
| `ui/` | PyQt6 dialogs and main window |
| `ai/` | Offline forecasting, EOQ/ABC, Q&A helper |
| `config/` | ConfigManager + JSON settings |
| `tests/` | pytest suite |

## Database API

```python
from db.database import init_db, SessionLocal, get_engine, session_scope, is_sqlite, is_sqlserver
from db.models import Product, Stock, Document

init_db()  # create tables if needed

with session_scope() as db:
    items = db.query(Product).limit(10).all()
```

Connection URL resolution order:
1. Explicit argument to `get_engine(...)`
2. Env `DATABASE_URL`
3. `app_config.json` → `database.engine` + sqlite path or sqlserver block

## Stock integrity rules (do not weaken)

- Posted movements reject qty ≤ 0 and invalid QC status
- Deleting a **DRAFT** document must reverse any posted stock
- Document numbers are unique sequential: `TYPE-YYYYMMDD-NNNN`
- Prefer `session_scope(db=...)` so tests can inject an in-memory session

## AI API

```python
from ai.predictor import DemandPredictor, predict_item_demand
from ai.optimizer import InventoryOptimizer
from ai.llm_helper import LLMHelper

p = DemandPredictor([5, 0, 0, 8, 0, 12])
print(p.demand_profile())
print(p.predict_with_confidence(days=7))

q = InventoryOptimizer.eoq(annual_demand=1200, ordering_cost=50, holding_cost_per_unit=2)
```

## Tests

```bash
pip install -r requirements.txt
python -m pytest tests -q
python -m pytest tests --cov=db --cov=logic --cov=ai --cov-report=term-missing
```

## Packaging (Windows)

See `packaging/imat.spec` and `packaging/build_windows.ps1`.

## Versioning

Bump `app_config.json` → `version` and `CHANGELOG.md` together.
