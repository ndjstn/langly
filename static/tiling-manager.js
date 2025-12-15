/**
 * Tiling Window Manager for Langly
 * Provides automatic tiling behavior like i3, awesome, dwm, etc.
 */

class TilingManager {
  constructor(container) {
    this.container = container || document.getElementById('agents-grid');
    this.panels = new Map();
    this.layout = 'grid'; // grid, vertical, horizontal, master-stack
    this.masterRatio = 0.5;
    this.focusedPanel = null;
    this.minimizedPanels = new Set();
    
    this.init();
  }

  init() {
    // Set container to flex for tiling layout
    this.container.style.display = 'flex';
    this.container.style.flexWrap = 'wrap';
    this.container.style.position = 'relative';
    this.container.style.height = '100%';
    
    // Initialize existing panels
    this.initializePanels();
    
    // Set up keyboard shortcuts
    this.setupKeyboardShortcuts();
    
    // Load saved layout preferences
    this.loadPreferences();
  }

  initializePanels() {
    // Find all panels in the container
    const panelElements = this.container.querySelectorAll('.panel');
    
    panelElements.forEach((panel, index) => {
      const id = panel.dataset?.panelId || `panel-${index}`;
      
      this.panels.set(id, {
        element: panel,
        minimized: false,
        focused: false,
        originalParent: panel.parentNode
      });
      
      // Add tiling-specific classes
      panel.classList.add('tiled-panel');
      
      // Override panel controls for tiling behavior
      this.overridePanelControls(panel, id);
    });
    
    // Apply initial layout
    this.applyLayout();
  }

  overridePanelControls(panel, id) {
    // Override minimize button
    const minimizeBtn = panel.querySelector('.minimize-btn, button[title="Minimize"]');
    if (minimizeBtn) {
      minimizeBtn.onclick = (e) => {
        e.preventDefault();
        this.toggleMinimize(id);
      };
    }
    
    // Override maximize button to cycle layouts
    const maximizeBtn = panel.querySelector('.maximize-btn, button[title="Maximize"]');
    if (maximizeBtn) {
      maximizeBtn.onclick = (e) => {
        e.preventDefault();
        this.toggleMaximize(id);
      };
    }
    
    // Override close button
    const closeBtn = panel.querySelector('.close-btn, button[title="Close"]');
    if (closeBtn) {
      closeBtn.onclick = (e) => {
        e.preventDefault();
        this.closePanel(id);
      };
    }
    
    // Add focus behavior
    panel.addEventListener('mousedown', () => {
      this.focusPanel(id);
    });
    
    // Disable individual panel dragging in tiling mode
    const dragHandle = panel.querySelector('.drag-handle');
    if (dragHandle) {
      dragHandle.style.display = 'none';
    }
    
    // Remove resize handle in tiling mode
    const resizeHandle = panel.querySelector('.resize-handle');
    if (resizeHandle) {
      resizeHandle.style.display = 'none';
    }
  }

  applyLayout() {
    const activePanels = Array.from(this.panels.entries())
      .filter(([id, data]) => !data.minimized && data.element.style.display !== 'none');
    
    if (activePanels.length === 0) return;
    
    // Reset all panel styles
    activePanels.forEach(([id, data]) => {
      const panel = data.element;
      panel.style.position = 'relative';
      panel.style.top = '';
      panel.style.left = '';
      panel.style.transform = '';
      panel.style.width = '';
      panel.style.height = '';
      panel.style.flex = '';
      panel.classList.remove('maximized');
    });
    
    switch (this.layout) {
      case 'grid':
        this.applyGridLayout(activePanels);
        break;
      case 'vertical':
        this.applyVerticalLayout(activePanels);
        break;
      case 'horizontal':
        this.applyHorizontalLayout(activePanels);
        break;
      case 'master-stack':
        this.applyMasterStackLayout(activePanels);
        break;
      case 'fullscreen':
        this.applyFullscreenLayout(activePanels);
        break;
    }
  }

  applyGridLayout(panels) {
    const count = panels.length;
    
    // Calculate optimal grid dimensions
    const cols = Math.ceil(Math.sqrt(count));
    const rows = Math.ceil(count / cols);
    
    // Set container to grid
    this.container.style.display = 'grid';
    this.container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
    this.container.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
    this.container.style.gap = '8px';
    
    // Position panels in grid
    panels.forEach(([id, data], index) => {
      const panel = data.element;
      panel.style.gridColumn = '';
      panel.style.gridRow = '';
    });
  }

