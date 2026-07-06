import streamlit as st
import json
import time

# Agent Imports
from agents.inventory_management.agent import inventory_graph
from agents.supplier_sourcing.agent import CompleteSuppliersManagerAgent
from agents.compliance_fulfillment.agent import ComplianceAndFulfillmentAgent

st.set_page_config(page_title="Supply Chain Multi-Agent System", layout="wide")

# Custom UI styling: Dark Purple Gradient + Glassmorphism for boxes
st.markdown("""
<style>
/* Full app background gradient */
.stApp {
    background: linear-gradient(135deg, #1e0b2b 0%, #4a195b 100%);
    background-attachment: fixed;
}

/* Glassmorphism blur effect for explicitly marked boxes */
[data-testid="stVerticalBlockBorderWrapper"]:has(.glass-card):not(:has([data-testid="stVerticalBlockBorderWrapper"])) {
    background: rgba(0, 0, 0, 0.45) !important;
    backdrop-filter: blur(18px) !important;
    -webkit-backdrop-filter: blur(18px) !important;
    border-radius: 15px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
}

/* Make headers pop a bit more to contrast against the gradient */
h1, h2, h3 {
    text-shadow: 1px 1px 3px rgba(0,0,0,0.6);
}
</style>
""", unsafe_allow_html=True)

# State Initialization
if "stage" not in st.session_state:
    st.session_state.stage = "config"
if "agent1_payload" not in st.session_state:
    st.session_state.agent1_payload = None
if "categorized_needs" not in st.session_state:
    st.session_state.categorized_needs = {}
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "contacted_suppliers" not in st.session_state:
    st.session_state.contacted_suppliers = []
if "received_quotes" not in st.session_state:
    st.session_state.received_quotes = []
if "report_block" not in st.session_state:
    st.session_state.report_block = None
if "category_statuses" not in st.session_state:
    st.session_state.category_statuses = {}
if "compliance_eval_index" not in st.session_state:
    st.session_state.compliance_eval_index = 0
if "finalized_supplier_id" not in st.session_state:
    st.session_state.finalized_supplier_id = None
if "finalized_supplier_name" not in st.session_state:
    st.session_state.finalized_supplier_name = None
if "finalized_quote" not in st.session_state:
    st.session_state.finalized_quote = None
if "conflict_data" not in st.session_state:
    st.session_state.conflict_data = None

st.title("Supply Chain Multi-Agent System")

# -----------------------------------------------------------------------------
# STAGE 0: CONFIGURATION
# -----------------------------------------------------------------------------
if st.session_state.stage == "config":
    st.header("Configuration")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True, height=580):
            st.markdown("<div class='glass-card'></div>", unsafe_allow_html=True)
            st.subheader("Sender Details")
            company = st.text_input("Company Name", "My Corp")
            address = st.text_input("Company Address", "123 Business Rd")
            name = st.text_input("Your Name", "John Doe")
            title = st.text_input("Your Title", "Procurement Manager")
            phone = st.text_input("Phone Number", "555-0199")
            email = st.text_input("Email Address", "john@example.com")

    with col2:
        with st.container(border=True, height=580):
            st.markdown("<div class='glass-card'></div>", unsafe_allow_html=True)
            st.subheader("Target Policies")
            fee = st.number_input("Max Advance Payment Percentage", value=0.50, min_value=0.0, max_value=1.0)
            days = st.number_input("Min Return Window Days", value=30)
            parties = st.text_input("Acceptable Liability Parties", "seller, shared")

    if st.button("Run Inventory Agent (Agent 1)", type="primary"):
        st.session_state.sender_details = {
            "company": company, "address": address, "name": name, 
            "title": title, "phone": phone, "email": email
        }
        st.session_state.user_policy = {
            "max_advance_payment_percentage": fee,
            "min_return_window_days": days,
            "acceptable_liability_parties": [p.strip().lower() for p in parties.split(",")]
        }
        st.session_state.stage = "agent1_run"
        st.rerun()

