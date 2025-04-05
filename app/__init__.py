import os
from flask import Flask
from flask_cors import CORS

def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Enable CORS for all routes
    CORS(app)
    
    # Load configuration
    from app.config import Config
    app.config.from_object(Config)
    
    # Ensure the upload directories exist
    for folder in [app.config['UPLOAD_FOLDER'], 
                   app.config['HANDWRITTEN_FOLDER'], 
                   app.config['CONTEXT_FOLDER'], 
                   app.config['SUBMISSIONS_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
    
    # Import and register routes
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    return app