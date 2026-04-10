#!/usr/bin/env bash
# Wrapper for starting model-ledger MCP server with Snowflake backend.
#
# Usage:
#   claude mcp add model-ledger -- ./scripts/mcp-snowflake.sh
#
# Requires:
#   - snowflake-connector-python (pip install model-ledger[snowflake])
#   - Environment variables: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER
#   - For SSO: SNOWFLAKE_AUTHENTICATOR=externalbrowser
#
# Customize SCHEMA below for your organization.

SCHEMA="${SNOWFLAKE_SCHEMA:-MODEL_LEDGER}"

exec model-ledger mcp --backend snowflake --schema "$SCHEMA"
