/**
 * Langly API Client
 * JavaScript client for interacting with the Langly FastAPI backend
 */

class LanglyAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || window.location.origin;
        this.apiVersion = 'v1';
        this.wsConnections = new Map();
    }

    // HTTP request helper
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}/api/${this.apiVersion}${endpoint}`;
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const config = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({
                    detail: response.statusText
                }));
                throw new APIError(
                    error.detail || 'Request failed',
                    response.status
                );
            }
            
            return await response.json();
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            throw new APIError(error.message, 0);
        }
    }

    // Health endpoints
    async getHealth() {
        return await fetch(`${this.baseUrl}/health`).then(r => r.json());
    }

    async getReadiness() {
        return await fetch(`${this.baseUrl}/ready`).then(r => r.json());
    }

    async getLiveness() {
        return await fetch(`${this.baseUrl}/live`).then(r => r.json());
    }

    // Task endpoints
    async createTask(taskData) {
        return await this.request('/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData),
        });
    }

    async getTask(taskId) {
        return await this.request(`/tasks/${taskId}`);
    }

    async listTasks(params = {}) {
        const query = new URLSearchParams(params).toString();
        return await this.request(`/tasks${query ? '?' + query : ''}`);
    }

    async updateTask(taskId, updates) {
        return await this.request(`/tasks/${taskId}`, {
            method: 'PATCH',
            body: JSON.stringify(updates),
        });
    }

    async cancelTask(taskId) {
        return await this.request(`/tasks/${taskId}/cancel`, {
            method: 'POST',
        });
    }

    // Workflow endpoints
    async createWorkflow(workflowData) {
        return await this.request('/workflows', {
            method: 'POST',
            body: JSON.stringify(workflowData),
        });
    }

    async getWorkflow(workflowId) {
        return await this.request(`/workflows/${workflowId}`);
    }

    async listWorkflows(params = {}) {
        const query = new URLSearchParams(params).toString();
        return await this.request(`/workflows${query ? '?' + query : ''}`);
    }

    async pauseWorkflow(workflowId) {
        return await this.request(`/workflows/${workflowId}/pause`, {
            method: 'POST',
        });
    }

    async resumeWorkflow(workflowId) {
        return await this.request(`/workflows/${workflowId}/resume`, {
            method: 'POST',
        });
    }

    // Agent endpoints
    async getAgent(agentId) {
        return await this.request(`/agents/${agentId}`);
    }

    async listAgents() {
        return await this.request('/agents');
    }

    async getAgentState(agentId) {
        return await this.request(`/agents/${agentId}/state`);
    }

    async getAgentMetrics(agentId) {
        return await this.request(`/agents/${agentId}/metrics`);
    }

    // Tool endpoints
    async listTools() {
        return await this.request('/tools');
    }

    async getTool(toolName) {
        return await this.request(`/tools/${toolName}`);
    }

    async registerTool(toolData) {
        return await this.request('/tools', {
            method: 'POST',
            body: JSON.stringify(toolData),
        });
    }

    async updateTool(toolName, updates) {
        return await this.request(`/tools/${toolName}`, {
            method: 'PATCH',
            body: JSON.stringify(updates),
        });
    }

    async deleteTool(toolName) {
        return await this.request(`/tools/${toolName}`, {
            method: 'DELETE',
        });
    }

    async executeTool(toolName, params) {
        return await this.request(`/tools/${toolName}/execute`, {
            method: 'POST',
            body: JSON.stringify(params),
        });
    }

    // HITL Intervention endpoints
    async listInterventions(status = 'pending') {
        return await this.request(`/interventions?status=${status}`);
    }

    async getIntervention(interventionId) {
        return await this.request(`/interventions/${interventionId}`);
    }

    async approveIntervention(interventionId, feedback = '') {
        return await this.request(`/interventions/${interventionId}/approve`, {
            method: 'POST',
            body: JSON.stringify({ feedback, approved: true }),
        });
    }

    async rejectIntervention(interventionId, feedback) {
        return await this.request(`/interventions/${interventionId}/reject`, {
            method: 'POST',
            body: JSON.stringify({ feedback, approved: false }),
        });
    }

    async requestMoreInfo(interventionId, questions) {
        return await this.request(`/interventions/${interventionId}/clarify`, {
            method: 'POST',
            body: JSON.stringify({ questions }),
        });
    }

    // Approval endpoints
    async listApprovals(status = 'pending') {
        return await this.request(`/approvals?status=${status}`);
    }

    async processApproval(approvalId, approved, feedback = '') {
        return await this.request(`/approvals/${approvalId}`, {
            method: 'POST',
            body: JSON.stringify({ approved, feedback }),
        });
    }

    // Checkpoint endpoints
    async listCheckpoints(workflowId) {
        return await this.request(`/checkpoints?workflow_id=${workflowId}`);
    }

    async getCheckpoint(checkpointId) {
        return await this.request(`/checkpoints/${checkpointId}`);
    }

    async createCheckpoint(workflowId, label = '') {
        return await this.request('/checkpoints', {
            method: 'POST',
            body: JSON.stringify({ workflow_id: workflowId, label }),
        });
    }

    async rollbackToCheckpoint(checkpointId) {
        return await this.request(`/checkpoints/${checkpointId}/rollback`, {
            method: 'POST',
        });
    }

    async compareCheckpoints(checkpointId1, checkpointId2) {
        return await this.request(
            `/checkpoints/compare?from=${checkpointId1}&to=${checkpointId2}`
        );
    }

    // Chat endpoint
    async sendMessage(message, workflowId = null) {
        return await this.request('/chat', {
            method: 'POST',
            body: JSON.stringify({ message, workflow_id: workflowId }),
        });
    }

    // Memory endpoints
    async queryMemory(query, memoryType = 'project') {
        return await this.request('/memory/query', {
            method: 'POST',
            body: JSON.stringify({ query, memory_type: memoryType }),
        });
    }

    async getConversationHistory(sessionId, limit = 50) {
        return await this.request(
            `/memory/conversation/${sessionId}?limit=${limit}`
        );
    }

    // Reliability endpoints
    async getSystemHealth() {
        return await this.request('/system/health');
    }

    async getCircuitBreakerStatus() {
        return await this.request('/system/circuit-breakers');
    }

    async getDegradationStatus() {
        return await this.request('/system/degradation');
    }

    // WebSocket connections
    connectWebSocket(channel = 'default', handlers = {}) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${channel}`;
        
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log(`WebSocket connected: ${channel}`);
            if (handlers.onOpen) handlers.onOpen();
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (handlers.onMessage) handlers.onMessage(data);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };
        
        ws.onerror = (error) => {
            console.error(`WebSocket error: ${channel}`, error);
            if (handlers.onError) handlers.onError(error);
        };
        
        ws.onclose = () => {
            console.log(`WebSocket closed: ${channel}`);
            this.wsConnections.delete(channel);
            if (handlers.onClose) handlers.onClose();
            
            // Auto-reconnect after 5 seconds
            if (handlers.autoReconnect !== false) {
                setTimeout(() => {
                    this.connectWebSocket(channel, handlers);
                }, 5000);
            }
        };
        
        this.wsConnections.set(channel, ws);
        return ws;
    }

    disconnectWebSocket(channel) {
        const ws = this.wsConnections.get(channel);
        if (ws) {
            ws.close();
            this.wsConnections.delete(channel);
        }
    }

    disconnectAllWebSockets() {
        this.wsConnections.forEach((ws, channel) => {
            ws.close();
        });
        this.wsConnections.clear();
    }

    sendWebSocketMessage(channel, data) {
        const ws = this.wsConnections.get(channel);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        } else {
            console.warn(`WebSocket not connected: ${channel}`);
        }
    }
}


