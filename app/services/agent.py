import json
from datetime import datetime, timezone
from beanie.odm.fields import PydanticObjectId
from huggingface_hub import InferenceClient
from app.core.config import settings
from app.models.chat import ChatMessage
from app.models.bill import Bill
from app.models.merchant import Merchant
from app.services.whatsapp import send_whatsapp_text
from app.services.evolution import send_evolution_text
import structlog

logger = structlog.get_logger()

# We use the official Llama-3.1 model which supports function calling natively
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
            total = 0.0
            for b in bills:
                if b.corrected_data:
                    try:
                        val = b.corrected_data.get("total", 0)
                        total += float(val) if val is not None else 0.0
                    except (ValueError, TypeError):
                        pass

            return json.dumps({
                "month": month, 
                "year": year, 
                "total_spent": round(total, 2), 
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
            
    except Exception as e:
        logger.error("Tool execution failed", error=str(e))
        return json.dumps({"error": str(e)})
    
    return json.dumps({"error": "Unknown tool"})

SYSTEM_PROMPT = """You are a helpful, human-like customer service representative for Vyaparamitra.
Your job is to assist the merchant with their queries about their uploaded bills, expenses, and reports.
Always be polite, professional, and clear.
If a user asks for a monthly report or recent bills, USE the available tools to fetch their actual data from the database before answering.
Once you receive the tool data, summarize it clearly for the user in a natural conversational tone."""

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
        
        Respond with JSON: {"need_tool": true/false, "tool_name": "tool_name" or null, "args": {...}}"""
        
        detection_response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct",
            messages=[{"role": "user", "content": tool_detection_prompt}],
            max_tokens=100,
            temperature=0.1
        )
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct",
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
                model="meta-llama/Llama-3.1-8B-Instruct",
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
