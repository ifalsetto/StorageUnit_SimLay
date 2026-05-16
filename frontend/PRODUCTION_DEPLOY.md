# Frontend Production Deployment

## Build
```bash
npm install
VITE_API_BASE=https://your-backend-domain.com npm run build
```

Deploy the `dist/` folder to any HTTPS static host:

- Cloudflare Pages
- Netlify
- Vercel
- Firebase Hosting
- S3 + CloudFront

## Runtime config override
The deployed site can override the backend API URL by replacing:

```text
public/simlay-runtime-config.js
```

with:

```javascript
window.SIMLAY_API_BASE = "https://your-backend-domain.com";
```
