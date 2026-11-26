// Vercel evaluates this file at build time, so the API origin can be supplied
// as a project environment variable instead of being hard-coded in vercel.json.
const apiOrigin = (process.env.API_ORIGIN || 'https://zappy.pythonanywhere.com').replace(/\/+$/, '');

export const config = {
  installCommand: 'npm --prefix frontend ci',
  buildCommand: 'npm --prefix frontend run build',
  outputDirectory: 'frontend/dist',
  rewrites: [
    { source: '/api/:path*', destination: `${apiOrigin}/api/:path*` },
  ],
};
