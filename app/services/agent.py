import json
from datetime import datetime, timezone
from beanie.odm.fields import PydanticObjectId
from huggingface_hub import InferenceClient
from app.core.config import settings
from app.models.chat import ChatMessage
from app.models.bill import Bill
from app.models.enums import BillStatus, BillCategory
from app.models.merchant import Merchant
from app.services.whatsapp import send_whatsapp_text
from app.services.evolution import send_evolution_text
import structlog

logger = structlog.get_logger()

# official Llama-3.1 model which supports function calling natively
client = InferenceClient(api_key=settings.HF_TOKEN)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_spending_summary",
            "description": "Get the total amount spent within a specific month and year. Useful for monthly reports.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "The month number (1-12)"},
                    "year": {"type": "integer", "description": "The 4-digit year (e.g. 2024)"}
                },
                "required": ["month", "year"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_bills",
            "description": "Fetch the details of the most recently processed bills/receipts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of bills to fetch (max 10)"}
                },
                "required": ["limit"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_pending_bill",
            "description": "Update the fields of the user's most recent pending bill with their corrections.",
            "parameters": {
                "type": "object",
                "properties": {
                    "corrections": {
                        "type": "object",
                        "description": "A dictionary of fields to update. Valid keys are: supplier, total, date, tax. Provide only the fields that need updating."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["PURCHASE", "SALES"],
                        "description": "Optional category of the bill."
                    }
                },
                "required": ["corrections"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "approve_pending_bill",
            "description": "Approve the user's most recent pending bill so it can be officially saved in the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["PURCHASE", "SALES"],
                        "description": "The category of the bill. MUST be provided."
                    }
                },
                "required": ["category"]
            }
        }
    }
]

async def execute_tool(tool_call, merchant_id: PydanticObjectId) -> str:
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    
    try:
        if name == "get_spending_summary":
            month = args["month"]
            year = args["year"]
            
            # Start and end date for MongoDB aggregation
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
            
            bills = await Bill.find(
                Bill.merchant_id == merchant_id,
                Bill.created_at >= start_date,
                Bill.created_at < end_date
            ).to_list()
            
            # Because corrected_data is stored as a native Dict in Mongo, we can parse it easily
            total_purchases = 0.0
            total_sales = 0.0
            for b in bills:
                if b.corrected_data:
                    try:
                        val = b.corrected_data.get("total", 0)
                        val = float(val) if val is not None else 0.0
                        if b.category == BillCategory.PURCHASE:
                            total_purchases += val
                        elif b.category == BillCategory.SALES:
                            total_sales += val
                    except (ValueError, TypeError):
                        pass

            net_profit = total_sales - total_purchases
            return json.dumps({
                "month": month, 
                "year": year, 
                "total_purchases": round(total_purchases, 2), 
                "total_sales": round(total_sales, 2),
                "net_profit": round(net_profit, 2),
                "total_bills_processed": len(bills)
            })
            
        elif name == "get_recent_bills":
            limit = min(args.get("limit", 5), 10)
            bills = await Bill.find(Bill.merchant_id == merchant_id).sort("-created_at").limit(limit).to_list()
            
            res = []
            for b in bills:
                if b.corrected_data:
                    res.append({
                        "date": b.created_at.strftime("%Y-%m-%d"),
                        "supplier": b.corrected_data.get("supplier", "Unknown"),
                        "total": b.corrected_data.get("total", 0)
                    })
            return json.dumps({"recent_bills": res})
            
        elif name == "update_pending_bill":
            corrections = args.get("corrections", {})
            category = args.get("category")
            bill = await Bill.find(
                Bill.merchant_id == merchant_id,
                Bill.status == BillStatus.REVIEW_PENDING
            ).sort("-created_at").first_or_none()
            
            if not bill:
                return json.dumps({"error": "No pending bill found to update."})
                
            if bill.corrected_data is None:
                bill.corrected_data = {}
                
            for k, v in corrections.items():
                bill.corrected_data[k] = v
                
            if category:
                bill.category = BillCategory(category)
                
            await bill.save()
            return json.dumps({
                "status": "success", 
                "message": "Bill updated successfully.", 
                "updated_data": bill.corrected_data,
                "category": bill.category.value
            })
            
        elif name == "approve_pending_bill":
            category = args.get("category")
            if not category:
                return json.dumps({"error": "Category (PURCHASE or SALES) is required to approve."})
                
            bill = await Bill.find(
                Bill.merchant_id == merchant_id,
                Bill.status == BillStatus.REVIEW_PENDING
            ).sort("-created_at").first_or_none()
            
            if not bill:
                return json.dumps({"error": "No pending bill found to approve."})
                
            bill.status = BillStatus.APPROVED
            bill.category = BillCategory(category)
            await bill.save()
            return json.dumps({"status": "success", "message": "Bill approved successfully.", "category": bill.category.value})
            
    except Exception as e:
        logger.error("Tool execution failed", error=str(e))
        return json.dumps({"error": str(e)})
    
    return json.dumps({"error": "Unknown tool"})

