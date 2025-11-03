
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

ALTER DATABASE shorts_maker SET timezone TO 'UTC';


COMMENT ON SCHEMA public IS 'Shorts Maker API Database Schema';