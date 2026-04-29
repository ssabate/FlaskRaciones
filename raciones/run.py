import os

from app import create_app, db
from app.models import User, Food, ConsumptionLog

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Food': Food, 'ConsumptionLog': ConsumptionLog}

if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host=host, port=port, debug=debug)
