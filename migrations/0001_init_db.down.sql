-- Apply by hand: psql "$DATABASE_URL" -f migrations/0001_init_db.down.sql

DROP TABLE IF EXISTS items;
