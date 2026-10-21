"""Model and Presidio calls share one connection pool per event loop, and tests keep their own transport."""

import asyncio

import httpx

from app.core import http_pool


def test_calls_in_one_loop_share_a_client():
    async def twice() -> bool:
        return http_pool.shared_client() is http_pool.shared_client()

    assert asyncio.run(twice())


def test_a_new_loop_never_reuses_a_client_from_a_closed_one():
    async def one() -> httpx.AsyncClient:
        return http_pool.shared_client()

    first = asyncio.run(one())
    assert asyncio.run(one()) is not first


def test_a_closed_client_is_replaced():
    async def after_close() -> bool:
        before = http_pool.shared_client()
        await http_pool.close()
        return http_pool.shared_client() is not before

    assert asyncio.run(after_close())


def test_a_given_transport_answers_instead_of_the_network():
    transport = httpx.MockTransport(lambda request: httpx.Response(204))

    async def call() -> int:
        async with http_pool.client_for(transport) as client:
            return (await client.get("http://model.invalid/")).status_code

    assert asyncio.run(call()) == 204
