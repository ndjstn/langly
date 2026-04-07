/**
 * Langly API Client
 * JavaScript client for interacting with the Langly FastAPI backend
 */

class LanglyAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || window.location.origin;
        this.apiVersion = 'v2';
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
        return await fetch(`${this.baseUrl}/api/v2/health/v2`).then(r => r.json());
    }

    async getReadiness() {
        return await fetch(`${this.baseUrl}/api/v2/health/ready`).then(r => r.json());
    }

    async getLiveness() {
        return await fetch(`${this.baseUrl}/api/v2/health/live`).then(r => r.json());
    }

    // Task endpoints
    async createTask(taskData) {
        throw new APIError('Tasks API is not supported in v2', 400);
    }

    async getTask(taskId) {
        throw new APIError('Tasks API is not supported in v2', 400);
    }

    async listTasks(params = {}) {
        throw new APIError('Tasks API is not supported in v2', 400);
    }

    async updateTask(taskId, updates) {
        throw new APIError('Tasks API is not supported in v2', 400);
    }

    async cancelTask(taskId) {
        throw new APIError('Tasks API is not supported in v2', 400);
    }

    // Workflow endpoints
    async createWorkflow(workflowData) {
        return await this.request('/workflows/run', {
            method: 'POST',
            body: JSON.stringify(workflowData),
        });
    }

    async getWorkflow(workflowId) {
        throw new APIError('Workflow detail is not supported in v2', 400);
    }

    async listWorkflows(params = {}) {
        throw new APIError('Workflow listing is not supported in v2', 400);
    }

    async pauseWorkflow(workflowId) {
        throw new APIError('Workflow pause is not supported in v2', 400);
    }

    async resumeWorkflow(workflowId) {
        throw new APIError('Workflow resume is not supported in v2', 400);
    }

    // Agent endpoints
    async getAgent(agentId) {
        return await this.request(`/agents/${agentId}`);
    }

    async listAgents() {
        return await this.request('/agents');
    }

    async getAgentState(agentId) {
        throw new APIError('Agent state is not supported in v2', 400);
    }

    async getAgentMetrics(agentId) {
        throw new APIError('Agent metrics are not supported in v2', 400);
    }

    // Tool endpoints
    async listTools() {
        return await this.request('/tools');
    }

    async getTool(toolName) {
        return await this.request(`/tools/${toolName}`);
    }

    async registerTool(toolData) {
        throw new APIError('Tool registration is not supported in v2', 400);
    }

    async updateTool(toolName, updates) {
        throw new APIError('Tool updates are not supported in v2', 400);
    }

    async deleteTool(toolName) {
        throw new APIError('Tool deletion is not supported in v2', 400);
    }

    async executeTool(toolName, params) {
        throw new APIError('Tool execution is not supported in v2 via API', 400);
    }

    // HITL Intervention endpoints
    async listInterventions(status = 'pending') {
        const resolved = status === 'resolved' ? 'true' : 'false';
        return await this.request(`/hitl/requests?resolved=${resolved}`);
    }

    async getIntervention(interventionId) {
        return await this.request(`/hitl/requests/${interventionId}`);
    }

    async approveIntervention(interventionId, feedback = '') {
        return await this.request(`/hitl/requests/${interventionId}/resolve`, {
            method: 'POST',
            body: JSON.stringify({ notes: feedback, approved: true }),
        });
    }

    async rejectIntervention(interventionId, feedback) {
        return await this.request(`/hitl/requests/${interventionId}/resolve`, {
            method: 'POST',
            body: JSON.stringify({ notes: feedback, approved: false }),
        });
    }

    async requestMoreInfo(interventionId, questions) {
        throw new APIError('Clarification flow is not supported in v2', 400);
    }

    // Approval endpoints
    async listApprovals(status = 'pending') {
        throw new APIError('Approvals endpoint is not supported in v2', 400);
    }

    async processApproval(approvalId, approved, feedback = '') {
        throw new APIError('Approvals endpoint is not supported in v2', 400);
    }

    // Checkpoint endpoints
    async listCheckpoints(workflowId) {
        throw new APIError('Checkpoints are not supported in v2', 400);
    }

    async getCheckpoint(checkpointId) {
        throw new APIError('Checkpoints are not supported in v2', 400);
    }

    async createCheckpoint(workflowId, label = '') {
        throw new APIError('Checkpoints are not supported in v2', 400);
    }

    async rollbackToCheckpoint(checkpointId) {
        throw new APIError('Checkpoints are not supported in v2', 400);
    }

    async compareCheckpoints(checkpointId1, checkpointId2) {
        throw new APIError('Checkpoints are not supported in v2', 400);
    }

    // Chat endpoint
    async sendMessage(message, workflowId = null) {
        return await this.request('/workflows/run', {
            method: 'POST',
            body: JSON.stringify({ message, session_id: workflowId }),
        });
    }

    // Memory endpoints
    async queryMemory(query, memoryType = 'project') {
        throw new APIError('Memory API is not supported in v2', 400);
    }

    async getConversationHistory(sessionId, limit = 50) {
        throw new APIError('Memory API is not supported in v2', 400);
    }

    // Reliability endpoints
    async getSystemHealth() {
        throw new APIError('System health API is not supported in v2', 400);
    }

    async getCircuitBreakerStatus() {
        throw new APIError('Circuit breaker API is not supported in v2', 400);
    }

    async getDegradationStatus() {
        throw new APIError('Degradation API is not supported in v2', 400);
    }

    // WebSocket connections
    connectWebSocket(channel = 'deltas', handlers = {}) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/${this.apiVersion}/ws/${channel}`;
        
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
