import os
import json
import pymongo
from typing import List, Optional, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from services.email_utils import EmailHelper

load_dotenv()

# Initialize the Groq Client
if not os.getenv("GROQ_API_KEY"):
    raise ValueError("Missing GROQ_API_KEY in your environment or .env file.")

client = Groq()
MODEL_ID = 'llama-3.3-70b-versatile'

# ---------------------------------------------------------------------
# TERMINAL VISUAL FORMATTING HELPERS
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
        print(f"\n{UI.BOLD}{UI.BLUE}-> {title}{UI.ENDC}", flush=True)
        print(f"{UI.BLUE}{'-'*50}{UI.ENDC}", flush=True)

    @staticmethod
    def log(msg: str):
        print(f"  [*] [System]: {msg}", flush=True)

    @staticmethod
    def warning(msg: str):
        print(f"  [WARN] {UI.WARNING}{msg}{UI.ENDC}")

    @staticmethod
    def success(msg: str):
        print(f"  [OK] {UI.GREEN}{msg}{UI.ENDC}")

    @staticmethod
    def print_email(direction: str, name: str, subject: str, body: str):
        color = UI.WARNING if direction == "OUTBOUND" else UI.BLUE
        print(f"\n  [EMAIL] {UI.BOLD}{direction} EMAIL - {name}{UI.ENDC}")
        print(f"  |- {UI.BOLD}Subject:{UI.ENDC} {color}{subject}{UI.ENDC}")
        print(f"  |- {UI.BOLD}Email Content:{UI.ENDC}\n  \"\"\"\n  {body.strip()}\n  \"\"\"")

# ---------------------------------------------------------------------
# PYDANTIC STRUCTURES FOR STABLE OUTPUT PACKAGES
# ---------------------------------------------------------------------
class RankedSupplier(BaseModel):
    rank: int
    supplier_id: str
    supplier_name: str
    total_quoted_amount: float
    delivery_date: str
    justification: str

class CategoryEvaluationResult(BaseModel):
    category: str
    ranked_suppliers: List[RankedSupplier]
    selected_winner_id: str

# ---------------------------------------------------------------------
# LOCAL DATABASE CONFIGURATION
# ---------------------------------------------------------------------
def get_supplier_collection():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    # Default to a specific DB for supplier info if needed, or stick to default
    client = pymongo.MongoClient(mongo_uri)
    db = client.supply_chain
    collection = db.suppliers

    if collection.count_documents({}) == 0:
        collection.insert_many([
            {"id": "SUP_COMP_01", "name": "Nexus Electronics", "email": "nexus@example.com", "category": "computer products", "on_time_rate": 0.97, "negative_feedback": False},
            {"id": "SUP_COMP_02", "name": "Stellar Components", "email": "stellar@example.com", "category": "computer products", "on_time_rate": 0.81, "negative_feedback": True},
            {"id": "SUP_COMP_03", "name": "Apex Tech Wholesale", "email": "apex@example.com", "category": "computer products", "on_time_rate": 0.92, "negative_feedback": False},
            {"id": "SUP_PHONE_01", "name": "Vertex Mobile Wholesale", "email": "vertex@example.com", "category": "phone products", "on_time_rate": 0.94, "negative_feedback": False},
            {"id": "SUP_PHONE_02", "name": "Horizon Cellular Supply", "email": "horizon@example.com", "category": "phone products", "on_time_rate": 0.88, "negative_feedback": False}
        ])
    return collection

