"""Postgres-backed stores and access helpers for Arya's features.

Everything here talks to the tables in backend/migrations/001_init.sql through a
SQLAlchemy Connection (one per request, see app.db.get_conn). No ORM.
Aparna's quiz and attempt store lives in app/stores/ and is not touched.
"""
