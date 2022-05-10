import asyncio
from functools import partial, wraps


def wrap_async(func):

    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_running_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


async def async_iter(iterable):
    for item in iterable:
        yield item


def format_mac(data):
    return ':'.join('{0:02x}'.format(a) for a in data)