  applyVerticalLayout(panels) {
    // Stack panels vertically
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'column';
    this.container.style.gap = '8px';
    
    panels.forEach(([id, data]) => {
      const panel = data.element;
      panel.style.flex = '1 1 0';
      panel.style.minHeight = '100px';
      panel.style.width = '100%';
    });
  }

  applyHorizontalLayout(panels) {
    // Arrange panels horizontally
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'row';
    this.container.style.gap = '8px';
    
    panels.forEach(([id, data]) => {
      const panel = data.element;
      panel.style.flex = '1 1 0';
      panel.style.minWidth = '200px';
      panel.style.height = '100%';
    });
  }

  applyMasterStackLayout(panels) {
    if (panels.length === 0) return;
    
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'row';
    this.container.style.gap = '8px';
    
    if (panels.length === 1) {
      // Single panel takes full space
      const [id, data] = panels[0];
      data.element.style.flex = '1';
      data.element.style.width = '100%';
      data.element.style.height = '100%';
    } else {
      // First panel is master (left)
      const [masterId, masterData] = panels[0];
      const master = masterData.element;
      master.style.flex = `0 0 ${this.masterRatio * 100}%`;
      master.style.height = '100%';
      
      // Create stack container for remaining panels
      const stackContainer = document.createElement('div');
      stackContainer.style.flex = `0 0 ${(1 - this.masterRatio) * 100}%`;
      stackContainer.style.display = 'flex';
      stackContainer.style.flexDirection = 'column';
      stackContainer.style.gap = '8px';
      stackContainer.style.height = '100%';
      
      // Add stack panels
      for (let i = 1; i < panels.length; i++) {
        const [id, data] = panels[i];
        const panel = data.element;
        panel.style.flex = '1 1 0';
        panel.style.minHeight = '100px';
        stackContainer.appendChild(panel);
      }
      
      // Clear container and re-add panels
      this.container.innerHTML = '';
      this.container.appendChild(master);
      this.container.appendChild(stackContainer);
    }
  }

  applyFullscreenLayout(panels) {
    // Show only focused panel or first panel
    const focusedPanel = this.focusedPanel && this.panels.get(this.focusedPanel);
    const panelToShow = focusedPanel || panels[0];
    
    if (!panelToShow) return;
    
    panels.forEach(([id, data]) => {
      if (id === (focusedPanel ? this.focusedPanel : panels[0][0])) {
        data.element.style.display = '';
        data.element.style.position = 'absolute';
        data.element.style.top = '0';
        data.element.style.left = '0';
        data.element.style.width = '100%';
        data.element.style.height = '100%';
        data.element.style.zIndex = '10';
      } else {
        data.element.style.display = 'none';
      }
    });
  }

  toggleMinimize(id) {
    const panelData = this.panels.get(id);
    if (!panelData) return;
    
    panelData.minimized = !panelData.minimized;
    
    if (panelData.minimized) {
      panelData.element.classList.add('tiled-minimized');
      panelData.element.style.display = 'none';
      this.minimizedPanels.add(id);
    } else {
      panelData.element.classList.remove('tiled-minimized');
      panelData.element.style.display = '';
      this.minimizedPanels.delete(id);
    }
    
    // Re-tile remaining panels
    this.applyLayout();
    this.savePreferences();
  }

  toggleMaximize(id) {
    // In tiling mode, maximize cycles through layouts or toggles fullscreen
    if (this.layout === 'fullscreen') {
      this.setLayout('grid');
    } else {
      this.focusedPanel = id;
      this.setLayout('fullscreen');
    }
  }

  closePanel(id) {
    const panelData = this.panels.get(id);
    if (!panelData) return;
    
    panelData.element.style.display = 'none';
    this.panels.delete(id);
    
    // Re-tile remaining panels
    this.applyLayout();
    this.savePreferences();
  }

