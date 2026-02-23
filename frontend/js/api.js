const API = {
  baseUrl: '',

  async _get(path) {
    try {
      const resp = await fetch(this.baseUrl + path);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (e) {
      console.error(`API ${path}:`, e);
      return null;
    }
  },

  async getStatus() { return this._get('/api/status/latest'); },
  async getPortfolio() { return this._get('/api/portfolio/current'); },
  async getNav(days = 90) { return this._get(`/api/nav?days=${days}`); },
  async getTrades(limit = 50) { return this._get(`/api/trades?limit=${limit}`); },
  async getSignal() { return this._get('/api/signal/latest'); },
  async getFactorWeights() { return this._get('/api/factor/weights'); },
};
