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
            "SECRET_KEY": secrets.token_hex(32),
            "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": ""
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
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'BlogCreator/1.0'  # Good practice for GitHub API
    }

def check_github_api_status():
    """Check GitHub API status and rate limits."""
    headers = get_github_headers()
    if not headers:
        return {'status': 'error', 'message': 'No GitHub token configured'}
    
    try:
        # Use a simple API call to check status and rate limits
        response = requests.get('https://api.github.com/rate_limit', headers=headers, timeout=10)
        
        if response.status_code == 200:
            rate_limit_data = response.json()
            core_limits = rate_limit_data.get('resources', {}).get('core', {})
            remaining = core_limits.get('remaining', 0)
            limit = core_limits.get('limit', 0)
            reset_time = core_limits.get('reset', 0)
            
            return {
                'status': 'ok',
                'rate_limit': {
                    'remaining': remaining,
                    'limit': limit,
                    'reset_time': reset_time,
                    'percentage_used': ((limit - remaining) / limit * 100) if limit > 0 else 0
                }
            }
        else:
            return {
                'status': 'error', 
                'message': f'GitHub API returned status {response.status_code}',
                'response': response.text[:200]
            }
            
    except requests.exceptions.Timeout:
        return {'status': 'error', 'message': 'GitHub API request timed out'}
    except requests.exceptions.ConnectionError:
        return {'status': 'error', 'message': 'Unable to connect to GitHub API'}
    except Exception as e:
        return {'status': 'error', 'message': f'GitHub API check failed: {str(e)}'}