  focusPanel(id) {
    // Remove focus from all panels
    this.panels.forEach((data) => {
      data.element.classList.remove('tiled-focused');
      data.focused = false;
    });
    
    // Add focus to selected panel
    const panelData = this.panels.get(id);
    if (panelData) {
      panelData.element.classList.add('tiled-focused');
      panelData.focused = true;
      this.focusedPanel = id;
    }
  }

  setLayout(layoutName) {
    const validLayouts = ['grid', 'vertical', 'horizontal', 'master-stack', 'fullscreen'];
    if (!validLayouts.includes(layoutName)) return;
    
    this.layout = layoutName;
    this.applyLayout();
    this.savePreferences();
    
    // Update UI indicator
    this.updateLayoutIndicator();
  }

  cycleLayout() {
    const layouts = ['grid', 'horizontal', 'vertical', 'master-stack'];
    const currentIndex = layouts.indexOf(this.layout);
    const nextIndex = (currentIndex + 1) % layouts.length;
    this.setLayout(layouts[nextIndex]);
  }

  adjustMasterRatio(delta) {
    this.masterRatio = Math.max(0.2, Math.min(0.8, this.masterRatio + delta));
    if (this.layout === 'master-stack') {
      this.applyLayout();
    }
    this.savePreferences();
  }

  setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Check if we're focused on an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }
      
      // Win/Super + key combinations
      if (e.metaKey || e.altKey) {
        switch(e.key) {
          case ' ':
            e.preventDefault();
            this.cycleLayout();
            break;
          case 'Enter':
            e.preventDefault();
            if (this.focusedPanel) {
              this.toggleMaximize(this.focusedPanel);
            }
            break;
          case 'h':
            e.preventDefault();
            this.adjustMasterRatio(-0.05);
            break;
          case 'l':
            e.preventDefault();
            this.adjustMasterRatio(0.05);
            break;
          case 'g':
            e.preventDefault();
            this.setLayout('grid');
            break;
          case 'v':
            e.preventDefault();
            this.setLayout('vertical');
            break;
          case 't':
            e.preventDefault();
            this.setLayout('horizontal');
            break;
          case 'm':
            e.preventDefault();
            this.setLayout('master-stack');
            break;
        }
      }
    });
  }

  updateLayoutIndicator() {
    // Update any UI element showing current layout
    const indicator = document.getElementById('layout-indicator');
    if (indicator) {
      indicator.textContent = `Layout: ${this.layout}`;
    }
  }

  savePreferences() {
    const prefs = {
      layout: this.layout,
      masterRatio: this.masterRatio,
      minimizedPanels: Array.from(this.minimizedPanels)
    };
    localStorage.setItem('langly_tiling_prefs', JSON.stringify(prefs));
  }

  loadPreferences() {
    const saved = localStorage.getItem('langly_tiling_prefs');
    if (!saved) return;
    
    try {
      const prefs = JSON.parse(saved);
      this.layout = prefs.layout || 'grid';
      this.masterRatio = prefs.masterRatio || 0.5;
      
      // Restore minimized panels
      if (prefs.minimizedPanels) {
        prefs.minimizedPanels.forEach(id => {
          if (this.panels.has(id)) {
            this.toggleMinimize(id);
          }
        });
      }
      
      this.applyLayout();
    } catch (e) {
      console.error('Failed to load tiling preferences:', e);
    }
  }

  // Public API
  showLayoutSelector() {
    const layouts = [
      { name: 'grid', icon: '⊞', description: 'Grid Layout' },
      { name: 'horizontal', icon: '═', description: 'Horizontal Stack' },
      { name: 'vertical', icon: '║', description: 'Vertical Stack' },
      { name: 'master-stack', icon: '⊟', description: 'Master + Stack' }
    ];
    
    // You can implement a nice UI selector here
    // For now, just cycle
    this.cycleLayout();
  }

  reset() {
    localStorage.removeItem('langly_tiling_prefs');
    this.layout = 'grid';
    this.masterRatio = 0.5;
    this.minimizedPanels.clear();
    this.focusedPanel = null;
    
    // Restore all panels
    this.panels.forEach((data, id) => {
      data.element.style.display = '';
      data.element.classList.remove('tiled-minimized', 'tiled-focused');
      data.minimized = false;
      data.focused = false;
    });
    
    this.applyLayout();
  }
}

// Initialize on load
window.TilingManager = TilingManager;
