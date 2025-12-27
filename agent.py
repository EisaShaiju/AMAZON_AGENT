"""
LangGraph-based ReAct Agent for E-Commerce Order Resolution
Implements production-grade agentic reasoning with state management
"""

import json
from typing import Dict, Any, List, Optional, Annotated, TypedDict
from datetime import datetime
import operator

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

import config
from tools import (
    get_order_status, 
    get_refund_status, 
    get_inventory,
    get_user_orders,
    ToolStatus
)
from retriever import PolicyRetriever


# Define Agent State
class AgentState(TypedDict):
    """State that flows through the LangGraph nodes"""
    # Input
    query: str
    user_id: str
    
    # Planning
    identified_intents: List[str]
    missing_information: List[str]
    planned_steps: List[str]
    requires_clarification: bool
    
    # Execution
    current_step: int
    iteration_count: int
    messages: Annotated[List[Any], operator.add]
    last_action: Optional[str]  # FIX: Add this to preserve action between nodes
    last_action_input: Optional[str]  # FIX: Add this too
    
    # Tool results
    tool_results: Dict[str, Any]
    
    # Reflection
    contradictions_found: List[str]
    assumptions: List[str]
    confidence_score: float
    
    # Final output
    final_answer: Optional[str]
    should_continue: bool


class ReActAgent:
    """
    LangGraph-based ReAct Agent for E-Commerce Order Resolution
    
    Architecture:
    - State-based graph execution
    - Dynamic re-planning through conditional edges
    - Explicit reflection nodes
    - Policy-grounded responses via RAG
    """
    
    def __init__(self):
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found. Please set it in .env file")
        
        # Initialize LLM
        self.llm = ChatGroq(
            groq_api_key=config.GROQ_API_KEY,
            model_name=config.MODEL_NAME,
            temperature=0.3,
            max_tokens=2000
        )
        
        # Initialize retriever
        self.retriever = PolicyRetriever()
        self.retriever.load_policies()
        
        # Initialize memory for conversation history
        self.memory = MemorySaver()
        
        # Build graph
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state graph for ReAct agent
        
        Graph Flow:
        START → plan → think → act → observe → reflect → decide → [continue or finish]
        """
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("think", self._think_node)
        workflow.add_node("act", self._act_node)
        workflow.add_node("observe", self._observe_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("answer", self._answer_node)
        
        # Define edges
        workflow.set_entry_point("plan")
        
        # Plan → Think (or Answer if clarification needed)
        workflow.add_conditional_edges(
            "plan",
            self._should_clarify,
            {
                "clarify": "answer",
                "continue": "think"
            }
        )
        
        # Think → Act
        workflow.add_edge("think", "act")
        
        # Act → Observe
        workflow.add_edge("act", "observe")
        
        # Observe → Reflect (every 2 iterations or on errors)
        workflow.add_conditional_edges(
            "observe",
            self._should_reflect,
            {
                "reflect": "reflect",
                "continue": "think"
            }
        )
        
        # Reflect → Think (re-plan) or Answer (finish)
        workflow.add_conditional_edges(
            "reflect",
            self._should_continue,
            {
                "continue": "think",
                "finish": "answer"
            }
        )
        
        # Answer → END
        workflow.add_edge("answer", END)
        
        # Compile with memory checkpointer for conversation history
        return workflow.compile(checkpointer=self.memory)
    
    # ========== NODE IMPLEMENTATIONS ==========
    
    def _plan_node(self, state: AgentState) -> AgentState:
        """
        Initial planning: Identify intents, missing info, and create execution plan
        """
        system_prompt = """You are an expert planning assistant for e-commerce customer service.
Analyze the query and create a structured plan.

Respond ONLY with valid JSON:
{
  "identified_intents": ["intent1", "intent2"],
  "missing_information": ["field1", "field2"],
  "planned_steps": ["step1", "step2"],
  "requires_clarification": false,
  "confidence": 0.9
}

Available intents: order_status, refund_status, delivery_delay, inventory_check, extra_charges, return_policy, cancellation
Available tools: get_order_status, get_refund_status, get_inventory, get_user_orders"""

        user_prompt = f"""Query: "{state['query']}"
User ID: {state['user_id']}

