"""Application entry point."""
import sys
from app import create_app
from app.models import db


app = create_app()


@app.cli.command()
def init_db():
    """Initialize the database."""
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")


if __name__ == '__main__':
    # Check for init-db command
    if len(sys.argv) > 1 and sys.argv[1] == 'init-db':
        with app.app_context():
            db.create_all()
            print("Database initialized successfully!")
    else:
        app.run(debug=True, host='0.0.0.0', port=5000)