# -----------------------------------------------------------------------------
# STAGE 1 & 2: AGENT 1 EXECUTION & CATEGORY MENU
# -----------------------------------------------------------------------------
elif st.session_state.stage in ["agent1_run", "category_menu"]:
    st.header("Inventory Management (Agent 1)")

    if st.session_state.agent1_payload is None:
        with st.spinner("Analyzing Database and Running Agent 1..."):
            final_state = inventory_graph.invoke({
                "current_inventory": [], "historical_sales": [], "final_output": None
            })
            output = final_state.get("final_output")
            payload = output.model_dump() if hasattr(output, "model_dump") else output
            st.session_state.agent1_payload = payload

            if payload and "replenishments" in payload and payload["replenishments"]:
                payload_copy = payload.copy()
                payload_copy["products"] = payload_copy.pop("replenishments")
                agent2 = CompleteSuppliersManagerAgent()
                st.session_state.categorized_needs = agent2.segment_items(payload_copy)
                st.session_state.category_statuses = {cat: "Pending" for cat in st.session_state.categorized_needs.keys()}

    payload = st.session_state.agent1_payload

    if not payload or ("replenishments" not in payload and "products" not in payload):
        st.success("No products need restocking. Pipeline complete.")
    else:
        st.success("Analysis Complete!")
        if "replenishments" in payload:
            st.table(payload["replenishments"])
        elif "products" in payload:
            st.table(payload["products"])

        st.divider()
        st.header("Category Menu")

        if not st.session_state.category_statuses:
            st.info("No categories to process.")
        else:
            all_done = all(status != "Pending" for status in st.session_state.category_statuses.values())
            if all_done:
                st.success("All categories processed!")
                if st.button("Start Over"):
                    st.session_state.clear()
                    st.rerun()

            # Display as cards in a grid
            cols = st.columns(3)
            for i, (cat, status) in enumerate(st.session_state.category_statuses.items()):
                with cols[i % 3]:
                    try:
                        # Fixed height ensures alignment across cards
                        card = st.container(border=True, height=270)
                    except TypeError:
                        card = st.container()

                    with card:
                        st.markdown("<div class='glass-card'></div>", unsafe_allow_html=True)
                        # Fixed height title wrapper so varying title length won't break layout
                        st.markdown(f"<div style='height: 70px; overflow: hidden;'><h3>{cat.upper()}</h3></div>", unsafe_allow_html=True)
                        if status == "Pending":
                            items_count = len(st.session_state.categorized_needs.get(cat, []))
                            st.write(f"📦 **{items_count} items**")
                            st.info(f"Status: {status}")
                            if st.button("Process", key=f"btn_{cat}", use_container_width=True):
                                st.session_state.selected_category = cat
                                st.session_state.stage = "sourcing_outbound"
                                st.rerun()
                        else:
                            st.write("📦 **Processed**")
                            if "Finalized" in status:
                                st.success(f"Status: {status}")
                            elif "No Suppliers" in status or "No Deal" in status:
                                st.error(f"Status: {status}")
                            else:
                                st.warning(f"Status: {status}")

                            st.button("Process", key=f"btn_{cat}", disabled=True, use_container_width=True)

# -----------------------------------------------------------------------------
# STAGE 3: SOURCING (AGENT 2)
# -----------------------------------------------------------------------------
elif st.session_state.stage == "sourcing_outbound":
    st.header(f"Agent 2: Sourcing {st.session_state.selected_category.upper()}")

    if not st.session_state.contacted_suppliers:
        with st.spinner("Drafting and sending RFQ Emails via LLM..."):
            agent2 = CompleteSuppliersManagerAgent()
            items_to_process = st.session_state.categorized_needs[st.session_state.selected_category]
            contacted = agent2.process_outbound_for_category(
                st.session_state.selected_category, 
                items_to_process, 
                st.session_state.sender_details
            )
            st.session_state.contacted_suppliers = contacted

        if not contacted:
            st.error("No suppliers found for this category.")
            st.session_state.category_statuses[st.session_state.selected_category] = "No Suppliers Found"
            del st.session_state.categorized_needs[st.session_state.selected_category]
            if st.button("Back to Menu"):
                st.session_state.stage = "category_menu"
                st.rerun()
        else:
            st.rerun()
    else:
        st.success(f"Sent out RFQs to {len(st.session_state.contacted_suppliers)} suppliers.")
        st.subheader("Check Inbound Replies")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Fetch Emails Now"):
                with st.spinner("Fetching emails..."):
                    agent2 = CompleteSuppliersManagerAgent()
                    category_replies = agent2.check_inbound_replies(st.session_state.contacted_suppliers)

                    if category_replies:
                        st.session_state.received_quotes = agent2.process_inbound_quotes(
                            st.session_state.selected_category, 
                            st.session_state.contacted_suppliers, 
                            category_replies
                        )
                        st.success(f"Processed {len(st.session_state.received_quotes)} quote(s)!")
                    else:
                        st.warning("No replies received yet.")

        with col2:
            if st.session_state.received_quotes:
                if st.button("Accept Quotes & Proceed to Agent 3", type="primary"):
                    with st.spinner("Ranking Quotes..."):
                        agent2 = CompleteSuppliersManagerAgent()
                        st.session_state.report_block = agent2.rank_quotes_for_category(
                            st.session_state.selected_category, 
                            st.session_state.received_quotes
                        )
                        st.session_state.compliance_eval_index = 0
                        st.session_state.stage = "compliance_eval"
                        st.rerun()

        if st.session_state.received_quotes:
            st.write("### Received Quotes Summary")
            for q in st.session_state.received_quotes:
                st.write(f"- **{q.get('supplier_name')}**: ${q.get('quoted_amount')} for {len(q.get('quoted_items', []))} items")

