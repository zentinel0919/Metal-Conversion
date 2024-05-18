# tests/test_main.py
import sys
import os
import pytest # type: ignore
from httpx import AsyncClient, ASGITransport # type: ignore
from app.main import app

# Ensure the app is in the sys path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.mark.asyncio
async def test_read_metal_price():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/prices/XAU")
        assert response.status_code == 200
        assert "price" in response.json()
