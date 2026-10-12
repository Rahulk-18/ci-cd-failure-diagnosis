"""Minimal FastAPI service — the app under CI. Deliberately small: the pipeline is the product."""

from fastapi import FastAPI

app = FastAPI(title="self-healing-cicd demo")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/greet")
def greet(name: str = "world") -> dict:
    return {"message": f"hello, {name}"}
