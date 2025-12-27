"""
CLI Interface for E-Commerce Order Resolution Agent
LangGraph-based ReAct agent with interactive and test modes
"""

import sys
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from agent import ReActAgent
import config

console = Console()


def print_banner():
    """Display welcome banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🤖  E-Commerce Order Resolution Agent (LangGraph)       ║
║                                                               ║
║     Powered by Groq + LangGraph                              ║
║     Model: Llama 3.3 70B Versatile                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def run_interactive_mode():
    """Interactive chat mode with conversation memory"""
    print_banner()
    console.print("\n💬 Interactive Mode - Type 'exit' to quit, 'test' to run test queries", style="bold green")
    console.print("💡 Conversation memory is enabled! Agent remembers context within the session.\n", style="bold yellow")
    
    agent = ReActAgent()
    thread_id = "interactive_session"  # Single thread for interactive mode
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("\n👋 Goodbye!\n", style="bold yellow")
                break
            
            if user_input.lower() == 'test':
                run_test_queries()
                continue
            
            if user_input.lower() == 'new':
                thread_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                console.print(f"\n🔄 Started new conversation thread: {thread_id}\n", style="bold cyan")
                continue
            
            if not user_input.strip():
                continue
            
            # Run agent with conversation memory (quiet mode by default)
            console.print("\n[bold magenta]Agent Processing...[/bold magenta]\n")
            response = agent.run(user_input, thread_id=thread_id, verbose=False, debug=False)
            
            # Display response in a panel
            console.print(Panel(
                response,
                title="[bold green]✓ Agent Response[/bold green]",
                border_style="green"
            ))
            
        except KeyboardInterrupt:
            console.print("\n\n👋 Interrupted. Goodbye!\n", style="bold yellow")
            break
        except Exception as e:
            console.print(f"\n[bold red]❌ Error:[/bold red] {str(e)}\n")


def run_test_queries():
    """Run predefined test queries"""
    console.print("\n" + "="*80, style="bold cyan")
    console.print("🧪 RUNNING TEST QUERIES", style="bold cyan")
    console.print("="*80 + "\n", style="bold cyan")
    
    test_queries = [
        {
            "query": "My order #98762 says 'Out for delivery' for 3 days. What's happening?",
            "description": "Order delay with specific ID"
        },
        {
            "query": "Is product P123 available in stock?",
            "description": "Inventory check"
        },
        {
            "query": "I want to check refund status for order 54321.",
            "description": "Refund status query"
        },
        {
            "query": "Why was I charged extra on my last purchase?",
            "description": "Missing order ID - should ask for clarification"
        },
        {
            "query": "My delivery is late and I want a refund — am I eligible?",
            "description": "Multi-intent: delay + refund eligibility"
        },
        {
            "query": "What is the return window for electronics?",
            "description": "Policy-only query"
        },
        {
            "query": "My order is late but refund shows processed. Explain.",
            "description": "Contradiction detection"
        }
    ]
    
    agent = ReActAgent()
    
    for i, test_case in enumerate(test_queries, 1):
        console.print(f"\n{'─'*80}", style="cyan")
        console.print(f"TEST {i}/{len(test_queries)}: {test_case['description']}", style="bold cyan")
        console.print(f"{'─'*80}\n", style="cyan")
        
        console.print(f"[bold blue]Query:[/bold blue] {test_case['query']}\n")
        
        try:
            response = agent.run(test_case['query'], verbose=True)
            
            console.print(Panel(
                response,
                title=f"[bold green]✓ Test {i} Complete[/bold green]",
                border_style="green"
            ))
            
        except Exception as e:
            console.print(f"[bold red]❌ Test {i} Failed:[/bold red] {str(e)}")
        
        if i < len(test_queries):
            input("\nPress Enter to continue to next test...")
    
    console.print(f"\n{'='*80}", style="bold green")
    console.print("✅ ALL TESTS COMPLETED", style="bold green")
    console.print(f"{'='*80}\n", style="bold green")


def run_single_query(query: str):
    """Run a single query from command line"""
    print_banner()
    console.print(f"\n[bold blue]Query:[/bold blue] {query}\n")
    
    agent = ReActAgent()
    response = agent.run(query, verbose=True)
    
    console.print(Panel(
        response,
        title="[bold green]✓ Agent Response[/bold green]",
        border_style="green"
    ))


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Command line argument provided
        if sys.argv[1] == "test":
            run_test_queries()
        else:
            # Treat as single query
            query = " ".join(sys.argv[1:])
            run_single_query(query)
    else:
        # Interactive mode
        run_interactive_mode()


if __name__ == "__main__":
    main()