def test_github_repo_access():
    """Test if we can access the configured repository."""
    details = get_repo_details()
    headers = get_github_headers()
    
    if not details['user'] or not details['repo']:
        return {'status': 'error', 'message': 'Repository details not configured'}
    
    if not headers:
        return {'status': 'error', 'message': 'GitHub token not configured'}
    
    try:
        # Test repository access
        repo_url = f"https://api.github.com/repos/{details['user']}/{details['repo']}"
        response = requests.get(repo_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            repo_data = response.json()
            permissions = repo_data.get('permissions', {})
            
            return {
                'status': 'ok',
                'repo_name': repo_data.get('full_name'),
                'permissions': {
                    'read': permissions.get('pull', False),
                    'write': permissions.get('push', False),
                    'admin': permissions.get('admin', False)
                },
                'default_branch': repo_data.get('default_branch', 'main')
            }
        elif response.status_code == 404:
            return {'status': 'error', 'message': 'Repository not found or no access'}
        elif response.status_code == 403:
            return {'status': 'error', 'message': 'Access forbidden - check token permissions'}
        else:
            return {
                'status': 'error', 
                'message': f'Repository access failed with status {response.status_code}',
                'response': response.text[:200]
            }
            
    except Exception as e:
        return {'status': 'error', 'message': f'Repository access test failed: {str(e)}'}

def github_api_request_with_retry(method, url, headers=None, json_data=None, max_retries=3, backoff_factor=2):
    """Make GitHub API request with retry logic and rate limit handling."""
    import time
    
    for attempt in range(max_retries):
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=json_data, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, json=json_data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for rate limiting
            if response.status_code == 403:
                rate_limit_remaining = response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_remaining == '0':
                    reset_time = int(response.headers.get('X-RateLimit-Reset', '0'))
                    current_time = int(time.time())
                    wait_time = max(reset_time - current_time, 60)  # Wait at least 1 minute
                    
                    if attempt < max_retries - 1:
                        print(f"Rate limit exceeded. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        return {
                            'success': False,
                            'error': 'rate_limit_exceeded',
                            'message': f'GitHub API rate limit exceeded. Resets in {wait_time} seconds.',
                            'retry_after': wait_time
                        }
            
            # Check for other temporary errors that might benefit from retry
            if response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"Server error {response.status_code}. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            # Return successful response or final error
            if response.status_code in [200, 201]:
                return {
                    'success': True,
                    'data': response.json(),
                    'status_code': response.status_code
                }
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {'message': response.text}
                return {
                    'success': False,
                    'error': 'api_error',
                    'message': error_data.get('message', f'GitHub API error: {response.status_code}'),
                    'status_code': response.status_code,
                    'details': error_data
                }
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"Request timeout. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                return {
                    'success': False,
                    'error': 'timeout',
                    'message': 'Request timed out after multiple attempts'
                }
                
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"Connection error. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                return {
                    'success': False,
                    'error': 'connection_error',
                    'message': 'Unable to connect to GitHub API after multiple attempts'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': 'unexpected_error',
                'message': f'Unexpected error: {str(e)}'
            }
    
    return {
        'success': False,
        'error': 'max_retries_exceeded',
        'message': f'Failed after {max_retries} attempts'
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
                
                <h2 class="text-xl font-semibold mb-4 text-gray-700">AI Configuration</h2>
                <div class="mb-4">
                    <label for="openai_api_key" class="block text-gray-700 text-sm font-bold mb-2">OpenAI API Key</label>
                    <input type="password" name="openai_api_key" placeholder="Enter new OpenAI API key or leave blank to keep existing" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                    <p class="text-gray-500 text-xs mt-1">For ChatGPT integration</p>
                </div>
                <div class="mb-4">
                    <label for="gemini_api_key" class="block text-gray-700 text-sm font-bold mb-2">Gemini API Key</label>
                    <input type="password" name="gemini_api_key" placeholder="Enter new Gemini API key or leave blank to keep existing" class="shadow border rounded w-full py-2 px-3 text-gray-700">
                    <p class="text-gray-500 text-xs mt-1">For Gemini integration</p>
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
            <!-- File Title -->
            <div class="mb-3">
                <h1 id="current-file-name" class="text-2xl font-bold text-gray-800">No File Selected</h1>
            </div>
            
            <!-- Controls Row -->
            <div class="flex items-center justify-between mb-4">
                <!-- AI Rewrite Controls -->
                <div id="ai-controls" class="flex items-center space-x-3 hidden">
                    <select id="ai-provider" class="border rounded-lg px-3 py-2 text-sm bg-white shadow-sm">
                        <option value="">Select AI</option>
                    </select>
                    <div class="flex items-center space-x-2">
                        <span class="text-sm text-gray-600 whitespace-nowrap">I want this post to be</span>
                        <input type="text" id="ai-style-input" placeholder="professional, engaging, etc." class="border rounded-lg px-3 py-2 text-sm w-64 shadow-sm">
                    </div>
                    <button id="ai-rewrite-btn" class="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-6 rounded-full text-sm disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-200 whitespace-nowrap" disabled>
                        <i class="fas fa-magic mr-2"></i>AI Rewrite
                    </button>
                </div>
                
                <!-- Save Button -->
                <button id="save-btn" class="bg-green-500 hover:bg-green-600 text-white font-medium py-2 px-6 rounded-full disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-200" disabled>
                    <i class="fas fa-save mr-2"></i>Save Changes
                </button>
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
            let aiConfig = { providers: [], styles: [] };
            
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

            // Pre-save checks
            async function performPreSaveChecks() {
                showProgress('Checking GitHub status...');
                
                try {
                    // Check GitHub API status
                    const githubStatus = await apiCall('/api/github/status');
                    if (githubStatus.status !== 'ok') {
                        throw new Error(`GitHub API issue: ${githubStatus.message}`);
                    }
                    
                    // Check rate limits
                    const rateLimit = githubStatus.rate_limit;
                    if (rateLimit.remaining < 5) {
                        throw new Error(`GitHub rate limit nearly exceeded (${rateLimit.remaining} requests remaining). Please wait before saving.`);
                    }
                    
                    // Check repository access
                    showProgress('Verifying repository access...');
                    const repoAccess = await apiCall('/api/github/repo-access');
                    if (repoAccess.status !== 'ok') {
                        throw new Error(`Repository access issue: ${repoAccess.message}`);
                    }
                    
                    // Check write permissions
                    if (!repoAccess.permissions.write) {
                        throw new Error('No write permissions to repository. Check your GitHub token.');
                    }
                    
                    return { success: true, rateLimit };
                    
                } catch (error) {
                    return { success: false, error: error.message };
                }
            }
            
            async function saveFile(path, content, sha, isNewFile) {
                showProgress(isNewFile ? 'Creating file...' : 'Preparing to save...');
                
                try {
                    // Perform pre-save checks
                    const preCheck = await performPreSaveChecks();
                    if (!preCheck.success) {
                        throw new Error(preCheck.error);
                    }
                    
                    // Display rate limit info if getting close
                    const remaining = preCheck.rateLimit.remaining;
                    if (remaining < 50) {
                        console.warn(`GitHub rate limit warning: ${remaining} requests remaining`);
                    }
                    
                    showProgress(isNewFile ? 'Creating file...' : 'Saving changes to GitHub...');
                    
                    const updatedFile = await apiCall('/api/file', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path, content, sha })
                    });
                    
                    showProgress('File saved successfully! Refreshing list...');
                    await fetchFiles();
                    
                    if (isNewFile) {
                        const newFileInList = Array.from(fileListEl.children).find(el => el.dataset.path === path);
                        if (newFileInList) newFileInList.click();
                    } else {
                        fileStatuses[path].sha = updatedFile.sha || updatedFile.content?.sha;
                        fileStatuses[path].hasUnsavedChanges = false;
                        fileStatuses[path].lastSaved = new Date();
                        updateUI();
                    }
                    
                    // Brief success message
                    showProgress('✓ File saved successfully!');
                    await new Promise(res => setTimeout(res, 1000));
                    
                } catch (error) {
                    console.error('Save error:', error);
                    
                    // Enhanced error handling with user-friendly messages
                    let errorMessage = error.message;
                    let suggestion = '';
                    
                    if (error.message.includes('rate limit')) {
                        suggestion = '\\n\\nTip: Try again in a few minutes, or copy your content as backup.';
                    } else if (error.message.includes('GitHub API')) {
                        suggestion = '\\n\\nTip: Check your internet connection and GitHub settings.';
                    } else if (error.message.includes('permissions')) {
                        suggestion = '\\n\\nTip: Update your GitHub Personal Access Token with repository write permissions.';
                    } else if (error.message.includes('timeout')) {
                        suggestion = '\\n\\nTip: GitHub might be slow. Try copying your content and refreshing the page.';
                    } else if (error.message.includes('conflict')) {
                        suggestion = '\\n\\nTip: The file may have been modified elsewhere. Refresh the page and try again.';
                    } else {
                        suggestion = '\\n\\nTip: Copy your content as backup, refresh the page, and try again.';
                    }
                    
                    alert('❌ Save Failed\\n\\n' + errorMessage + suggestion);
                    
                } finally {
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
                saveFile(filename, '# ' + filename + '\\n\\nStart writing here.', null, true);
                input.value = '';
            });

            // AI Rewrite functionality
            async function loadAIConfig() {
                try {
                    const config = await apiCall('/api/ai-styles');
                    aiConfig = config;
                    updateAIControls();
                } catch (error) {
                    console.log('AI config not available:', error.message);
                }
            }

            function updateAIControls() {
                const aiControlsEl = document.getElementById('ai-controls');
                const providerSelect = document.getElementById('ai-provider');
                const rewriteBtn = document.getElementById('ai-rewrite-btn');

                // Show/hide AI controls based on availability
                if (aiConfig.providers.length > 0 && currentFile) {
                    aiControlsEl.classList.remove('hidden');
                } else {
                    aiControlsEl.classList.add('hidden');
                    return;
                }

                // Populate provider dropdown
                providerSelect.innerHTML = '<option value="">Select AI</option>';
                aiConfig.providers.forEach(provider => {
                    const option = document.createElement('option');
                    option.value = provider.id;
                    option.textContent = provider.name;
                    providerSelect.appendChild(option);
                });

                // Update rewrite button state
                updateRewriteButtonState();
            }

            function updateRewriteButtonState() {
                const providerSelect = document.getElementById('ai-provider');
                const styleInput = document.getElementById('ai-style-input');
                const rewriteBtn = document.getElementById('ai-rewrite-btn');

                const hasProvider = providerSelect.value !== '';
                const hasStyle = styleInput.value.trim() !== '';
                const hasContent = currentFile && easyMDE.value().trim() !== '';

                rewriteBtn.disabled = !(hasProvider && hasStyle && hasContent);
            }

            async function performAIRewrite() {
                const providerSelect = document.getElementById('ai-provider');
                const styleInput = document.getElementById('ai-style-input');
                
                const provider = providerSelect.value;
                const style = styleInput.value.trim();
                const content = easyMDE.value();

                if (!provider || !style || !content.trim()) {
                    alert('Please select an AI provider, enter a style, and ensure there is content to rewrite.');
                    return;
                }

                const providerName = aiConfig.providers.find(p => p.id === provider)?.name;
                
                try {
                    // Step 1: Preparing request
                    showProgress(`Preparing content for ${providerName}...`);
                    await new Promise(resolve => setTimeout(resolve, 500));
                    
                    // Step 2: Sending to AI
                    showProgress(`Sending content to ${providerName} for rewriting...`);
                    await new Promise(resolve => setTimeout(resolve, 300));
                    
                    // Step 3: AI processing
                    showProgress(`${providerName} is analyzing and rewriting your content...`);
                    
                    const result = await apiCall('/api/ai-rewrite', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content, provider, style })
                    });

                    // Step 4: Applying changes
                    showProgress('Applying rewritten content to editor...');
                    await new Promise(resolve => setTimeout(resolve, 300));
                    
                    // Replace editor content with rewritten version
                    easyMDE.value(result.rewritten_content);
                    
                    // Mark as having unsaved changes
                    if (currentFile) {
                        fileStatuses[currentFile.path].hasUnsavedChanges = true;
                        updateUI();
                    }
                    
                    // Step 5: Complete
                    showProgress('Rewrite completed successfully!');
                    await new Promise(resolve => setTimeout(resolve, 800));
                    
                } catch (error) {
                    alert(`AI rewrite failed: ${error.message}`);
                } finally {
                    hideProgress();
                }
            }

            // Event listeners for AI controls
            document.getElementById('ai-provider').addEventListener('change', updateRewriteButtonState);
            document.getElementById('ai-style-input').addEventListener('input', updateRewriteButtonState);
            document.getElementById('ai-rewrite-btn').addEventListener('click', performAIRewrite);

            // Update the existing updateUI function to include AI controls
            const originalUpdateUI = updateUI;
            updateUI = function() {
                originalUpdateUI();
                updateAIControls();
            };

            // Initialize everything
            loadAIConfig();
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
        
        # AI Configuration
        if request.form.get('openai_api_key'):
            config['OPENAI_API_KEY'] = request.form['openai_api_key']
        if request.form.get('gemini_api_key'):
            config['GEMINI_API_KEY'] = request.form['gemini_api_key']
        
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

