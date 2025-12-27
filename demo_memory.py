"""
Demo: Conversation Memory with LangGraph Checkpointing
Shows how the agent maintains context across multiple queries
"""

from agent import ReActAgent
from rich.console import Console

console = Console()

def demo_conversation_memory():
    """Demonstrate conversation memory"""
    
    console.print("\n" + "="*80, style="bold cyan")
    console.print("🧠 CONVERSATION MEMORY DEMO", style="bold cyan")
    console.print("="*80 + "\n", style="bold cyan")
    
    agent = ReActAgent()
    thread_id = "demo_thread"
    
    # Query 1: User mentions they ordered a laptop skin
    console.print("\n📝 Query 1: 'I ordered a laptop skin and it's currently dispatched'", style="bold green")
    console.print("-" * 80 + "\n")
    response1 = agent.run(
        "I ordered a laptop skin and it's currently dispatched",
        thread_id=thread_id,
        verbose=False
    )
    console.print(f"🤖 Response: {response1}\n", style="yellow")
    
    # Query 2: Ask about past orders (should remember context)
    console.print("\n📝 Query 2: 'What all have I ordered?'", style="bold green")
    console.print("-" * 80 + "\n")
    response2 = agent.run(
        "What all have I ordered?",
        thread_id=thread_id,
        verbose=False
    )
    console.print(f"🤖 Response: {response2}\n", style="yellow")
    
    # Query 3: Follow-up about specific order
    console.print("\n📝 Query 3: 'When will my laptop skin arrive?'", style="bold green")
    console.print("-" * 80 + "\n")
    response3 = agent.run(
        "When will my laptop skin arrive?",
        thread_id=thread_id,
        verbose=False
    )
    console.print(f"🤖 Response: {response3}\n", style="yellow")
    
    console.print("\n" + "="*80, style="bold cyan")
    console.print("✅ Demo Complete! Agent maintained context across 3 queries.", style="bold green")
    console.print("="*80 + "\n", style="bold cyan")


def demo_separate_threads():
    """Demonstrate separate conversation threads"""
    
    console.print("\n" + "="*80, style="bold cyan")
    console.print("🧵 SEPARATE THREADS DEMO", style="bold cyan")
    console.print("="*80 + "\n", style="bold cyan")
    
    agent = ReActAgent()
    
    # Thread 1: Customer A
    console.print("\n📝 Thread 1 (Customer A): 'My order #98762 is delayed'", style="bold green")
    response1 = agent.run(
        "My order #98762 says 'Out for delivery' for 3 days",
        thread_id="customer_a",
        verbose=False
    )
    console.print(f"🤖 Response: {response1[:100]}...\n", style="yellow")
    
    # Thread 2: Customer B (different context)
    console.print("\n📝 Thread 2 (Customer B): 'I want to return product P123'", style="bold green")
    response2 = agent.run(
        "I want to return product P123",
        thread_id="customer_b",
        verbose=False
    )
    console.print(f"🤖 Response: {response2[:100]}...\n", style="yellow")
    
    # Back to Thread 1 (should remember order #98762)
    console.print("\n📝 Back to Thread 1 (Customer A): 'Can I get a refund?'", style="bold green")
    response3 = agent.run(
        "Can I get a refund?",
        thread_id="customer_a",
        verbose=False
    )
    console.print(f"🤖 Response: {response3[:150]}...\n", style="yellow")
    
    console.print("\n" + "="*80, style="bold cyan")
    console.print("✅ Demo Complete! Each thread maintains separate context.", style="bold green")
    console.print("="*80 + "\n", style="bold cyan")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "threads":
        demo_separate_threads()
    else:
        demo_conversation_memory()
