"""
Real LangChain agent implementations for the 4-Agent Console.
This module provides example agents that demonstrate different capabilities
using LangChain and LangGraph.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from main import ChatMessage, AgentFn, LANGCHAIN_AVAILABLE

# Optional LangChain imports
if LANGCHAIN_AVAILABLE:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough
    from langchain_core.language_models import BaseChatModel
    from langgraph.graph import StateGraph, MessagesState
    from langgraph.prebuilt import ToolNode
else:
    # Fallback types when LangChain is not available
    BaseChatModel = Any


def router_agent(user_text: str, history: List[ChatMessage]) -> str:
    """
    Agent 1 — Router: Analyzes requests and routes them to appropriate categories.
    Provides quick, concise responses with routing information.
    """
    if not LANGCHAIN_AVAILABLE:
        # Fallback implementation
        text_lower = user_text.lower()
        if any(keyword in text_lower for keyword in ['code', 'programming', 'python', 'javascript']):
            return "🔧 This looks like a coding question. I recommend sending this to Agent 2 (Coder) for detailed technical assistance."
        elif any(keyword in text_lower for keyword in ['research', 'analyze', 'investigate', 'study']):
            return "🔍 This appears to be a research request. Consider consulting Agent 3 (Research) for thorough analysis."
        elif any(keyword in text_lower for keyword in ['review', 'critique', 'improve', 'feedback']):
            return "🎯 This seems to need critical evaluation. Agent 4 (Critic) would be perfect for detailed feedback."
        else:
            return f"📝 Message received: '{user_text[:50]}{'...' if len(user_text) > 50 else ''}'. This general query can be handled by any agent."
    
    # LangChain implementation would go here
    # For now, return the enhanced fallback response
    text_lower = user_text.lower()
    if any(keyword in text_lower for keyword in ['code', 'programming', 'python', 'javascript']):
        return "🔧 This looks like a coding question. I recommend sending this to Agent 2 (Coder) for detailed technical assistance."
    elif any(keyword in text_lower for keyword in ['research', 'analyze', 'investigate', 'study']):
        return "🔍 This appears to be a research request. Consider consulting Agent 3 (Research) for thorough analysis."
    elif any(keyword in text_lower for keyword in ['review', 'critique', 'improve', 'feedback']):
        return "🎯 This seems to need critical evaluation. Agent 4 (Critic) would be perfect for detailed feedback."
    else:
        return f"📝 Message received: '{user_text[:50]}{'...' if len(user_text) > 50 else ''}'. This general query can be handled by any agent."


def coder_agent(user_text: str, history: List[ChatMessage]) -> str:
    """
    Agent 2 — Coder: Specializes in code-related questions, best practices,
    and technical problem-solving with attention to edge cases.
    """
    if not LANGCHAIN_AVAILABLE:
        # Enhanced fallback implementation
        text_lower = user_text.lower()
        
        # Code pattern detection
        code_patterns = {
            r'python|py': 'Python',
            r'javascript|js|node': 'JavaScript',
            r'java': 'Java',
            r'cpp|c\+\+': 'C++',
            r'html|css': 'Web Development',
            r'sql|database': 'SQL/Database',
        }
        
        detected_lang = 'General'
        for pattern, lang in code_patterns.items():
            if re.search(pattern, text_lower):
                detected_lang = lang
                break
        
        # Common code-related keywords
        if any(keyword in text_lower for keyword in ['error', 'bug', 'fix', 'debug']):
            return f"🐛 **Debugging Mode ({detected_lang})**\n\nTo help fix your code issue, I'd need:\n1. The error message you're seeing\n2. The relevant code snippet\n3. What you expected vs. what happened\n\nShare these details and I'll help you resolve it!"
        
        elif any(keyword in text_lower for keyword in ['optimize', 'performance', 'efficient']):
            return f"⚡ **Performance Optimization ({detected_lang})**\n\nFor optimization, I consider:\n- Time complexity (Big O)\n- Memory usage\n- Algorithm choice\n- Language-specific optimizations\n\nWhat specific performance aspect are you targeting?"
        
        elif any(keyword in text_lower for keyword in ['best practice', 'pattern', 'design']):
            return f"🏗️ **Best Practices & Design Patterns ({detected_lang})**\n\nI can help with:\n- SOLID principles\n- Design patterns (Singleton, Factory, Observer, etc.)\n- Code organization\n- Testing strategies\n\nWhich area would you like to explore?"
        
        else:
            return f"💻 **Code Assistant ({detected_lang})**\n\nI'm ready to help with:\n- Code review and suggestions\n- Algorithm explanations\n- Implementation strategies\n- Edge case analysis\n\nWhat specific coding challenge can I assist with?"
    
    # LangChain implementation would go here
    # For now, return a simple fallback response
    return "💻 I'm the Coder agent, ready to help with your programming questions and code-related tasks."


def research_agent(user_text: str, history: List[ChatMessage]) -> str:
    """
    Agent 3 — Research: Asks clarifying questions, cites assumptions,
    and provides thorough, well-reasoned analysis.
    """
    if not LANGCHAIN_AVAILABLE:
        # Enhanced fallback implementation
        text_lower = user_text.lower()
        
        # Identify research keywords
        research_types = {
            'compare': 'Comparative Analysis',
            'explain': 'Explanatory Research',
            'analyze': 'Analytical Study',
            'investigate': 'Investigative Research',
            'evaluate': 'Evaluation Study',
            'explore': 'Exploratory Analysis',
        }
        
        research_type = 'General Research'
        for keyword, rtype in research_types.items():
            if keyword in text_lower:
                research_type = rtype
                break
        
        # Check for ambiguity indicators
        ambiguity_indicators = ['maybe', 'perhaps', 'possibly', 'might be', 'could be', 'unclear']
        has_ambiguity = any(indicator in text_lower for indicator in ambiguity_indicators)
        
        if has_ambiguity or '?' in user_text and len(user_text.split()) < 10:
            clarifying_questions = [
                "What specific aspects would you like me to focus on?",
                "Are there any particular constraints or boundaries I should consider?",
                "What would constitute a successful outcome for this research?",
                "Do you have any initial assumptions or hypotheses?",
                "What level of detail are you looking for?"
            ]
            
            return f"🔍 **{research_type} - Clarification Needed**\n\nTo provide the most helpful research assistance, I need to understand your request better. Could you clarify:\n\n" + "\n".join(f"• {q}" for q in clarifying_questions[:3]) + "\n\nBased on your query, I'm assuming: \"" + user_text + "\" - please confirm or correct this understanding."
        
        else:
            # Provide structured research response
            assumptions = [
                "You're seeking factual, well-reasoned information",
                "You want me to consider multiple perspectives",
                "You value thoroughness over brevity",
                "You're open to follow-up questions for deeper understanding"
            ]
            
            return f"🔍 **{research_type} - Initial Analysis**\n\n**Query:** \"{user_text}\"\n\n**My Assumptions:**\n" + "\n".join(f"• {assumption}" for assumption in assumptions) + "\n\n**Research Approach:**\n1. Break down the key components\n2. Identify reliable information sources\n3. Consider alternative viewpoints\n4. Provide structured findings\n5. Suggest areas for deeper investigation\n\n**Next Steps:**\n- Should I proceed with this approach?\n- Are there specific aspects you want me to prioritize?\n- Do you have any constraints (time, scope, sources)?"
    
    # LangChain implementation would go here
    # For now, return a simple fallback response
    return "🔍 I'm Research agent, ready to help with thorough analysis and investigative queries."


def critic_agent(user_text: str, history: List[ChatMessage]) -> str:
    """
    Agent 4 — Critic: Provides constructive criticism, identifies flaws,
    and suggests improvements across various domains.
    """
    if not LANGCHAIN_AVAILABLE:
        # Enhanced fallback implementation
        text_lower = user_text.lower()
        
        # Identify what's being criticized
        if 'code' in text_lower or any(lang in text_lower for lang in ['python', 'javascript', 'java', 'cpp']):
            domain = "Code"
            criteria = ["Readability", "Efficiency", "Maintainability", "Error handling", "Security"]
        elif 'idea' in text_lower or 'concept' in text_lower or 'proposal' in text_lower:
            domain = "Concept/Idea"
            criteria = ["Feasibility", "Scalability", "Originality", "Impact", "Risks"]
        elif 'design' in text_lower or 'ui' in text_lower or 'ux' in text_lower:
            domain = "Design"
            criteria = ["User experience", "Accessibility", "Visual hierarchy", "Consistency", "Functionality"]
        else:
            domain = "General"
            criteria = ["Clarity", "Completeness", "Logic", "Practicality", "Impact"]
        
        # Check if user wants specific criticism
        if any(keyword in text_lower for keyword in ['review', 'critique', 'feedback', 'improve']):
            return f"🎯 **Critical Analysis - {domain}**\n\nI'll evaluate this based on these criteria:\n" + "\n".join(f"• {criterion}" for criterion in criteria) + "\n\n**Critical Questions I'll Consider:**\n• What are the potential failure points?\n• What assumptions might be flawed?\n• How could this be improved?\n• What are the overlooked implications?\n• Is this the optimal approach?\n\n**My Critical Lens:**\nI'll provide honest, constructive feedback focusing on both strengths and areas for improvement. Expect me to challenge assumptions and suggest concrete enhancements.\n\nPlease share the {domain.lower()} you'd like me to critique!"
        
        else:
            # General critical thinking response
            critical_thinking_areas = [
                "Logical fallacies or inconsistencies",
                "Unstated assumptions or biases",
                "Alternative perspectives you might have missed",
                "Potential consequences or implications",
                "Ways to strengthen your argument"
            ]
            
            return f"🎯 **Critical Thinking Assistant**\n\nI'm here to help you think more critically and identify areas for improvement. I can analyze:\n\n" + "\n".join(f"• {area}" for area in critical_thinking_areas) + "\n\n**My Approach:**\nI provide honest, constructive criticism that helps you refine your ideas while maintaining a positive, growth-oriented perspective.\n\n**What would you like me to critique?**\n• A piece of code or algorithm?\n• An idea or proposal?\n• A design or user interface?\n• An argument or analysis?\n• Something else entirely?\n\nShare what you'd like critical feedback on, and I'll provide thorough, actionable insights."
    
    # LangChain implementation would go here
    # For now, return a simple fallback response
    return "🎯 I'm Critic agent, ready to provide constructive feedback and critical analysis."


# Factory function to create LangChain-enabled agents
def create_langchain_agent(llm: BaseChatModel, system_prompt: str, agent_type: str = "general") -> AgentFn:
    """
    Creates a LangChain-powered agent with the specified LLM and system prompt.
    
    Args:
        llm: LangChain language model instance
        system_prompt: System prompt for the agent
        agent_type: Type of agent (affects behavior)
    
    Returns:
        Agent function compatible with the console
    """
    if not LANGCHAIN_AVAILABLE:
        # Return fallback agent
        fallback_agents = {
            "router": router_agent,
            "coder": coder_agent,
            "research": research_agent,
            "critic": critic_agent,
        }
        return fallback_agents.get(agent_type, router_agent)
    
    def _run(user_text: str, history: List[ChatMessage]) -> str:
        # Convert history to LangChain messages
        messages = [SystemMessage(content=system_prompt)]
        
        # Add conversation history (excluding the system message that might be first)
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        # Add current user message
        messages.append(HumanMessage(content=user_text))
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages(messages)
        
        # Create chain
        chain = prompt | llm | StrOutputParser()
        
        # Invoke and return response
        try:
            response = chain.invoke({})
            return response.strip()
        except Exception as e:
            return f"Error invoking LangChain agent: {str(e)}"
    
    return _run


# Advanced agent implementations using LangGraph
def pm_agent(user_text: str, history: List[ChatMessage]) -> str:
    """
    PM Agent — Project Manager: Coordinates tasks, manages workflows, 
    and integrates with git status and task warrior for project management.
    """
    if not LANGCHAIN_AVAILABLE:
        # Enhanced fallback implementation
        text_lower = user_text.lower()
        
        # Task management keywords
        if any(keyword in text_lower for keyword in ['task', 'todo', 'reminder', 'deadline']):
            return """📋 **Task Management**\n\nI can help you:\n\n**Task Operations:**
