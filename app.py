import os
import requests
import base64
import json
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix

# --- App Initialization ---
app = Flask(__name__)

# Configure for proxy (HAProxy/nginx with HTTPS)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- Configuration Management ---
CONFIG_FILE = 'config.json'

def load_config():
    """Loads configuration from a JSON file."""
    if not os.path.exists(CONFIG_FILE):
        # Create a default config if it doesn't exist
        import secrets
        default_config = {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "admin",
            "GITHUB_USERNAME": "",
            "GITHUB_REPO": "",
            "GITHUB_BRANCH": "main",
            "GITHUB_TOKEN": "",
            "SECRET_KEY": secrets.token_hex(32)
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    # Add SECRET_KEY if it doesn't exist (for existing configs)
    if 'SECRET_KEY' not in config:
        import secrets
        config['SECRET_KEY'] = secrets.token_hex(32)
        save_config(config)
    
    return config

def save_config(config):
    """Saves configuration to a JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# --- GitHub API Helper Functions ---
def get_github_headers():
    """Constructs the necessary headers for GitHub API requests from config."""
    config = load_config()
    token = config.get('GITHUB_TOKEN')
    if not token:
        return None
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

def get_repo_details():
    """Gets repository details from config."""
    config = load_config()
    return {
        'user': config.get('GITHUB_USERNAME'),
        'repo': config.get('GITHUB_REPO'),
        'branch': config.get('GITHUB_BRANCH')
    }

# --- HTML Templates ---
# All HTML is embedded for simplicity in a single file.

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style> body { font-family: 'Inter', sans-serif; } </style>
</head>
<body class="bg-gray-100 flex items-center justify-center h-screen">
    <div class="w-full max-w-sm bg-white rounded-lg shadow-md p-8">
        <h1 class="text-2xl font-bold text-center text-gray-800 mb-6">Admin Login</h1>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
                        <span class="block sm:inline">{{ message }}</span>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form action="{{ url_for('login') }}" method="post">
            <div class="mb-4">
                <label for="username" class="block text-gray-700 text-sm font-bold mb-2">Username</label>
                <input type="text" name="username" id="username" required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700">
            </div>
            <div class="mb-6">
                <label for="password" class="block text-gray-700 text-sm font-bold mb-2">Password</label>
                <input type="password" name="password" id="password" required class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700">
            </div>
            <button type="submit" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded w-full">Login</button>
        </form>
    </div>
</body>
</html>
"""

SETTINGS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Settings</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style> body { font-family: 'Inter', sans-serif; } </style>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto p-8">
        <div class="w-full max-w-2xl mx-auto bg-white rounded-lg shadow-md p-8">
            <h1 class="text-2xl font-bold text-gray-800 mb-2">Settings</h1>
            <p class="text-gray-600 mb-6">Configure the connection to your GitHub repository.</p>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative mb-4">
                    <span>{{ message }}</span>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}

            <form action="{{ url_for('settings') }}" method="post">
                <h2 class="text-xl font-semibold mb-4 text-gray-700">GitHub Details</h2>
                <div class="mb-4">
                    <label for="github_username" class="block text-gray-700 text-sm font-bold mb-2">GitHub Username</label>
                    <input type="text" name="github_username" value="{{ config.GITHUB_USERNAME }}" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                </div>
                <div class="mb-4">
                    <label for="github_repo" class="block text-gray-700 text-sm font-bold mb-2">Repository Name</label>
                    <input type="text" name="github_repo" value="{{ config.GITHUB_REPO }}" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                </div>
                <div class="mb-4">
                    <label for="github_branch" class="block text-gray-700 text-sm font-bold mb-2">Branch Name</label>
                    <input type="text" name="github_branch" value="{{ config.GITHUB_BRANCH }}" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                </div>
                <div class="mb-6">
                    <label for="github_token" class="block text-gray-700 text-sm font-bold mb-2">Personal Access Token</label>
                    <input type="password" name="github_token" placeholder="Enter new token or leave blank to keep existing" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                </div>
                
                <hr class="my-6">
                
                <h2 class="text-xl font-semibold mb-4 text-gray-700">Admin Credentials</h2>
                 <div class="mb-4">
                    <label for="admin_username" class="block text-gray-700 text-sm font-bold mb-2">Admin Username</label>
                    <input type="text" name="admin_username" value="{{ config.ADMIN_USERNAME }}" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                </div>
                <div class="mb-6">
                    <label for="admin_password" class="block text-gray-700 text-sm font-bold mb-2">Admin Password</label>
                    <input type="password" name="admin_password" placeholder="Enter new password or leave blank to keep existing" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                </div>

                <div class="flex items-center justify-between mt-8">
                    <button type="submit" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">Save Settings</button>
                    <a href="{{ url_for('editor') }}" class="inline-block align-baseline font-bold text-sm text-blue-500 hover:text-blue-800">Go to Editor &rarr;</a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Markdown Editor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://unpkg.com/easymde/dist/easymde.min.css">
    <script src="https://unpkg.com/easymde/dist/easymde.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .editor-container { height: calc(100vh - 150px); }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .saved { background-color: #4ade80; }
        .unsaved { background-color: #f87171; }
        .EasyMDEContainer { height: 100%; display: flex; flex-direction: column; }
        .CodeMirror { flex-grow: 1; }
    </style>
</head>
<body class="bg-gray-50">
    <div class="flex h-screen">
        <aside class="w-1/3 bg-gray-800 text-white p-4 flex flex-col max-w-sm">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold">Files</h2>
                <a href="{{ url_for('settings') }}" title="Settings"><i class="fas fa-cog text-gray-400 hover:text-white"></i></a>
            </div>
            <div id="file-list" class="flex-grow overflow-y-auto"></div>
            <div class="mt-4">
                <button id="new-file-btn" class="w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded mb-2">New File</button>
                <button id="refresh-btn" class="w-full bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded">Refresh</button>
            </div>
        </aside>

        <main class="w-2/3 p-6 flex flex-col">
            <div class="flex justify-between items-center mb-4">
                <h1 id="current-file-name" class="text-2xl font-bold text-gray-800">No File Selected</h1>
                <button id="save-btn" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded disabled:bg-gray-400" disabled>Save Changes</button>
            </div>
            <div class="editor-container flex-grow">
                <textarea id="editor"></textarea>
            </div>
        </main>
    </div>

    <div id="progress-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white p-8 rounded-lg shadow-xl text-center">
            <div class="loader ease-linear rounded-full border-4 border-t-4 border-gray-200 h-12 w-12 mb-4 mx-auto animate-spin"></div>
            <h3 id="progress-message" class="text-lg font-medium text-gray-700"></h3>
        </div>
    </div>
    
    <div id="new-file-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white p-8 rounded-lg shadow-xl w-full max-w-md">
            <h2 class="text-xl font-bold mb-4">Create New File</h2>
            <input type="text" id="new-file-input" class="w-full border rounded p-2 mb-4" placeholder="filename.md">
            <div class="flex justify-end">
                <button onclick="document.getElementById('new-file-modal').classList.add('hidden')" class="bg-gray-300 hover:bg-gray-400 text-black font-bold py-2 px-4 rounded mr-2">Cancel</button>
                <button id="save-new-file-btn" class="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded">Save</button>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const fileListEl = document.getElementById('file-list');
            const currentFileNameEl = document.getElementById('current-file-name');
            const saveBtn = document.getElementById('save-btn');
            
            let currentFile = null;
            let fileStatuses = {};
            
            const easyMDE = new EasyMDE({
                element: document.getElementById('editor'),
                spellChecker: false,
                placeholder: "Select a file to start editing...",
                status: false,
            });

            easyMDE.codemirror.on("change", () => {
                if (currentFile) {
                    fileStatuses[currentFile.path].hasUnsavedChanges = true;
                    updateUI();
                }
            });

            async function apiCall(url, options = {}) {
                const response = await fetch(url, options);
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: "An unknown error occurred." }));
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
                return response.json();
            }

            async function fetchFiles() {
                try {
                    const files = await apiCall('/api/files');
                    renderFileList(files);
                } catch (error) {
                    alert(`Error fetching files: ${error.message}`);
                }
            }

            async function fetchFileContent(file) {
                try {
                    const data = await apiCall(`/api/file/${file.path}`);
                    easyMDE.value(data.content);
                    currentFile = file;
                    if (!fileStatuses[file.path]) {
                        fileStatuses[file.path] = { sha: file.sha };
                    }
                    fileStatuses[file.path].hasUnsavedChanges = false;
                    fileStatuses[file.path].lastSaved = new Date();
                    updateUI();
                } catch (error) {
                    alert(`Error fetching file content: ${error.message}`);
                }
            }

            async function saveFile(path, content, sha, isNewFile) {
                showProgress(isNewFile ? 'Creating file...' : 'Saving changes...');
                try {
                    await new Promise(res => setTimeout(res, 500));
                    showProgress('Pushing to repository...');
                    const updatedFile = await apiCall('/api/file', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path, content, sha })
                    });
                    
                    showProgress('Refreshing file list...');
                    await fetchFiles();
                    
                    if (isNewFile) {
                        const newFileInList = Array.from(fileListEl.children).find(el => el.dataset.path === path);
                        if (newFileInList) newFileInList.click();
                    } else {
                        fileStatuses[path].sha = updatedFile.sha;
                        fileStatuses[path].hasUnsavedChanges = false;
                        fileStatuses[path].lastSaved = new Date();
                        updateUI();
                    }
                } catch (error) {
                    alert(`Error saving file: ${error.message}`);
                } finally {
                    await new Promise(res => setTimeout(res, 500));
                    hideProgress();
                }
            }
            
            async function deleteFile(path, sha) {
                if (!confirm(`Are you sure you want to delete "${path}"? This cannot be undone.`)) return;
                
                showProgress(`Deleting ${path}...`);
                try {
                    await apiCall('/api/file', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path, sha })
                    });
                    showProgress('Refreshing file list...');
                    if (currentFile && currentFile.path === path) {
                        currentFile = null;
                        easyMDE.value('');
                    }
                    await fetchFiles();
                    updateUI();
                } catch (error) {
                    alert(`Error deleting file: ${error.message}`);
                } finally {
                    hideProgress();
                }
            }

            function renderFileList(files) {
                fileListEl.innerHTML = '';
                files.forEach(file => {
                    if (!fileStatuses[file.path]) {
                        fileStatuses[file.path] = { sha: file.sha, hasUnsavedChanges: false, lastSaved: null };
                    }
                    const fileEl = document.createElement('div');
                    fileEl.className = 'p-2 rounded hover:bg-gray-700 cursor-pointer flex justify-between items-center';
                    fileEl.dataset.path = file.path;
                    fileEl.dataset.sha = file.sha;
                    fileEl.dataset.name = file.name;

                    const nameWrapper = document.createElement('div');
                    nameWrapper.className = 'flex items-center';
                    const statusDot = document.createElement('span');
                    statusDot.className = 'status-dot mr-2';
                    nameWrapper.appendChild(statusDot);
                    nameWrapper.append(file.name);
                    
                    const deleteBtn = document.createElement('button');
                    deleteBtn.innerHTML = '<i class="fas fa-trash-alt text-gray-400 hover:text-red-500"></i>';
                    deleteBtn.onclick = (e) => {
                        e.stopPropagation();
                        deleteFile(file.path, file.sha);
                    };

                    fileEl.appendChild(nameWrapper);
                    fileEl.appendChild(deleteBtn);
                    fileEl.onclick = () => fetchFileContent(file);
                    fileListEl.appendChild(fileEl);
                });
                updateUI();
            }
            
            function updateUI() {
                currentFileNameEl.textContent = currentFile ? currentFile.name : "No File Selected";
                saveBtn.disabled = !(currentFile && fileStatuses[currentFile.path]?.hasUnsavedChanges);
                
                Array.from(fileListEl.children).forEach(el => {
                    const status = fileStatuses[el.dataset.path];
                    const dot = el.querySelector('.status-dot');
                    if (status && status.lastSaved) {
                        dot.className = 'status-dot mr-2 ' + (status.hasUnsavedChanges ? 'unsaved' : 'saved');
                    }
                });
            }

            function showProgress(message) {
                document.getElementById('progress-message').textContent = message;
                document.getElementById('progress-modal').classList.remove('hidden');
            }

            function hideProgress() {
                document.getElementById('progress-modal').classList.add('hidden');
            }

            document.getElementById('refresh-btn').addEventListener('click', fetchFiles);
            saveBtn.addEventListener('click', () => {
                if (!currentFile) return;
                saveFile(currentFile.path, easyMDE.value(), fileStatuses[currentFile.path].sha, false);
            });
            document.getElementById('new-file-btn').addEventListener('click', () => document.getElementById('new-file-modal').classList.remove('hidden'));
            document.getElementById('save-new-file-btn').addEventListener('click', () => {
                const input = document.getElementById('new-file-input');
                let filename = input.value.trim();
                if (!filename) return alert('Filename cannot be empty.');
                if (!filename.endsWith('.md')) filename += '.md';
                document.getElementById('new-file-modal').classList.add('hidden');
                saveFile(filename, `# ${filename}\\n\\nStart writing here.`, null, true);
                input.value = '';
            });

            fetchFiles();
        });
    </script>
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def index():
    """Redirects to editor if configured, otherwise to login/settings."""
    config = load_config()
    if not config.get('GITHUB_TOKEN'):
        flash("Please configure your GitHub settings first.", "info")
        return redirect(url_for('login'))
    if 'is_admin' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('editor'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles admin login."""
    config = load_config()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == config['ADMIN_USERNAME'] and password == config['ADMIN_PASSWORD']:
            session['is_admin'] = True
            # If GitHub is not configured, go to settings, else editor
            if not config.get('GITHUB_TOKEN'):
                 return redirect(url_for('settings'))
            return redirect(url_for('editor'))
        else:
            flash("Invalid credentials.", "error")
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Shows and saves settings."""
    if 'is_admin' not in session:
        return redirect(url_for('login'))
    
    config = load_config()
    if request.method == 'POST':
        config['GITHUB_USERNAME'] = request.form['github_username']
        config['GITHUB_REPO'] = request.form['github_repo']
        config['GITHUB_BRANCH'] = request.form['github_branch']
        if request.form.get('github_token'):
            config['GITHUB_TOKEN'] = request.form['github_token']
        
        config['ADMIN_USERNAME'] = request.form['admin_username']
        if request.form.get('admin_password'):
            config['ADMIN_PASSWORD'] = request.form['admin_password']
            
        save_config(config)
        flash("Settings saved successfully!", "success")
        return redirect(url_for('settings'))
        
    return render_template_string(SETTINGS_TEMPLATE, config=config)

@app.route('/editor')
def editor():
    """Renders the main editor page."""
    if 'is_admin' not in session:
        return redirect(url_for('login'))
    config = load_config()
    if not config.get('GITHUB_TOKEN'):
        flash("Please configure your GitHub settings first.", "info")
        return redirect(url_for('settings'))
    return render_template_string(EDITOR_TEMPLATE)

# --- API Routes ---

@app.route('/api/files')
def list_files():
    if 'is_admin' not in session: return jsonify({'error': 'Not authenticated'}), 401
    details = get_repo_details()
    headers = get_github_headers()
    api_url = f"https://api.github.com/repos/{details['user']}/{details['repo']}/contents?ref={details['branch']}"
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200: return jsonify({'error': 'Failed to fetch repo contents'}), response.status_code
    files = [{'name': i['name'], 'path': i['path'], 'sha': i['sha']} for i in response.json() if i['type'] == 'file' and i['name'].endswith('.md')]
    return jsonify(sorted(files, key=lambda x: x['name']))

@app.route('/api/file/<path:filepath>')
def get_file(filepath):
    if 'is_admin' not in session: return jsonify({'error': 'Not authenticated'}), 401
    details = get_repo_details()
    headers = get_github_headers()
    api_url = f"https://api.github.com/repos/{details['user']}/{details['repo']}/contents/{filepath}?ref={details['branch']}"
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200: return jsonify({'error': 'Failed to fetch file content'}), response.status_code
    content = base64.b64decode(response.json().get('content', '')).decode('utf-8')
    return jsonify({'content': content})

@app.route('/api/file', methods=['POST', 'DELETE'])
def manage_file():
    if 'is_admin' not in session: return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.json
        path = data['path']
        sha = data.get('sha')
        details = get_repo_details()
        headers = get_github_headers()
        
        # Validate required fields
        if not details['user'] or not details['repo']:
            return jsonify({'error': 'GitHub username or repository not configured'}), 400
        
        if not headers:
            return jsonify({'error': 'GitHub token not configured'}), 400
            
        api_url = f"https://api.github.com/repos/{details['user']}/{details['repo']}/contents/{path}"
        
        print(f"DEBUG: API URL: {api_url}")
        print(f"DEBUG: Method: {request.method}")
        print(f"DEBUG: Path: {path}")
        print(f"DEBUG: SHA: {sha}")
        
        if request.method == 'POST': # Create or Update
            content = data['content']
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            payload = {
                'message': f'docs: update {path}', 
                'content': content_b64, 
                'branch': details['branch']
            }
            if sha: 
                payload['sha'] = sha
            
            print(f"DEBUG: Payload keys: {list(payload.keys())}")
            print(f"DEBUG: Branch: {details['branch']}")
            
            response = requests.put(api_url, headers=headers, json=payload)
            status_code = response.status_code
            
        elif request.method == 'DELETE': # Delete
            if not sha: return jsonify({'error': 'File SHA is required for deletion'}), 400
            payload = {
                'message': f'docs: delete {path}', 
                'sha': sha, 
                'branch': details['branch']
            }
            response = requests.delete(api_url, headers=headers, json=payload)
            status_code = response.status_code
        
        print(f"DEBUG: Response status: {status_code}")
        
        if status_code in [200, 201]:
            return jsonify(response.json()), status_code
        else:
            error_details = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            print(f"DEBUG: Error response: {error_details}")
            return jsonify({
                'error': 'GitHub API request failed', 
                'details': error_details,
                'status_code': status_code,
                'url': api_url
            }), status_code
            
    except Exception as e:
        print(f"DEBUG: Exception in manage_file: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

# Initialize Flask app with persistent config
config = load_config()
app.secret_key = config['SECRET_KEY']

# Session configuration (environment-aware)
# Only use secure cookies when behind HTTPS proxy
use_secure_cookies = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
app.config.update(
    SESSION_COOKIE_SECURE=use_secure_cookies,  # Only send cookies over HTTPS when in production
    SESSION_COOKIE_HTTPONLY=True,  # Prevent XSS
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
