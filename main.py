import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Agent 1 Imports
from agents.inventory_management.agent import inventory_graph
from shared.database import sales_collection

# Agent 2 & 3 Imports
from agents.supplier_sourcing.agent import CompleteSuppliersManagerAgent, UI
from agents.compliance_fulfillment.agent import ComplianceAndFulfillmentAgent

def run_pipeline():
    UI.section("STAGE 1: INVENTORY MANAGEMENT AGENT")
    print("Total DB Records:", sales_collection.count_documents({}))
    print("\n--- Starting Inventory Graph Workflow ---")
    
    # Invoke Agent 1 graph
    final_state = inventory_graph.invoke({
        "current_inventory": [], 
        "historical_sales": [], 
        "final_output": None
    })
    
    output = final_state.get("final_output")
    if hasattr(output, "model_dump"):
        agent1_payload = output.model_dump()
    else:
        agent1_payload = output
        
    print("\n=== Agent 1 Final Output ===")
    print(json.dumps(agent1_payload, indent=2))
    
    if not agent1_payload or "replenishments" not in agent1_payload or not agent1_payload["replenishments"]:
        print("\nNo products need restocking. Pipeline ending early.")
        return
        
    # Map 'replenishments' from Agent 1 to 'products' for Agent 2
    agent1_payload["products"] = agent1_payload.pop("replenishments")

    # User Input for Email Signature (Agent 2)
    print(f"\n{UI.BOLD}{UI.BLUE}🔹 Please provide your details for the email signature:{UI.ENDC}")
    sender_details = {
        "company": input("  Company Name: ").strip(),
        "address": input("  Company Address: ").strip(),
        "name": input("  Your Name / Contact Person: ").strip(),
        "title": input("  Your Title: ").strip(),
        "phone": input("  Phone Number: ").strip(),
        "email": input("  Email Address: ").strip()
    }

    UI.section("STAGE 2 & 3: CATEGORY PROCESSING LOOP")
    agent2 = CompleteSuppliersManagerAgent()
    
    # 1. Segment items into mapped categories
    categorized_needs = agent2.segment_items(agent1_payload)
    
    if not categorized_needs:
        print("No mapped categories found.")
        return

    # User Input for Target Compliance Policies (Ask once upfront)
    print(f"\n{UI.BOLD}{UI.BLUE}🔹 Please provide your target compliance policies:{UI.ENDC}")
    try:
        fee_input = input("  Max Advance Payment Percentage (e.g., 0.50 for 50%): ").strip()
        fee = float(fee_input) if fee_input else 0.50
        days_input = input("  Min Return Window Days (e.g., 30): ").strip()
        days = int(days_input) if days_input else 30
        parties_input = input("  Acceptable Liability Parties (comma-separated, e.g., seller, shared): ").strip()
        parties = [p.strip().lower() for p in parties_input.split(",")] if parties_input else ["seller", "shared"]
    except ValueError:
        print("  Invalid input, using default policies.")
        fee, days, parties = 0.50, 30, ["seller", "shared"]
        
    user_policy = {
        "max_advance_payment_percentage": fee,
        "min_return_window_days": days,
        "acceptable_liability_parties": parties
    }
    agent3 = ComplianceAndFulfillmentAgent(user_policy=user_policy, sender_details=sender_details)

    while categorized_needs:
        print(f"\n{UI.HEADER}{UI.BOLD}=== CATEGORY MENU ==={UI.ENDC}")
        categories = list(categorized_needs.keys())
        for i, c in enumerate(categories):
            print(f"  [{i+1}] {c.upper()} ({len(categorized_needs[c])} items)")
        print(f"  [Q] Quit")
        
        choice = input("\nSelect a category to process: ").strip()
        if choice.lower() == 'q':
            break
            
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(categories):
                raise ValueError
            selected_cat = categories[idx]
        except ValueError:
            print("Invalid selection.")
            continue
            
        items_to_process = categorized_needs[selected_cat]
        
        # Phase 1: Outbound
        contacted = agent2.process_outbound_for_category(selected_cat, items_to_process, sender_details)
        if not contacted:
            print(f"{UI.WARNING}No suppliers found for this category.{UI.ENDC}")
            del categorized_needs[selected_cat]
            continue
            
        # Phase 2: Inbound
        quotes = agent2.fetch_inbound_quotes_for_category(selected_cat, contacted)
        
        if not quotes:
            print(f"{UI.FAIL}No quotes received for {selected_cat}.{UI.ENDC}")
            continue
            
        print(f"\n{UI.BLUE}Received Quotes summary:{UI.ENDC}")
        for q in quotes:
            print(f" - {q.get('supplier_name')}: ${q.get('quoted_amount')} for {len(q.get('quoted_items', []))} items")
            
        proceed = input("\nAre these quotes fine? Send to Agent 3? (y/n): ").strip().lower()
        if proceed == 'y':
            # Phase 3: Ranking
            report_block = agent2.rank_quotes_for_category(selected_cat, quotes)
            
            # Phase 4: Compliance
            agent3.process_negotiation_pipeline(selected_cat, report_block, quotes)
            
            # Remove from queue if done
            del categorized_needs[selected_cat]
            print(f"{UI.GREEN}Finished processing {selected_cat}.{UI.ENDC}")
        else:
            print("Skipping to menu. You can try this category again.")
        
    UI.section("Pipeline Execution Complete")

if __name__ == "__main__":
    run_pipeline()