// Custom API Error class
class APIError extends Error {
    constructor(message, statusCode) {
        super(message);
        this.name = 'APIError';
        this.statusCode = statusCode;
    }
}


// Event emitter for real-time updates
class EventEmitter {
    constructor() {
        this.listeners = new Map();
    }

    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
        return () => this.off(event, callback);
    }

    off(event, callback) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    emit(event, data) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.forEach(callback => callback(data));
        }
    }

    clear() {
        this.listeners.clear();
    }
}


// Langly Application State Manager
class LanglyApp {
    constructor() {
        this.api = new LanglyAPI();
        this.events = new EventEmitter();
        this.state = {
            health: null,
            agents: [],
            tasks: [],
            workflows: [],
            interventions: [],
            tools: [],
        };
        
        this.pollInterval = null;
    }

    async initialize() {
        // Check health
        try {
            this.state.health = await this.api.getHealth();
            this.events.emit('health:update', this.state.health);
        } catch (e) {
            console.error('Health check failed:', e);
            this.state.health = { status: 'offline' };
        }

        // Connect WebSocket for real-time updates
        this.api.connectWebSocket('default', {
            onMessage: (data) => this.handleWebSocketMessage(data),
            onOpen: () => this.events.emit('ws:connected'),
            onClose: () => this.events.emit('ws:disconnected'),
        });

        // Start polling for health updates
        this.startHealthPolling(30000);

        return this;
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'agent_update':
                this.events.emit('agent:update', data.payload);
                break;
            case 'task_update':
                this.events.emit('task:update', data.payload);
                break;
            case 'workflow_update':
                this.events.emit('workflow:update', data.payload);
                break;
            case 'intervention_required':
                this.events.emit('intervention:new', data.payload);
                break;
            case 'approval_required':
                this.events.emit('approval:new', data.payload);
                break;
            case 'error':
                this.events.emit('system:error', data.payload);
                break;
            default:
                console.log('Unknown WebSocket message type:', data.type);
        }
    }

    startHealthPolling(interval = 30000) {
        this.stopHealthPolling();
        this.pollInterval = setInterval(async () => {
            try {
                this.state.health = await this.api.getHealth();
                this.events.emit('health:update', this.state.health);
            } catch (e) {
                this.state.health = { status: 'offline' };
                this.events.emit('health:update', this.state.health);
            }
        }, interval);
    }

    stopHealthPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    async loadAgents() {
        try {
            this.state.agents = await this.api.listAgents();
            this.events.emit('agents:loaded', this.state.agents);
        } catch (e) {
            console.error('Failed to load agents:', e);
        }
    }

    async loadTasks() {
        try {
            this.state.tasks = await this.api.listTasks();
            this.events.emit('tasks:loaded', this.state.tasks);
        } catch (e) {
            console.error('Failed to load tasks:', e);
        }
    }

    async loadWorkflows() {
        try {
            this.state.workflows = await this.api.listWorkflows();
            this.events.emit('workflows:loaded', this.state.workflows);
        } catch (e) {
            console.error('Failed to load workflows:', e);
        }
    }

    async loadInterventions() {
        try {
            this.state.interventions = await this.api.listInterventions();
            this.events.emit('interventions:loaded', this.state.interventions);
        } catch (e) {
            console.error('Failed to load interventions:', e);
        }
    }

    async loadTools() {
        try {
            this.state.tools = await this.api.listTools();
            this.events.emit('tools:loaded', this.state.tools);
        } catch (e) {
            console.error('Failed to load tools:', e);
        }
    }

    destroy() {
        this.stopHealthPolling();
        this.api.disconnectAllWebSockets();
        this.events.clear();
    }
}


// Export for use in pages
window.LanglyAPI = LanglyAPI;
window.LanglyApp = LanglyApp;
window.APIError = APIError;
window.EventEmitter = EventEmitter;