Create execution plan."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Parse plan
        try:
            plan_text = response.content.strip()
            if "```json" in plan_text:
                plan_text = plan_text.split("```json")[1].split("```")[0].strip()
            elif "```" in plan_text:
                plan_text = plan_text.split("```")[1].split("```")[0].strip()
            
            plan = json.loads(plan_text)
            
            state["identified_intents"] = plan.get("identified_intents", [])
            state["missing_information"] = plan.get("missing_information", [])
            state["planned_steps"] = plan.get("planned_steps", [])
            state["requires_clarification"] = plan.get("requires_clarification", False)
            state["confidence_score"] = plan.get("confidence", 0.5)
            state["current_step"] = 0
            state["iteration_count"] = 0
            state["tool_results"] = {}
            state["contradictions_found"] = []
            state["assumptions"] = []
            state["should_continue"] = True
            
            state["messages"] = [
                HumanMessage(content=f"📋 PLAN:\n{json.dumps(plan, indent=2)}")
            ]
            
        except Exception as e:
            # Fallback plan
            state["identified_intents"] = ["general_inquiry"]
            state["missing_information"] = []
            state["planned_steps"] = ["Analyze query", "Retrieve policies", "Respond"]
            state["requires_clarification"] = False
            state["confidence_score"] = 0.3
            state["messages"] = [HumanMessage(content=f"⚠️ Planning error: {str(e)}")]
        
        return state
    
    def _think_node(self, state: AgentState) -> AgentState:
        """
        Reasoning step: Decide next action based on current state
        """
        # Build context from previous steps
        context = self._build_context(state)
        
        system_prompt = """You are a ReAct agent. Think step-by-step about what to do next.

Based on the current state:
1. What information do we have?
2. What information is missing?
3. What's the next logical action?

Respond with your thought process and the next action in this format:
THOUGHT: [Your reasoning]
ACTION: [tool_name]([arguments])

Available actions:
- get_order_status(order_id): Get order details
- get_refund_status(order_id): Check refund status  
- get_inventory(product_id): Check inventory
- get_user_orders(user_id): Get recent orders
- retrieve_policy(query): Get relevant policies
- FINISH: Generate final answer

Example:
THOUGHT: The user asked about order #98762 status. I need to fetch the order details first.
ACTION: get_order_status("98762")"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]
        
        response = self.llm.invoke(messages)
        thought_content = response.content.strip()
        
        # Store thought silently
        state["messages"] = [AIMessage(content=thought_content)]
        state["iteration_count"] += 1
        
        return state
    
    def _act_node(self, state: AgentState) -> AgentState:
        """
        Action step: Execute the planned tool/action
        """
        # Get last thought
        last_message = state["messages"][-1].content if state["messages"] else ""
        
        # Parse action
        action, action_input = self._parse_action(last_message)
        
        if not action or action == "None":
            # Force FINISH if parsing failed
            action = "FINISH"
            action_input = ""
            state["should_continue"] = False
        
        # Store action silently
        state["last_action"] = action
        state["last_action_input"] = action_input
        state["messages"] = [AIMessage(content=f"{action}({action_input})")]
        
        return state
    
    def _observe_node(self, state: AgentState) -> AgentState:
        """
        Observation step: Execute tool and capture results
        """
        action = state.get("last_action")
        action_input = state.get("last_action_input", "")
        
        if action == "FINISH":
            state["should_continue"] = False
            observation = "Ready to generate final answer"
        else:
            # Execute tool
            observation = self._execute_tool(action, action_input, state)
            
            # Store result
            state["tool_results"][f"{action}_{action_input}"] = observation
        
        # Store observation silently
        state["messages"] = [AIMessage(content=observation)]
        
        return state
    
    def _reflect_node(self, state: AgentState) -> AgentState:
        """
        Reflection step: Analyze results, detect contradictions, decide if re-planning needed
        """
        context = self._build_reflection_context(state)
        
        system_prompt = """You are a critical thinking assistant. Analyze the agent's progress.

Check for:
1. Contradictions between tool outputs
2. Weak assumptions
3. Missing critical information
4. Policy conflicts