SYSTEM_PROMPT = """You are a strictly bound customer service representative for Vyaparamitra.
CRITICAL RULE 1: You MUST ALWAYS respond in colloquial Telugu language ONLY. (Use Telugu script).
CRITICAL RULE 2: You MUST ONLY talk about the merchant's uploaded bills, expenses, and reports. 
CRITICAL RULE 3: Do NOT engage in general conversation. If the user asks about anything unrelated to their bills or Vyaparamitra, politely decline to answer in Telugu.
Always be polite, professional, and clear.
If a user asks for a monthly report or recent bills, USE the available tools to fetch their actual data from the database before answering. For monthly reports, clearly state the total purchases, total sales, and net profit in colloquial Telugu.
If the user provides corrections for a recently uploaded bill, USE the `update_pending_bill` tool.
IMPORTANT: Before approving a bill, you MUST know whether it is a PURCHASE or SALES bill. If the user says 'Yes' ('అవును') but did not specify the category, ask them which category it is.
Once you know the category and the user confirms, USE the `approve_pending_bill` tool and provide the category.
Once you receive the tool data, summarize it clearly for the user in a natural colloquial Telugu conversational tone."""

async def respond_to_user_async(merchant_id: str, platform: str, phone_number: str, text_body: str):
    merchant_oid = PydanticObjectId(merchant_id)
    
    # Save user message
    user_msg = ChatMessage(merchant_id=merchant_oid, role="user", content=text_body)
    await user_msg.insert()
    
    # Fetch history
    history = await ChatMessage.find(ChatMessage.merchant_id == merchant_oid).sort("-created_at").limit(10).to_list()
    history.reverse() # Chronological order
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
        
    try:
        # FIRST: Check if user wants to use a tool (simple prompt-based detection)
        tool_detection_prompt = f"""Check if this query needs database tools:
        Query: {text_body}
        
        Tools available:
        - get_spending_summary: for monthly spending reports
        - get_recent_bills: for recent bill details
        - update_pending_bill: for updating an uploaded bill with user corrections
        - approve_pending_bill: for approving an uploaded bill. Requires knowing if it's PURCHASE or SALES.
        
        Respond with JSON: {{"need_tool": true/false, "tool_name": "tool_name" or null, "args": {{...}}}}"""
        
        detection_response = client.chat.completions.create(
            model="Qwen/Qwen2.5-7B-Instruct",
            messages=[{"role": "user", "content": tool_detection_prompt}],
            max_tokens=100,
            temperature=0.1
        )
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-7B-Instruct",
            messages=messages,
            max_tokens=300
        )
        
        choice = response.choices[0]
        
        # Check if the LLM wants to use a tool
        if choice.message.tool_calls:
            logger.info("LLM requested tool calls", tool_calls=len(choice.message.tool_calls))
            
            # Need to append the assistant's tool_calls message strictly as it gave it
            # The huggingface client returns an object, we convert it to dict for messages list
            messages.append({
                "role": "assistant",
                "content": choice.message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in choice.message.tool_calls
                ]
            })
            
            for tool_call in choice.message.tool_calls:
                tool_result = await execute_tool(tool_call, merchant_oid)
                # Append tool response
                messages.append({
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": tool_result
                })
                
            # Make the final call to get the synthesized response
            logger.info("Sending tool results back to LLM")
            final_response = client.chat.completions.create(
                model="Qwen/Qwen2.5-7B-Instruct",
                messages=messages,
                max_tokens=300
            )
            final_text = final_response.choices[0].message.content
        else:
            final_text = choice.message.content
            
        if final_text:
            logger.info("Generated final response", length=len(final_text))
            # Save assistant message
            ai_msg = ChatMessage(merchant_id=merchant_oid, role="assistant", content=final_text)
            await ai_msg.insert()
            
            # Send back to user
            if platform == "whatsapp":
                await send_whatsapp_text(phone_number, final_text)
            elif platform == "evolution":
                await send_evolution_text(phone_number, final_text)
                
    except Exception as e:
        logger.error("Agent failed", error=str(e), exc_info=True)
        err_msg = "Sorry, I am having trouble accessing your data right now. Please try again later."
        if platform == "whatsapp":
            await send_whatsapp_text(phone_number, err_msg)
        elif platform == "evolution":
            await send_evolution_text(phone_number, err_msg)