# ---------------------------------------------------------------------
# AGENT CORE LOGIC
# ---------------------------------------------------------------------
class CompleteSuppliersManagerAgent:
    def __init__(self, collection=None):
        self.collection = collection if collection is not None else get_supplier_collection()
        self.policies_collection = self.collection.database.policies
        self.email_helper = EmailHelper()

    def call_groq(self, prompt: str, response_schema: Optional[type] = None) -> str:
        kwargs = {
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1024
        }
        if response_schema:
            import json
            schema_json = response_schema.model_json_schema()
            prompt += f"\n\nYou MUST return raw JSON adhering strictly to this schema: {json.dumps(schema_json)}"
            kwargs["response_format"] = {"type": "json_object"}
            kwargs["messages"] = [{"role": "user", "content": prompt}]
            
        try:
            chat_completion = client.chat.completions.create(**kwargs)
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq API Error: {e}")
            return "{}"

    def segment_items(self, agent1_output: dict) -> dict:
        categorized_needs = {}
        for item in agent1_output.get("products", []):
            cat = item.get("category", "unknown").lower()
            if cat == "electronics":
                cat = "computer products"
            elif cat == "home & kitchen":
                cat = "home and kitchen"
            
            if cat not in categorized_needs:
                categorized_needs[cat] = []
            categorized_needs[cat].append(item)
        return categorized_needs

    def process_outbound_for_category(self, category: str, items: List[dict], sender_details: dict) -> List[dict]:
        matching_suppliers = list(self.collection.find({"category": category}))
        if not matching_suppliers:
            return []
            
        items_string = "\n".join([f"- {i.get('name', 'Unknown')}: {i['quantity']} units" for i in items])
        contacted_suppliers = []
        
        for supplier in matching_suppliers:
            s_id = supplier["id"]
            s_name = supplier["name"]
            s_email = supplier["email"]
            
            signature = ""
            if sender_details:
                signature = f"\n\nPlease use the following details for the email signature:\nName: {sender_details.get('name')}\nTitle: {sender_details.get('title')}\nCompany: {sender_details.get('company')}\nAddress: {sender_details.get('address')}\nPhone: {sender_details.get('phone')}\nEmail: {sender_details.get('email')}"

            print(f"  {UI.BLUE}[*] Drafting RFQ via LLM for {s_name}... (this may take a few seconds){UI.ENDC}", flush=True)
            
            prompt = f"Draft a professional, clear RFQ email to wholesale vendor '{s_name}' asking for a price and shipping delivery date commitment on:\n{items_string}\nAlso explicitly request that they include their company's return and liability policy details in their response.{signature}"
            email_text = self.call_groq(prompt)
            subject = f"RFQ: Urgent Procurement Order Request ({s_id})"
            
            print(f"\n  [EMAIL] {UI.BOLD}OUTBOUND EMAIL - {s_name}{UI.ENDC}", flush=True)
            print(f"  |- {UI.BOLD}Subject:{UI.ENDC} {UI.WARNING}{subject}{UI.ENDC}", flush=True)
            print(f"  |- {UI.BOLD}Status:{UI.ENDC} Sending directly to {s_email} (content hidden)...", flush=True)
            
            self.email_helper.send_email(s_email, subject, email_text)
            contacted_suppliers.append({
                "id": s_id,
                "name": s_name,
                "email": s_email,
                "category": category,
                "requested_items": items
            })
        return contacted_suppliers

    def check_inbound_replies(self, contacted_suppliers: List[dict]) -> dict:
        contacted_emails = [s["email"] for s in contacted_suppliers]
        replies = self.email_helper.fetch_recent_replies(contacted_emails)
        return {e: replies[e] for e in contacted_emails if e in replies}

    def process_inbound_quotes(self, category: str, contacted_suppliers: List[dict], category_replies: dict) -> List[dict]:
        received_quotes = []
        for s in contacted_suppliers:
            s_id = s["id"]
            s_name = s["name"]
            s_email = s["email"]
            if s_email in category_replies:
                reply_email_text = category_replies[s_email]
                
                print(f"\n  [EMAIL] {UI.BOLD}INBOUND EMAIL - {s_name}{UI.ENDC}")
                print(f"  |- {UI.BOLD}Status:{UI.ENDC} Processing response via LLM (content hidden)...")
                
                extract_prompt = f"""
                Extract the total quoted amount (as a float) and the estimated delivery date (as a YYYY-MM-DD string) from this email reply.
                If you cannot find a date, use a reasonable date next week. If you cannot find an amount, use 0.0.
                Extract the exact items they are quoting as `quoted_items`.
                Extract the specific quantity they quoted for each item in `quoted_quantities` (e.g. {{"Mouse": 30}}).
                Extract the cost for each item as a dictionary in `itemized_costs` (e.g. {{"Mouse": 15.00}}).
                Extract any discounts mentioned as a string in `optional_discounts`.
                Finally, extract their corporate policy details:
                - `return_window_days` (int)
                - `advance_payment_percentage` (float, e.g., 0.50 for 50%)
                - `damaged_goods_liability` (string, e.g., 'seller' or 'buyer')
                
                Email Text:
                {reply_email_text}
                """
                class QuoteExtraction(BaseModel):
                    amount: float
                    date: str
                    quoted_items: List[str]
                    quoted_quantities: Dict[str, int]
                    itemized_costs: Dict[str, float]
                    optional_discounts: str
                    return_window_days: int
                    advance_payment_percentage: float
                    damaged_goods_liability: str
                    
                extraction_raw = self.call_groq(extract_prompt, response_schema=QuoteExtraction)
                try:
                    extraction = json.loads(extraction_raw)
                    
                    policy_doc = {
                        "supplier_id": s_id,
                        "supplier_name": s_name,
                        "return_window_days": extraction.get("return_window_days", 30),
                        "advance_payment_percentage": extraction.get("advance_payment_percentage", 0.0),
                        "damaged_goods_liability": extraction.get("damaged_goods_liability", "unknown"),
                        "optional_discounts": extraction.get("optional_discounts", "None")
                    }
                    self.policies_collection.update_one(
                        {"supplier_id": s_id},
                        {"$set": policy_doc},
                        upsert=True
                    )
                    
                    received_quotes.append({
                        "supplier_id": s_id,
                        "supplier_name": s_name,
                        "supplier_email": s_email,
                        "category": category,
                        "quoted_amount": extraction.get("amount", 0.0),
                        "delivery_date": extraction.get("date", "Unknown"),
                        "quoted_items": extraction.get("quoted_items", []),
                        "quoted_quantities": extraction.get("quoted_quantities", {}),
                        "itemized_costs": extraction.get("itemized_costs", {}),
                        "optional_discounts": extraction.get("optional_discounts", "None"),
                        "is_combination": False
                    })
                except Exception as e:
                    print(f"Failed to parse extraction for {s_name}: {e}")
            else:
                UI.warning(f"No response received from {s_name} ({s_id}). Skipping.")

        # Check for full fulfillment vs partial
        req_item_map = {str(i.get("name", "Unknown")).lower(): i.get("quantity", 0) for i in contacted_suppliers[0].get("requested_items", [])}
        
        full_quotes = []
        partial_quotes = []
        for q in received_quotes:
            is_full = True
            quoted_qtys = q.get("quoted_quantities", {})
            for r_name, r_qty in req_item_map.items():
                # Check case insensitive matching
                matched_qty = 0
                for q_name, q_qty in quoted_qtys.items():
                    if str(q_name).lower() == r_name or r_name in str(q_name).lower():
                        matched_qty += q_qty
                if matched_qty < r_qty:
                    is_full = False
                    break
            
            if is_full:
                full_quotes.append(q)
            else:
                partial_quotes.append(q)

        # Combination Algorithm
        if not full_quotes and len(partial_quotes) > 1:
            print(f"  {UI.WARNING}No single supplier could fulfill the entire order. Calculating combinations...{UI.ENDC}")
            remaining_needs = req_item_map.copy()
            selected_quotes = []
            
            # Sort quotes by how many total units they can provide
            def score_quote(q):
                score = 0
                for q_name, q_qty in q.get("quoted_quantities", {}).items():
                    for r_name in remaining_needs:
                        if str(q_name).lower() == r_name or r_name in str(q_name).lower():
                            score += q_qty
                return score
                
            sorted_partials = sorted(partial_quotes, key=score_quote, reverse=True)
            
            for pq in sorted_partials:
                useful = False
                taken_items = {}
                for q_name, q_qty in pq.get("quoted_quantities", {}).items():
                    for r_name in list(remaining_needs.keys()):
                        if (str(q_name).lower() == r_name or r_name in str(q_name).lower()) and remaining_needs[r_name] > 0:
                            useful = True
                            taken = min(q_qty, remaining_needs[r_name])
                            remaining_needs[r_name] -= taken
                            taken_items[str(q_name)] = taken
                            if remaining_needs[r_name] == 0:
                                del remaining_needs[r_name]
                if useful:
                    pq["confirmed_taken_items"] = taken_items
                    selected_quotes.append(pq)
                if not remaining_needs:
                    break
                    
            if not remaining_needs:
                combo_names = " & ".join([q["supplier_name"] for q in selected_quotes])
                print(f"  {UI.BLUE}[*] Found a valid combination: {combo_names}{UI.ENDC}")
                print(f"  [*] Grouping into a combo quote and passing to Agent 3 for compliance and final acceptance...")
                
                combo_quote = {
                    "supplier_id": "COMBO_" + "_".join([q["supplier_id"] for q in selected_quotes]),
                    "supplier_name": combo_names,
                    "is_combination": True,
                    "component_quotes": selected_quotes,
                    "quoted_amount": sum(q["quoted_amount"] for q in selected_quotes),
                    "delivery_date": max((q["delivery_date"] for q in selected_quotes), default="Unknown"),
                    "category": category,
                    "quoted_items": sum([q.get("quoted_items", []) for q in selected_quotes], [])
                }
                received_quotes.append(combo_quote)
            else:
                print(f"  {UI.FAIL}Could not find a combination to fulfill the order completely.{UI.ENDC}")

        return received_quotes

    def rank_quotes_for_category(self, category: str, quotes: List[dict]) -> dict:
        UI.step("Step 3B: Injecting Quality Metrics From Local Database")
        
        for quote in quotes:
            if quote.get("is_combination", False):
                # For combinations, we average the metrics
                scores = []
                flags = []
                for comp in quote["component_quotes"]:
                    db_meta = self.collection.find_one({"id": comp["supplier_id"]})
                    if db_meta:
                        scores.append(db_meta.get("on_time_rate", 0.0))
                        flags.append(db_meta.get("negative_feedback", False))
                quote["historical_on_time_delivery"] = sum(scores)/len(scores) if scores else 0.0
                quote["has_negative_reputation_flags"] = any(flags)
            else:
                db_meta = self.collection.find_one({"id": quote["supplier_id"]})
                if db_meta:
                    quote["historical_on_time_delivery"] = db_meta.get("on_time_rate", 0.0)
                    quote["has_negative_reputation_flags"] = db_meta.get("negative_feedback", False)

        UI.step("Step 3C: Processing Comparative AI Ranking Algorithm")
        print(f"\n  Generating ranked stack list order for: {UI.BOLD}{category.upper()}{UI.ENDC}")
        
        comparison_prompt = f"""
        Analyze, evaluate, and rank ALL provided supplier proposals for the category '{category}'. 
        Sort them from best to worst (Rank 1 being the absolute best option).
        
        Decision Rules:
        - Prioritize single suppliers who can provide ALL requested items over combinations (is_combination=True).
        - A combination of suppliers should ALWAYS be ranked below a single supplier who can fulfill the entire order, unless the single supplier has negative reputation flags.
        - Prioritize competitive balance between cost and speed.
        - Penalize suppliers with low historical_on_time_delivery rates (e.g., under 0.90).
        - Strictly downgrade any supplier where has_negative_reputation_flags is True.
        
        Data Set:
        {json.dumps(quotes, indent=2)}
        """
        
        ranking_raw = self.call_groq(comparison_prompt, response_schema=CategoryEvaluationResult)
        try:
            ranking_clean = ranking_raw.strip()
            if ranking_clean.startswith("```json"):
                ranking_clean = ranking_clean[7:-3].strip()
            elif ranking_clean.startswith("```"):
                ranking_clean = ranking_clean[3:-3].strip()
                
            evaluation_data = json.loads(ranking_clean)
            winner_id = evaluation_data["ranked_suppliers"][0]["supplier_id"]
            winner_name = evaluation_data["ranked_suppliers"][0]["supplier_name"]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"  {UI.FAIL}Error parsing ranking output: {e}{UI.ENDC}", flush=True)
            winner_id = quotes[0]["supplier_id"] if quotes else "unknown"
            winner_name = quotes[0]["supplier_name"] if quotes else "unknown"
            evaluation_data = {"ranked_suppliers": [{"supplier_id": winner_id, "supplier_name": winner_name, "rank": 1}]}
        
        print(f"  [1ST] Ranked Best Option: {UI.GREEN}{UI.BOLD}{winner_name} ({winner_id}){UI.ENDC}")
        
        UI.step(f"Step 4: Pulling Terms & Compliance Policies From Best Vendor ({winner_name})")
        
        winner_quote = next((q for q in quotes if q["supplier_id"] == winner_id), None)
        active_policies = []
        
        if winner_quote and winner_quote.get("is_combination"):
            for comp in winner_quote["component_quotes"]:
                policy_doc = self.policies_collection.find_one({"supplier_id": comp["supplier_id"]})
                if policy_doc:
                    active_policies.append({
                        "supplier_id": comp["supplier_id"],
                        "supplier_name": comp["supplier_name"],
                        "return_window_days": policy_doc.get("return_window_days", 30),
                        "advance_payment_percentage": policy_doc.get("advance_payment_percentage", 0.0),
                        "damaged_goods_liability": policy_doc.get("damaged_goods_liability", "unknown"),
                        "optional_discounts": policy_doc.get("optional_discounts", "None")
                    })
        else:
            policy_doc = self.policies_collection.find_one({"supplier_id": winner_id})
            if policy_doc:
                active_policies.append({
                    "supplier_id": winner_id,
                    "supplier_name": winner_name,
                    "return_window_days": policy_doc.get("return_window_days", 30),
                    "advance_payment_percentage": policy_doc.get("advance_payment_percentage", 0.0),
                    "damaged_goods_liability": policy_doc.get("damaged_goods_liability", "unknown"),
                    "optional_discounts": policy_doc.get("optional_discounts", "None")
                })
        
        report_block = {
            "category_group": category,
            "ranked_supplier_list": evaluation_data["ranked_suppliers"],
            "best_supplier_choice": {
                "supplier_id": winner_id,
                "supplier_name": winner_name,
                "is_combination": winner_quote.get("is_combination", False) if winner_quote else False,
                "active_compliance_policies": active_policies
            }
        }
        return report_block