Respond with JSON:
{
  "contradictions": ["contradiction1", "contradiction2"],
  "assumptions": ["assumption1"],
  "confidence": 0.8,
  "should_revise_plan": false,
  "reasoning": "explanation",
  "next_steps": ["step1", "step2"]
}"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            reflection_text = response.content.strip()
            if "```json" in reflection_text:
                reflection_text = reflection_text.split("```json")[1].split("```")[0].strip()
            
            reflection = json.loads(reflection_text)
            
            state["contradictions_found"] = reflection.get("contradictions", [])
            state["assumptions"] = reflection.get("assumptions", [])
            state["confidence_score"] = reflection.get("confidence", state["confidence_score"])
            
            # Update plan if needed
            if reflection.get("should_revise_plan"):
                state["planned_steps"] = reflection.get("next_steps", state["planned_steps"])
            
            state["messages"] = [
                AIMessage(content=f"🔍 REFLECTION:\n{reflection.get('reasoning', '')}")
            ]
            
            # Decide if we should finish
            if state["iteration_count"] >= config.MAX_ITERATIONS:
                state["should_continue"] = False
            elif reflection.get("confidence", 0) > 0.85 and not reflection.get("contradictions"):
                state["should_continue"] = False
                
        except Exception as e:
            state["messages"] = [AIMessage(content=f"⚠️ Reflection error: {str(e)}")]
        
        return state
    
    def _answer_node(self, state: AgentState) -> AgentState:
        """
        Final answer generation: Create user-safe, policy-grounded response
        """
        # Handle clarification request
        if state.get("requires_clarification") and state.get("missing_information"):
            clarification = self._generate_clarification(state)
            state["final_answer"] = clarification
            return state
        
        # Retrieve relevant policies
        policy_context = self.retriever.retrieve(state["query"], top_k=3)
        
        # Build comprehensive context
        context = self._build_final_context(state, policy_context)
        
        system_prompt = """You are a customer service AI assistant. Generate a concise response in 3-4 sentences maximum.

Format: [What we found] + [Why/Policy explanation] + [What to do next]

RULES:
- Be direct and brief - no lengthy sections
- Ground response in tool data and policies
- State uncertainty briefly if present
- Provide one clear action

Example: "Your order #98762 is out for delivery, delayed 3 days beyond the Dec 24 expected date. Under our delivery delay policy (Section 3), delays exceeding 48 hours qualify for 5% compensation. You can claim this through your account dashboard, or wait for delivery which tracking shows arriving within 24 hours."
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]
        
        response = self.llm.invoke(messages)
        state["final_answer"] = response.content.strip()
        
        return state
    
    # ========== CONDITIONAL EDGE FUNCTIONS ==========
    
    def _should_clarify(self, state: AgentState) -> str:
        """Decide if clarification is needed"""
        if state.get("requires_clarification") and state.get("missing_information"):
            return "clarify"
        return "continue"
    
    def _should_reflect(self, state: AgentState) -> str:
        """Decide if reflection is needed - reduced frequency for efficiency"""
        # Skip reflection if we just got good data
        last_obs = state["messages"][-1].content if state["messages"] else ""
        if "Success:" in last_obs and state.get("last_action") != "FINISH":
            return "continue"
        
        # Reflect only if FINISH action
        if state.get("last_action") == "FINISH":
            return "reflect"
        
        # Reflect only every 3 iterations (not every 2)
        if state["iteration_count"] % 3 == 0 and state["iteration_count"] > 0:
            # Check if we have errors or contradictions
            if "error" in last_obs.lower() or "partial" in last_obs.lower():
                return "reflect"
        
        # Force reflection if near limit
        if state["iteration_count"] >= config.MAX_ITERATIONS - 1:
            return "reflect"
        
        return "continue"
    
    def _should_continue(self, state: AgentState) -> str:
        """Decide if agent should continue or finish - with early exit optimizations"""
        # Always finish if FINISH action was called
        if state.get("last_action") == "FINISH":
            return "finish"
        
        # Stop if explicitly told not to continue
        if not state.get("should_continue", True):
            return "finish"
        
        # Stop at max iterations (reduced to 10 for faster responses)
        if state["iteration_count"] >= min(config.MAX_ITERATIONS, 10):
            return "finish"
        
        # Early exit if we have good data and high confidence
        if state.get("confidence_score", 0) > 0.7 and len(state.get("tool_results", {})) > 0:
            last_obs = state["messages"][-1].content if state["messages"] else ""
            if "Success:" in last_obs:
                return "finish"
        
        # Detect infinite loops - same action repeated 3+ times
        if len(state.get("tool_results", {})) >= 3:
            # Check if same tool called multiple times with same input
            tool_calls = list(state["tool_results"].keys())
            if len(tool_calls) >= 3:
                last_three = tool_calls[-3:]
                if len(set(last_three)) == 1:  # All the same
                    return "finish"
            return "finish"
        
        return "continue"
    
    # ========== HELPER METHODS ==========
    
    def _parse_action(self, thought: str) -> tuple[Optional[str], str]:
        """Extract action and input from thought"""
        if "ACTION:" not in thought:
            # Try to trigger FINISH if we've done enough iterations
            return "FINISH", ""
        
        action_line = thought.split("ACTION:")[1].strip().split("\n")[0]
        
        if "FINISH" in action_line:
            return "FINISH", ""
        
        # Parse function call
        if "(" in action_line and ")" in action_line:
            action_name = action_line.split("(")[0].strip()
            # Handle both quoted and unquoted arguments
            action_input = action_line.split("(")[1].split(")")[0].strip()
            # Remove quotes if present
            action_input = action_input.strip('"').strip("'")
            
            # Validate action name is not empty
            if action_name and action_name != "":
                return action_name, action_input
        
        # If we can't parse, finish
        return "FINISH", ""
    
    def _execute_tool(self, tool_name: str, tool_input: str, state: AgentState) -> str:
        """Execute a tool and return observation"""
        try:
            if tool_name == "get_order_status":
                result = get_order_status(tool_input).to_dict()
            elif tool_name == "get_refund_status":
                result = get_refund_status(tool_input).to_dict()
            elif tool_name == "get_inventory":
                result = get_inventory(tool_input).to_dict()
            elif tool_name == "get_user_orders":
                result = get_user_orders(tool_input).to_dict()
            elif tool_name == "retrieve_policy":
                docs = self.retriever.retrieve(tool_input, top_k=2)
                return f"Retrieved policies:\n{docs}"
            else:
                return f"⚠️ Unknown tool: {tool_name}"
            
            # Format result
            status = result.get("status", "unknown")
            data = result.get("data", {})
            error = result.get("error", "")
            
            if status == ToolStatus.SUCCESS.value:
                return f"✅ Success:\n{json.dumps(data, indent=2)}"
            elif status == ToolStatus.PARTIAL.value:
                return f"⚠️ Partial data:\n{json.dumps(data, indent=2)}\nNote: Some fields may be missing"
            else:
                return f"❌ Error: {error}"
                
        except Exception as e:
            return f"❌ Tool execution error: {str(e)}"
    
    def _build_context(self, state: AgentState) -> str:
        """Build context for thinking step"""
        context = f"""Original Query: {state['query']}
