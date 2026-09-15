DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'safesite_agent') THEN
        CREATE ROLE safesite_agent LOGIN PASSWORD 'safesite_agent_dev_password';
    END IF;
END
$$;

ALTER ROLE safesite_agent SET default_transaction_read_only = on;
GRANT CONNECT ON DATABASE safesite TO safesite_agent;
GRANT USAGE ON SCHEMA public TO safesite_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO safesite_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO safesite_agent;
REVOKE CREATE ON SCHEMA public FROM safesite_agent;
