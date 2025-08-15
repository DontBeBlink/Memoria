/**
 * Centralized API module for Memoria
 * Handles authentication, 401 responses, offline queueing, and provides consistent fetch interface
 */

class MemoriaAPI {
  constructor() {
    this.baseURL = window.location.origin;
    this.passcode = localStorage.getItem('memoria_pass') || '';
    this.authWarningElement = null;
    this.offlineIndicator = null;
    this.queueIndicator = null;
    this.isOnline = navigator.onLine;
    this.queueCount = 0;
    
    // Listen for online/offline events
    window.addEventListener('online', () => this.handleOnlineStatus(true));
    window.addEventListener('offline', () => this.handleOnlineStatus(false));
    
    // Listen for service worker messages
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', (e) => {
        if (e.data && e.data.type === 'queue-updated') {
          this.updateQueueCount();
        }
      });
    }
    
    // Initial queue count update
    this.updateQueueCount();
  }

  /**
   * Set the auth warning element for 401 handling
   */
  setAuthWarningElement(element) {
    this.authWarningElement = element;
  }

  /**
   * Set the offline indicator element
   */
  setOfflineIndicator(element) {
    this.offlineIndicator = element;
    this.updateOfflineIndicator();
  }

  /**
   * Set the queue indicator element
   */
  setQueueIndicator(element) {
    this.queueIndicator = element;
    this.updateQueueIndicator();
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
   * Handle online/offline status changes
   */
  handleOnlineStatus(online) {
    this.isOnline = online;
    this.updateOfflineIndicator();
    
    if (online) {
      // When back online, try to process queued requests
      this.processQueue();
    }
  }

  /**
   * Update offline indicator UI
   */
  updateOfflineIndicator() {
    if (this.offlineIndicator) {
      if (this.isOnline) {
        this.offlineIndicator.style.display = 'none';
      } else {
        this.offlineIndicator.style.display = 'block';
        this.offlineIndicator.textContent = 'You are offline. New items will be queued.';
        this.offlineIndicator.className = 'offline-toast';
      }
    }
  }

  /**
   * Update queue count and indicator
   */
  async updateQueueCount() {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      try {
        const channel = new MessageChannel();
        const promise = new Promise((resolve) => {
          channel.port1.onmessage = (e) => resolve(e.data.count || 0);
        });
        
        navigator.serviceWorker.controller.postMessage(
          { type: 'get-queue-count' },
          [channel.port2]
        );
        
        this.queueCount = await promise;
        this.updateQueueIndicator();
      } catch (error) {
        console.error('Failed to get queue count:', error);
      }
    }
  }

  /**
   * Update queue indicator UI
   */
  updateQueueIndicator() {
    if (this.queueIndicator) {
      if (this.queueCount > 0) {
        this.queueIndicator.style.display = 'inline-block';
        this.queueIndicator.textContent = `${this.queueCount} queued`;
        this.queueIndicator.className = 'queue-indicator';
      } else {
        this.queueIndicator.style.display = 'none';
      }
    }
  }

  /**
   * Process queued requests
   */
  async processQueue() {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      try {
        navigator.serviceWorker.controller.postMessage({ type: 'process-queue' });
        // Update queue count after a short delay
        setTimeout(() => this.updateQueueCount(), 1000);
      } catch (error) {
        console.error('Failed to process queue:', error);
      }
    }
  }

  /**
   * Make an API request with authentication and offline handling
   */
  async request(path, method = 'GET', body = null) {
    try {
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
      
      // Handle queued response (202 status from service worker)
      if (res.status === 202) {
        const data = await res.json();
        if (data.queued) {
          this.updateQueueCount();
          return { queued: true, message: data.message };
        }
      }
      
      if (!res.ok) throw new Error(await res.text());
      
      // Handle 204 No Content responses
      if (res.status === 204) {
        return null;
      }
      
      return res.json();
    } catch (error) {
      // If this is a network error and we're making a POST request to memories or tasks,
      // the service worker should have already queued it
      if (method === 'POST' && (path === '/memories' || path === '/tasks')) {
        this.updateQueueCount();
        return { queued: true, message: 'Request queued for when online' };
      }
      throw error;
    }
  }
}

// Create global instance
window.memoriaAPI = new MemoriaAPI();