@app.route('/api/github/status')
def github_status():
    """Check GitHub API status and rate limits."""
    if 'is_admin' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    status = check_github_api_status()
    return jsonify(status)

@app.route('/api/github/repo-access')
def github_repo_access():
    """Test GitHub repository access."""
    if 'is_admin' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    access_info = test_github_repo_access()
    return jsonify(access_info)

@app.route('/api/file', methods=['POST', 'DELETE'])
def manage_file():
    if 'is_admin' not in session: 
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.json
        path = data['path']
        sha = data.get('sha')
        details = get_repo_details()
        headers = get_github_headers()
        
        # Validate required fields
        if not details['user'] or not details['repo']:
            return jsonify({
                'error': 'GitHub configuration incomplete',
                'message': 'GitHub username or repository not configured',
                'suggestion': 'Please check your settings'
            }), 400
        
        if not headers:
            return jsonify({
                'error': 'GitHub token missing',
                'message': 'GitHub token not configured',
                'suggestion': 'Please add a valid GitHub Personal Access Token in settings'
            }), 400
        
        # Pre-flight checks before attempting the operation
        print(f"INFO: Performing pre-flight checks for {request.method} operation on {path}")
        
        # Check GitHub API status and rate limits
        api_status = check_github_api_status()
        if api_status['status'] != 'ok':
            return jsonify({
                'error': 'GitHub API unavailable',
                'message': api_status['message'],
                'suggestion': 'Please try again later'
            }), 503
        
        # Check rate limits
        rate_limit = api_status.get('rate_limit', {})
        remaining = rate_limit.get('remaining', 0)
        percentage_used = rate_limit.get('percentage_used', 100)
        
        if remaining < 10:  # Less than 10 requests remaining
            return jsonify({
                'error': 'Rate limit nearly exceeded',
                'message': f'Only {remaining} GitHub API requests remaining',
                'suggestion': f'Rate limit resets at {rate_limit.get("reset_time", "unknown time")}',
                'retry_after': rate_limit.get('reset_time', 0)
            }), 429
        
        if percentage_used > 90:  # More than 90% of rate limit used
            print(f"WARNING: GitHub API rate limit {percentage_used:.1f}% used ({remaining} remaining)")
        
        # Test repository access
        repo_access = test_github_repo_access()
        if repo_access['status'] != 'ok':
            return jsonify({
                'error': 'Repository access failed',
                'message': repo_access['message'],
                'suggestion': 'Check repository name and token permissions'
            }), 403
        
        # Check write permissions for POST/DELETE operations
        permissions = repo_access.get('permissions', {})
        if not permissions.get('write', False):
            return jsonify({
                'error': 'Insufficient permissions',
                'message': 'Your GitHub token does not have write access to this repository',
                'suggestion': 'Update your Personal Access Token with appropriate permissions'
            }), 403
        
        api_url = f"https://api.github.com/repos/{details['user']}/{details['repo']}/contents/{path}"
        
        print(f"INFO: Pre-flight checks passed. Proceeding with {request.method} operation")
        print(f"INFO: API URL: {api_url}")
        print(f"INFO: Rate limit status: {remaining}/{rate_limit.get('limit', 'unknown')} remaining")
        
        if request.method == 'POST':  # Create or Update
            content = data['content']
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            payload = {
                'message': f'docs: update {path}', 
                'content': content_b64, 
                'branch': details['branch']
            }
            if sha: 
                payload['sha'] = sha
            
            print(f"INFO: Sending PUT request to GitHub API")
            result = github_api_request_with_retry('PUT', api_url, headers, payload)
            
        elif request.method == 'DELETE':  # Delete
            if not sha: 
                return jsonify({
                    'error': 'SHA required',
                    'message': 'File SHA is required for deletion',
                    'suggestion': 'Refresh the file list and try again'
                }), 400
            
            payload = {
                'message': f'docs: delete {path}', 
                'sha': sha, 
                'branch': details['branch']
            }
            
            print(f"INFO: Sending DELETE request to GitHub API")
            result = github_api_request_with_retry('DELETE', api_url, headers, payload)
        
        # Handle the result from the resilient API function
        if result['success']:
            print(f"SUCCESS: {request.method} operation completed successfully")
            return jsonify(result['data']), result['status_code']
        else:
            print(f"ERROR: {request.method} operation failed: {result['message']}")
            
            # Provide user-friendly error messages and suggestions
            error_response = {
                'error': result['error'],
                'message': result['message']
            }
            
            # Add specific suggestions based on error type
            if result['error'] == 'rate_limit_exceeded':
                error_response['suggestion'] = f"Wait {result.get('retry_after', 60)} seconds and try again"
                return jsonify(error_response), 429
            elif result['error'] == 'timeout':
                error_response['suggestion'] = 'GitHub API is slow. Try again in a few moments.'
                return jsonify(error_response), 504
            elif result['error'] == 'connection_error':
                error_response['suggestion'] = 'Check your internet connection and try again.'
                return jsonify(error_response), 503
            elif result['error'] == 'api_error':
                status_code = result.get('status_code', 500)
                if status_code == 404:
                    error_response['suggestion'] = 'File or repository not found. Check the path and try again.'
                elif status_code == 403:
                    error_response['suggestion'] = 'Access denied. Check your token permissions.'
                elif status_code == 409:
                    error_response['suggestion'] = 'File conflict. Refresh and try again.'
                else:
                    error_response['suggestion'] = 'GitHub API error. Please try again.'
                return jsonify(error_response), status_code
            else:
                error_response['suggestion'] = 'An unexpected error occurred. Please try again.'
                return jsonify(error_response), 500
            
    except Exception as e:
        print(f"ERROR: Exception in manage_file: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'message': f'Unexpected server error: {str(e)}',
            'suggestion': 'Please try again or contact support if the problem persists'
        }), 500

