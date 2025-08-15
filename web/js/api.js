/**
 * Centralized API module for Memoria
 * Handles authentication, 401 responses, and provides consistent fetch interface
 */

class MemoriaAPI {
  constructor() {
    this.baseURL = window.location.origin;
    this.passcode = localStorage.getItem('memoria_pass') || '';
    this.authWarningElement = null;
  }

  /**
   * Set the auth warning element for 401 handling
   */
  setAuthWarningElement(element) {
    this.authWarningElement = element;
  }

  /**
   * Update the passcode
   */
  setPasscode(passcode) {
    this.passcode = passcode;
    localStorage.setItem('memoria_pass', passcode);
    // Expose globally for compatibility with dictation.js
    window.PASS = passcode;
  }

  /**
   * Get the current passcode
   */
  getPasscode() {
    return this.passcode;
  }

  /**
   * Make an API request with authentication
   */
  async request(path, method = 'GET', body = null) {
    const res = await fetch(this.baseURL + path, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(this.passcode ? {'x-auth-token': this.passcode} : {})
      },
      body: body ? JSON.stringify(body) : null
    });
    
    if (res.status === 401) {
      if (this.authWarningElement) {
        this.authWarningElement.classList.add('show');
      }
      throw new Error('Unauthorized');
    } else {
      if (this.authWarningElement) {
        this.authWarningElement.classList.remove('show');
      }
    }
    
    if (!res.ok) throw new Error(await res.text());
    
    // Handle 204 No Content responses
    if (res.status === 204) {
      return null;
    }
    
    return res.json();
  }
}

// Create global instance
window.memoriaAPI = new MemoriaAPI();