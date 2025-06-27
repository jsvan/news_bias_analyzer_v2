import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Determine if this is a GitHub Pages build
  const isGitHubPages = process.env.VITE_GITHUB_PAGES === 'true' || mode === 'github-pages';
  
  // Get the repository name for GitHub Pages base path
  // This should be the name of your GitHub repository
  const repoName = process.env.VITE_REPO_NAME || 'news_bias_analyzer';
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    // Set base URL for GitHub Pages deployment
    base: isGitHubPages ? `/${repoName}/` : '/',
    
    // Build configuration
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: false,
      // Ensure all assets use relative paths for GitHub Pages
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            ui: ['@mui/material', '@mui/icons-material'],
            charts: ['recharts'],
          },
        },
      },
    },
    
    // Development server configuration
    server: {
      port: 3000,
      host: true,
      proxy: {
        '/api': {
          target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    
    // Preview server configuration (for local testing of production builds)
    preview: {
      port: 4173,
      host: true,
    },
    
    // Define environment variables that will be available in the client
    define: {
      __VITE_APP_VERSION__: JSON.stringify(process.env.npm_package_version || '0.1.0'),
    },
  };
});