# llm_config.py - Configure LLM backends for each agent
import os
from crewai import LLM
from dotenv import load_dotenv

load_dotenv()

# Example: set API keys via environment
#os.environ["OPENAI_API_KEY"] = "<YOUR_OPENAI_KEY>"
#os.environ["BEDROCK_API_KEY"] = "<YOUR_AWS_BEDROCK_KEY>"  # pseudo, use actual method for Bedrock auth

# Define an LLM for each agent. Using different providers/models to showcase flexibility.
openai_gpt4 = LLM(model="gpt-4")  # OpenAI GPT-4 for high reasoning tasks
#bedrock_claude = LLM(model="anthropic.claude-2", base_url="<BEDROCK_ENDPOINT_URL>")  
# ^ Assume base_url is set to AWS Bedrock endpoint for Claude 2, with credentials configured

ollama_llama2 = LLM(
    model="ollama/deepseek-r1:8b",
    base_url="http://localhost:11434",
    provider="ollama"
)
# ^ Local Llama-2 13B via Ollama running on localhost

openai_gpt35 = LLM(model="gpt-3.5-turbo", temperature=0.7, max_tokens=512)  


print(f"key id: {os.getenv('AWS_ACCESS_KEY_ID')}")
bedrock_llm = LLM(
    model="bedrock/amazon.nova-lite-v1:0"
)
# ^ Using a cheaper OpenAI model for tasks that don't need GPT-4, with moderate token limit
