import asyncio
from app.config import settings
from app.seed import main

if __name__ == '__main__' and settings.seed_catalog:
    asyncio.run(main())
