"""Pool sizing for SQLAlchemy and friends.

pool_size is the real ceiling on concurrency, not a knob people often turn.
"""
from sqlalchemy import create_engine

engine_a = create_engine('postgresql://localhost/db', pool_size=20, max_overflow=10)
engine_b = create_engine('mysql://localhost/db', pool_size=5)
engine_c = create_engine('sqlite:///local.db')  # no pool sizing -> not a fact
