"""Connector factories — config-driven model discovery.

    >>> from model_ledger.connectors import sql_connector, rest_connector
    >>> connector = sql_connector(name="models", connection=conn,
    ...     query="SELECT name, owner FROM registry", name_column="name")
    >>> nodes = connector.discover()
"""
from model_ledger.connectors.sql import sql_connector
from model_ledger.connectors.rest import rest_connector

__all__ = ["sql_connector", "rest_connector"]
