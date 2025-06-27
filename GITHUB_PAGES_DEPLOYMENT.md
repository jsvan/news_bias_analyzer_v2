# GitHub Pages Deployment Guide

This guide explains how to deploy the News Bias Analyzer frontend to GitHub Pages while maintaining backend functionality.

## 🚀 Quick Setup

### 1. Enable GitHub Pages

1. Go to your repository **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**
3. The workflow will automatically deploy when you push to the `master` branch

### 2. Configure Environment Variables (Optional)

In your repository settings, go to **Settings** → **Secrets and variables** → **Actions** → **Variables**:

- `VITE_API_BASE_URL`: Your hosted API URL (if you have one)
- Example: `https://api.yourdomain.com`

### 3. Update CORS Configuration

In `server/dashboard_api.py` and `server/extension_api.py`, update the GitHub Pages URL:

```python
# Replace "jsv" with your GitHub username
"https://yourusername.github.io"
```

## 📦 Deployment Modes

### Mode 1: GitHub Pages Only (No Backend)
- ✅ **Frontend**: Hosted on GitHub Pages
- ❌ **Data**: No mock data - requires real API connection
- ⚠️ **Limitation**: Shows error message directing users to run backend
- 🎯 **Purpose**: Deployment endpoint for when backend is available

### Mode 2: GitHub Pages + Local API
- ✅ **Frontend**: Hosted on GitHub Pages  
- ✅ **Backend**: Your local machine (for personal use)
- ✅ **Extension**: Can connect to your local API
- ⚠️ **Limitation**: Only you can access real data

### Mode 3: GitHub Pages + Hosted API
- ✅ **Frontend**: Hosted on GitHub Pages
- ✅ **Backend**: Cloud-hosted (AWS, DigitalOcean, etc.)
- ✅ **Extension**: Works for all users
- ✅ **Real Data**: Live news analysis for everyone

## 🛠️ Local Development

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Backend Development
```bash
# Terminal 1: Start dashboard API
cd server
python dashboard_api.py

# Terminal 2: Start extension API
python extension_api.py
```

## 🔧 Configuration Files

### Environment Variables

Create `frontend/.env.local` for local development:

```env
VITE_APP_ENV=development
VITE_API_BASE_URL=http://localhost:8000
VITE_GITHUB_PAGES=false
```

### Build Scripts

- `npm run dev`: Local development
- `npm run build`: Production build
- `npm run build:github-pages`: GitHub Pages specific build
- `npm run preview`: Test production build locally

## 🌐 Extension Multi-Environment Support

The Chrome extension automatically detects the environment and connects to the appropriate API:

- **Development**: `http://localhost:8000`
- **Production**: Your hosted API URL
- **Fallback**: Graceful degradation when API unavailable

### Extension Configuration

Update `extension/js/config.js` with your production API URL:

```javascript
case 'production':
  return {
    API_ENDPOINT: 'https://your-api-domain.com',
    ENVIRONMENT: 'production'
  };
```

## 🔒 CORS Configuration

The backend automatically configures CORS based on the environment:

### Development
- Allows all localhost origins
- Allows Chrome/Firefox extensions

### Production  
- Allows only specified domains
- Includes GitHub Pages URL
- Includes extension origins

## ⚠️ No Mock Data

This system does NOT provide mock or fake data for ethical reasons:

- **Accuracy Required**: News bias analysis must be based on real data
- **No Simulation**: Fake sentiment data would be misleading
- **Real Sources Only**: Analysis requires actual news article processing
- **API Required**: Backend server must be running for any functionality

## 🚦 Environment Detection

The system automatically detects the deployment environment:

1. **GitHub Pages**: `VITE_GITHUB_PAGES=true`
2. **Production**: `VITE_APP_ENV=production`
3. **Development**: Default local development

## 📱 Testing the Deployment

### Test GitHub Pages Deployment
1. Push to master branch
2. Wait for GitHub Actions to complete
3. Visit `https://yourusername.github.io/news_bias_analyzer`
4. Verify error message displays correctly (no backend available)

### Test with Local API
1. Start your local backend: `python server/dashboard_api.py`
2. Set environment variable: `VITE_API_BASE_URL=http://localhost:8000`
3. Rebuild and deploy

### Test Extension
1. Load the extension in Chrome
2. Visit any news article
3. Check that it connects to your API
4. Verify sentiment analysis works

## 🐛 Troubleshooting

### GitHub Pages Not Loading
- Check **Settings** → **Pages** is set to **GitHub Actions**
- Verify the workflow completed successfully in **Actions** tab
- Check browser console for errors

### API Connection Issues
- Verify CORS configuration includes your GitHub Pages URL
- Check browser console for CORS errors
- Ensure API is running and accessible

### Extension Not Working
- Check `chrome://extensions/` for errors
- Verify API endpoint in extension config
- Check popup console for debugging info

### Build Failures
- Ensure all dependencies are installed: `npm ci`
- Check for TypeScript errors: `npm run build`
- Verify environment variables are set correctly

## 🎯 Next Steps

1. **Custom Domain**: Add a custom domain in repository settings
2. **API Hosting**: Deploy backend to AWS, DigitalOcean, or Heroku
3. **Analytics**: Enable Google Analytics with `VITE_ENABLE_ANALYTICS=true`
4. **Monitoring**: Set up uptime monitoring for your API

## 📚 Additional Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Vite Build Configuration](https://vitejs.dev/guide/build.html)
- [Chrome Extension Development](https://developer.chrome.com/docs/extensions/)

---

**Ready to deploy?** Just push your changes to the `master` branch and GitHub Actions will handle the rest! 🚀