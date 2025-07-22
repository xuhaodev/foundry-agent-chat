import chainlit as cl
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
import asyncio

# Initialize Azure AI client
project = AIProjectClient(
    credential=DefaultAzureCredential(),
    endpoint="https://xuhao-mahwkv9w-uaenorth.services.ai.azure.com/api/projects/xuhao-mahwkv9w-uaenorth-project"
)

# Get the agent
agent = project.agents.get_agent("asst_RXFtziX4eGfY8iLHdt2Qh6v1")

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    # Create a new thread for this chat session
    thread = project.agents.threads.create()
    
    # Store thread ID in user session
    cl.user_session.set("thread_id", thread.id)
    
    # Send welcome message
    await cl.Message(
        content=f"🤖 **Azure AI Assistant Ready!**\n\nI'm connected to your Azure AI agent and ready to help. Thread ID: `{thread.id}`\n\nFeel free to ask me anything!"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    try:
        # Get thread ID from user session
        thread_id = cl.user_session.get("thread_id")
        
        if not thread_id:
            await cl.Message(content="❌ **Error:** No active thread found. Please refresh the page.").send()
            return
        
        # Show typing indicator
        async with cl.Step(name="🤔 Thinking...") as step:
            # Create user message in the thread
            user_message = project.agents.messages.create(
                thread_id=thread_id,
                role="user",
                content=message.content
            )
            
            step.output = f"User message created: {message.content[:50]}..."
        
        # Show processing indicator
        async with cl.Step(name="🔄 Processing with Azure AI...") as step:
            # Create and process the run
            run = project.agents.runs.create_and_process(
                thread_id=thread_id,
                agent_id=agent.id
            )
            
            step.output = f"Run status: {run.status}"
        
        # Handle the response
        if run.status == "failed":
            error_msg = f"❌ **Run failed:** {run.last_error}" if run.last_error else "❌ **Run failed:** Unknown error"
            await cl.Message(content=error_msg).send()
        else:
            try:
                # Method 1: Try to get response directly from run result if available
                if hasattr(run, 'result') and run.result:
                    print(f"Debug: Found run result directly")
                    await cl.Message(
                        content=str(run.result),
                        author="Azure AI Assistant"
                    ).send()
                    return
                
                # Method 2: Get messages from thread
                print(f"Debug: Getting messages for thread {thread_id}")
                messages_paged = project.agents.messages.list(
                    thread_id=thread_id, 
                    order=ListSortOrder.DESCENDING  # Get newest messages first
                )
                print(f"Debug: Got messages_paged of type {type(messages_paged)}")
                
                # Convert ItemPaged to list
                messages = list(messages_paged)
                print(f"Debug: Converted to list with {len(messages)} messages")
                
                # Find all assistant messages from the most recent response
                assistant_responses = []
                found_user_message = False
                
                for i, msg in enumerate(messages):
                    print(f"Debug: Message {i}: role={msg.role}, created_at={getattr(msg, 'created_at', 'unknown')}")
                    
                    # Stop when we hit a user message (we've collected all assistant responses after the last user message)
                    if msg.role == "user" and found_user_message:
                        break
                    elif msg.role == "user":
                        found_user_message = True
                        continue
                    
                    # Collect assistant messages
                    if msg.role == "assistant":
                        # Try different ways to get the message content
                        message_content = None
                        
                        # Method 1: Check for text_messages attribute
                        if hasattr(msg, 'text_messages') and msg.text_messages:
                            try:
                                message_content = msg.text_messages[-1].text.value
                                print(f"Debug: Got content via text_messages: {len(message_content)} chars")
                            except Exception as e:
                                print(f"Debug: Error getting text_messages content: {e}")
                        
                        # Method 2: Check for content attribute
                        if not message_content and hasattr(msg, 'content') and msg.content:
                            try:
                                if isinstance(msg.content, list) and len(msg.content) > 0:
                                    if hasattr(msg.content[0], 'text'):
                                        message_content = msg.content[0].text.value
                                    else:
                                        message_content = str(msg.content[0])
                                else:
                                    message_content = str(msg.content)
                                print(f"Debug: Got content via content attribute: {len(message_content)} chars")
                            except Exception as e:
                                print(f"Debug: Error getting content attribute: {e}")
                        
                        # Method 3: Try to get any text from the message object
                        if not message_content:
                            try:
                                # Check all attributes that might contain text
                                for attr_name in dir(msg):
                                    if 'text' in attr_name.lower() or 'content' in attr_name.lower():
                                        attr_value = getattr(msg, attr_name)
                                        if attr_value and isinstance(attr_value, str) and len(attr_value) > 10:
                                            message_content = attr_value
                                            print(f"Debug: Got content via {attr_name}: {len(message_content)} chars")
                                            break
                            except Exception as e:
                                print(f"Debug: Error in fallback content extraction: {e}")
                        
                        if message_content:
                            assistant_responses.insert(0, message_content)  # Insert at beginning to maintain order
                            print(f"Debug: Added assistant message {i}, total responses: {len(assistant_responses)}")
                        else:
                            print(f"Debug: Could not extract content from assistant message {i}")
                            # Debug: print available attributes
                            print(f"Debug: Available attributes: {[attr for attr in dir(msg) if not attr.startswith('_')]}")
                
                if assistant_responses:
                    # Combine all assistant responses
                    full_response = ""
                    for i, response in enumerate(assistant_responses):
                        if i > 0:
                            full_response += "\n\n---\n\n"  # Separator between responses
                        full_response += response
                    
                    print(f"Debug: Combined {len(assistant_responses)} assistant responses")
                    print(f"Debug: Total response length: {len(full_response)} characters")
                    print(f"Debug: Response preview: {full_response[:200]}...")
                    
                    # Send the combined response
                    await cl.Message(
                        content=full_response,
                        author="Azure AI Assistant"
                    ).send()
                else:
                    print("Debug: No assistant responses found, trying simple approach")
                    # Method 3: Simple fallback - just get the first few assistant messages
                    simple_responses = []
                    for msg in messages[:10]:  # Check only first 10 messages
                        if msg.role == "assistant":
                            # Try to get any content
                            content = None
                            try:
                                # Try different attributes
                                if hasattr(msg, 'text_messages') and msg.text_messages:
                                    content = str(msg.text_messages[-1].text.value)
                                elif hasattr(msg, 'content'):
                                    content = str(msg.content)
                                elif hasattr(msg, 'text'):
                                    content = str(msg.text)
                                
                                if content and len(content.strip()) > 0:
                                    simple_responses.append(content)
                                    if len(simple_responses) >= 3:  # Limit to 3 responses
                                        break
                            except Exception as e:
                                print(f"Debug: Error in simple approach: {e}")
                                continue
                    
                    if simple_responses:
                        simple_combined = "\n\n---\n\n".join(simple_responses)
                        print(f"Debug: Simple approach found {len(simple_responses)} responses")
                        await cl.Message(
                            content=simple_combined,
                            author="Azure AI Assistant"
                        ).send()
                    else:
                        await cl.Message(content="❌ **Error:** No response received from the assistant.").send()
                    
            except Exception as inner_e:
                print(f"Debug: Inner exception occurred: {type(inner_e).__name__}: {str(inner_e)}")
                import traceback
                print(f"Debug: Full traceback: {traceback.format_exc()}")
                await cl.Message(content=f"❌ **Error in message processing:** {str(inner_e)}").send()
                
    except Exception as e:
        await cl.Message(content=f"❌ **Error:** {str(e)}").send()

@cl.on_stop
async def stop():
    """Handle chat session stop"""
    print("Chat session ended")

if __name__ == "__main__":
    cl.run()