User ID: {state['user_id']}

Current Plan:
- Intents: {', '.join(state['identified_intents'])}
- Steps: {', '.join(state['planned_steps'])}

Iteration: {state['iteration_count']}/{config.MAX_ITERATIONS}

Tool Results:
{json.dumps(state['tool_results'], indent=2) if state['tool_results'] else 'None yet'}

What should we do next?"""
        return context
    
    def _build_reflection_context(self, state: AgentState) -> str:
        """Build context for reflection"""
        recent_messages = state["messages"][-4:] if len(state["messages"]) > 4 else state["messages"]
        msg_text = "\n".join([m.content for m in recent_messages])
        
        return f"""Query: {state['query']}
Intents: {state['identified_intents']}

Recent Activity:
{msg_text}

Tool Results:
{json.dumps(state['tool_results'], indent=2)}

Analyze for contradictions and confidence."""
    
    def _build_final_context(self, state: AgentState, policies: str) -> str:
        """Build context for final answer"""
        return f"""Original Query: {state['query']}

Identified Intents: {', '.join(state['identified_intents'])}

Tool Results:
{json.dumps(state['tool_results'], indent=2)}

Relevant Policies:
{policies}

Contradictions Found: {state['contradictions_found']}
Confidence: {state['confidence_score']}

Generate final response."""
    
    def _generate_clarification(self, state: AgentState) -> str:
        """Generate clarification request"""
        missing = ', '.join(state['missing_information'])
        return f"""I'd be happy to help with your request: "{state['query']}"

To assist you better, I need some additional information:
{chr(10).join([f"- {item}" for item in state['missing_information']])}

Could you please provide these details?"""
    
    # ========== PUBLIC API ==========
    
    def run(self, query: str, user_id: str = "user_12345", thread_id: str = "default", verbose: bool = False, debug: bool = False) -> str:
        """
        Execute the agent on a query
        
        Args:
            query: User's question/request
            user_id: User identifier
            thread_id: Conversation thread ID (use same ID to continue conversation)
            verbose: Show brief execution summary (default: False)
            debug: Show full execution trace (default: False)
        
        Returns:
            Final answer
        """
        initial_state = {
            "query": query,
            "user_id": user_id,
            "messages": [],
            "should_continue": True
        }
        
        # Execute graph with checkpointing for conversation memory
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 15  # Reduced from 50 for faster responses
        }
        final_state = self.graph.invoke(initial_state, config)
        
        if debug:
            print("\n" + "="*80)
            print("EXECUTION TRACE (DEBUG MODE)")
            print("="*80)
            for msg in final_state.get("messages", []):
                print(f"\n{msg.content}")
            
            print("\n" + "="*80)
            print("✅ FINAL ANSWER")
            print("="*80)
            print(final_state.get("final_answer", "No answer generated"))
            print()
        
        return final_state.get("final_answer", "I apologize, but I encountered an issue processing your request.")
    
    def visualize(self, output_path: str = "agent_graph.png"):
        """
        Visualize the agent's graph structure
        
        Args:
            output_path: Path to save visualization
        """
        try:
            from IPython.display import Image, display
            display(Image(self.graph.get_graph().draw_mermaid_png()))
        except Exception as e:
            print(f"Visualization requires graphviz and IPython: {e}")
            print("\nGraph structure:")
            print("plan → [clarify check] → think → act → observe → [reflect check] → reflect → [continue check] → answer")
