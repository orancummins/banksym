import os

# Use an in-memory SQLite database for the whole test session so persistence
# is exercised without leaving a banksym.db file behind. This must be set
# before banksym.settings.get_settings() is first called (it is cached).
os.environ.setdefault("BANKSYM_DATABASE_URL", "sqlite://")
