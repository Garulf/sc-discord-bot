import os

from dotenv import load_dotenv

from src.bot import SCBot


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "")
    bot = SCBot()
    bot.run(token)


if __name__ == "__main__":
    main()
