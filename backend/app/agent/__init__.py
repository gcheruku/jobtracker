"""Agentic layer: a Claude tool-using assistant over the job pipeline.

`tools` declares the read-only tool surface (schemas + executors) that wraps the
existing services; `runner` drives the Claude agent loop (plan → call tools →
observe → repeat) and streams events to the UI.
"""
