#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single-page Flask app with 4 independent "agent windows" that can host different
LangChain/LangGraph-backed agents.

- One HTML page (inline template)
- 4 panels, each with its own chat history + input
- Backend routes: /api/agent/<agent_id>/send, /api/agent/<agent_id>/history, /api/agent/<agent_id>/reset
- Works even without LangChain installed (falls back to a simple echo agent)
- Ready for you to swap each agent's handler with real LangChain/LangGraph logic

Run:
  python app.py
Open:
  http://127.0.0.1:8000
"""
from __future__ import annotations

import os
import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from flask import Flask, jsonify, request, render_template_string, abort, make_response

# Import our enhanced agent implementations
try:
    from agents import router_agent, coder_agent, research_agent, critic_agent
except ImportError:
    # Fallback if agents.py is not available
    def router_agent(user_text: str, history: List[ChatMessage]) -> str:
        return f"[Router] {user_text}"
    
    def coder_agent(user_text: str, history: List[ChatMessage]) -> str:
        return f"[Coder] {user_text}"
    
    def research_agent(user_text: str, history: List[ChatMessage]) -> str:
        return f"[Research] {user_text}"
    
    def critic_agent(user_text: str, history: List[ChatMessage]) -> str:
        return f"[Critic] {user_text}"


# ----------------------------
# Git Management Functions
# ----------------------------
import subprocess
import json
from pathlib import Path
import shutil
import re


# ----------------------------
# GitHub Integration Functions
# ----------------------------
def get_github_status():
    """Get GitHub repository status and information."""
    try:
        # Get repository URL
        result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                             capture_output=True, text=True, check=True)
        repo_url = result.stdout.strip()
        
        # Extract owner/repo from URL
        if 'github.com' in repo_url:
            parts = repo_url.split('github.com/')[-1].replace('.git', '').split('/')
            if len(parts) == 2:
                owner, repo = parts
            else:
                return {'error': 'Invalid GitHub URL format'}
        else:
            return {'error': 'Not a GitHub repository'}
        
        # Get current branch
        branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                   capture_output=True, text=True, check=True)
        current_branch = branch_result.stdout.strip()
        
        return {
            'is_github': True,
            'owner': owner,
            'repo': repo,
            'url': repo_url,
            'branch': current_branch
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {'is_github': False, 'error': 'Not a git repository or no GitHub remote'}


def get_github_prs():
    """Get pull requests for current repository."""
    try:
        status = get_github_status()
        if not status.get('is_github'):
            return {'error': 'Not a GitHub repository'}
        
        # Use gh CLI to get PRs
        result = subprocess.run(['gh', 'pr', 'list', '--json', '--limit', '10'], 
                             capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            prs = json.loads(result.stdout)
            return {
                'prs': prs,
                'count': len(prs),
                'open_count': len([pr for pr in prs if pr['state'] == 'OPEN'])
            }
        return {'prs': [], 'count': 0, 'open_count': 0}
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return {'prs': [], 'count': 0, 'error': 'GitHub CLI not available or failed'}


def get_github_issues():
    """Get issues for current repository."""
    try:
        status = get_github_status()
        if not status.get('is_github'):
            return {'error': 'Not a GitHub repository'}
        
        # Use gh CLI to get issues
        result = subprocess.run(['gh', 'issue', 'list', '--json', '--limit', '20'], 
                             capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            issues = json.loads(result.stdout)
            return {
                'issues': issues,
                'count': len(issues),
                'open_count': len([issue for issue in issues if issue['state'] == 'OPEN'])
            }
        return {'issues': [], 'count': 0, 'open_count': 0}
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return {'issues': [], 'count': 0, 'error': 'GitHub CLI not available or failed'}


def get_github_workflows():
    """Get GitHub Actions workflow status."""
    try:
        status = get_github_status()
        if not status.get('is_github'):
            return {'error': 'Not a GitHub repository'}
        
        # Use gh CLI to get workflow runs
        result = subprocess.run(['gh', 'run', 'list', '--json', '--limit', '10'], 
                             capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            runs = json.loads(result.stdout)
            # Get workflow status summary
            recent_runs = runs[:5]
            return {
                'runs': recent_runs,
                'count': len(runs),
                'success_count': len([run for run in recent_runs if run['status'] == 'completed'])
            }
        return {'runs': [], 'count': 0, 'success_count': 0}
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return {'runs': [], 'count': 0, 'error': 'GitHub CLI not available or failed'}


# ----------------------------
# Git Management Functions
# ----------------------------
def get_git_status():
    """Get git repository status and file tree."""
    try:
        # Check if we're in a git repository
        subprocess.run(['git', 'rev-parse', '--git-dir'], 
                    check=True, capture_output=True)
        
        # Get git status
        result = subprocess.run(['git', 'status', '--porcelain'], 
                             capture_output=True, text=True, check=True)
        
        # Get branch info
        branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                   capture_output=True, text=True, check=True)
        current_branch = branch_result.stdout.strip()
        
        # Parse status output
        files = []
        for line in result.stdout.split('\n'):
            if line.strip():
                status = line[:2]
                file_path = line[3:]
                files.append({
                    'status': status,
                    'file': file_path,
                    'color': get_status_color(status)
                })
        
        return {
            'is_repo': True,
            'branch': current_branch,
            'files': files,
            'clean': len(files) == 0
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {'is_repo': False, 'error': 'Not a git repository'}


def get_status_color(status):
    """Get color for git status."""
    if status.startswith('??'):
        return '#ff6b6b'  # Untracked - red
    elif status.startswith(' M'):
        return '#feca57'  # Modified - yellow
    elif status.startswith('A'):
        return '#48dbfb'  # Added - blue
    elif status.startswith('D'):
        return '#ee5a24'  # Deleted - orange
    elif status.startswith('R'):
        return '#a55eea'  # Renamed - purple
    else:
        return '#95afc0'  # Default - gray


def get_git_tree():
    """Get git file tree with colors."""
    try:
        result = subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'HEAD'], 
                             capture_output=True, text=True, check=True)
        files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        tree = []
        for file_path in files:
            tree.append({
                'name': file_path.split('/')[-1],
                'path': file_path,
                'type': 'file' if '.' in file_path else 'dir'
            })
        
        return tree
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def get_git_log(max_count=50):
    """Get git commit log with branch information."""
    try:
        # Get the list of branches for each commit
        # Using pretty format to get structured data
        format_str = '%H|%P|%an|%ae|%ai|%s'
        result = subprocess.run(
            ['git', 'log', '--all', '--graph', f'--format={format_str}', f'-{max_count}'],
            capture_output=True, text=True, check=True
        )
        
        if not result.stdout.strip():
            return {'commits': []}
        
        commits = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            # Remove graph characters
            line = re.sub(r'^[\s\*\|\\\/]+', '', line).strip()
            if not line:
                continue
                
            parts = line.split('|')
            if len(parts) >= 6:
                commit_hash = parts[0]
                parents = parts[1].split() if parts[1] else []
                author = parts[2]
                email = parts[3]
                date = parts[4]
                message = '|'.join(parts[5:])  # Join back in case message has |
                
                # Get branches containing this commit
                branch_result = subprocess.run(
                    ['git', 'branch', '-a', '--contains', commit_hash],
                    capture_output=True, text=True, check=True
                )
                branches = []
                for branch in branch_result.stdout.split('\n'):
                    branch = branch.strip()
                    if branch and not branch.startswith('*'):
                        branch = branch.replace('* ', '')
                        if branch and branch not in branches:
                            branches.append(branch)
                
                # Get tags for this commit
                tag_result = subprocess.run(
                    ['git', 'tag', '--points-at', commit_hash],
                    capture_output=True, text=True, check=True
                )
                tags = [tag.strip() for tag in tag_result.stdout.split('\n') if tag.strip()]
                
                commits.append({
                    'hash': commit_hash,
                    'parents': parents,
                    'author': author,
                    'email': email,
                    'date': date,
                    'message': message,
                    'branches': branches,
                    'tags': tags
                })
        
        return {'commits': commits}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {'commits': [], 'error': 'Git not available or not a repository'}


# ----------------------------
# Task Warrior Functions
# ----------------------------
def get_task_warrior_tasks():
    """Get tasks from Task Warrior."""
    try:
        # Get only pending tasks (not completed or deleted)
        result = subprocess.run(['task', 'status:pending', 'export', 'rc.json.array=on'], 
                             capture_output=True, text=True, check=True)
        if result.stdout.strip():
            tasks = json.loads(result.stdout)
            # Filter to only show pending tasks and format them properly
            active_tasks = []
            for task in tasks:
                if task.get('status') == 'pending':
                    active_tasks.append({
                        'id': task.get('id', 0),
                        'description': task.get('description', 'No description'),
                        'project': task.get('project', ''),
                        'due': task.get('due', ''),
                        'priority': task.get('priority', ''),
                        'tags': task.get('tags', []),
                        'urgency': task.get('urgency', 0)
                    })
            return active_tasks
        return []
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"TaskWarrior error: {e}")
        return []


def add_task_warrior_task(description, project=None):
    """Add a new task to Task Warrior."""
    try:
        cmd = ['task', 'add', description]
        if project:
            cmd.extend(['project:', project])
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def complete_task_warrior_task(task_id):
    """Complete a task in Task Warrior."""
    try:
        subprocess.run(['task', str(task_id), 'done'], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# ----------------------------
# Color Schemes for Themes
# ----------------------------
COLOR_SCHEMES = {
    "default": {
        "bg": "#0b0d10",
        "panel": "#11151b", 
        "muted": "#93a4b7",
        "text": "#e6edf3",
        "border": "#243040",
        "accent": "#4aa3ff",
        "danger": "#ff4a6a",
        "ok": "#4affb5",
        "warning": "#ffa500",
        "github": "#24292e",
        "tasks": "#1a1f2e"
    },
    "dracula": {
        "bg": "#282a36",
        "panel": "#44475a",
        "muted": "#6272a4",
        "text": "#f8f8f2",
        "border": "#6272a4",
        "accent": "#bd93f9",
        "danger": "#ff5555",
        "ok": "#50fa7b",
        "warning": "#f1fa8c",
        "github": "#282a36",
        "tasks": "#44475a"
    },
    "gruvbox-dark": {
        "bg": "#282828",
        "panel": "#3c3836",
        "muted": "#928374",
        "text": "#ebdbb2",
        "border": "#665c54",
        "accent": "#d3869b",
        "danger": "#fb4934",
        "ok": "#b8bb26",
        "warning": "#fabd2f",
        "github": "#282828",
        "tasks": "#3c3836"
    },
    "nord": {
        "bg": "#2e3440",
        "panel": "#3b4252",
        "muted": "#4c566a",
        "text": "#d8dee9",
        "border": "#434c5e",
        "accent": "#88c0d0",
        "danger": "#bf616a",
        "ok": "#a3be8c",
        "warning": "#ebcb8b",
        "github": "#2e3440",
        "tasks": "#3b4252"
    },
    "tokyonight": {
        "bg": "#1a1b26",
        "panel": "#24283b",
        "muted": "#565f89",
        "text": "#c0caf5",
        "border": "#414868",
        "accent": "#7aa2f7",
        "danger": "#f7768e",
        "ok": "#9ece6a",
        "warning": "#e0af68",
        "github": "#1a1b26",
        "tasks": "#24283b"
    },
    "catppuccin-mocha": {
        "bg": "#1e1e2e",
        "panel": "#313244",
        "muted": "#6c7086",
        "text": "#cdd6f4",
        "border": "#45475a",
        "accent": "#8caaee",
        "danger": "#f38ba8",
        "ok": "#a6e3a1",
        "warning": "#f9e2af",
        "github": "#1e1e2e",
        "tasks": "#313244"
    },
    "material": {
        "bg": "#263238",
        "panel": "#37474f",
        "muted": "#546e7a",
        "text": "#eeffff",
        "border": "#455a64",
        "accent": "#c792ea",
        "danger": "#f07178",
        "ok": "#c3e88d",
        "warning": "#ffcb6b",
        "github": "#263238",
        "tasks": "#37474f"
    },
    "solarized-dark": {
        "bg": "#002b36",
        "panel": "#073642",
        "muted": "#657b83",
        "text": "#839496",
        "border": "#586e75",
        "accent": "#6c71c4",
        "danger": "#dc322f",
        "ok": "#859900",
        "warning": "#b58900",
        "github": "#002b36",
        "tasks": "#073642"
    },
    "onedark": {
        "bg": "#282c34",
        "panel": "#353b45",
        "muted": "#5c6370",
        "text": "#abb2bf",
        "border": "#4b5263",
        "accent": "#61afef",
        "danger": "#e06c75",
        "ok": "#98c379",
        "warning": "#d19a66",
        "github": "#282c34",
        "tasks": "#353b45"
    },
    "monokai": {
        "bg": "#272822",
        "panel": "#3e3d32",
        "muted": "#75715e",
        "text": "#f8f8f2",
        "border": "#49483e",
        "accent": "#66d9ef",
        "danger": "#f92672",
        "ok": "#a6e22e",
        "warning": "#fd971f",
        "github": "#272822",
        "tasks": "#3e3d32"
    },
    "cyberdream": {
        "bg": "#16181a",
        "panel": "#1e2124",
        "muted": "#7f8490",
        "text": "#ffffff",
        "border": "#3c4048",
        "accent": "#5ea1ff",
        "danger": "#ff6e6e",
        "ok": "#5eff6c",
        "warning": "#f1ff5f",
        "github": "#16181a",
        "tasks": "#1e2124"
    },
    "rose-pine": {
        "bg": "#1f1d2e",
        "panel": "#26233a",
        "muted": "#6e6a86",
        "text": "#e0def4",
        "border": "#56526e",
        "accent": "#9ccfd8",
        "danger": "#eb6f92",
        "ok": "#31748f",
        "warning": "#f6c177",
        "github": "#1f1d2e",
        "tasks": "#26233a"
    },
    "everforest": {
        "bg": "#2d353b",
        "panel": "#343f44",
        "muted": "#9da9a0",
        "text": "#d3c6aa",
        "border": "#4a5558",
        "accent": "#7fbbb3",
        "danger": "#e67e80",
        "ok": "#a7c080",
        "warning": "#dbbc7f",
        "github": "#2d353b",
        "tasks": "#343f44"
    },
    "kanagawa": {
        "bg": "#1f1f28",
        "panel": "#2a2a37",
        "muted": "#658594",
        "text": "#dcd7ba",
        "border": "#363646",
        "accent": "#7e9cd8",
        "danger": "#c34043",
        "ok": "#76946a",
        "warning": "#c0a36e",
        "github": "#1f1f28",
        "tasks": "#2a2a37"
    },
    "nightfox": {
        "bg": "#192330",
        "panel": "#21313f",
        "muted": "#71839b",
        "text": "#e0def4",
        "border": "#314759",
        "accent": "#82aaff",
        "danger": "#c94f6d",
        "ok": "#81b29a",
        "warning": "#ddb67f",
        "github": "#192330",
        "tasks": "#21313f"
    },
    "github-dark": {
        "bg": "#0d1117",
        "panel": "#161b22",
        "muted": "#7d8590",
        "text": "#c9d1d9",
        "border": "#21262d",
        "accent": "#58a6ff",
        "danger": "#f85149",
        "ok": "#3fb950",
        "warning": "#d29922",
        "github": "#0d1117",
        "tasks": "#161b22"
    },
    "cobalt2": {
        "bg": "#132738",
        "panel": "#1e3a4f",
        "muted": "#839496",
        "text": "#e5e5e5",
        "border": "#2c3f53",
        "accent": "#8fffff",
        "danger": "#ff6e6e",
        "ok": "#a6e22e",
        "warning": "#ff9f43",
        "github": "#132738",
        "tasks": "#1e3a4f"
    },
    "citylights": {
        "bg": "#1a1a1d",
        "panel": "#24252a",
        "muted": "#7f8490",
        "text": "#cfd7d7",
        "border": "#313439",
        "accent": "#7ca9f7",
        "danger": "#e27e8d",
        "ok": "#95e6cb",
        "warning": "#ffca85",
        "github": "#1a1a1d",
        "tasks": "#24252a"
    },
    "hybrid": {
        "bg": "#1c1e26",
        "panel": "#282a3a",
        "muted": "#6b7089",
        "text": "#d8d9dd",
        "border": "#343646",
        "accent": "#82aaff",
        "danger": "#f97b72",
        "ok": "#95e6cb",
        "warning": "#ffca85",
        "github": "#1c1e26",
        "tasks": "#282a3a"
    },
    "embark": {
        "bg": "#223244",
        "panel": "#3f4b59",
        "muted": "#93a1a1",
        "text": "#e0e0e0",
        "border": "#34404d",
        "accent": "#87ceeb",
        "danger": "#e57373",
        "ok": "#a1b56c",
        "warning": "#d4aa00",
        "github": "#223244",
        "tasks": "#3f4b59"
    }
}


# ----------------------------
# Optional LangChain imports
# ----------------------------
LANGCHAIN_AVAILABLE = False
try:
    # Keep these imports optional so that app runs out-of-the-box.
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage  # type: ignore

    LANGCHAIN_AVAILABLE = True
except Exception:
    LANGCHAIN_AVAILABLE = False


# ----------------------------
# App + config
# ----------------------------
app = Flask(__name__, static_folder='static')

APP_TITLE = os.getenv("APP_TITLE", "4-Agent Console (Flask)")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "200"))
REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "30"))


# ----------------------------
# In-memory per-agent store
# ----------------------------
@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    content: str
    ts: float = field(default_factory=lambda: time.time())
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class AgentStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_agent: Dict[str, List[ChatMessage]] = {}

    def get_history(self, agent_id: str) -> List[ChatMessage]:
        with self._lock:
            return list(self._by_agent.get(agent_id, []))

    def append(self, agent_id: str, msg: ChatMessage) -> None:
        with self._lock:
            hist = self._by_agent.setdefault(agent_id, [])
            hist.append(msg)
            if len(hist) > MAX_HISTORY_MESSAGES:
                # Drop oldest
                del hist[: len(hist) - MAX_HISTORY_MESSAGES]

    def reset(self, agent_id: str) -> None:
        with self._lock:
            self._by_agent[agent_id] = []

    def ensure_seed(self, agent_id: str, system_prompt: str) -> None:
        with self._lock:
            hist = self._by_agent.setdefault(agent_id, [])
            if not hist or hist[0].role != "system":
                hist.insert(0, ChatMessage(role="system", content=system_prompt))


STORE = AgentStore()


# ----------------------------
# Agent interface + registry
# ----------------------------
AgentFn = Callable[[str, List[ChatMessage]], str]


def echo_agent(user_text: str, history: List[ChatMessage]) -> str:
    # Simple fallback agent: echoes + adds tiny context
    last_user = next((m.content for m in reversed(history) if m.role == "user"), None)
    if last_user and last_user != user_text:
        return f"(echo) You said: {user_text}\n\n(prev user msg was: {last_user})"
    return f"(echo) You said: {user_text}"


def placeholder_langchain_agent(agent_name: str) -> AgentFn:
    """
    Stub you can replace with real LangChain/LangGraph logic per agent.
    Keeps LangChain optional and demonstrates how to map store messages -> LC messages.
    """
    def _run(user_text: str, history: List[ChatMessage]) -> str:
        if not LANGCHAIN_AVAILABLE:
            return f"[{agent_name}] LangChain not installed; fallback.\n\n{echo_agent(user_text, history)}"

        # Example: convert our history into LangChain messages
        lc_messages: List[Any] = []
        for m in history:
            if m.role == "system":
                lc_messages.append(SystemMessage(content=m.content))
            elif m.role == "user":
                lc_messages.append(HumanMessage(content=m.content))
            else:
                lc_messages.append(AIMessage(content=m.content))

        # In a real agent, you'd call your chain/graph here and return the model output.
        # This is just a safe placeholder that proves the mapping is working.
        return (
            f"[{agent_name}] (placeholder)\n"
            f"- received: {user_text}\n"
            f"- history messages: {len(lc_messages)}\n\n"
            f"Replace `placeholder_langchain_agent()` with your LangChain/LangGraph runnable."
        )

    return _run


# Import new agents
try:
    from agents import pm_agent, github_agent
except ImportError:
    def pm_agent(user_text: str, history: List[ChatMessage]) -> str:
        return f"[PM] {user_text}"
    
    def github_agent(user_text: str, history: List[ChatMessage]) -> str:
        return f"[GitHub] {user_text}"


AGENTS: Dict[str, Dict[str, Any]] = {
    "pm": {
        "title": "🎯 PM Agent",
        "system": "You are the PM Agent - Project Manager and Task Master. You coordinate tasks, manage workflows, integrate with TaskWarrior and git status for comprehensive project management. Handle GitHub operations, release management, and team coordination. Decompose high-level goals into actionable tasks.",
        "fn": pm_agent,
        "icon": "🎯",
    },
    "planning": {
        "title": "📋 Planning Agent",
        "system": "You are the Planning Agent - Task Decomposition Specialist. You break down complex problems into smaller, manageable tasks. Create detailed implementation plans, identify dependencies, estimate complexity, and iteratively refine plans until tasks are small enough for fast execution.",
        "fn": router_agent,
        "icon": "📋",
    },
    "devops": {
        "title": "⚙️ DevOps Agent",
        "system": "You are the DevOps Agent - Debug/Test/Deploy Specialist. You handle testing strategies, deployment scripts, CI/CD pipelines, error diagnosis, monitoring, and GitHub Actions workflows. Focus on reliability, automation, and production readiness.",
        "fn": research_agent,
        "icon": "⚙️",
    },
    "coder": {
        "title": "💻 Coder Agent",
        "system": "You are the Coder Agent - Implementation Specialist. You generate code, perform refactoring, conduct code reviews, and handle technical implementation. Focus on best practices, edge cases, and correctness. Write clean, maintainable, well-documented code.",
        "fn": coder_agent,
        "icon": "💻",
    },
}


def require_agent(agent_id: str) -> Dict[str, Any]:
    spec = AGENTS.get(agent_id)
    if not spec:
        abort(404, description=f"Unknown agent_id: {agent_id}")
    STORE.ensure_seed(agent_id, spec["system"])
    return spec


# ----------------------------
# Routes
# ----------------------------
PAGE_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{{ title }}</title>
  <link rel="stylesheet" href="/static/panel-system.css">
  <link rel="stylesheet" href="/static/git-tree.css">
  <link rel="stylesheet" href="/static/tiling-manager.css">
  <style>
    :root {
      --bg: #0b0d10;
      --panel: #11151b;
      --muted: #93a4b7;
      --text: #e6edf3;
      --border: #243040;
      --accent: #4aa3ff;
      --danger: #ff4a6a;
      --ok: #4affb5;
      --warning: #ffa500;
      --github: #24292e;
      --tasks: #1a1f2e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    header {
      padding: 8px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--panel);
    }
    header h1 {
      margin: 0;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }
    header .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    button {
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
      padding: 6px 10px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 11px;
    }
    button:hover { border-color: var(--accent); }
    button.danger:hover { border-color: var(--danger); }
    .git-bar {
      padding: 8px 16px;
      border-bottom: 1px solid var(--border);
      background: var(--github);
      color: white;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 16px;
      overflow-x: auto;
      white-space: nowrap;
    }
    .git-status {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .git-branch {
      background: var(--accent);
      padding: 4px 8px;
      border-radius: 12px;
      font-weight: 600;
    }
    .git-files {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .git-file {
      padding: 2px 6px;
      border-radius: 6px;
      font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    .main-container {
      display: flex;
      flex: 1;
      overflow: hidden;
    }
    .agents-section {
      flex: 1;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      padding: 12px;
    }
    .agents-section .panel {
      flex: 1 1 calc(50% - 6px);
      min-width: 300px;
      height: calc(50vh - 100px);
    }
    /* Kanban Board Styles */
    .kanban-section {
      padding: 12px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      max-height: 280px;
      overflow: hidden;
      transition: max-height 0.3s ease;
    }
    .kanban-section.collapsed {
      max-height: 48px;
    }
    .kanban-section.collapsed .kanban-board {
      display: none;
    }
    .kanban-header {
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-weight: 600;
      font-size: 14px;
      cursor: pointer;
    }
    .kanban-header .toggle-icon {
      transition: transform 0.3s;
      margin-right: 8px;
    }
    .kanban-section.collapsed .kanban-header .toggle-icon {
      transform: rotate(-90deg);
    }
    .kanban-board {
      display: flex;
      gap: 12px;
      padding: 12px;
      overflow-x: auto;
      min-height: 180px;
      max-height: 200px;
    }
    .kanban-column {
      flex: 1;
      min-width: 250px;
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--border);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
    }
    .kanban-column-header {
      padding: 12px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-weight: 600;
      font-size: 12px;
    }
    .kanban-count {
      background: var(--accent);
      color: white;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 10px;
    }
    .kanban-column-content {
      flex: 1;
      padding: 8px;
      min-height: 100px;
      overflow-y: auto;
    }
    .kanban-card {
      padding: 8px 10px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-bottom: 8px;
      cursor: move;
      transition: all 0.2s;
      font-size: 11px;
    }
    .kanban-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }
    .kanban-card.dragging {
      opacity: 0.5;
    }
    
    /* Sidebar Styles */
    .sidebar {
      width: 280px;
      background: var(--tasks);
      display: flex;
      flex-direction: column;
      transition: width 0.3s;
      flex-shrink: 0;
    }
    .sidebar-left {
      border-right: 1px solid var(--border);
    }
    .sidebar-right {
      border-left: 1px solid var(--border);
    }
    .sidebar.collapsed {
      width: 40px;
    }
    .sidebar-header {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      font-weight: 600;
      font-size: 13px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
    }
    .sidebar.collapsed .sidebar-header span:not(.git-tree-toggle) {
      display: none;
    }
    .sidebar.collapsed .sidebar-header button {
      display: none;
    }
    .sidebar-content {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
    }
    .sidebar.collapsed .sidebar-content {
      display: none;
    }
    .git-tree-toggle {
      transition: transform 0.3s;
      margin-right: 8px;
    }
    .sidebar.collapsed .git-tree-toggle {
      transform: rotate(-90deg);
    }
    
    /* Minimized Dock Styles */
    .minimized-dock {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: var(--panel);
      border-top: 1px solid var(--accent);
      display: flex;
      gap: 8px;
      padding: 8px;
      z-index: 1000;
      transform: translateY(100%);
      transition: transform 0.3s;
    }
    .minimized-dock.has-panels {
      transform: translateY(0);
    }
    .minimized-dock-item {
      padding: 8px 12px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      transition: all 0.2s;
    }
    .minimized-dock-item:hover {
      background: var(--accent);
      color: white;
    }
    .minimized-dock-item .icon {
      font-size: 16px;
    }
    .task-item {
      padding: 8px 12px;
      margin-bottom: 8px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255,255,255,0.02);
    }
    .task-item:hover {
      background: rgba(255,255,255,0.05);
    }
    .task-title {
      font-size: 12px;
      margin-bottom: 4px;
    }
    .task-meta {
      font-size: 10px;
      color: var(--muted);
      display: flex;
      gap: 8px;
    }
    .panel {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--panel);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .panel .bar {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .panel .bar .title {
      display: flex;
      align-items: baseline;
      gap: 8px;
      flex-wrap: wrap;
    }
    .panel .bar .title .name {
      font-weight: 600;
      font-size: 12px;
    }
    .panel .bar .title .id {
      font-size: 10px;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    .panel .bar .panel-actions {
      display: flex;
      gap: 6px;
    }
    .log {
      padding: 8px;
      flex: 1;
      overflow: auto;
      font-size: 12px;
    }
    .msg {
      margin: 8px 0;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid var(--border);
      max-width: 100%;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.3;
    }
    .msg.user {
      margin-left: 16px;
      border-color: rgba(74, 163, 255, 0.35);
      background: rgba(74, 163, 255, 0.07);
    }
    .msg.assistant {
      margin-right: 16px;
      border-color: rgba(74, 255, 181, 0.25);
      background: rgba(74, 255, 181, 0.06);
    }
    .msg.system {
      border-style: dashed;
      color: var(--muted);
      font-size: 11px;
    }
    .composer {
      border-top: 1px solid var(--border);
      padding: 8px;
      display: flex;
      gap: 8px;
      align-items: flex-end;
    }
    textarea {
      width: 100%;
      min-height: 36px;
      max-height: 120px;
      resize: vertical;
      padding: 8px 8px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.15);
      color: var(--text);
      outline: none;
      font-size: 12px;
      line-height: 1.3;
    }
    textarea:focus { border-color: var(--accent); }
    .status {
      font-size: 10px;
      color: var(--muted);
      padding: 0 12px 8px 12px;
    }
    .pill {
      display: inline-flex;
      gap: 4px;
      align-items: center;
      padding: 2px 6px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 10px;
    }
    .pill.ok { border-color: rgba(74,255,181,0.35); color: rgba(74,255,181,0.85); }
    .pill.bad { border-color: rgba(255,74,106,0.35); color: rgba(255,74,106,0.85); }
    .small {
      font-size: 10px;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    .github-section {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
    }
    .github-info {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .github-stats {
      display: flex;
      gap: 16px;
    }
    .github-stat {
      text-align: center;
    }
    .github-stat .number {
      font-size: 16px;
      font-weight: 600;
    }
    .github-stat .label {
      font-size: 10px;
      color: var(--muted);
    }
    .git-tree-section {
      display: none;  /* Hidden - using left sidebar instead */
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      transition: max-height 0.3s ease;
      overflow: hidden;
    }
    .git-tree-header {
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      background: rgba(0, 0, 0, 0.1);
    }
    .git-tree-header:hover {
      background: rgba(0, 0, 0, 0.2);
    }
    .git-tree-header .title {
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .git-tree-toggle {
      transition: transform 0.3s;
    }
    .git-tree-section.collapsed .git-tree-toggle {
      transform: rotate(-90deg);
    }
    .git-tree-content {
      max-height: 400px;
      overflow: auto;
      transition: max-height 0.3s ease;
    }
    .git-tree-section.collapsed .git-tree-content {
      max-height: 0;
    }
    @media (max-width: 1200px) {
      .sidebar { width: 240px; }
      .agents-section .panel { 
        flex: 1 1 100%;
        height: auto;
        min-height: 300px;
      }
    }
  </style>
</head>
<body>
<header>
  <div>
    <h1>{{ title }}</h1>
  </div>
  <div class="actions">
    <select id="theme-selector" onchange="changeTheme()" style="margin-right: 8px; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--panel); color: var(--text);">
      <option value="">Select Theme</option>
    </select>
    <span class="pill {{ 'ok' if langchain_available else 'bad' }}">
      <span>LangChain</span>
      <span class="small">{{ 'available' if langchain_available else 'not installed' }}</span>
    </span>
    <button class="danger" onclick="resetAll()">Reset all</button>
  </div>
</header>

<div class="git-bar" id="git-bar">
  <div class="git-status">
    <span id="git-branch"></span>
    <span id="git-clean"></span>
  </div>
  <div class="git-files" id="git-files"></div>
</div>

<div class="github-section" id="github-section" style="display: none;">
  <div class="github-info">
    <span id="github-repo"></span>
    <div class="github-stats">
      <div class="github-stat">
        <div class="number" id="github-prs">0</div>
        <div class="label">PRs</div>
      </div>
      <div class="github-stat">
        <div class="number" id="github-issues">0</div>
        <div class="label">Issues</div>
      </div>
      <div class="github-stat">
        <div class="number" id="github-workflows">0</div>
        <div class="label">Workflows</div>
      </div>
    </div>
  </div>
</div>

<!-- Kanban Board Section -->
<div class="kanban-section" id="kanban-section">
  <div class="kanban-header" onclick="toggleKanban(event)">
    <span style="display: flex; align-items: center;">
      <span class="toggle-icon">▼</span>
      📋 Task Board
    </span>
    <button onclick="event.stopPropagation(); refreshKanban()">Refresh</button>
  </div>
  <div class="kanban-board" id="kanban-board">
    <div class="kanban-column" data-status="backlog">
      <div class="kanban-column-header">
        <span>📦 Backlog</span>
        <span class="kanban-count" id="backlog-count">0</span>
      </div>
      <div class="kanban-column-content" id="backlog-tasks"></div>
    </div>
    <div class="kanban-column" data-status="todo">
      <div class="kanban-column-header">
        <span>📝 Todo</span>
        <span class="kanban-count" id="todo-count">0</span>
      </div>
      <div class="kanban-column-content" id="todo-tasks"></div>
    </div>
    <div class="kanban-column" data-status="doing">
      <div class="kanban-column-header">
        <span>🔄 Doing</span>
        <span class="kanban-count" id="doing-count">0</span>
      </div>
      <div class="kanban-column-content" id="doing-tasks"></div>
    </div>
    <div class="kanban-column" data-status="done">
      <div class="kanban-column-header">
        <span>✅ Done</span>
        <span class="kanban-count" id="done-count">0</span>
      </div>
      <div class="kanban-column-content" id="done-tasks"></div>
    </div>
  </div>
</div>

<div class="main-container">
  <!-- Left Sidebar - Git History -->
  <aside class="sidebar sidebar-left">
    <div class="sidebar-header" onclick="toggleGitTree()">
      <span class="git-tree-toggle">▼</span>
      <span>📊 Git History</span>
      <button onclick="event.stopPropagation(); refreshGitTree()">⟳</button>
    </div>
    <div class="sidebar-content git-tree-content" id="git-tree-content">
      <div id="git-tree-container" class="git-tree-container"></div>
    </div>
  </aside>
  
  <div class="agents-section" id="agents-grid"></div>
  
  <!-- Right Sidebar - Tasks -->
  <aside class="sidebar sidebar-right">
    <div class="sidebar-header">
      <span>Tasks</span>
      <button onclick="addTask()">+ Add</button>
    </div>
    <div class="sidebar-content" id="tasks-list"></div>
  </aside>
</div>

<!-- Minimized Panels Dock -->
<div class="minimized-dock" id="minimized-dock"></div>

<script>
  const AGENTS = {{ agents_json | safe }};

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    children.forEach(ch => node.appendChild(ch));
    return node;
  }

  function scrollToBottom(logEl) {
    logEl.scrollTop = logEl.scrollHeight;
  }

  async function apiGET(url) {
    const r = await fetch(url, { method: "GET" });
    if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
    return await r.json();
  }

  async function apiPOST(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const msg = data && data.error ? data.error : `POST ${url} -> ${r.status}`;
      throw new Error(msg);
    }
    return data;
  }

  function renderMessage(m) {
    const div = el("div", { class: `msg ${m.role}` });
    div.textContent = m.content;
    return div;
  }

  function setStatus(panel, text) {
    panel._status.textContent = text || "";
  }

  function disableComposer(panel, disabled) {
    panel._textarea.disabled = disabled;
    panel._sendBtn.disabled = disabled;
    panel._resetBtn.disabled = disabled;
  }

  async function loadHistory(panel) {
    const { agent_id } = panel._meta;
    const data = await apiGET(`/api/agent/${agent_id}/history`);
    panel._log.innerHTML = "";
    data.history.forEach(m => panel._log.appendChild(renderMessage(m)));
    scrollToBottom(panel._log);
  }

  async function sendMessage(panel) {
    const { agent_id } = panel._meta;
    const text = (panel._textarea.value || "").trim();
    if (!text) return;

    panel._textarea.value = "";
    disableComposer(panel, true);
    setStatus(panel, "Sending...");

    panel._log.appendChild(renderMessage({ role: "user", content: text }));
    scrollToBottom(panel._log);

    try {
      const data = await apiPOST(`/api/agent/${agent_id}/send`, { text });
      panel._log.appendChild(renderMessage({ role: "assistant", content: data.reply }));
      scrollToBottom(panel._log);
      setStatus(panel, "OK");
    } catch (e) {
      panel._log.appendChild(renderMessage({ role: "assistant", content: `Error: ${e.message}` }));
      scrollToBottom(panel._log);
      setStatus(panel, "Error");
    } finally {
      disableComposer(panel, false);
    }
  }

  async function resetAgent(panel) {
    const { agent_id } = panel._meta;
    disableComposer(panel, true);
    setStatus(panel, "Resetting...");
    try {
      await apiPOST(`/api/agent/${agent_id}/reset`, {});
      await loadHistory(panel);
      setStatus(panel, "OK");
    } catch (e) {
      setStatus(panel, `Error: ${e.message}`);
    } finally {
      disableComposer(panel, false);
    }
  }

  async function resetAll() {
    for (const agent of Object.keys(AGENTS)) {
      try { await apiPOST(`/api/agent/${agent}/reset`, {}); } catch (_) {}
    }
    location.reload();
  }

  // Panel control functions
  function toggleMinimize(panel) {
    const currentState = panel.dataset.state;
    const logDiv = panel.querySelector('.log');
    const composerDiv = panel.querySelector('.composer');
    const statusDiv = panel.querySelector('.status');
    const agentId = panel._meta?.agent_id || panel.dataset.panelId;
    
    if (currentState === 'minimized') {
      // Restore from minimized
      panel.dataset.state = 'normal';
      panel.style.height = '';
      panel.style.display = '';
      logDiv.style.display = '';
      composerDiv.style.display = '';
      statusDiv.style.display = '';
      
      // Remove from dock
      removeFromMinimizedDock(agentId);
    } else {
      // Minimize to dock
      panel.dataset.state = 'minimized';
      panel.style.display = 'none';
      
      // Add to minimized dock
      addToMinimizedDock(panel);
    }
  }
  
  function toggleMaximize(panel) {
    const currentState = panel.dataset.state;
    
    if (currentState === 'maximized') {
      // Restore
      panel.dataset.state = 'normal';
      panel.classList.remove('maximized');
      panel.style.position = '';
      panel.style.top = '';
      panel.style.left = '';
      panel.style.width = '';
      panel.style.height = '';
      panel.style.zIndex = '';
    } else {
      // Maximize
      panel.dataset.state = 'maximized';
      panel.classList.add('maximized');
      panel.style.position = 'fixed';
      panel.style.top = '0';
      panel.style.left = '0';
      panel.style.width = '100vw';
      panel.style.height = '100vh';
      panel.style.zIndex = '999';
      panel.style.borderRadius = '0';
    }
  }
  
  function closePanel(panel) {
    panel.style.display = 'none';
    // Optionally save closed state to localStorage
    const panelId = panel.dataset.panelId;
    const closedPanels = JSON.parse(localStorage.getItem('closedPanels') || '[]');
    if (!closedPanels.includes(panelId)) {
      closedPanels.push(panelId);
      localStorage.setItem('closedPanels', JSON.stringify(closedPanels));
    }
  }

  function buildPanel(agent_id, spec) {
    const panel = el("div", { class: "panel draggable-panel" });
    panel._meta = { agent_id };
    panel.dataset.panelId = agent_id;
    panel.dataset.state = 'normal';

    const bar = el("div", { class: "bar panel-header" });
    
    // Panel title with drag handle
    const title = el("div", { class: "title panel-title" }, [
      el("span", { class: "drag-handle", text: "⋮⋮", style: "cursor: move; opacity: 0.5; margin-right: 8px;" }),
      el("div", { class: "name", text: spec.title }),
      el("div", { class: "id", text: agent_id })
    ]);

    // Panel controls with minimize, maximize, close, and reset
    const actions = el("div", { class: "panel-actions panel-controls" });
    
    // Minimize button
    const minimizeBtn = el("button", { text: "−", title: "Minimize", style: "min-width: 24px;" });
    minimizeBtn.addEventListener("click", () => toggleMinimize(panel));
    
    // Maximize button
    const maximizeBtn = el("button", { text: "□", title: "Maximize", style: "min-width: 24px;" });
    maximizeBtn.addEventListener("click", () => toggleMaximize(panel));
    
    // Close button
    const closeBtn = el("button", { text: "×", title: "Close", style: "min-width: 24px;" });
    closeBtn.addEventListener("click", () => closePanel(panel));
    
    // Reset button
    const resetBtn = el("button", { class: "danger", text: "Reset" });
    resetBtn.addEventListener("click", () => resetAgent(panel));
    
    actions.appendChild(minimizeBtn);
    actions.appendChild(maximizeBtn);
    actions.appendChild(closeBtn);
    actions.appendChild(resetBtn);

    bar.appendChild(title);
    bar.appendChild(actions);

    const log = el("div", { class: "log" });
    const composer = el("div", { class: "composer" });

    const textarea = el("textarea", { placeholder: "Type a message… (Shift+Enter for newline)" });
    textarea.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        sendMessage(panel);
      }
    });

    const sendBtn = el("button", { text: "Send" });
    sendBtn.addEventListener("click", () => sendMessage(panel));

    composer.appendChild(textarea);
    composer.appendChild(sendBtn);

    const status = el("div", { class: "status", text: "" });

    panel.appendChild(bar);
    panel.appendChild(log);
    panel.appendChild(composer);
    panel.appendChild(status);

    panel._log = log;
    panel._textarea = textarea;
    panel._sendBtn = sendBtn;
    panel._resetBtn = resetBtn;
    panel._status = status;

    return panel;
  }

  async function loadGitStatus() {
    try {
      const data = await apiGET('/api/git/status');
      const branch = document.getElementById('git-branch');
      const clean = document.getElementById('git-clean');
      const files = document.getElementById('git-files');
      
      branch.innerHTML = '';
      clean.innerHTML = '';
      files.innerHTML = '';
      
      if (data.is_repo) {
        branch.appendChild(el('span', { class: 'git-branch', text: data.branch }));
        clean.appendChild(el('span', { class: `pill ${data.clean ? 'ok' : 'bad'}`, text: data.clean ? 'Clean' : 'Dirty' }));
        
        data.files.slice(0, 5).forEach(file => {
          files.appendChild(el('span', { 
            class: 'git-file', 
            style: `background: ${file.color};`,
            text: `${file.status} ${file.file}`
          }));
        });
      } else {
        branch.textContent = 'No git repository';
      }
    } catch (e) {
      console.error('Failed to load git status:', e);
    }
  }

  async function loadGithubStatus() {
    try {
      const data = await apiGET('/api/github/status');
      const githubSection = document.getElementById('github-section');
      
      if (data.is_github) {
        document.getElementById('github-repo').textContent = `${data.owner}/${data.repo}`;
        
        // Load detailed GitHub stats
        const [prs, issues, workflows] = await Promise.all([
          apiGET('/api/github/prs'),
          apiGET('/api/github/issues'),
          apiGET('/api/github/workflows')
        ]);
        
        document.getElementById('github-prs').textContent = prs.open_count || 0;
        document.getElementById('github-issues').textContent = issues.open_count || 0;
        document.getElementById('github-workflows').textContent = workflows.success_count || 0;
        
        githubSection.style.display = 'block';
      }
    } catch (e) {
      console.log('GitHub not available:', e.message);
    }
  }

  async function loadTasks() {
    try {
      const data = await apiGET('/api/tasks');
      const tasksList = document.getElementById('tasks-list');
      tasksList.innerHTML = '';
      
      data.slice(0, 10).forEach(task => {
        const taskEl = el('div', { class: 'task-item' });
        const title = el('div', { class: 'task-title', text: task.description });
        const meta = el('div', { class: 'task-meta' });
        
        if (task.project) {
          meta.appendChild(el('span', { text: task.project }));
        }
        if (task.due) {
          meta.appendChild(el('span', { text: task.due }));
        }
        
        taskEl.appendChild(title);
        taskEl.appendChild(meta);
        
        if (task.id) {
          taskEl.addEventListener('click', () => completeTask(task.id));
          taskEl.style.cursor = 'pointer';
        }
        
        tasksList.appendChild(taskEl);
      });
    } catch (e) {
      console.log('Tasks not available:', e.message);
      document.getElementById('tasks-list').innerHTML = '<div style="padding: 10px; color: var(--muted);">Task Warrior not available</div>';
    }
  }

  async function addTask() {
    const description = prompt('Task description:');
    if (description && description.trim()) {
      try {
        await apiPOST('/api/tasks/add', { description: description.trim() });
        loadTasks();
      } catch (e) {
        alert('Failed to add task: ' + e.message);
      }
    }
  }

  async function completeTask(taskId) {
    try {
      await apiPOST(`/api/tasks/${taskId}/complete`, {});
      loadTasks();
    } catch (e) {
      alert('Failed to complete task: ' + e.message);
    }
  }

  // Enhanced loadThemes function with better error handling and debugging
  async function loadThemes() {
    try {
      console.log('[THEME] Starting to load themes...');
      const data = await apiGET('/api/themes');
      console.log('[THEME] Themes data received:', data);
      
      if (!data || !data.themes || !Array.isArray(data.themes)) {
        console.error('[THEME] Invalid themes data structure:', data);
        // Fallback: create themes manually
        const fallbackThemes = ['default', 'dracula', 'nord', 'tokyonight'];
        loadThemesFromList(fallbackThemes);
        return;
      }
      
      const selector = document.getElementById('theme-selector');
      console.log('[THEME] Theme selector element found:', selector);
      
      if (!selector) {
        console.error('[THEME] Theme selector element not found');
        return;
      }
      
      // Clear selector and populate with themes
      selector.innerHTML = '<option value="">Select Theme</option>';
      
      let successCount = 0;
      let errorCount = 0;
      
      data.themes.forEach((theme, index) => {
        try {
          console.log(`[THEME] Processing theme ${index}: ${theme}`);
          const optionText = theme.replace(/-/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
          const option = el('option', { value: theme, text: optionText });
          selector.appendChild(option);
          successCount++;
          console.log(`[THEME] Added theme option: ${optionText}`);
        } catch (error) {
          console.error(`[THEME] Error adding theme ${theme}:`, error);
          errorCount++;
        }
      });
      
      console.log(`[THEME] Theme loading complete. Success: ${successCount}, Errors: ${errorCount}`);
      console.log(`[THEME] Final selector options count: ${selector.options.length}`);
      
      // Call loadCurrentTheme to apply the current theme
      await loadCurrentTheme();
      
    } catch (error) {
      console.error('[THEME] Failed to load themes:', error);
      // Display error message in the UI
      alert('Failed to load themes: ' + error.message);
    }
  }

  // Enhanced loadCurrentTheme function with better error handling
  async function loadCurrentTheme() {
    try {
      console.log('[CURRENT] Starting to load current theme...');
      const data = await apiGET('/api/theme/current');
      console.log('[CURRENT] Current theme data received:', data);
      
      const selector = document.getElementById('theme-selector');
      if (!selector) {
        console.error('[CURRENT] Theme selector not found');
        return;
      }
      
      // Apply current theme
      if (data && data.current_theme) {
        selector.value = data.current_theme;
        console.log(`[CURRENT] Set selector value to: ${data.current_theme}`);
        
        // Apply theme colors to CSS variables
        if (data.colors) {
          const root = document.documentElement;
          const appliedColors = {};
          Object.entries(data.colors).forEach(([key, value]) => {
            root.style.setProperty(`--${key}`, value);
            appliedColors[key] = value;
          });
          console.log(`[CURRENT] Applied colors:`, appliedColors);
        }
      }
    } catch (error) {
      console.error('[CURRENT] Failed to load current theme:', error);
    }
  }

  // Enhanced changeTheme function with better error handling and debugging
  async function changeTheme() {
    const selector = document.getElementById('theme-selector');
    if (!selector) {
      console.error('[CHANGE] Theme selector not found');
      alert('Theme selector not found');
      return;
    }
    
    const themeName = selector.value;
    console.log(`[CHANGE] Changing theme to: ${themeName}`);
    
    if (!themeName) {
      console.log('[CHANGE] No theme selected, returning');
      return;
    }
    
    try {
      const response = await apiPOST('/api/theme/set', { theme: themeName });
      console.log(`[CHANGE] Theme set response:`, response);
      
      if (response && response.success) {
        console.log(`[CHANGE] Theme change successful, reloading page`);
        // Reload page to apply new theme
        location.reload();
      } else {
        console.error(`[CHANGE] Theme change failed: ${response?.error || 'Unknown error'}`);
        alert('Failed to change theme: ' + (response?.error || 'Unknown error'));
        
        // Reset selector to current theme
        try {
          const currentData = await apiGET('/api/theme/current');
          if (currentData && currentData.current_theme) {
            selector.value = currentData.current_theme;
          } else {
            selector.value = 'default';
          }
        } catch (loadError) {
          console.error('[CHANGE] Failed to fetch current theme after error:', loadError);
          selector.value = 'default';
        }
      }
    } catch (changeError) {
      console.error('[CHANGE] Error changing theme:', changeError);
      alert('Failed to change theme: ' + changeError.message);
      
      // Reset to default on error
      selector.value = 'default';
    }
  }

  async function init() {
    console.log('[INIT] Initializing application...');
    
    // Add global error handling
    window.addEventListener('error', (event) => {
      console.error('[GLOBAL] JavaScript error:', event.error);
    });
    
    try {
      const grid = document.getElementById('agents-grid');
      if (!grid) {
        console.error('[INIT] Agents grid not found');
        return;
      }
      
      const panels = [];
      console.log('[INIT] Building panels...');

      for (const [agent_id, spec] of Object.entries(AGENTS)) {
        try {
          const panel = buildPanel(agent_id, spec);
          grid.appendChild(panel);
          panels.push(panel);
          console.log(`[INIT] Built panel for agent: ${agent_id}`);
        } catch (error) {
          console.error(`[INIT] Error building panel for ${agent_id}:`, error);
        }
      }

      // Load themes first with detailed error handling
      console.log('[INIT] Starting theme loading...');
      try {
        await loadThemes();
        console.log('[INIT] Themes loaded');
        
        // Then load current theme with better error handling
        await loadCurrentTheme();
        console.log('[INIT] Current theme loaded');
      } catch (error) {
        console.error('[INIT] Error loading current theme:', error);
        alert('Error loading themes: ' + error.message);
      }
      
      // Load other components with error handling
      const loadPromises = [];
      
      // Git status
      loadPromises.push(
        loadGitStatus().catch(e => {
          console.error('[INIT] Error loading git status:', e);
        })
      );
      
      // GitHub status
      loadPromises.push(
        loadGithubStatus().catch(e => {
          console.error('[INIT] Error loading GitHub status:', e);
        })
      );
      
      // Tasks
      loadPromises.push(
        loadTasks().catch(e => {
          console.error('[INIT] Error loading tasks:', e);
        })
      );
      
      // Agent histories
      Object.keys(AGENTS).forEach(agent_id => {
        loadPromises.push(
          loadHistory({ _meta: { agent_id } }).catch(e => {
            console.error(`[INIT] Error loading history for ${agent_id}:`, e);
          })
        );
      });
      
      // Wait for all async operations to complete
      console.log('[INIT] Waiting for operations to complete...');
      await Promise.all(loadPromises);
      console.log('[INIT] All operations completed');
      
      // Set initial statuses with error handling
      panels.forEach((panel, index) => {
        try {
          setStatus(panel, "OK");
          console.log(`[INIT] Set status for panel ${index}: OK`);
        } catch (error) {
          console.error(`[INIT] Error setting status for panel ${index}:`, error);
          setStatus(panel, `Error: ${e.message}`);
        }
      });
      
      console.log('[INIT] Initialization complete');
      
      // Initialize Git Tree and Kanban after a short delay
      setTimeout(() => {
        // Initialize git tree if sidebar is open
        const sidebar = document.querySelector('.sidebar-left');
        if (sidebar && !sidebar.classList.contains('collapsed')) {
          initGitTree();
        }
        
        // Initialize Kanban board
        refreshKanban();
      }, 1000);
      
      // Auto-refresh with error handling
      setInterval(() => {
        loadGitStatus().catch(e => {
          console.error('[AUTO-REFRESH] Error refreshing git status:', e);
        });
        
        loadGithubStatus().catch(e => {
          console.error('[AUTO-REFRESH] Error refreshing GitHub status:', e);
        });
      }, 30000); // Every 30 seconds
      
    } catch (error) {
      console.error('[INIT] Critical error during initialization:', error);
      alert('Error during application initialization: ' + error.message);
    }
  }

  // Git Tree Functions
  let gitTreeVisualizer = null;
  
  function toggleKanban(event) {
      // Don't toggle if clicking buttons
      if (event && event.target.tagName === 'BUTTON') return;
      const section = document.querySelector('.kanban-section');
      section.classList.toggle('collapsed');
    }

    function toggleGitTree() {
    const sidebar = document.querySelector('.sidebar-left');
    sidebar.classList.toggle('collapsed');
    
    // Initialize git tree if not already done
    if (!sidebar.classList.contains('collapsed') && !gitTreeVisualizer) {
      initGitTree();
    }
  }
  
  async function initGitTree() {
    try {
      // Wait for GitTreeVisualizer to be available
      if (typeof GitTreeVisualizer === 'undefined') {
        console.error('[GIT TREE] GitTreeVisualizer not loaded, retrying...');
        setTimeout(initGitTree, 500);
        return;
      }
      
      console.log('[GIT TREE] Initializing Git Tree Visualizer');
      gitTreeVisualizer = new GitTreeVisualizer('git-tree-container');
      await refreshGitTree();
    } catch (e) {
      console.error('[GIT TREE] Failed to initialize:', e);
    }
  }
  
  async function refreshGitTree() {
    try {
      console.log('[GIT TREE] Refreshing git tree...');
      const data = await apiGET('/api/git/log?max_count=30');
      if (gitTreeVisualizer) {
        gitTreeVisualizer.renderTree(data);
        console.log('[GIT TREE] Git tree rendered successfully');
      }
    } catch (e) {
      console.error('[GIT TREE] Failed to load git log:', e);
      if (gitTreeVisualizer) {
        gitTreeVisualizer.renderTree({ commits: [], error: e.message });
      }
    }
  }
  
  // Minimized Dock Functions
  function addToMinimizedDock(panel) {
    const dock = document.getElementById('minimized-dock');
    const agentId = panel._meta?.agent_id || panel.dataset.panelId;
    const agentSpec = AGENTS[agentId] || { title: 'Unknown', icon: '?' };
    
    // Create dock item
    const dockItem = el('div', { 
      class: 'minimized-dock-item',
      'data-panel-id': agentId
    });
    
    dockItem.appendChild(el('span', { class: 'icon', text: agentSpec.icon || '📄' }));
    dockItem.appendChild(el('span', { text: agentSpec.title || agentId }));
    
    dockItem.addEventListener('click', () => restoreFromDock(agentId));
    
    dock.appendChild(dockItem);
    dock.classList.add('has-panels');
  }
  
  function removeFromMinimizedDock(agentId) {
    const dock = document.getElementById('minimized-dock');
    const dockItem = dock.querySelector(`[data-panel-id="${agentId}"]`);
    if (dockItem) {
      dockItem.remove();
    }
    
    if (dock.children.length === 0) {
      dock.classList.remove('has-panels');
    }
  }
  
  function restoreFromDock(agentId) {
    const panel = document.querySelector(`[data-panel-id="${agentId}"]`).closest('.panel');
    if (panel) {
      toggleMinimize(panel);
    }
  }
  
  // Kanban Board Functions
  async function refreshKanban() {
    try {
      console.log('[KANBAN] Refreshing Kanban board...');
      const tasks = await apiGET('/api/tasks');
      
      // Clear all columns
      const columns = {
        'backlog-tasks': [],
        'todo-tasks': [],
        'doing-tasks': [],
        'done-tasks': []
      };
      
      // Sort tasks into columns based on tags or priority
      tasks.forEach(task => {
        const card = createKanbanCard(task);
        
        // Determine column based on tags or status
        if (task.tags && task.tags.includes('doing')) {
          columns['doing-tasks'].push(card);
        } else if (task.tags && task.tags.includes('done')) {
          columns['done-tasks'].push(card);
        } else if (task.urgency > 10) {
          columns['todo-tasks'].push(card);
        } else {
          columns['backlog-tasks'].push(card);
        }
      });
      
      // Update columns and counts
      Object.entries(columns).forEach(([columnId, cards]) => {
        const column = document.getElementById(columnId);
        const countEl = document.getElementById(columnId.replace('-tasks', '-count'));
        
        if (column) {
          column.innerHTML = '';
          cards.forEach(card => column.appendChild(card));
        }
        
        if (countEl) {
          countEl.textContent = cards.length;
        }
      });
      
      console.log('[KANBAN] Kanban board refreshed');
    } catch (e) {
      console.error('[KANBAN] Failed to refresh:', e);
    }
  }
  
  function createKanbanCard(task) {
    const card = el('div', { 
      class: 'kanban-card',
      draggable: 'true',
      'data-task-id': task.id
    });
    
    card.textContent = task.description;
    
    // Add drag event handlers
    card.addEventListener('dragstart', (e) => {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/html', card.innerHTML);
      card.classList.add('dragging');
    });
    
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
    });
    
    return card;
  }

  init();

</script>
<script src="/static/panel-system.js"></script>
<script src="/static/git-tree.js"></script>
<script src="/static/tiling-manager.js"></script>
<script>
  // Initialize tiling window manager after page load
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
      // Initialize the tiling manager (disabled to prevent grid blocking)
      // window.tilingManager = new TilingManager(document.getElementById('agents-grid'));
      console.log('[TILING] Tiling manager disabled - was blocking elements');
      
      // All tiling UI elements removed to prevent blocking
    }, 500); // Allow panels to be created first
  });
</script>
</body>
</html>
"""


