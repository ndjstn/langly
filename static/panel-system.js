/**
 * Flexible Panel System for Langly
 * Provides minimize, maximize, drag-and-drop, and resize functionality
 */

class PanelSystem {
  constructor() {
    this.panels = new Map();
    this.draggedPanel = null;
    this.resizing = null;
    this.layoutKey = 'langly_panel_layout';
    this.init();
  }

  init() {
    // Load saved layout
    this.loadLayout();
    
    // Set up event listeners
    document.addEventListener('mouseup', () => {
      this.draggedPanel = null;
      this.resizing = null;
    });
    
    document.addEventListener('mousemove', (e) => {
      if (this.draggedPanel) {
        this.handleDrag(e);
      }
      if (this.resizing) {
        this.handleResize(e);
      }
    });
  }

  createPanel(id, title, content, options = {}) {
    const panel = document.createElement('div');
    panel.className = 'panel draggable-panel';
    panel.dataset.panelId = id;
    panel.dataset.state = 'normal'; // normal, minimized, maximized
    
    // Panel header with controls
    const header = document.createElement('div');
    header.className = 'panel-header';
    header.innerHTML = `
      <div class="panel-title">
        <span class="drag-handle">⋮⋮</span>
        <span class="panel-icon">${options.icon || '🤖'}</span>
        <span class="panel-name">${title}</span>
      </div>
      <div class="panel-controls">
        <button class="panel-btn minimize-btn" title="Minimize">−</button>
        <button class="panel-btn maximize-btn" title="Maximize">□</button>
        <button class="panel-btn close-btn" title="Close">×</button>
      </div>
    `;
    
    // Panel body
    const body = document.createElement('div');
    body.className = 'panel-body';
    body.appendChild(content);
    
    // Resize handle
    const resizeHandle = document.createElement('div');
    resizeHandle.className = 'resize-handle';
    
    panel.appendChild(header);
    panel.appendChild(body);
    panel.appendChild(resizeHandle);
    
    // Add event listeners
    this.attachPanelEvents(panel, header, resizeHandle);
    
    // Store panel reference
    this.panels.set(id, {
      element: panel,
      state: 'normal',
      position: { x: 0, y: 0 },
      size: { width: null, height: null }
    });
    
    return panel;
  }

  attachPanelEvents(panel, header, resizeHandle) {
    const id = panel.dataset.panelId;
    
    // Drag functionality
    const dragHandle = header.querySelector('.drag-handle');
    dragHandle.addEventListener('mousedown', (e) => {
      if (panel.dataset.state === 'maximized') return;
      
      e.preventDefault();
      this.draggedPanel = {
        element: panel,
        startX: e.clientX - panel.offsetLeft,
        startY: e.clientY - panel.offsetTop
      };
      panel.classList.add('dragging');
    });
    
    // Minimize button
    header.querySelector('.minimize-btn').addEventListener('click', () => {
      this.toggleMinimize(id);
    });
    
    // Maximize button
    header.querySelector('.maximize-btn').addEventListener('click', () => {
      this.toggleMaximize(id);
    });
    
    // Close button
    header.querySelector('.close-btn').addEventListener('click', () => {
      this.closePanel(id);
    });
    
    // Resize functionality
    resizeHandle.addEventListener('mousedown', (e) => {
      if (panel.dataset.state === 'maximized') return;
      
      e.preventDefault();
      this.resizing = {
        element: panel,
        startX: e.clientX,
        startY: e.clientY,
        startWidth: panel.offsetWidth,
        startHeight: panel.offsetHeight
      };
    });
  }

  handleDrag(e) {
    if (!this.draggedPanel) return;
    
    const panel = this.draggedPanel.element;
    const x = e.clientX - this.draggedPanel.startX;
    const y = e.clientY - this.draggedPanel.startY;
    
    panel.style.left = x + 'px';
    panel.style.top = y + 'px';
    panel.style.position = 'absolute';
    
    // Update stored position
    const id = panel.dataset.panelId;
    if (this.panels.has(id)) {
      this.panels.get(id).position = { x, y };
    }
  }

  handleResize(e) {
    if (!this.resizing) return;
    
    const panel = this.resizing.element;
    const deltaX = e.clientX - this.resizing.startX;
    const deltaY = e.clientY - this.resizing.startY;
    
    const newWidth = Math.max(250, this.resizing.startWidth + deltaX);
    const newHeight = Math.max(200, this.resizing.startHeight + deltaY);
    
    panel.style.width = newWidth + 'px';
    panel.style.height = newHeight + 'px';
    
    // Update stored size
    const id = panel.dataset.panelId;
    if (this.panels.has(id)) {
      this.panels.get(id).size = { width: newWidth, height: newHeight };
    }
  }

