"""
Configuration file for the E-Commerce Order Resolution Agent
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration - Using Groq for LangGraph
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # groq for fast inference
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "mixtral-8x7b-32768")  # Mixtral - reliable and available
TEMPERATURE = 0.3  # Lower temperature for more deterministic reasoning
MAX_TOKENS = 2000

# LangGraph Agent Configuration
MAX_ITERATIONS = 10  # Maximum reasoning steps before stopping
REFLECTION_FREQUENCY = 2  # Reflect every N iterations
REFLECTION_ON_ERROR = True  # Trigger reflection on tool errors
VERBOSE = True  # Print agent's thoughts and actions
ENABLE_GRAPH_VISUALIZATION = False  # Requires graphviz

# Tool Configuration
TOOL_FAILURE_RATE = 0.2  # 20% chance of tool failure
PARTIAL_DATA_RATE = 0.3  # 30% chance of partial/missing data
SIMULATE_DELAYS = True  # Simulate API latency

# RAG Configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_POLICIES = 3  # Number of policy sections to retrieve
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
POLICY_DIR = "policies"

# User Session
DEFAULT_USER_ID = "user_12345"  # For tracking user orders