@app.get("/")
def index() -> str:
    # Get current theme from cookie or default
    current_theme = request.cookies.get('theme', 'default')
    current_colors = COLOR_SCHEMES.get(current_theme, COLOR_SCHEMES['default'])
    
    # Ensure all agents have a system seed message.
    for agent_id, spec in AGENTS.items():
        STORE.ensure_seed(agent_id, spec["system"])
    
    # Generate CSS variables for current theme with proper spacing
    css_vars = "\n".join([f"      --{key}: {value};" for key, value in current_colors.items()])
    
    # Create dynamic CSS replacement block
    css_block = f"    :root {{\n{css_vars}\n    }}"
    
    # Use regex to find and replace :root block more flexibly
    import re
    page_html = re.sub(
        r'    :root \{[^}]+\}',
        css_block,
        PAGE_HTML,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Create JSON-serializable version of AGENTS (without function references)
    agents_for_json = {
        agent_id: {"title": spec["title"], "system": spec["system"]}
        for agent_id, spec in AGENTS.items()
    }
    
    response = make_response(render_template_string(
        page_html,
        title=APP_TITLE,
        agents_json=json.dumps(agents_for_json),
        langchain_available=LANGCHAIN_AVAILABLE,
        current_theme=current_theme,
        themes_json=list(COLOR_SCHEMES.keys()),
        color_schemes_json=COLOR_SCHEMES
    ))
    
    # Set cookie for theme persistence
    if current_theme != 'default':
        response.set_cookie('theme', current_theme, max_age=365*24*3600)  # 1 year
    
    return response


@app.get("/api/agent/<agent_id>/history")
def agent_history(agent_id: str):
    require_agent(agent_id)
    hist = STORE.get_history(agent_id)
    return jsonify(
        {
            "agent_id": agent_id,
            "history": [
                {"role": m.role, "content": m.content, "ts": m.ts, "msg_id": m.msg_id}
                for m in hist
            ],
        }
    )


@app.post("/api/agent/<agent_id>/reset")
def agent_reset(agent_id: str):
    spec = require_agent(agent_id)
    STORE.reset(agent_id)
    STORE.ensure_seed(agent_id, spec["system"])
    return jsonify({"ok": True, "agent_id": agent_id})


@app.post("/api/agent/<agent_id>/send")
def agent_send(agent_id: str):
    spec = require_agent(agent_id)
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Field 'text' must be a non-empty string."}), 400

    text = text.strip()

    # Record user message
    STORE.append(agent_id, ChatMessage(role="user", content=text))

    # Run agent function
    fn: AgentFn = spec["fn"]
    history = STORE.get_history(agent_id)

    start = time.time()
    try:
        reply = fn(text, history)
        if not isinstance(reply, str):
            raise TypeError(f"Agent returned non-string type: {type(reply).__name__}")
    except Exception as e:
        reply = f"[{spec['title']}] Internal error: {type(e).__name__}: {e}"
    finally:
        elapsed = time.time() - start

    # Record assistant message
    STORE.append(agent_id, ChatMessage(role="assistant", content=reply))

    return jsonify(
        {
            "agent_id": agent_id,
            "reply": reply,
            "elapsed_sec": round(elapsed, 4),
        }
    )


# ----------------------------
# Project Management API Endpoints
# ----------------------------
@app.get("/api/git/status")
def git_status_api():
    """Get git repository status and worktree."""
    return jsonify(get_git_status())


@app.get("/api/git/tree")
def git_tree_api():
    """Get git file tree."""
    return jsonify(get_git_tree())


@app.get("/api/git/log")
def git_log_api():
    """Get git commit log with branch information."""
    max_count = request.args.get('max_count', 50, type=int)
    return jsonify(get_git_log(max_count))


@app.get("/api/github/status")
def github_status_api():
    """Get GitHub repository status."""
    return jsonify(get_github_status())


@app.get("/api/github/prs")
def github_prs_api():
    """Get GitHub pull requests."""
    return jsonify(get_github_prs())


@app.get("/api/github/issues")
def github_issues_api():
    """Get GitHub issues."""
    return jsonify(get_github_issues())


@app.get("/api/github/workflows")
def github_workflows_api():
    """Get GitHub Actions workflow status."""
    return jsonify(get_github_workflows())


@app.get("/api/tasks")
def tasks_api():
    """Get Task Warrior tasks."""
    return jsonify(get_task_warrior_tasks())


@app.post("/api/tasks/add")
def add_task_api():
    """Add a new task to Task Warrior."""
    payload = request.get_json(silent=True) or {}
    description = payload.get("description", "")
    project = payload.get("project")
    
    if not isinstance(description, str) or not description.strip():
        return jsonify({"error": "Field 'description' must be a non-empty string."}), 400
    
    success = add_task_warrior_task(description.strip(), project)
    return jsonify({
        "success": success,
        "description": description.strip(),
        "project": project
    })


@app.post("/api/tasks/<task_id>/complete")
def complete_task_api(task_id: str):
    """Complete a task in Task Warrior."""
    success = complete_task_warrior_task(task_id)
    return jsonify({
        "success": success,
        "task_id": task_id
    })


@app.post("/api/github/pr/create")
def create_pr_api():
    """Create a new GitHub pull request."""
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "")
    description = payload.get("description", "")
    branch = payload.get("branch", "main")
    
    if not title or not description:
        return jsonify({"error": "Fields 'title' and 'description' are required."}), 400
    
    try:
        # Use gh CLI to create PR
        cmd = ['gh', 'pr', 'create', '--title', title, '--body', description, '--base', 'main']
        if branch:
            cmd.extend(['--head', branch])
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return jsonify({
            "success": result.returncode == 0,
            "title": title,
            "description": description,
            "branch": branch
        })
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Failed to create PR: {str(e)}"})


