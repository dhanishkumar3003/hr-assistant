from app.db.session import get_db

# Re-exported so every module imports dependencies from one place:
# from app.core.deps import get_db
__all__ = ["get_db"]