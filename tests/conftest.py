import pytest_asyncio
from core.db import engine


@pytest_asyncio.fixture(autouse=True)
async def cleanup_engine():
    """Dispose engine connections after tests to prevent loop mismatch"""
    yield
    await engine.dispose()
