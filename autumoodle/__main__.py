
if __name__ == "__main__":
    from .cli import run
    from asyncio import run as asyncio_run

    asyncio_run(run())
