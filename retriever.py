"""
RAG Retriever: Policy document embedding and retrieval with conflict detection
"""

import os
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import config


class PolicyRetriever:
    """
    Handles policy document embedding, retrieval, and conflict detection
    """
    
    def __init__(self):
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        
        # Initialize ChromaDB for vector storage
        self.chroma_client = chromadb.Client(Settings(
            anonymized_telemetry=False,
            is_persistent=False
        ))
        
        self.collection = self.chroma_client.create_collection(
            name="policies",
            metadata={"description": "E-commerce policy documents"}
        )
        
        self.policies_loaded = False
    
    def load_policies(self, policy_dir: str = None):
        """
        Load and embed policy documents from directory
        """
        if policy_dir is None:
            policy_dir = config.POLICY_DIR
        
        if not os.path.exists(policy_dir):
            print(f"⚠ Policy directory not found: {policy_dir}")
            print("Using embedded sample policies...")
            self._load_sample_policies()
            return
        
        documents = []
        metadatas = []
        ids = []
        
        for filename in os.listdir(policy_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(policy_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Chunk the document
                chunks = self._chunk_text(content, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
                
                for i, chunk in enumerate(chunks):
                    documents.append(chunk)
                    metadatas.append({
                        "source": filename,
                        "chunk_id": i,
                        "policy_type": filename.replace('.txt', '').replace('_', ' ')
                    })
                    ids.append(f"{filename}_{i}")
        
        if documents:
            # Embed and store
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            self.policies_loaded = True
            print(f"Loaded {len(documents)} policy chunks from {len(set([m['source'] for m in metadatas]))} files")
        else:
            print("No policy files found, using sample policies")
            self._load_sample_policies()
    
    def _load_sample_policies(self):
        """
        Load sample policies when no policy files are found
        """
        sample_policies = {
            "refund_policy.txt": """
REFUND POLICY

Section 1: General Refund Terms
- Refunds are processed within 5-7 business days of approval
- Full refunds are issued for defective products
- Partial refunds may apply for used or opened items

Section 2: Delivery Delays
- Orders delayed beyond 48 hours from expected delivery may qualify for refund
- Delays due to weather or natural disasters are excluded
- Customer must request refund within 10 days of expected delivery

Section 3: Cancellation
- Orders can be cancelled within 24 hours of placement for full refund
- After 24 hours, cancellation fees may apply based on order status
            """,
            
            "delivery_delay_policy.txt": """
DELIVERY DELAY POLICY

Section 1: Expected Delivery Times
- Standard delivery: 5-7 business days
- Express delivery: 2-3 business days
- Same-day delivery: Orders placed before 12 PM

Section 2: Delay Handling
- Delays of 1-2 days: Customer service notification
- Delays beyond 48 hours: Automatic refund eligibility
- Delays beyond 7 days: Full refund + 10% credit

Section 3: Compensation
- Minor delays (1-2 days): Free shipping on next order
- Major delays (3+ days): 5% refund or store credit
- Severe delays (7+ days): Full refund + additional compensation
            """,
            
            "return_policy.txt": """
RETURN POLICY

Section 1: Return Window
- Electronics: 14 days from delivery
- Clothing and accessories: 30 days from delivery
- Perishables: No returns accepted

Section 2: Condition Requirements
- Items must be unused and in original packaging
- All accessories and documentation must be included
- Damaged items may be returned regardless of usage

Section 3: Return Process
- Initiate return through customer portal or support
- Return shipping label provided for eligible returns
- Inspection completed within 3 business days of receipt
            """,
            
            "charges_and_fees_policy.txt": """
CHARGES AND FEES POLICY

Section 1: Order Charges
- Product price: As listed at time of purchase
- Shipping charges: Based on weight and distance
- Tax: Calculated based on delivery address

Section 2: Additional Fees
- Express delivery surcharge: $10-15
- Remote area delivery: Additional $5
- COD fee: $2 per order

Section 3: Hidden Charges
- Platform fee: Included in product price
- Processing fee: Only for installment payments
- No hidden fees - all charges displayed at checkout
            """
        }
        
        documents = []
        metadatas = []
        ids = []
        
        for filename, content in sample_policies.items():
            chunks = self._chunk_text(content, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({
                    "source": filename,
                    "chunk_id": i,
                    "policy_type": filename.replace('.txt', '').replace('_', ' ')
                })
                ids.append(f"{filename}_{i}")
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        self.policies_loaded = True
        print(f"✓ Loaded {len(documents)} sample policy chunks")
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Split text into overlapping chunks
        """
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def retrieve(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant policy chunks for a query
        
        Returns:
            List of dicts with 'content', 'source', 'relevance_score'
        """
        if not self.policies_loaded:
            self.load_policies()
        
        if top_k is None:
            top_k = config.TOP_K_POLICIES
        
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        retrieved_policies = []
        
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                retrieved_policies.append({
                    'content': doc,
                    'source': results['metadatas'][0][i]['source'],
                    'policy_type': results['metadatas'][0][i]['policy_type'],
                    'relevance_score': 1 - results['distances'][0][i] if 'distances' in results else 1.0,
                    'chunk_id': results['metadatas'][0][i]['chunk_id']
                })
        
        return retrieved_policies
    
    def detect_conflicts(self, policies: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Detect potential conflicts between retrieved policies
        
        Returns:
            (has_conflicts, conflict_descriptions)
        """
        conflicts = []
        
        # Check if policies are from different sources
        sources = set([p['source'] for p in policies])
        if len(sources) > 1:
            # Check for contradictory statements (simple keyword-based detection)
            refund_keywords = ['refund', 'no refund', 'not eligible']
            delay_keywords = ['48 hours', '7 days', 'immediate']
            
            refund_mentions = [p for p in policies if any(kw in p['content'].lower() for kw in refund_keywords)]
            delay_mentions = [p for p in policies if any(kw in p['content'].lower() for kw in delay_keywords)]
            
            if len(refund_mentions) > 1:
                conflicts.append(
                    f"Potentially conflicting refund policies from {set([p['source'] for p in refund_mentions])}"
                )
            
            if len(delay_mentions) > 1:
                conflicts.append(
                    f"Different delay thresholds mentioned across policies"
                )
        
        return len(conflicts) > 0, conflicts
    
    def format_policy_context(self, policies: List[Dict[str, Any]]) -> str:
        """
        Format retrieved policies for agent consumption
        """
        if not policies:
            return "No relevant policies found."
        
        formatted = "📋 RELEVANT POLICIES:\n\n"
        
        for i, policy in enumerate(policies, 1):
            formatted += f"{i}. From {policy['policy_type']} (relevance: {policy['relevance_score']:.2f}):\n"
            formatted += f"   {policy['content']}\n\n"
        
        # Add conflict warnings
        has_conflicts, conflict_msgs = self.detect_conflicts(policies)
        if has_conflicts:
            formatted += "⚠ POLICY CONFLICTS DETECTED:\n"
            for msg in conflict_msgs:
                formatted += f"   - {msg}\n"
            formatted += "\n"
        
        return formatted


if __name__ == "__main__":
    # Test retriever
    print("=== Testing Policy Retriever ===\n")
    
    retriever = PolicyRetriever()
    retriever.load_policies()
    
    print("\n1. Query: 'delivery delay refund eligibility'")
    policies = retriever.retrieve("delivery delay refund eligibility", top_k=3)
    print(retriever.format_policy_context(policies))
    
    print("\n2. Query: 'return window for electronics'")
    policies = retriever.retrieve("return window for electronics", top_k=2)
    print(retriever.format_policy_context(policies))
