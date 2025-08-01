# Blog Creator

A powerful markdown blog content management system that seamlessly integrates with GitHub repositories. Blog Creator serves as the backend CMS for the [SimpleBlog](https://github.com/mightywomble/simpleblog) frontend, providing a complete blogging solution.

## 🎯 Overview

Blog Creator is a Flask-based web application that allows you to create, edit, and manage markdown blog posts directly in your GitHub repositories. It works in tandem with [SimpleBlog](https://github.com/mightywomble/simpleblog) to provide a complete blogging ecosystem:

- **Blog Creator** (this app) - Backend CMS for content management
- **SimpleBlog** - Frontend blog display with modern UI/UX

## ✨ Features

### 📝 Content Management
- **Markdown Editor**: Built-in EasyMDE editor with live preview
- **AI-Powered Rewriting**: Enhance content with ChatGPT and Gemini AI
- **File Management**: Create, edit, and delete markdown files
- **GitHub Integration**: Direct integration with GitHub repositories
- **Auto-save Status**: Visual indicators for saved/unsaved changes
- **File Browser**: Navigate and organize your blog posts

### 🔐 Security & Authentication
- **Admin Authentication**: Secure login system
- **Session Management**: Protected admin sessions
- **Configurable Credentials**: Customizable admin username/password

### ⚙️ Configuration
- **GitHub Repository Setup**: Configure target repository for blog posts
- **Branch Selection**: Choose which branch to work with
- **Token Authentication**: Secure GitHub API access
- **Settings Management**: Easy configuration through web interface

### 🤖 AI-Powered Features
- **Content Enhancement**: Rewrite content with ChatGPT or Gemini AI
- **Multiple AI Providers**: Support for OpenAI and Google Gemini
- **Customizable Styles**: Configure rewriting styles (professional, engaging, technical, etc.)
- **Smart Integration**: AI controls appear automatically when configured
- **Preserve Structure**: Maintains markdown formatting while improving content

### 🎨 User Interface
- **Modern Design**: Clean, responsive interface built with Tailwind CSS
- **Real-time Updates**: Live file status indicators
- **Modal Dialogs**: Intuitive file creation and management
- **Progress Indicators**: Visual feedback for operations
- **AI Controls**: Integrated AI rewriting interface in the editor

## 🔄 How it Works with SimpleBlog

This application creates a complete blogging workflow:

1. **Content Creation** (Blog Creator):
   - Write and edit markdown posts using the built-in editor
   - Organize posts in your GitHub repository
   - Manage file structure and content

2. **Content Display** ([SimpleBlog](https://github.com/mightywomble/simpleblog)):
   - Fetches markdown files from your GitHub repository
   - Displays posts with modern glass-morphism design
   - Provides search, filtering, and sharing features
   - Offers responsive design for all devices

3. **Workflow**:
   ```
   Blog Creator → GitHub Repository → SimpleBlog Frontend
   (Content Management)    (Storage)    (Public Display)
   ```

## 🚀 Quick Start

### Prerequisites

- Python 3.7+
- GitHub account
- GitHub Personal Access Token
- GitHub repository for storing blog posts

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/blogcreator.git
   cd blogcreator
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install flask requests
   # Optional: For AI features
   pip install openai google-generativeai
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Access the application:**
   Open your browser and navigate to `http://0.0.0.0:5003`

## 🛠️ Setup Guide

### Development Environment

1. **Initial Setup:**
   - Follow the Quick Start steps above
   - The app will create a default `config.json` file

2. **First Login:**
   - Default credentials: `admin` / `admin`
   - You'll be prompted to change these on first login

3. **GitHub Configuration:**
   - Go to Settings in the admin panel
   - Configure your GitHub details:
     - **Username**: Your GitHub username
     - **Repository**: Repository name for blog posts
     - **Branch**: Target branch (usually `main`)
     - **Token**: GitHub Personal Access Token

4. **GitHub Token Setup:**
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Create a token with `repo` permissions
   - Add the token to your Blog Creator settings

5. **AI Configuration (Optional):**
   - **OpenAI Setup**:
     - Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
     - Add the key in Settings → AI Configuration
   - **Gemini Setup**:
     - Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
     - Add the key in Settings → AI Configuration
   - **Customize AI Styles**:
     - Edit the comma-separated list of rewriting styles
     - Examples: professional, engaging, technical, creative, formal, casual

### Production Environment

1. **Server Setup:**
   ```bash
   # Clone and setup as above
   git clone https://github.com/yourusername/blogcreator.git
   cd blogcreator
   python3 -m venv venv
   source venv/bin/activate
   pip install flask requests gunicorn
   ```

2. **Production Server (Gunicorn):**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5003 app:app
   ```

3. **Process Management (systemd):**
   Create `/etc/systemd/system/blogcreator.service`:
   ```ini
   [Unit]
   Description=Blog Creator
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/path/to/blogcreator
   Environment="PATH=/path/to/blogcreator/venv/bin"
   ExecStart=/path/to/blogcreator/venv/bin/gunicorn -w 4 -b 0.0.0.0:5003 app:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl enable blogcreator
   sudo systemctl start blogcreator
   ```

4. **Reverse Proxy (Nginx):**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:5003;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
   }
   ```

5. **SSL Certificate (Let's Encrypt):**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

## 📁 File Structure

```
blogcreator/
├── app.py              # Main Flask application
├── config.json         # Configuration file (auto-created)
├── README.md          # This file
└── venv/              # Virtual environment (created during setup)
```

## ⚙️ Configuration

The `config.json` file contains all application settings:

```json
{
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "your-secure-password",
    "GITHUB_USERNAME": "your-github-username",
    "GITHUB_REPO": "your-blog-repo",
    "GITHUB_BRANCH": "main",
    "GITHUB_TOKEN": "your-github-token",
    "OPENAI_API_KEY": "your-openai-api-key",
    "GEMINI_API_KEY": "your-gemini-api-key",
    "AI_STYLE_WORDS": ["professional", "engaging", "technical", "creative", "formal", "casual"]
}
```

## 🔧 API Endpoints

### Core Endpoints
- `GET /` - Main dashboard (redirects to editor)
- `GET /login` - Admin login page
- `POST /login` - Process login
- `GET /settings` - Configuration page
- `POST /settings` - Save configuration
- `GET /editor` - Main editor interface

### File Management API
- `GET /api/files` - List repository files
- `GET /api/file/<path>` - Get file content
- `POST /api/file` - Create/update file
- `DELETE /api/file` - Delete file

### AI Integration API
- `GET /api/ai-styles` - Get available AI providers and styles
- `POST /api/ai-rewrite` - Rewrite content with AI

## 🐛 Troubleshooting

### Common Issues

1. **GitHub API Rate Limiting**
   - Ensure you're using a GitHub token
   - Check rate limit status in GitHub settings

2. **Permission Errors**
   - Verify GitHub token has `repo` permissions
   - Ensure repository exists and is accessible

3. **Port Already in Use**
   - Change port in `app.py` if 5003 is occupied
   - Check for other running instances

4. **Login Issues**
   - Clear browser cache and cookies
   - Reset `config.json` if corrupted

5. **AI Features Not Working**
   - Verify API keys are correctly configured in Settings
   - Check that AI dependencies are installed: `pip install openai google-generativeai`
   - Ensure you have sufficient API credits/quota
   - Check console for detailed error messages

### Debug Mode

Run with debug enabled for development:
```python
# In app.py, change:
app.run(debug=True, host='0.0.0.0', port=5003)
```

## 🔒 Security Considerations

- **Production**: Change default admin credentials immediately
- **HTTPS**: Use SSL certificates in production
- **Token Security**: Keep GitHub tokens secure and rotate regularly
- **Access Control**: Restrict access to admin panel
- **Updates**: Keep dependencies updated

## 🤝 Integration with SimpleBlog

To use this with SimpleBlog:

1. **Setup Blog Creator** (this app) for content management
2. **Setup SimpleBlog** for public display
3. **Configure both** to use the same GitHub repository
4. **Workflow**:
   - Create/edit posts in Blog Creator
   - Posts are automatically available in SimpleBlog
   - SimpleBlog pulls latest content from GitHub

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

If you encounter any issues:

1. Check the troubleshooting section above
2. Search existing [GitHub issues](https://github.com/yourusername/blogcreator/issues)
3. Create a new issue with detailed information

## 🔗 Related Projects

- [SimpleBlog](https://github.com/mightywomble/simpleblog) - Frontend blog display
- [EasyMDE](https://github.com/Ionaru/easy-markdown-editor) - Markdown editor used in this project

---

Made with ❤️ for the developer community
