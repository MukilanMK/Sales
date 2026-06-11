import os
import json
import pymongo
import time
import sys
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from services.email_utils import EmailHelper

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("Missing GROQ_API_KEY in your environment or .env file.")

client = Groq()
MODEL_ID = 'llama-3.3-70b-versatile'



# ---------------------------------------------------------------------
# TERMINAL VISUAL INTERFACE UTILS
# ---------------------------------------------------------------------
class UI:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def section(title: str):
        print(f"\n{UI.BOLD}{UI.HEADER}{'='*70}{UI.ENDC}")
        print(f"{UI.BOLD}{UI.HEADER} >> {title.upper()} <<{UI.ENDC}")
        print(f"{UI.BOLD}{UI.HEADER}{'='*70}{UI.ENDC}")

    @staticmethod
    def step(title: str):
        print(f"\n{UI.BOLD}{UI.BLUE}🔹 {title}{UI.ENDC}")
        print(f"{UI.BLUE}{'-'*50}{UI.ENDC}")

    @staticmethod
    def log(msg: str):
        print(f"  ⚙️ [System]: {msg}")

    @staticmethod
    def warning(msg: str):
        print(f"  ⚠️ {UI.WARNING}{msg}{UI.ENDC}")

    @staticmethod
    def success(msg: str):
        print(f"  ✅ {UI.GREEN}{msg}{UI.ENDC}")

    @staticmethod
    def print_email(direction: str, name: str, body: str):
        color = UI.WARNING if direction == "OUTBOUND TO" else UI.BLUE
        print(f"\n  📨 {UI.BOLD}{direction} {name.upper()}{UI.ENDC}")
        print(f"  ├─ {UI.BOLD}Subject:{UI.ENDC} Procurement Compliance Terms Alignment Validation")
        print(f"  └─ {UI.BOLD}Body Content:{UI.ENDC}\n  \"\"\"\n  {body.strip()}\n  \"\"\"")

# ---------------------------------------------------------------------
# DATA CAPTURE SCHEMAS
# ---------------------------------------------------------------------
class ConflictAnalysis(BaseModel):
    has_conflict: bool
    conflict_reasoning: str
    flagged_fields: List[str]

class DeliveryTelemetryInput(BaseModel):
    was_on_time: bool
    admin_satisfaction_feedback: str