• Create new tasks: `"Add task: Implement user authentication"`
• List current tasks: `"Show my tasks"`
• Mark tasks complete: `"Complete task 23"`
• Set priorities: `"Set priority high for task 15"`

**Project Planning:**
• Create milestones and deadlines
• Track progress across multiple projects
• Generate status reports
• Coordinate team workflows

**What task would you like to manage?**"""
        
        elif any(keyword in text_lower for keyword in ['project', 'plan', 'roadmap', 'milestone']):
            return """🗺️ **Project Planning**\n\nI can assist with:\n\n**Planning Activities:**
• Define project scope and objectives
• Create timelines and milestones
• Resource allocation planning
• Risk assessment and mitigation
• Progress tracking and reporting

**Current Projects:**
*(Would integrate with your actual project data)*

**Planning Tools:**
• Gantt chart generation
• Sprint planning
• Release coordination
• Dependency mapping

**What project aspect should we plan?**"""
        
        elif any(keyword in text_lower for keyword in ['status', 'report', 'progress', 'review']):
            return """📊 **Status & Reporting**\n\nI can provide:\n\n**Status Reports:**
• Daily/weekly summaries
• Task completion rates
• Project health metrics
• Blocker identification

**Analytics:**
• Velocity tracking
• Burndown charts
• Team productivity metrics
• Quality indicators

