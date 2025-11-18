# run.py
from src.config import Config
from src.main import app

if __name__ == "__main__":
    # The app is run from here to ensure it works correctly
    # when the project is executed as a package.
    app.run(
        debug=Config.DEBUG,
        host=Config.FLASK_RUN_HOST,
        port=Config.FLASK_RUN_PORT,
    )