  toggleMinimize(id) {
    const panelData = this.panels.get(id);
    if (!panelData) return;
    
    const panel = panelData.element;
    const currentState = panel.dataset.state;
    
    if (currentState === 'minimized') {
      panel.dataset.state = 'normal';
      panel.classList.remove('minimized');
      panelData.state = 'normal';
    } else {
      panel.dataset.state = 'minimized';
      panel.classList.add('minimized');
      panelData.state = 'minimized';
    }
    
    this.saveLayout();
  }

  toggleMaximize(id) {
    const panelData = this.panels.get(id);
    if (!panelData) return;
    
    const panel = panelData.element;
    const currentState = panel.dataset.state;
    
    if (currentState === 'maximized') {
      panel.dataset.state = 'normal';
      panel.classList.remove('maximized');
      panelData.state = 'normal';
      
      // Restore previous size/position
      if (panelData.size.width) {
        panel.style.width = panelData.size.width + 'px';
        panel.style.height = panelData.size.height + 'px';
      }
      if (panelData.position.x !== 0 || panelData.position.y !== 0) {
        panel.style.left = panelData.position.x + 'px';
        panel.style.top = panelData.position.y + 'px';
      }
    } else {
      // Save current position before maximizing
      panelData.size = {
        width: panel.offsetWidth,
        height: panel.offsetHeight
      };
      panelData.position = {
        x: panel.offsetLeft,
        y: panel.offsetTop
      };
      
      panel.dataset.state = 'maximized';
      panel.classList.add('maximized');
      panelData.state = 'maximized';
      
      // Reset inline styles for maximized state
      panel.style.width = '';
      panel.style.height = '';
      panel.style.left = '';
      panel.style.top = '';
    }
    
    this.saveLayout();
  }

  closePanel(id) {
    const panelData = this.panels.get(id);
    if (!panelData) return;
    
    panelData.element.style.display = 'none';
    panelData.state = 'closed';
    this.saveLayout();
  }

  showPanel(id) {
    const panelData = this.panels.get(id);
    if (!panelData) return;
    
    panelData.element.style.display = '';
    if (panelData.state === 'closed') {
      panelData.state = 'normal';
      panelData.element.dataset.state = 'normal';
    }
    this.saveLayout();
  }

  saveLayout() {
    const layout = {};
    
    this.panels.forEach((data, id) => {
      layout[id] = {
        state: data.state,
        position: data.position,
        size: data.size,
        visible: data.element.style.display !== 'none'
      };
    });
    
    localStorage.setItem(this.layoutKey, JSON.stringify(layout));
  }

  loadLayout() {
    const savedLayout = localStorage.getItem(this.layoutKey);
    if (!savedLayout) return;
    
    try {
      const layout = JSON.parse(savedLayout);
      
      // Apply layout after panels are created
      setTimeout(() => {
        Object.entries(layout).forEach(([id, config]) => {
          const panelData = this.panels.get(id);
          if (!panelData) return;
          
          const panel = panelData.element;
          
          // Restore state
          panel.dataset.state = config.state;
          panelData.state = config.state;
          
          if (config.state === 'minimized') {
            panel.classList.add('minimized');
          } else if (config.state === 'maximized') {
            panel.classList.add('maximized');
          }
          
          // Restore visibility
          if (!config.visible) {
            panel.style.display = 'none';
          }
          
          // Restore position (only if not maximized)
          if (config.state !== 'maximized' && config.position) {
            if (config.position.x !== 0 || config.position.y !== 0) {
              panel.style.position = 'absolute';
              panel.style.left = config.position.x + 'px';
              panel.style.top = config.position.y + 'px';
            }
            panelData.position = config.position;
          }
          
          // Restore size (only if not maximized or minimized)
          if (config.state === 'normal' && config.size && config.size.width) {
            panel.style.width = config.size.width + 'px';
            panel.style.height = config.size.height + 'px';
            panelData.size = config.size;
          }
        });
      }, 100);
    } catch (e) {
      console.error('Failed to load panel layout:', e);
    }
  }

  resetLayout() {
    localStorage.removeItem(this.layoutKey);
    location.reload();
  }
}

// Export for use in main app
window.PanelSystem = PanelSystem;
