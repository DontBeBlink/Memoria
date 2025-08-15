/**
 * Shared UI components for Memoria
 * Handles header rendering, navigation, breadcrumbs, and auth banner
 */

class MemoriaUI {
  constructor() {
    this.currentPage = 'hub'; // default
    this.pages = {
      'hub': { title: 'Hub', href: '/index.html' },
      'memories': { title: 'Memories', href: '/web/memories.html' },
      'agenda': { title: 'Agenda', href: '/web/agenda.html' },
      'backup': { title: 'Backup', href: '/web/backup.html' },
      'settings': { title: 'Settings', href: '/web/settings.html' }
    };
  }

  /**
   * Set the current page for breadcrumb and active nav styling
   */
  setCurrentPage(page) {
    this.currentPage = page;
  }

  /**
   * Render the shared header with navigation and breadcrumbs
   */
  renderHeader(containerElement, options = {}) {
    const {
      showMicButton = false,
      showInstallButton = false,
      onPasscodeSet = null,
      onMicButtonClick = null,
      onInstallClick = null
    } = options;

    const currentPageInfo = this.pages[this.currentPage] || { title: 'Hub' };
    
    containerElement.innerHTML = `
      <h1>
        ${this.currentPage === 'hub' 
          ? 'Memoria Hub' 
          : `<a href="/" style="color: inherit; text-decoration: none;">Memoria Hub</a> / ${currentPageInfo.title}`
        }
      </h1>
      <div class="nav-links" style="display: flex; gap: 8px; align-items: center; margin-right: auto;">
        ${this.renderNavLinks()}
      </div>
      <div class="row">
        <input id="pass" type="text" placeholder="Passcode" style="max-width:160px; padding:8px; border-radius:6px; border:1px solid #374151; background:#0f172a; color:#e5e7eb;"/>
        <button id="savePass">Set</button>
        ${showMicButton ? '<button id="micButton" class="mic-button" title="Hold to record voice memo">🎤</button>' : ''}
        ${showMicButton ? '<span id="micStatus" class="status-message"></span>' : ''}
        ${showInstallButton ? '<button id="install" style="display:none;">Install App</button>' : ''}
      </div>
    `;

    // Setup event handlers
    this.setupPasscodeHandler(onPasscodeSet);
    
    if (showMicButton && onMicButtonClick) {
      const micButton = containerElement.querySelector('#micButton');
      if (micButton) micButton.addEventListener('click', onMicButtonClick);
    }
    
    if (showInstallButton && onInstallClick) {
      const installButton = containerElement.querySelector('#install');
      if (installButton) installButton.addEventListener('click', onInstallClick);
    }
  }

  /**
   * Render navigation links with active state
   */
  renderNavLinks() {
    return Object.entries(this.pages).map(([key, page]) => {
      const isActive = key === this.currentPage;
      const style = isActive 
        ? 'color:#e5e7eb; text-decoration:none; padding:8px 12px; border:1px solid #2563eb; border-radius:6px; font-size:14px; background:#2563eb;'
        : 'color:#60a5fa; text-decoration:none; padding:8px 12px; border:1px solid #374151; border-radius:6px; font-size:14px;';
      
      return `<a href="${page.href}" style="${style}">${page.title}</a>`;
    }).join('');
  }

  /**
   * Setup passcode input handler
   */
  setupPasscodeHandler(onPasscodeSet) {
    const passEl = document.getElementById('pass');
    const savePassBtn = document.getElementById('savePass');
    
    if (passEl && savePassBtn) {
      // Set current passcode
      passEl.value = window.memoriaAPI.getPasscode();
      
      savePassBtn.onclick = () => {
        const passcode = passEl.value.trim();
        window.memoriaAPI.setPasscode(passcode);
        alert('Passcode set locally');
        if (onPasscodeSet) onPasscodeSet(passcode);
      };
    }
  }

  /**
   * Render auth warning banner
   */
  renderAuthWarning(containerElement) {
    containerElement.innerHTML = `
      <div id="authWarning" class="auth-warning">
        <strong>Unauthorized!</strong> Please set your Passcode to match the AUTH_TOKEN from your .env file.
      </div>
    `;
    
    // Set the auth warning element in the API
    const authWarning = containerElement.querySelector('#authWarning');
    window.memoriaAPI.setAuthWarningElement(authWarning);
    
    return authWarning;
  }
}

// Create global instance
window.memoriaUI = new MemoriaUI();