@app.route('/api/ai-styles')
def get_ai_styles():
    """Returns available AI style words and configured providers."""
    if 'is_admin' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    config = load_config()
    
    # Check which AI providers are configured
    providers = []
    if config.get('OPENAI_API_KEY'):
        providers.append({'id': 'openai', 'name': 'ChatGPT'})
    if config.get('GEMINI_API_KEY'):
        providers.append({'id': 'gemini', 'name': 'Gemini'})
        
    return jsonify({
        'providers': providers,
        'styles': config.get('AI_STYLE_WORDS', [])
    })

@app.route('/api/ai-rewrite', methods=['POST'])
def ai_rewrite():
    """Rewrites content using the specified AI provider and style."""
    if 'is_admin' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.json
        content = data.get('content', '').strip()
        provider = data.get('provider')
        style = data.get('style', '').strip()
        
        if not content:
            return jsonify({'error': 'Content is required'}), 400
        if not provider:
            return jsonify({'error': 'AI provider is required'}), 400
        if not style:
            return jsonify({'error': 'Style is required'}), 400
            
        config = load_config()
        
        # Get the rewritten content based on provider
        if provider == 'openai':
            api_key = config.get('OPENAI_API_KEY')
            if not api_key:
                return jsonify({'error': 'OpenAI API key not configured'}), 400
            rewritten_content = get_openai_rewrite(content, style, api_key)
        elif provider == 'gemini':
            api_key = config.get('GEMINI_API_KEY')
            if not api_key:
                return jsonify({'error': 'Gemini API key not configured'}), 400
            rewritten_content = get_gemini_rewrite(content, style, api_key)
        else:
            return jsonify({'error': 'Unknown AI provider'}), 400
            
        return jsonify({'rewritten_content': rewritten_content})
        
    except Exception as e:
        print(f"DEBUG: Exception in ai_rewrite: {str(e)}")
        return jsonify({'error': f'AI rewrite failed: {str(e)}'}), 500