# ---------------------------------------------------------------------
# AGENT 3 OPERATIONAL LOGIC
# ---------------------------------------------------------------------
class ComplianceAndFulfillmentAgent:
    def __init__(self, user_policy: dict, mongo_uri: str = None):
        self.user_policy = user_policy
        if mongo_uri is None:
            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        _client = pymongo.MongoClient(mongo_uri)
        self.db = _client.supply_chain_db
        self.collection = self.db.suppliers
        self.email_helper = EmailHelper()

    def get_supplier_email(self, s_id: str) -> str:
        row = self.collection.find_one({"id": s_id})
        return row.get("email", "unknown@example.com") if row else "unknown@example.com"

    def call_groq(self, prompt: str, response_schema: Optional[type] = None) -> str:
        kwargs = {
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        if response_schema:
            kwargs["response_format"] = {"type": "json_object"}
            kwargs["messages"].append({
                "role": "system", 
                "content": f"Output an explicit JSON string matching this structure schema: {json.dumps(response_schema.model_json_schema())}"
            })
        completion = client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content.strip()

    def analyze_conflicts(self, name: str, vendor_policies: dict) -> dict:
        UI.step(f"Running Policy Conflict Screening for {name}")
        
        prompt = f"""
        Compare the incoming vendor policies against our baseline corporate requirements rules.
        
        Our Requirements rules:
        - Maximum Advance Payment Percentage: {self.user_policy['max_advance_payment_percentage'] * 100}%
        - Minimum Return Window Period: {self.user_policy['min_return_window_days']} Days
        - Acceptable Damaged Goods Liability Options: {self.user_policy['acceptable_liability_parties']}
        
        Vendor's Active Policy:
        {json.dumps(vendor_policies, indent=2)}
        
        Flag any value that violates or provides worse coverage terms than our rules.
        """
        raw_analysis = self.call_groq(prompt, response_schema=ConflictAnalysis)
        return json.loads(raw_analysis)

    def process_negotiation_pipeline(self, category_group: str, report_block: dict, quotes: List[dict]) -> bool:
        ranked_suppliers = report_block["ranked_supplier_list"]
        
        finalized_supplier_id = None
        finalized_supplier_name = None
        finalized_quote = None
        
        for rank_item in ranked_suppliers:
            s_id = rank_item["supplier_id"]
            s_name = rank_item["supplier_name"]
            
            # Find the full quote from the quotes list
            supplier_quote = next((q for q in quotes if q["supplier_id"] == s_id), None)
            if not supplier_quote:
                continue
                
            is_combo = supplier_quote.get("is_combination", False)
            
            UI.section(f"Compliance Evaluation Segment: Rank {rank_item['rank']} - {s_name} ({category_group})")
            
            # Reconstruct the policies list to check
            policies_list = []
            if is_combo:
                for comp in supplier_quote["component_quotes"]:
                    policy_doc = self.policies_collection.find_one({"supplier_id": comp["supplier_id"]})
                    if policy_doc:
                        policies_list.append(policy_doc)
            else:
                policy_doc = self.policies_collection.find_one({"supplier_id": s_id})
                if policy_doc:
                    policies_list.append(policy_doc)
            
            failed_analysis = None
            failed_name = s_name
            failed_id = s_id
            
            for policy in policies_list:
                comp_name = policy.get("supplier_name", s_name)
                comp_id = policy.get("supplier_id", s_id)
                analysis = self.analyze_conflicts(comp_name, policy)
                if analysis["has_conflict"]:
                    failed_analysis = analysis
                    failed_name = comp_name
                    failed_id = comp_id
                    break
                    
            if not failed_analysis:
                UI.success(f"No contract term anomalies flagged for {s_name}.")
                print(f"\n📋 {UI.BOLD}OPTIONS FOR {s_name.upper()}:{UI.ENDC}")
                print("  [1] OK to continue and Finalize with this supplier")
                print("  [2] Find others from the rank list (Skip to next)")
                
                choice = input("  Enter selected execution code [1-2]: ").strip()
                if choice == "1":
                    finalized_supplier_id = s_id
                    finalized_supplier_name = s_name
                    finalized_quote = supplier_quote
                    break
                else:
                    UI.log(f"Skipping {s_name} and moving to next ranked supplier...")
                    continue
            else:
                UI.warning(f"POLICY MISMATCH IDENTIFIED FOR {failed_name}!")
                print(f"     Reasoning: {failed_analysis['conflict_reasoning']}")
                print(f"     Flagged Discrepancies: {failed_analysis['flagged_fields']}")
                
                print(f"\n📋 {UI.BOLD}OPTIONS FOR {failed_name.upper()}:{UI.ENDC}")
                print("  [1] OK with this to proceed anyway (Waive requirements)")
                print("  [2] Make changes in the supplier's policy (Negotiate)")
                print("  [3] Change the supplier (Skip to next rank)")
                
                choice = input("  Enter selected execution code [1-3]: ").strip()
                if choice == "1":
                    UI.success(f"Administrative bypass logged. Proceeding with {s_name}.")
                    finalized_supplier_id = s_id
                    finalized_supplier_name = s_name
                    finalized_quote = supplier_quote
                    break
                elif choice == "2":
                    changes_needed = input("\n✍️ Enter the changes needed in their policy: ").strip()
                    
                    neg_prompt = f"Compose a polite, highly concise business message to {failed_name} requesting the following specific adjustments to their policies: '{changes_needed}'. Also mention we cannot proceed unless these are met."
                    counter_offer = self.call_groq(neg_prompt)
                    
                    s_email = self.get_supplier_email(failed_id)
                    subject = f"Procurement Compliance Terms Alignment Validation ({failed_id})"
                    UI.print_email("OUTBOUND TO", failed_name, subject, counter_offer)
                    self.email_helper.send_email(s_email, subject, counter_offer)
                    
                    UI.step(f"Waiting for Real Response from {failed_name}")
                    vendor_reply = self.email_helper.wait_for_reply(s_email, [failed_id], timeout_seconds=180)
                    
                    if not vendor_reply:
                        UI.warning(f"No response from {failed_name}. Skipping to next rank.")
                        continue
                    else:
                        vendor_reply_text = vendor_reply.get("body", "")
                        UI.print_email("INBOUND FROM", failed_name, vendor_reply.get("subject", "RE:"), vendor_reply_text)
                        
                        print(f"\n📋 {UI.BOLD}Did they agree?{UI.ENDC}")
                        print("  [1] Yes, Finalize with them")
                        print("  [2] No, Reject and move to next rank")
                        sub_choice = input("  Enter choice [1-2]: ").strip()
                        if sub_choice == "1":
                            finalized_supplier_id = s_id
                            finalized_supplier_name = s_name
                            finalized_quote = supplier_quote
                            break
                        else:
                            UI.log(f"Rejecting {s_name} after negotiation and moving to next ranked supplier...")
                            continue
                else:
                    UI.log(f"Skipping {s_name} and moving to next ranked supplier...")
                    continue
                    
        if finalized_supplier_id:
            UI.section("Finalizing Deals and Dispatching Notices")
            
            # Send Deal Acceptance
            if finalized_quote.get("is_combination"):
                for comp in finalized_quote["component_quotes"]:
                    self.send_deal_acceptance(comp["supplier_id"], comp["supplier_name"])
            else:
                self.send_deal_acceptance(finalized_supplier_id, finalized_supplier_name)
                
            # Send Rejection to others
            for rank_item in ranked_suppliers:
                if rank_item["supplier_id"] != finalized_supplier_id:
                    self.send_rejection_notice(rank_item["supplier_id"], rank_item["supplier_name"])
                    
            UI.success("All supplier communication finalized.")
            return True
        else:
            UI.warning("Exhausted all ranked suppliers. No deal finalized.")
            return False

    def send_deal_acceptance(self, s_id: str, name: str):
        prompt = f"Write an automated brief purchase validation confirmation email to {name} declaring contract forms accepted and instructing logistics departure runs to begin."
        body = self.call_groq(prompt)
        s_email = self.get_supplier_email(s_id)
        subject = f"Contract Accepted - Begin Logistics ({s_id})"
        UI.print_email("OUTBOUND TO", name, subject, body)
        self.email_helper.send_email(s_email, subject, body)

    def send_rejection_notice(self, s_id: str, s_name: str):
        reject_prompt = f"Draft a short, polite, and professional procurement cancellation note to {s_name} stating that we have decided to go with another vendor for this order, but we appreciate their quote."
        rejection_msg = self.call_groq(reject_prompt)
        s_email = self.get_supplier_email(s_id)
        subject = f"Update on Request for Quotation ({s_id})"
        UI.print_email("OUTBOUND TO", s_name, subject, rejection_msg)
        self.email_helper.send_email(s_email, subject, rejection_msg)

