import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendRoutes = ['/auth', '/subjects', '/questions', '/agent', '/students', '/modules', '/qa', '/retrieve', '/events', '/usage', '/attempts'];
const backendTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(backendRoutes.map((route) => [route, { target: backendTarget, changeOrigin: true }]))
  }
});