# --- AI Rewrite Functions ---

def get_openai_rewrite(content, style_prompt, api_key):
    """Rewrites content using OpenAI API."""
    import gc
    
    try:
        # Lazy import to reduce memory footprint
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        system_prompt = f"You are an expert content editor. Rewrite the following markdown content to be more {style_prompt}. Maintain the original structure and formatting, but improve the content quality. Return only the rewritten markdown content without any additional commentary."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean up to free memory
        del client, response
        gc.collect()
        
        return result
        
    except Exception as e:
        # Force garbage collection on error
        gc.collect()
        raise Exception(f"OpenAI API error: {str(e)}")

def get_gemini_rewrite(content, style_prompt, api_key):
    """Rewrites content using Gemini API with memory optimization."""
    import gc
    import os
    
    try:
        # Set environment variable to reduce gRPC memory usage
        os.environ['GRPC_POLL_STRATEGY'] = 'poll'
        os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
        
        # Lazy import to reduce memory footprint
        import google.generativeai as genai
        
        # Configure with minimal settings
        genai.configure(api_key=api_key)
        
        # Use REST transport instead of gRPC to reduce memory usage
        generation_config = {
            'temperature': 0.7,
            'max_output_tokens': 2000,
        }
        
        model = genai.GenerativeModel(
            'gemini-2.5-pro',
            generation_config=generation_config
        )
        
        prompt = f"You are an expert content editor. Rewrite the following markdown content to be more {style_prompt}. Maintain the original structure and formatting, but improve the content quality. Return only the rewritten markdown content without any additional commentary.\n\nContent to rewrite:\n{content}"
        
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        # Clean up to free memory
        del model, response
        gc.collect()
        
        return result
        
    except Exception as e:
        # Force garbage collection on error
        gc.collect()
        raise Exception(f"Gemini API error: {str(e)}")

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