# -----------------------------------------------------------------------------
# STAGE 4: COMPLIANCE & NEGOTIATION (AGENT 3)
# -----------------------------------------------------------------------------
elif st.session_state.stage == "compliance_eval":
    st.header(f"Agent 3: Compliance & Negotiation")

    agent3 = ComplianceAndFulfillmentAgent(st.session_state.user_policy, sender_details=st.session_state.sender_details)
    ranked_suppliers = st.session_state.report_block["ranked_supplier_list"]
    quotes = st.session_state.received_quotes

    if st.session_state.compliance_eval_index >= len(ranked_suppliers):
        st.error("Exhausted all ranked suppliers. No deal finalized.")
        st.session_state.category_statuses[st.session_state.selected_category] = "No Deal Reached"
        del st.session_state.categorized_needs[st.session_state.selected_category]
        if st.button("Return to Category Menu"):
            st.session_state.contacted_suppliers = []
            st.session_state.received_quotes = []
            st.session_state.stage = "category_menu"
            st.rerun()
    else:
        rank_item = ranked_suppliers[st.session_state.compliance_eval_index]
        s_id = rank_item["supplier_id"]
        s_name = rank_item["supplier_name"]

        st.subheader(f"Evaluating Rank {rank_item['rank']}: {s_name}")
        supplier_quote = next((q for q in quotes if q["supplier_id"] == s_id), None)

        # Evaluate Supplier ONLY ONCE per rank to avoid hitting LLM unnecessarily on reruns
        if st.session_state.conflict_data is None:
            with st.spinner("Evaluating compliance against target policies..."):
                analysis, comp_name, comp_id = agent3.evaluate_supplier(s_id, s_name, supplier_quote)
                st.session_state.conflict_data = {
                    "has_conflict": analysis is not None,
                    "analysis": analysis,
                    "comp_name": comp_name,
                    "comp_id": comp_id
                }
                st.rerun()

        conflict_data = st.session_state.conflict_data

        if not conflict_data["has_conflict"]:
            st.success("✅ No contract term anomalies flagged!")
            if st.button("OK to continue and Finalize"):
                st.session_state.finalized_supplier_id = s_id
                st.session_state.finalized_supplier_name = s_name
                st.session_state.finalized_quote = supplier_quote
                st.session_state.stage = "deal_acceptance"
                st.rerun()

            if st.button("Skip to next rank"):
                st.session_state.compliance_eval_index += 1
                st.session_state.conflict_data = None
                st.rerun()
        else:
            st.warning(f"⚠️ POLICY MISMATCH IDENTIFIED FOR {conflict_data['comp_name']}!")
            st.write(f"**Reasoning:** {conflict_data['analysis']['conflict_reasoning']}")
            st.write(f"**Flagged Discrepancies:** {conflict_data['analysis']['flagged_fields']}")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Waive requirements (Proceed)"):
                    st.session_state.finalized_supplier_id = s_id
                    st.session_state.finalized_supplier_name = s_name
                    st.session_state.finalized_quote = supplier_quote
                    st.session_state.stage = "deal_acceptance"
                    st.rerun()
            with col2:
                if st.button("Change supplier (Skip)"):
                    st.session_state.compliance_eval_index += 1
                    st.session_state.conflict_data = None
                    st.rerun()
            with col3:
                if st.button("Negotiate terms"):
                    st.session_state.stage = "negotiate_terms"
                    st.rerun()

