const API = {
  // Auto-detect base path from current page location
  baseUrl: (() => {
    const path = window.location.pathname;
    const match = path.match(/^(\/[^/]+)\//);
    return match ? match[1] : '';
  })(),

  async _get(path) {
    try {
      const resp = await fetch(this.baseUrl + path, { credentials: 'same-origin' });
      if (resp.status === 401) {
        showLogin();
        return null;
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (e) {
      console.error(`API ${path}:`, e);
      return null;
    }
  },

  async login(password) {
    const resp = await fetch(this.baseUrl + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ password }),
    });
    return resp.ok;
  },

  async checkAuth() {
    try {
      const resp = await fetch(this.baseUrl + '/api/auth/check', { credentials: 'same-origin' });
      const data = await resp.json();
      return data.authenticated;
    } catch { return false; }
  },

  async getStatus() { return this._get('/api/status/latest'); },
  async getPortfolio() { return this._get('/api/portfolio/current'); },
  async getNav(days = 90) { return this._get(`/api/nav?days=${days}`); },
  async getTrades(limit = 50) { return this._get(`/api/trades?limit=${limit}`); },
  async getSignal() { return this._get('/api/signal/latest'); },
  async getFactorWeights() { return this._get('/api/factor/weights'); },
};