@app.post("/api/github/issue/create")
def create_issue_api():
    """Create a new GitHub issue."""
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "")
    description = payload.get("description", "")
    issue_type = payload.get("type", "bug")
    labels = payload.get("labels", [])
    
    if not title or not description:
        return jsonify({"error": "Fields 'title' and 'description' are required."}), 400
    
    try:
        # Use gh CLI to create issue
        cmd = ['gh', 'issue', 'create', '--title', title, '--body', description]
        if issue_type:
            cmd.extend(['--label', issue_type])
        for label in labels:
            cmd.extend(['--label', label])
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return jsonify({
            "success": result.returncode == 0,
            "title": title,
            "description": description,
            "type": issue_type,
            "labels": labels
        })
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Failed to create issue: {str(e)}"})


# ----------------------------
# Theme Management API Endpoints
# ----------------------------
@app.get("/api/themes")
def get_themes():
    """Get all available color schemes."""
    return jsonify({
        "themes": list(COLOR_SCHEMES.keys()),
        "schemes": COLOR_SCHEMES
    })


@app.get("/api/theme/current")
def get_current_theme():
    """Get current theme name."""
    current_theme = request.cookies.get('theme', 'default')
    return jsonify({
        "current_theme": current_theme,
        "colors": COLOR_SCHEMES.get(current_theme, COLOR_SCHEMES['default'])
    })


@app.post("/api/theme/set")
def set_theme():
    """Set current theme."""
    payload = request.get_json(silent=True) or {}
    theme_name = payload.get("theme", "default")
    
    if theme_name not in COLOR_SCHEMES:
        return jsonify({"error": f"Theme '{theme_name}' not found"}), 400
    
    response = jsonify({
        "success": True,
        "theme": theme_name,
        "colors": COLOR_SCHEMES[theme_name]
    })
    response.set_cookie('theme', theme_name, max_age=365*24*3600)  # 1 year
    return response


# ----------------------------
# Entry point
# ----------------------------
if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "0") == "1"

    # Install deps:
    #   pip install flask
    # Optional (for real agents):
    #   pip install langchain-core langgraph
    app.run(host=host, port=port, debug=debug, threaded=True)