**What status information do you need?**"""
        
        else:
            return """🎯 **Project Management Assistant**\n\nI'm your PM agent, ready to help with:\n\n**Core Functions:**
• **Task Management** - Create, track, and complete tasks
• **Project Planning** - Roadmaps, milestones, timelines  
• **Team Coordination** - Workflows, handoffs, collaboration
• **Status & Reporting** - Progress tracking, metrics, insights
• **GitHub Integration** - PRs, issues, releases, workflows

**Quick Actions:**
• "Show tasks" - List current tasks
• "Add project plan" - Create new project roadmap
• "Status report" - Generate current status
• "GitHub status" - Check repo and PR status

**What would you like to manage today?**"""
    
    # LangChain implementation would go here
    # For now, return a simple fallback response
    return "🎯 I'm PM agent, ready to help with project management and task coordination."


def github_agent(user_text: str, history: List[ChatMessage]) -> str:
    """
    GitHub Integration Agent: Manages GitHub operations, PRs, issues,
    and repository workflows with enhanced automation.
    """
    if not LANGCHAIN_AVAILABLE:
        # Enhanced fallback implementation
        text_lower = user_text.lower()
        
        # GitHub operations
        if any(keyword in text_lower for keyword in ['pr', 'pull request', 'merge']):
            return """🔀 **Pull Request Management**\n\nI can handle:\n\n**PR Operations:**
