import logging
import os

from dotenv import load_dotenv

from src.bot import SCBot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "")
    bot = SCBot()
    bot.run(token)


if __name__ == "__main__":
    main()