# -----------------------------------------------------------------------------
# STAGE 4.5: NEGOTIATE TERMS
# -----------------------------------------------------------------------------
elif st.session_state.stage == "negotiate_terms":
    st.header("Negotiate Terms")
    changes = st.text_area("Enter the changes needed in their policy:")

    if st.button("Send Counter-Offer", type="primary"):
        agent3 = ComplianceAndFulfillmentAgent(st.session_state.user_policy, sender_details=st.session_state.sender_details)
        conflict_data = st.session_state.conflict_data

        with st.spinner("Drafting and sending counter-offer..."):
            s_email = agent3.send_counter_offer(conflict_data["comp_id"], conflict_data["comp_name"], changes)
            st.session_state.neg_email = s_email
            st.session_state.stage = "wait_negotiate"
            st.rerun()

    if st.button("Cancel"):
        st.session_state.stage = "compliance_eval"
        st.rerun()

elif st.session_state.stage == "wait_negotiate":
    st.header("Waiting for Reply")
    st.info("Counter offer sent. Awaiting vendor reply.")

    if st.button("Check Inbox Now"):
        agent3 = ComplianceAndFulfillmentAgent(st.session_state.user_policy, sender_details=st.session_state.sender_details)
        with st.spinner("Checking inbox for 3 minutes..."):
            vendor_reply = agent3.wait_for_counter_reply(st.session_state.neg_email, st.session_state.conflict_data["comp_id"])
            if vendor_reply:
                st.success("Reply Received!")
                st.write(vendor_reply.get("body", ""))
                st.session_state.vendor_reply_text = vendor_reply.get("body", "")
                st.session_state.stage = "decide_negotiate"
                st.rerun()
            else:
                st.error("No reply yet.")

elif st.session_state.stage == "decide_negotiate":
    st.header("Vendor Reply Received")
    st.write(st.session_state.vendor_reply_text)

    if st.button("Accept New Terms & Finalize"):
        rank_item = st.session_state.report_block["ranked_supplier_list"][st.session_state.compliance_eval_index]
        st.session_state.finalized_supplier_id = rank_item["supplier_id"]
        st.session_state.finalized_supplier_name = rank_item["supplier_name"]
        st.session_state.finalized_quote = next((q for q in st.session_state.received_quotes if q["supplier_id"] == rank_item["supplier_id"]), None)
        st.session_state.stage = "deal_acceptance"
        st.rerun()

    if st.button("Reject & Move to Next Rank"):
        st.session_state.compliance_eval_index += 1
        st.session_state.conflict_data = None
        st.session_state.stage = "compliance_eval"
        st.rerun()

# -----------------------------------------------------------------------------
# STAGE 5: DEAL FINALIZATION
# -----------------------------------------------------------------------------
elif st.session_state.stage == "deal_acceptance":
    st.header("Deal Acceptance & Logistics")
    st.write(f"Finalizing deal with **{st.session_state.finalized_supplier_name}**.")

    with st.form("po_form"):
        st.subheader("Purchase Order Details")
        po_num = st.text_input("Purchase Order Number", "PO-2023-1001")
        po_date = st.text_input("Date of Purchase", "2023-10-31")
        ship_addr = st.text_area("Shipping Address", "123 Main St, Warehouse B")

        submitted = st.form_submit_button("Send Deal Acceptance & Rejection Notices")

        if submitted:
            agent3 = ComplianceAndFulfillmentAgent(st.session_state.user_policy, sender_details=st.session_state.sender_details)

            po_details = {
                "po_number": po_num,
                "po_date": po_date,
                "shipping_address": ship_addr,
                "quote": st.session_state.finalized_quote
            }

            with st.spinner("Dispatching Emails..."):
                agent3.finalize_supplier(
                    st.session_state.finalized_supplier_id, 
                    st.session_state.finalized_supplier_name, 
                    st.session_state.finalized_quote, 
                    po_details, 
                    st.session_state.report_block["ranked_supplier_list"]
                )

            st.success("All supplier communication finalized successfully!")
            st.session_state.category_statuses[st.session_state.selected_category] = "Deal Finalized ✅"
            del st.session_state.categorized_needs[st.session_state.selected_category]

            # Reset state for next category
            st.session_state.contacted_suppliers = []
            st.session_state.received_quotes = []
            st.session_state.report_block = None
            st.session_state.conflict_data = None
            st.session_state.compliance_eval_index = 0

            st.session_state.stage = "category_menu"
            time.sleep(2)
            st.rerun()
