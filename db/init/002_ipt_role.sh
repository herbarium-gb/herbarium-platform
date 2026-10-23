#!/bin/bash
# Creates the read-only ipt_herbarium role for accessing published data.
#
# Runs on first database initialization (after 001_init.sql).
# For existing databases, see "PostgreSQL and IPT" in README.md.
#
# Grants SELECT on public.dwc_occurrence only, with no access to raw data
# or permission to write or create objects.
# Skipped if PG_IPT_PASSWORD is unset.

set -e

if [ -z "$PG_IPT_PASSWORD" ]; then
    echo "PG_IPT_PASSWORD not set, skipping ipt_herbarium role"
else
    psql -v ON_ERROR_STOP=1 \
         --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
         -v ipt_password="$PG_IPT_PASSWORD" <<-'EOSQL'
		CREATE ROLE ipt_herbarium WITH LOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION
		    PASSWORD :'ipt_password';
		ALTER ROLE ipt_herbarium SET default_transaction_read_only = on;

		GRANT USAGE ON SCHEMA public TO ipt_herbarium;
		GRANT SELECT ON TABLE public.dwc_occurrence TO ipt_herbarium;
	EOSQL
fi
