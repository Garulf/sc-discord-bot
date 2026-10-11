import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from src.gok_site import GokSiteClient

TOKEN = "secret-token"


@pytest.fixture
async def site():
    requests: list[dict] = []

    async def record(request: web.Request) -> web.Response:
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return web.json_response({"error": "unauthorized"}, status=401)
        body = await request.json() if request.can_read_body else None
        requests.append({"method": request.method, "path": request.path, "body": body})
        return web.json_response({"updated": 1})

    app = web.Application()
    app.router.add_route("*", "/api/bot/members", record)
    app.router.add_route("*", "/api/bot/members/{id}", record)
    server = TestServer(app)
    await server.start_server()
    yield server, requests
    await server.close()


@pytest.fixture
async def client(site):
    server, _ = site
    client = GokSiteClient(str(server.make_url("/")), TOKEN)
    yield client
    await client.close()


async def test_update_member_puts_roles_and_name(site, client):
    _, requests = site

    updated = await client.update_member({"id": "42", "roles": ["7"], "name": "Ghost"})

    assert updated == 1
    assert requests == [{"method": "PUT", "path": "/api/bot/members/42", "body": {"roles": ["7"], "name": "Ghost"}}]


async def test_remove_member_deletes_by_id(site, client):
    _, requests = site

    await client.remove_member(42)

    assert requests == [{"method": "DELETE", "path": "/api/bot/members/42", "body": None}]


async def test_sync_roster_puts_full_member_list(site, client):
    _, requests = site
    members = [{"id": "1", "roles": [], "name": "A"}, {"id": "2", "roles": ["7"], "name": "B"}]

    await client.sync_roster(members)

    assert requests == [{"method": "PUT", "path": "/api/bot/members", "body": {"members": members}}]


async def test_base_url_trailing_slash_is_optional(site):
    server, requests = site
    client = GokSiteClient(str(server.make_url("")).rstrip("/"), TOKEN)
    try:
        await client.remove_member(5)
    finally:
        await client.close()

    assert requests[0]["path"] == "/api/bot/members/5"


async def test_rejected_request_raises(site):
    server, _ = site
    client = GokSiteClient(str(server.make_url("/")), "wrong-token")
    try:
        with pytest.raises(aiohttp.ClientResponseError):
            await client.remove_member(5)
    finally:
        await client.close()