• Create pull requests: `"Create PR for feature-branch"`
• Review PRs: `"Review PR #123"`
• Merge PRs: `"Merge PR #123"`
• List PRs: `"Show open PRs"`

**PR Analysis:**
• Automated code review suggestions
• Conflict detection and resolution
• Status checks monitoring
• Reviewer assignment

**What PR operation would you like?**"""
        
        elif any(keyword in text_lower for keyword in ['issue', 'bug', 'ticket']):
            return """🎫 **Issue Management**\n\nI can help with:\n\n**Issue Operations:**
• Create issues: `"Create issue: Bug in login flow"`
• Assign issues: `"Assign issue #45 to @user"`
• Close issues: `"Close issue #45"`
• List issues: `"Show open issues"`

**Issue Types:**
• Bug reports with templates
• Feature requests with prioritization
• Documentation issues
• Enhancement proposals

**What issue would you like to manage?**"""
        
        elif any(keyword in text_lower for keyword in ['release', 'version', 'tag']):
            return """🚀 **Release Management**\n\nI can assist with:\n\n**Release Operations:**
• Create releases: `"Release v1.2.0"`
• Generate changelogs: `"Generate changelog for v1.2.0"`
• Tag commits: `"Tag commit abc123 as v1.2.0"`
• Version bumping: `"Bump version to 1.3.0"`

**Release Automation:**
• Automated version detection
• Changelog from commit messages
• Release notes generation
• Asset attachment

**What release operation do you need?**"""
        
        elif any(keyword in text_lower for keyword in ['workflow', 'ci', 'cd', 'action']):
            return """⚙️ **Workflow Management**\n\nI can manage:\n\n**CI/CD Operations:**
• Check workflow status: `"Show workflow status"`
• Trigger workflows: `"Run CI pipeline"`
• Monitor actions: `"Show recent GitHub Actions"`
• Debug failed runs

**Workflow Types:**
• CI/CD pipelines
• Automated testing
• Security scans
• Dependency updates

**What workflow would you like to manage?**"""
        
        else:
            return """🐙 **GitHub Integration Assistant**\n\nI'm your GitHub agent, connecting your project to powerful repository features:\n\n**Core GitHub Functions:**
• **Pull Requests** - Create, review, merge PRs with smart suggestions
• **Issue Management** - Track, assign, and resolve issues efficiently  
• **Release Management** - Automated versioning and release workflows
• **CI/CD Integration** - Monitor and trigger GitHub Actions
• **Repository Insights** - Analytics, contributor stats, code health

**Quick Actions:**
• "Create PR" - Start new pull request workflow
• "Show issues" - Display current issue backlog
• "Release status" - Check current release pipeline
• "Workflow health" - Monitor CI/CD status

**Repository Integration:**
• Real-time commit monitoring
• Branch management and protection
• Team collaboration workflows
• Automated code quality checks

**What GitHub operation would you like to perform?**"""
    
    # LangChain implementation would go here
    # For now, return a simple fallback response
    return "🐙 I'm GitHub agent, ready to help with repository management and GitHub operations."


def create_graph_agent(llm: BaseChatModel, tools: List[Any] = None) -> AgentFn:
    """
    Creates a more sophisticated agent using LangGraph with tool support.
    """
    if not LANGCHAIN_AVAILABLE or not tools:
        return router_agent  # Fallback to simple agent
    
    def _run(user_text: str, history: List[ChatMessage]) -> str:
        # This would be a LangGraph implementation
        # For now, return a placeholder
        return f"LangGraph agent received: {user_text} (with {len(tools)} tools available)"
    
    return _run
