"""
Run Flask app with Waitress WSGI server (production-grade, no reloader issues)
This avoids Flask's development server reloader that caches Python bytecode
"""
from waitress import serve
from main import app

if __name__ == '__main__':
    print("\n" + "="*70)
    print("Starting Contract Analyzer with Waitress WSGI Server")
    print("No reloader - code changes require manual restart")
    print("="*70 + "\n")
    
    # Serve the app on all interfaces, port 5000
    serve(app, host='0.0.0.0', port=5000, threads=4)
