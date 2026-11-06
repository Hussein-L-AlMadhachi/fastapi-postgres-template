-- Apply by hand: psql "$DATABASE_URL" -f migrations/0001_init_db.down.sql

drop table if exists items;
drop table if exists users;